"""
SharePoint-based resident verification for testing
Used when Entrata test environment is unavailable
"""
import os
import logging
import msal
import requests
import time
import base64
import json
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

# Separate token cache for External ID tenant Graph API calls
_external_id_graph_token_cache = {
    'token': None,
    'expires_at': None,
    'cached_at': None,
    'lifetime': None,
    'source': None,
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


def get_external_id_graph_token(source='request_path'):
    """
    Acquire Microsoft Graph token for External ID tenant user lookups.
    This is separate from the workforce tenant Graph token.
    
    Returns:
        tuple: (access_token, metrics_dict)
    """
    metrics = {
        'cache_hit': False,
        'acquisition_ms': 0.0,
        'cache_age_s': 0.0,
        'ttl_remaining_s': 0.0
    }
    
    with _external_id_graph_token_cache['lock']:
        now = time.time()
        
        # Check cache
        if _external_id_graph_token_cache['token'] and _external_id_graph_token_cache['expires_at']:
            if now < (_external_id_graph_token_cache['expires_at'] - 300):
                cached_at = _external_id_graph_token_cache.get('cached_at', now)
                cache_age = now - cached_at
                ttl_remaining = _external_id_graph_token_cache['expires_at'] - now
                logger.info(f"✅ External ID Graph token cache HIT (age={cache_age:.0f}s, ttl={ttl_remaining:.0f}s)")
                metrics['cache_hit'] = True
                metrics['cache_age_s'] = cache_age
                metrics['ttl_remaining_s'] = ttl_remaining
                return _external_id_graph_token_cache['token'], metrics
        
        # Cache miss - acquire new token
        logger.info(f"⚠️ External ID Graph token cache MISS - acquiring new token")
        token_start = time.time()
        
        # Check for External ID Graph app registration credentials
        # Priority 1: Dedicated Graph app in External ID tenant
        client_id = os.environ.get('EXTERNAL_ID_GRAPH_CLIENT_ID') or os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('EXTERNAL_ID_GRAPH_CLIENT_SECRET') or os.environ.get('AZURE_CLIENT_SECRET')
        tenant_id = os.environ.get('AUTH_EXTENSION_TENANT_ID')
        
        logger.info(f"🔍 GRAPH TOKEN ACQUISITION CONTEXT:")
        logger.info(f"   Tenant ID: {tenant_id[:16] if tenant_id else 'NOT SET'}...")
        logger.info(f"   Client ID: {client_id[:16] if client_id else 'NOT SET'}...")
        logger.info(f"   Client Secret: {'SET' if client_secret else 'NOT SET'}")
        logger.info(f"   Tenant Type: External ID (CIAM)")
        logger.info(f"   Target API: Microsoft Graph (https://graph.microsoft.com)")
        
        if not all([client_id, client_secret, tenant_id]):
            logger.error("❌ External ID Graph credentials not configured")
            logger.error("   Required: EXTERNAL_ID_GRAPH_CLIENT_ID + EXTERNAL_ID_GRAPH_CLIENT_SECRET")
            logger.error("   Or fallback: AZURE_CLIENT_ID + AZURE_CLIENT_SECRET")
            logger.error("   Plus: AUTH_EXTENSION_TENANT_ID")
            metrics['acquisition_ms'] = (time.time() - token_start) * 1000
            return None, metrics
        
        try:
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            scope = ["https://graph.microsoft.com/.default"]
            
            logger.info(f"   Authority URL: {authority}")
            logger.info(f"   Scopes: {scope}")
            logger.info(f"   Flow: Client Credentials (application permissions)")
            
            app = msal.ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret
            )
            
            result = app.acquire_token_for_client(scopes=scope)
            
            metrics['acquisition_ms'] = (time.time() - token_start) * 1000
            
            if "access_token" not in result:
                logger.error(f"❌ Token acquisition failed: {result.get('error')} - {result.get('error_description', '')}")
                return None, metrics
            
            access_token = result["access_token"]
            expires_in = result.get("expires_in", 3600)
            
            # Decode token for diagnostics (without verification)
            try:
                # Split token (header.payload.signature)
                parts = access_token.split('.')
                if len(parts) == 3:
                    # Decode payload (add padding if needed)
                    payload_base64 = parts[1]
                    padding = len(payload_base64) % 4
                    if padding:
                        payload_base64 += '=' * (4 - padding)
                    payload = json.loads(base64.urlsafe_b64decode(payload_base64))
                    
                    logger.info(f"🔍 TOKEN DIAGNOSTICS (decoded payload):")
                    logger.info(f"   tid (tenant): {payload.get('tid', 'N/A')[:16]}...")
                    logger.info(f"   aud (audience): {payload.get('aud', 'N/A')}")
                    logger.info(f"   appid: {payload.get('appid', 'N/A')[:16]}...")
                    logger.info(f"   iss (issuer): {payload.get('iss', 'N/A')}")
                    logger.info(f"   roles: {payload.get('roles', [])}")
                    logger.info(f"   scp (scopes): {payload.get('scp', 'N/A')}")
                    
                    # Check for User.Read.All permission
                    roles = payload.get('roles', [])
                    if 'User.Read.All' in roles:
                        logger.info(f"   ✅ User.Read.All permission PRESENT")
                    else:
                        logger.warning(f"   ⚠️ User.Read.All permission NOT FOUND in roles")
                        logger.warning(f"   Available roles: {roles}")
            except Exception as decode_error:
                logger.warning(f"⚠️ Could not decode token for diagnostics: {decode_error}")
            
            # Cache the token
            _external_id_graph_token_cache['token'] = access_token
            _external_id_graph_token_cache['expires_at'] = now + expires_in
            _external_id_graph_token_cache['cached_at'] = now
            _external_id_graph_token_cache['lifetime'] = expires_in
            _external_id_graph_token_cache['source'] = source
            
            logger.info(f"✅ External ID Graph token acquired: {metrics['acquisition_ms']:.1f}ms, TTL={expires_in}s")
            
            metrics['ttl_remaining_s'] = expires_in
            
            return access_token, metrics
            
        except Exception as e:
            metrics['acquisition_ms'] = (time.time() - token_start) * 1000
            logger.error(f"❌ External ID Graph token acquisition error: {e}")
            return None, metrics


