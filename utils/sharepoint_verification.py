"""
SharePoint-based resident verification for testing
Used when Entrata test environment is unavailable
"""
import os
import logging
import msal
import requests
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def get_sharepoint_access_token():
    """Get access token for SharePoint/Microsoft Graph API with timing"""
    token_start = time.time()
    
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        logger.error("❌ Azure credentials not configured")
        return None, {}
    
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]
        
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )
        
        result = app.acquire_token_for_client(scopes=scope)
        
        token_elapsed = (time.time() - token_start) * 1000  # Convert to ms
        
        if "access_token" not in result:
            logger.error(f"❌ Token acquisition failed: {result.get('error')}")
            return None, {'token_acquisition_ms': token_elapsed}
        
        logger.info(f"⏱️ SharePoint token acquisition: {token_elapsed:.1f}ms")
        return result["access_token"], {'token_acquisition_ms': token_elapsed}
    
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        token_elapsed = (time.time() - token_start) * 1000
        return None, {'token_acquisition_ms': token_elapsed}


def verify_resident_sharepoint(email, first_name, last_name, date_of_birth):
    """
    Verify a resident exists in SharePoint test list with matching details
    
    Args:
        email: Resident email address
        first_name: Resident first name
        last_name: Resident last name
        date_of_birth: Date of birth (YYYY-MM-DD format or datetime object)
        
    Returns:
        dict with 'verified': bool, 'resident_id': str/None, 'message': str, 'timings': dict
    """
    # Track timing for each stage
    timings = {}
    overall_start = time.time()
    
    # Normalize inputs
    email = email.lower().strip()
    first_name = first_name.strip()
    last_name = last_name.strip()
    
    # Parse DOB if string - support multiple formats
    if isinstance(date_of_birth, str):
        dob = None
        # Try MM-DD-YYYY format (user input from sign-up form)
        try:
            dob = datetime.strptime(date_of_birth, '%m-%d-%Y')
        except ValueError:
            # Try YYYY-MM-DD format (ISO standard)
            try:
                dob = datetime.strptime(date_of_birth, '%Y-%m-%d')
            except ValueError:
                # Try MM/DD/YYYY format (possible SharePoint format)
                try:
                    dob = datetime.strptime(date_of_birth, '%m/%d/%Y')
                except ValueError:
                    logger.error(f"❌ Invalid date format: {date_of_birth}")
                    return {
                        'verified': False,
                        'resident_id': None,
                        'message': 'Invalid date of birth format. Please use MM-DD-YYYY.',
                        'timings': timings
                    }
    else:
        dob = date_of_birth
    
    # Get access token
    access_token, token_timings = get_sharepoint_access_token()
    timings.update(token_timings)
    
    if not access_token:
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.',
            'timings': timings
        }
    
    try:
        # Get SharePoint site for verification list
        site_hostname = os.environ.get('SHAREPOINT_VERIFICATION_SITE_HOSTNAME', 'peakcampus-my.sharepoint.com')
        site_path = os.environ.get('SHAREPOINT_VERIFICATION_SITE_PATH', '/personal/pbatson_peakmade_com')
        
        site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        logger.info(f"🔗 Graph endpoint: {site_url}")
        
        # Resolve site - with timing
        site_start = time.time()
        site_response = requests.get(site_url, headers=headers)
        site_elapsed = (time.time() - site_start) * 1000
        timings['site_resolution_ms'] = site_elapsed
        
        logger.info(f"📊 Graph site resolution: {site_response.status_code} in {site_elapsed:.1f}ms")
        if 'request-id' in site_response.headers:
            logger.info(f"📊 Graph request-id: {site_response.headers['request-id']}")
        if 'client-request-id' in site_response.headers:
            logger.info(f"📊 Graph client-request-id: {site_response.headers['client-request-id']}")
        
        site_response.raise_for_status()
        site_data = site_response.json()
        site_id = site_data["id"]
        
        # Get verification list ID
        list_id = os.environ.get('SHAREPOINT_VERIFICATION_LIST_ID', 'f2ebd72a-6c00-448c-bf07-19f9afbad017')
        
        # Query SharePoint list - with timing
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        logger.info(f"🔗 Graph endpoint: {list_items_url}")
        
        list_start = time.time()
        items_response = requests.get(list_items_url, headers=headers)
        list_elapsed = (time.time() - list_start) * 1000
        timings['list_query_ms'] = list_elapsed
        
        logger.info(f"📊 Graph list query: {items_response.status_code} in {list_elapsed:.1f}ms")
        if 'request-id' in items_response.headers:
            logger.info(f"📊 Graph request-id: {items_response.headers['request-id']}")
        if 'client-request-id' in items_response.headers:
            logger.info(f"📊 Graph client-request-id: {items_response.headers['client-request-id']}")
        
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        logger.info(f"📊 Graph returned {len(items)} records")
        
        # Helper to parse SharePoint dates
        def parse_sp_date(date_val):
            if not date_val:
                return None
            if isinstance(date_val, datetime):
                return date_val.date()
            if isinstance(date_val, str):
                try:
                    parsed = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                    return parsed.date()
                except:
                    try:
                        if 'T' in date_val:
                            return datetime.strptime(date_val.split('T')[0], '%Y-%m-%d').date()
                        return datetime.strptime(date_val, '%Y-%m-%d').date()
                    except:
                        return None
            return None
        
        # Search for matching resident
        for item in items:
            fields = item.get("fields", {})
            
            # Get email (try multiple field names)
            resident_email = (
                fields.get('Email', '') or 
                fields.get('EmailAddress', '') or 
                fields.get('email', '')
            ).lower().strip()
            
            # Skip if email doesn't match
            if resident_email != email:
                continue
            
            # Check name match (case-insensitive)
            resident_first = fields.get('FirstName', '').strip().lower()
            resident_last = fields.get('LastName', '').strip().lower()
            
            if resident_first != first_name.lower() or resident_last != last_name.lower():
                logger.info(f"Email match but name mismatch: {resident_first} {resident_last} vs {first_name} {last_name}")
                continue
            
            # Check DOB match
            resident_dob_raw = fields.get('DateofBirth') or fields.get('DateOfBirth') or fields.get('DOB')
            resident_dob = parse_sp_date(resident_dob_raw)
            
            if resident_dob and resident_dob != dob.date():
                logger.info(f"Email/name match but DOB mismatch: {resident_dob} vs {dob.date()}")
                continue
            
            # Match found!
            resident_id = str(fields.get('ResidentID', '') or fields.get('ID', ''))
            
            overall_elapsed = (time.time() - overall_start) * 1000
            timings['total_verification_ms'] = overall_elapsed
            
            logger.info(f"✅ Resident verified via SharePoint: {email} (ID: {resident_id})")
            logger.info(f"⏱️ Total SharePoint verification: {overall_elapsed:.1f}ms")
            
            return {
                'verified': True,
                'resident_id': resident_id,
                'message': 'Resident verified successfully',
                'timings': timings
            }
        
        # No match found
        overall_elapsed = (time.time() - overall_start) * 1000
        timings['total_verification_ms'] = overall_elapsed
        
        logger.info(f"❌ No matching resident found in SharePoint: {email}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'The data you provided could not be verified.',
            'timings': timings
        }
    
    except requests.exceptions.RequestException as e:
        overall_elapsed = (time.time() - overall_start) * 1000
        timings['total_verification_ms'] = overall_elapsed
        
        logger.error(f"❌ SharePoint API error: {e}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.',
            'timings': timings
        }
    except Exception as e:
        overall_elapsed = (time.time() - overall_start) * 1000
        timings['total_verification_ms'] = overall_elapsed
        
        logger.error(f"❌ Verification error: {e}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.',
            'timings': timings
        }


