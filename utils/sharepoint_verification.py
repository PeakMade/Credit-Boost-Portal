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
from threading import Lock

logger = logging.getLogger(__name__)

# ============================================================================
# GRAPH TOKEN CACHING FOR PERFORMANCE
# ============================================================================
# Cache Microsoft Graph access tokens to avoid repeated MSAL token acquisitions
# Tokens are valid for 60+ minutes, cache with safety margin
# ============================================================================

_graph_token_cache = {
    'token': None,
    'expires_at': None,
    'cached_at': None,
    'source': None,  # 'startup_warmup' or 'request_path'
    'lock': Lock()
}

# ============================================================================
# SHAREPOINT SITE ID CACHING FOR PERFORMANCE
# ============================================================================
# Cache resolved SharePoint site IDs to avoid repeated Graph API lookups
# Site IDs are stable and don't change frequently
# ============================================================================

_sharepoint_site_cache = {
    'site_id': None,
    'site_key': None,  # Cache key: hostname:path
    'cached_at': None,
    'source': None,  # 'startup_warmup' or 'request_path'
    'lock': Lock()
}


def get_graph_token_cache_state():
    """
    Get current Graph token cache state for diagnostics
    Call at request start to see if warm-up populated cache
    
    Returns:
        dict with cache state information
    """
    with _graph_token_cache['lock']:
        now = time.time()
        
        if _graph_token_cache['token'] is None:
            return {
                'present': False,
                'source': None,
                'age_s': 0,
                'ttl_remaining_s': 0,
                'expired': False
            }
        
        cached_at = _graph_token_cache.get('cached_at', 0)
        expires_at = _graph_token_cache.get('expires_at', 0)
        
        return {
            'present': True,
            'source': _graph_token_cache.get('source', 'unknown'),
            'age_s': now - cached_at if cached_at else 0,
            'ttl_remaining_s': max(0, expires_at - now) if expires_at else 0,
            'expired': now >= expires_at if expires_at else True
        }


def get_site_id_cache_state():
    """
    Get current Site ID cache state for diagnostics
    Call at request start to see if warm-up populated cache
    
    Returns:
        dict with cache state information
    """
    with _sharepoint_site_cache['lock']:
        now = time.time()
        
        if _sharepoint_site_cache['site_id'] is None:
            return {
                'present': False,
                'source': None,
                'site_key': None,
                'age_s': 0
            }
        
        cached_at = _sharepoint_site_cache.get('cached_at', 0)
        
        return {
            'present': True,
            'source': _sharepoint_site_cache.get('source', 'unknown'),
            'site_key': _sharepoint_site_cache.get('site_key'),
            'age_s': now - cached_at if cached_at else 0
        }


def warmup_graph_token():
    """
    Warm up Graph access token cache on application startup
    Pre-acquires and caches token to eliminate cold-start latency
    
    Returns:
        dict with warmup results: success (bool), duration_ms (float), ttl_s (float), error (str or None)
    """
    logger.info("🔥 graph_token_warmup_started")
    warmup_start = time.time()
    
    try:
        token, metrics = get_sharepoint_access_token(source='startup_warmup')
        
        duration_ms = (time.time() - warmup_start) * 1000
        
        if token:
            logger.info(f"✅ graph_token_warmup_succeeded: duration={duration_ms:.1f}ms, ttl={metrics['token_ttl_remaining_s']:.0f}s")
            return {
                'success': True,
                'duration_ms': duration_ms,
                'ttl_s': metrics['token_ttl_remaining_s'],
                'error': None
            }
        else:
            logger.warning(f"⚠️ graph_token_warmup_failed: token acquisition returned None, duration={duration_ms:.1f}ms")
            return {
                'success': False,
                'duration_ms': duration_ms,
                'ttl_s': 0,
                'error': 'Token acquisition returned None'
            }
    
    except Exception as e:
        duration_ms = (time.time() - warmup_start) * 1000
        error_msg = str(e)
        logger.warning(f"⚠️ graph_token_warmup_failed: {error_msg}, duration={duration_ms:.1f}ms")
        return {
            'success': False,
            'duration_ms': duration_ms,
            'ttl_s': 0,
            'error': error_msg
        }


def get_verification_site_config():
    """
    Get SharePoint site configuration for resident verification
    Shared by both startup warm-up and runtime verification
    Ensures consistency between warm-up target and actual verification site
    
    Returns:
        dict with hostname, path, and formatted URL
    """
    site_hostname = os.environ.get('SHAREPOINT_VERIFICATION_SITE_HOSTNAME', 'peakcampus-my.sharepoint.com')
    site_path = os.environ.get('SHAREPOINT_VERIFICATION_SITE_PATH', '/personal/pbatson_peakmade_com')
    
    return {
        'hostname': site_hostname,
        'path': site_path,
        'url': f"https://{site_hostname}{site_path}",
        'cache_key': f"{site_hostname}:{site_path}"
    }


