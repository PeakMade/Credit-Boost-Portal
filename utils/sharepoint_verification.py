"""
SharePoint-based resident verification for testing
Used when Entrata test environment is unavailable
"""
import os
import logging
import msal
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


def get_sharepoint_access_token():
    """Get access token for SharePoint/Microsoft Graph API"""
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        logger.error("❌ Azure credentials not configured")
        return None
    
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]
        
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )
        
        result = app.acquire_token_for_client(scopes=scope)
        
        if "access_token" not in result:
            logger.error(f"❌ Token acquisition failed: {result.get('error')}")
            return None
        
        return result["access_token"]
    
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        return None


def verify_resident_sharepoint(email, first_name, last_name, date_of_birth):
    """
    Verify a resident exists in SharePoint test list with matching details
    
    Args:
        email: Resident email address
        first_name: Resident first name
        last_name: Resident last name
        date_of_birth: Date of birth (YYYY-MM-DD format or datetime object)
        
    Returns:
        dict with 'verified': bool, 'resident_id': str/None, 'message': str
    """
    # Normalize inputs
    email = email.lower().strip()
    first_name = first_name.strip()
    last_name = last_name.strip()
    
    # Parse DOB if string
    if isinstance(date_of_birth, str):
        try:
            dob = datetime.strptime(date_of_birth, '%Y-%m-%d')
        except ValueError:
            logger.error(f"❌ Invalid date format: {date_of_birth}")
            return {
                'verified': False,
                'resident_id': None,
                'message': 'Invalid date of birth format'
            }
    else:
        dob = date_of_birth
    
    # Get access token
    access_token = get_sharepoint_access_token()
    if not access_token:
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.'
        }
    
    try:
        # Get SharePoint site
        site_hostname = "peakcampus.sharepoint.com"
        site_path = "/sites/BaseCampApps"
        site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        site_response = requests.get(site_url, headers=headers)
        site_response.raise_for_status()
        site_data = site_response.json()
        site_id = site_data["id"]
        
        # Get verification test list
        # Try custom test list first, fall back to tenants list
        test_list_id = os.environ.get('SHAREPOINT_VERIFICATION_LIST_ID')
        list_id = test_list_id if test_list_id else '7569dfb7-5d2f-452d-a384-0af63b38b559'  # Tenants list
        
        logger.info(f"🔍 Querying SharePoint list {list_id} for verification")
        
        # Query SharePoint list
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        logger.info(f"Found {len(items)} records in SharePoint list")
        
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
            logger.info(f"✅ Resident verified via SharePoint: {email} (ID: {resident_id})")
            return {
                'verified': True,
                'resident_id': resident_id,
                'message': 'Resident verified successfully'
            }
        
        # No match found
        logger.info(f"❌ No matching resident found in SharePoint: {email}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'The data you provided could not be verified.'
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ SharePoint API error: {e}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.'
        }
    except Exception as e:
        logger.error(f"❌ Verification error: {e}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.'
        }