def check_admin_authorization(email):
    """
    Check if user is authorized as admin via SharePoint admin list
    
    Args:
        email: User email address
        
    Returns:
        bool: True if authorized admin, False otherwise
    """
    email = email.lower().strip()
    
    # Get access token
    access_token = get_sharepoint_access_token()
    if not access_token:
        logger.error("❌ Unable to verify admin authorization - no access token")
        return False
    
    try:
        # Get SharePoint site (main app site for admin list)
        site_url = os.environ.get('SHAREPOINT_SITE_URL', 'https://peakcampus.sharepoint.com/sites/BaseCampApps')
        # Extract hostname and path from full URL
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        site_hostname = parsed.hostname
        site_path = parsed.path
        
        graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        logger.info(f"Resolving SharePoint site for admin list: {site_hostname}{site_path}")
        site_response = requests.get(graph_site_url, headers=headers)
        site_response.raise_for_status()
        site_data = site_response.json()
        site_id = site_data["id"]
        
        # Get admin list ID from environment
        admin_list_id = os.environ.get('SHAREPOINT_ADMIN_LIST_ID', 'c07805eb-b91c-47df-ac6e-b8dc811862c0')
        
        logger.info(f"🔍 Checking admin authorization for {email} in list {admin_list_id}")
        
        # Query SharePoint admin list
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{admin_list_id}/items?expand=fields"
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        logger.info(f"Found {len(items)} admin records in SharePoint list")
        
        # Search for matching admin
        for item in items:
            fields = item.get("fields", {})
            
            # Get email (try multiple field names)
            admin_email = (
                fields.get('Email', '') or 
                fields.get('EmailAddress', '') or 
                fields.get('email', '')
            ).lower().strip()
            
            if not admin_email:
                continue
            
            # Check if email matches
            if admin_email == email:
                # Check if active (try multiple field names and values)
                active = fields.get('Active', fields.get('IsActive', ''))
                
                # Handle different active value formats
                is_active = False
                if isinstance(active, bool):
                    is_active = active
                elif isinstance(active, str):
                    is_active = active.lower() in ['yes', 'true', '1', 'active']
                elif active == 1:
                    is_active = True
                
                if is_active:
                    logger.info(f"✅ Admin authorized: {email}")
                    return True
                else:
                    logger.info(f"❌ Admin found but not active: {email}")
                    return False
        
        # No match found
        logger.info(f"❌ Email not found in admin list: {email}")
        return False
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ SharePoint API error checking admin: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Admin authorization check error: {e}")
        return False