def warmup_site_id():
    """
    Warm up SharePoint site ID cache on application startup
    Pre-resolves and caches site ID to eliminate cold-start latency
    
    Returns:
        dict with warmup results: success (bool), duration_ms (float), site_id (str or None), error (str or None)
    """
    logger.info("🔥 site_id_warmup_started")
    warmup_start = time.time()
    
    try:
        # Get Graph token first
        token, token_metrics = get_sharepoint_access_token(source='startup_warmup')
        
        if not token:
            error_msg = "Failed to acquire Graph token"
            logger.warning(f"⚠️ site_id_warmup_failed: {error_msg}")
            return {
                'success': False,
                'duration_ms': 0,
                'site_id': None,
                'error': error_msg
            }
        
        # Get verification site config (shared with runtime)
        site_config = get_verification_site_config()
        site_hostname = site_config['hostname']
        site_path = site_config['path']
        
        logger.info(f"🎯 Warming verification site: {site_config['url']}")
        logger.info(f"   Site hostname: {site_hostname}")
        logger.info(f"   Site path: {site_path}")
        logger.info(f"   Cache key: {site_config['cache_key']}")
        
        # Resolve and cache site ID
        site_id, cache_hit, resolution_ms, cache_age = get_cached_site_id(site_hostname, site_path, token, source='startup_warmup')
        
        duration_ms = (time.time() - warmup_start) * 1000
        
        if site_id:
            logger.info(f"✅ site_id_warmup_succeeded: duration={duration_ms:.1f}ms, site_id={site_id[:40]}...")
            return {
                'success': True,
                'duration_ms': duration_ms,
                'site_id': site_id,
                'error': None
            }
        else:
            logger.warning(f"⚠️ site_id_warmup_failed: site resolution returned None, duration={duration_ms:.1f}ms")
            return {
                'success': False,
                'duration_ms': duration_ms,
                'site_id': None,
                'error': 'Site resolution returned None'
            }
    
    except Exception as e:
        duration_ms = (time.time() - warmup_start) * 1000
        error_msg = str(e)
        logger.warning(f"⚠️ site_id_warmup_failed: {error_msg}, duration={duration_ms:.1f}ms")
        return {
            'success': False,
            'duration_ms': duration_ms,
            'site_id': None,
            'error': error_msg
        }


def get_sharepoint_access_token(source='request_path'):
    """
    Get access token for SharePoint/Microsoft Graph API with caching
    
    Args:
        source: 'startup_warmup' or 'request_path' - tracks where cache was populated
    
    Returns:
        tuple: (access_token: str or None, metrics: dict)
    """
    metrics = {
        'graph_token_cache_hit': False,
        'token_acquisition_ms': 0.0,
        'token_cache_age_s': 0.0,
        'token_ttl_remaining_s': 0.0,
        'token_cache_source': None
    }
    
    with _graph_token_cache['lock']:
        now = time.time()
        
        # Check cache validity (with 5-minute safety margin)
        if _graph_token_cache['token'] is not None and _graph_token_cache['expires_at'] is not None:
            if now < (_graph_token_cache['expires_at'] - 300):  # Refresh 5 min before expiry
                cached_at = _graph_token_cache.get('cached_at', now)
                cache_age = now - cached_at
                ttl_remaining = _graph_token_cache['expires_at'] - now
                cache_source = _graph_token_cache.get('source', 'unknown')
                logger.info(f"✅ Graph token cache HIT (source={cache_source}, age={cache_age:.0f}s, ttl_remaining={ttl_remaining:.0f}s)")
                metrics['graph_token_cache_hit'] = True
                metrics['token_cache_age_s'] = cache_age
                metrics['token_ttl_remaining_s'] = ttl_remaining
                metrics['token_cache_source'] = cache_source
                return _graph_token_cache['token'], metrics
        
        # Cache miss - acquire new token
        logger.info(f"⚠️ Graph token cache MISS - acquiring new token")
        token_start = time.time()
        
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        tenant_id = os.environ.get('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            logger.error("❌ Azure credentials not configured")
            metrics['token_acquisition_ms'] = (time.time() - token_start) * 1000
            return None, metrics
        
        try:
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            scope = ["https://graph.microsoft.com/.default"]
            
            app = msal.ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret
            )
            
            result = app.acquire_token_for_client(scopes=scope)
            
            metrics['token_acquisition_ms'] = (time.time() - token_start) * 1000
            
            if "access_token" not in result:
                logger.error(f"❌ Token acquisition failed: {result.get('error')}")
                return None, metrics
            
            # Update cache
            access_token = result["access_token"]
            expires_in = result.get("expires_in", 3600)  # Default 1 hour
            _graph_token_cache['token'] = access_token
            _graph_token_cache['expires_at'] = now + expires_in
            _graph_token_cache['cached_at'] = now
            _graph_token_cache['lifetime'] = expires_in
            _graph_token_cache['source'] = source
            
            logger.info(f"✅ Graph token acquired: {metrics['token_acquisition_ms']:.1f}ms, TTL={expires_in}s, source={source}")
            
            metrics['token_ttl_remaining_s'] = expires_in
            metrics['token_cache_source'] = source
            
            return access_token, metrics
        
        except Exception as e:
            metrics['token_acquisition_ms'] = (time.time() - token_start) * 1000
            logger.error(f"❌ Authentication error: {e}")
            return None, metrics