def get_user_email_from_graph(object_id):
    """
    Get user's email from Microsoft Graph API using object identifier.
    Queries the External ID (CIAM) tenant to retrieve email from user identities.
    
    Args:
        object_id: User's object identifier from Easy Auth token claims
    
    Returns:
        str: User's email address or None if not found
    """
    try:
        # Validate input
        if not object_id or object_id == 'unknown':
            logger.warning("⚠️ Invalid object_id for Graph lookup")
            return None
        
        logger.info(f"🔍 GRAPH EMAIL LOOKUP: Starting for OID {object_id[:8]}...")
        
        # Get External ID tenant
        external_id_tenant = os.environ.get('AUTH_EXTENSION_TENANT_ID')
        if not external_id_tenant:
            logger.error("❌ AUTH_EXTENSION_TENANT_ID not set - cannot query External ID users")
            return None
        
        logger.info(f"   Target tenant: {external_id_tenant[:16]}... (External ID/CIAM)")
        
        # Acquire Graph token for External ID tenant
        token, metrics = get_external_id_graph_token(source='email_lookup')
        if not token:
            logger.error("❌ Failed to acquire External ID Graph token")
            return None
        
        # Build Graph API request
        # Request specific fields to optimize response
        select_fields = "id,mail,userPrincipalName,otherMails,identities"
        graph_url = f"https://graph.microsoft.com/v1.0/users/{object_id}?$select={select_fields}"
        
        logger.info(f"🌐 GRAPH API REQUEST:")
        logger.info(f"   Method: GET")
        logger.info(f"   URL: {graph_url}")
        logger.info(f"   Headers: Authorization: Bearer [token], Content-Type: application/json")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(graph_url, headers=headers, timeout=10)
        
        logger.info(f"📥 GRAPH API RESPONSE: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"   Response body keys: {list(user_data.keys())}")
            
            # Priority 1: mail attribute
            email = user_data.get('mail')
            if email and email != 'unknown' and '@' in email:
                logger.info(f"✅ Found email in 'mail': {email}")
                return email
            
            # Priority 2: Check identities for emailAddress (External ID local accounts)
            identities = user_data.get('identities', [])
            logger.info(f"   Identities count: {len(identities)}")
            for identity in identities:
                sign_in_type = identity.get('signInType')
                issuer_assigned_id = identity.get('issuerAssignedId')
                logger.info(f"   Identity: signInType={sign_in_type}, issuer={issuer_assigned_id}")
                
                if sign_in_type == 'emailAddress' and issuer_assigned_id:
                    if issuer_assigned_id != 'unknown' and '@' in issuer_assigned_id:
                        logger.info(f"✅ Found email in identities (emailAddress): {issuer_assigned_id}")
                        return issuer_assigned_id
            
            # Priority 3: otherMails
            other_mails = user_data.get('otherMails', [])
            if other_mails and len(other_mails) > 0:
                email = other_mails[0]
                if email and email != 'unknown' and '@' in email:
                    logger.info(f"✅ Found email in otherMails: {email}")
                    return email
            
            # Priority 4: userPrincipalName (if it looks like an email)
            upn = user_data.get('userPrincipalName', '')
            logger.info(f"   UPN: {upn}")
            # Reject synthetic UPNs like xxx@tenant.onmicrosoft.com
            if upn and upn != 'unknown' and '@' in upn:
                if not upn.endswith('.onmicrosoft.com'):
                    logger.info(f"✅ Using UPN as email: {upn}")
                    return upn
                else:
                    logger.info(f"   ℹ️ Skipping synthetic UPN: {upn}")
            
            logger.warning(f"⚠️ No valid email found for user {object_id[:8]}... in any field")
            logger.warning(f"   Checked: mail, identities, otherMails, userPrincipalName")
            return None
            
        elif response.status_code == 404:
            logger.warning(f"⚠️ User {object_id[:8]}... not found in External ID tenant")
            return None
        elif response.status_code == 403:
            logger.error(f"❌ Graph API authorization error (403)")
            logger.error(f"   Error: {response.text[:300]}")
            logger.error(f"   Likely cause: App registration lacks User.Read.All permission")
            logger.error(f"   Check: External ID tenant app permissions")
            return None
        else:
            logger.error(f"❌ Graph API error: {response.status_code}")
            logger.error(f"   Response: {response.text[:300]}")
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
    
    # Hardcoded admin fallback for known admins when SharePoint is unreachable
    # This ensures admins can always access the system even if SharePoint auth fails
    HARDCODED_ADMINS = ['pbatson@peakmade.com', 'admin@creditboost.com']
    if email in HARDCODED_ADMINS:
        logger.info(f"✅ Admin authorized via hardcoded list: {email}")
        return True
    
    # Get access token
    access_token, _ = get_sharepoint_access_token()
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
        site_response = requests.get(graph_site_url, headers=headers, timeout=10)
        
        if site_response.status_code == 401:
            logger.error(f"❌ 401 Unauthorized accessing SharePoint site - token may lack permissions")
            logger.error(f"   Required permission: Sites.Read.All or Sites.FullControl.All")
            logger.error(f"   Check app registration in Azure AD for SharePoint tenant")
            return False
        
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