def get_user_email_from_graph(object_id):
    """
    Get user's email from Microsoft Graph API using object identifier
    Used for External ID local accounts where email is stored as an identity
    
    Args:
        object_id: User's object identifier from token claims
    
    Returns:
        str: User's email address or None if not found
    """
    try:
        # CRITICAL: For External ID users, we need to query the CIAM tenant
        # The user is in the External ID tenant, not the organization tenant
        external_id_tenant = os.environ.get('AUTH_EXTENSION_TENANT_ID')
        
        if not external_id_tenant:
            logger.warning("⚠️ AUTH_EXTENSION_TENANT_ID not set, cannot query External ID users")
            return None
        
        # Acquire token for External ID tenant (not the org tenant)
        # We need client credentials for an app in the External ID tenant with User.Read.All
        # For now, try using the org tenant token - it may work if there's a trust relationship
        token, _ = get_sharepoint_access_token(source='request_path')
        if not token:
            logger.error("❌ Failed to acquire Graph token for user lookup")
            return None
        
        # Query using the object ID directly (tenant-independent endpoint)
        graph_url = f"https://graph.microsoft.com/v1.0/users/{object_id}?$select=identities,mail,userPrincipalName"
        logger.info(f"🔍 Querying Graph API for user: {object_id[:8]}...")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(graph_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Try mail attribute first
            if user_data.get('mail'):
                logger.info(f"✅ Found email in 'mail' attribute: {user_data['mail']}")
                return user_data['mail']
            
            # Check identities for local account email (External ID local accounts)
            identities = user_data.get('identities', [])
            for identity in identities:
                if identity.get('signInType') == 'emailAddress':
                    email = identity.get('issuerAssignedId')
                    if email:
                        logger.info(f"✅ Found email in identities (emailAddress): {email}")
                        return email
            
            # Fallback to UPN if it looks like an email
            upn = user_data.get('userPrincipalName', '')
            if '@' in upn and not upn.endswith('.onmicrosoft.com'):
                logger.info(f"✅ Using UPN as email: {upn}")
                return upn
            
            logger.warning(f"⚠️ User {object_id[:8]}... has no email in mail, identities, or UPN")
            return None
        elif response.status_code == 404:
            logger.warning(f"⚠️ User {object_id[:8]}... not found in this tenant (may be in different tenant)")
            return None
        else:
            logger.error(f"❌ Graph API error getting user: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error querying Graph API for user email: {e}")
        return None


def get_cached_site_id(site_hostname, site_path, access_token, source='request_path'):
    """
    Get SharePoint site ID with caching
    
    Args:
        site_hostname: SharePoint site hostname
        site_path: SharePoint site path
        access_token: Graph API access token
        source: 'startup_warmup' or 'request_path' - tracks where cache was populated
    
    Returns:
        tuple: (site_id: str or None, cache_hit: bool, resolution_ms: float, cache_age_s: float)
    """
    cache_key = f"{site_hostname}:{site_path}"
    
    with _sharepoint_site_cache['lock']:
        # Check cache
        if _sharepoint_site_cache['site_id'] is not None and _sharepoint_site_cache['site_key'] == cache_key:
            cache_age = time.time() - _sharepoint_site_cache.get('cached_at', time.time())
            cache_source = _sharepoint_site_cache.get('source', 'unknown')
            logger.info(f"✅ Site ID cache HIT for {cache_key} (source={cache_source}, age={cache_age:.0f}s)")
            return _sharepoint_site_cache['site_id'], True, 0.0, cache_age
        
        # Cache miss - resolve site
        logger.info(f"⚠️ Site ID cache MISS - resolving {cache_key}")
        site_start = time.time()
        
        try:
            site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            logger.info(f"🔗 Graph endpoint: {site_url}")
            
            site_response = requests.get(site_url, headers=headers, timeout=10)
            resolution_ms = (time.time() - site_start) * 1000
            
            logger.info(f"📊 Graph site resolution: {site_response.status_code} in {resolution_ms:.1f}ms")
            if 'request-id' in site_response.headers:
                logger.info(f"📊 Graph request-id: {site_response.headers['request-id']}")
            
            site_response.raise_for_status()
            site_data = site_response.json()
            site_id = site_data["id"]
            
            # Update cache
            _sharepoint_site_cache['site_id'] = site_id
            _sharepoint_site_cache['site_key'] = cache_key
            _sharepoint_site_cache['cached_at'] = time.time()
            _sharepoint_site_cache['source'] = source
            
            logger.info(f"✅ Site ID cached: {site_id}, source={source}")
            
            return site_id, False, resolution_ms, 0.0
        
        except Exception as e:
            resolution_ms = (time.time() - site_start) * 1000
            logger.error(f"❌ Site resolution error: {e}")
            return None, False, resolution_ms, 0.0


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
        dob_input = date_of_birth.strip()
        
        # Try MM-DD-YYYY format (user input from sign-up form)
        try:
            dob = datetime.strptime(dob_input, '%m-%d-%Y')
        except ValueError:
            # Try YYYY-MM-DD format (ISO standard)
            try:
                dob = datetime.strptime(dob_input, '%Y-%m-%d')
            except ValueError:
                # Try MM/DD/YYYY format (possible SharePoint format)
                try:
                    dob = datetime.strptime(dob_input, '%m/%d/%Y')
                except ValueError:
                    # Try MMDDYYYY format (no separators - 8 digits)
                    try:
                        if len(dob_input) == 8 and dob_input.isdigit():
                            dob = datetime.strptime(dob_input, '%m%d%Y')
                        else:
                            raise ValueError("Not 8-digit format")
                    except ValueError:
                        logger.error(f"❌ Invalid date format: {date_of_birth}")
                        return {
                            'verified': False,
                            'resident_id': None,
                            'message': 'Invalid date of birth format. Please use MM-DD-YYYY or MMDDYYYY.',
                            'timings': timings
                        }
    else:
        dob = date_of_birth
    
    # Get access token with caching
    access_token, token_metrics = get_sharepoint_access_token()
    timings.update(token_metrics)
    
    if not access_token:
        return {
            'verified': False,
            'resident_id': None,
            'message': 'Unable to verify at this time. Please try again later.',
            'timings': timings
        }
    
    try:
        # Get SharePoint site for verification list
        # Use shared config to ensure consistency with startup warm-up
        site_config = get_verification_site_config()
        site_hostname = site_config['hostname']
        site_path = site_config['path']
        
        logger.info(f"🎯 Verification target site: {site_config['url']}")
        logger.info(f"   Site hostname: {site_hostname}")
        logger.info(f"   Site path: {site_path}")
        logger.info(f"   Cache key: {site_config['cache_key']}")
        
        # Get site ID with caching
        site_id, site_cache_hit, site_resolution_ms, site_cache_age = get_cached_site_id(site_hostname, site_path, access_token)
        timings['site_id_cache_hit'] = site_cache_hit
        timings['site_resolution_ms'] = site_resolution_ms
        timings['site_cache_age_s'] = site_cache_age
        
        if not site_id:
            overall_elapsed = (time.time() - overall_start) * 1000
            timings['total_verification_ms'] = overall_elapsed
            return {
                'verified': False,
                'resident_id': None,
                'message': 'Unable to verify at this time. Please try again later.',
                'timings': timings
            }
        
        # Get verification list ID
        list_id = os.environ.get('SHAREPOINT_VERIFICATION_LIST_ID', 'f2ebd72a-6c00-448c-bf07-19f9afbad017')
        
        # Query SharePoint list - with timing
        # NOTE: Graph API filtering on custom lists is unreliable, so we fetch all items and filter in memory
        # This is acceptable for small verification lists (<100 residents)
        # For larger lists, consider: $filter=fields/Email eq '{email}' if supported
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields&$top=100"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        logger.info(f"🔗 Graph endpoint: {list_items_url}")
        
        list_start = time.time()
        items_response = requests.get(list_items_url, headers=headers, timeout=10)
        list_elapsed = (time.time() - list_start) * 1000
        timings['list_query_ms'] = list_elapsed
        
        logger.info(f"📊 Graph list query: {items_response.status_code} in {list_elapsed:.1f}ms")
        if 'request-id' in items_response.headers:
            logger.info(f"📊 Graph request-id: {items_response.headers['request-id']}")
        
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
