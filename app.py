from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import HTTPException
from datetime import datetime
from functools import wraps
import json
import base64
import os
import logging
import sys
import time
import hashlib
from dotenv import load_dotenv
from utils.data_loader import load_residents_from_excel
from utils.sharepoint_data_loader import load_residents_from_sharepoint_list, load_residents_from_credhub_lists
from utils.excel_export import (create_resident_list_export, create_reporting_runs_export,
                                create_disputes_export, create_audit_logs_export)
from utils.entrata_api import get_entrata_client
from utils.sharepoint_verification import verify_resident_sharepoint, warmup_graph_token, warmup_site_id, get_graph_token_cache_state, get_site_id_cache_state, get_verification_site_config, get_user_email_from_graph
from utils.entra_token_validation import require_bearer_token, warmup_jwks_cache, log_auth_config_diagnostics, get_jwks_cache_state
from utils.custom_extension_responses import (
    build_continue_response,
    build_validation_error_response,
    build_block_page_response,
    parse_custom_extension_request,
    get_canonical_success_response,
    CANONICAL_SUCCESS_RESPONSE,
    validate_response_schema
)

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'demo-secret-key-change-in-production')

# Configure session for production stability
app.config['SESSION_COOKIE_SECURE'] = not app.debug  # Use secure cookies in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['SESSION_COOKIE_NAME'] = 'credit_boost_session'

# Configure logging for Azure
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================================================
# SAFE DIAGNOSTIC LOGGING HELPERS
# ============================================================================
# Diagnostics must never break the verification flow
# These helpers ensure logging failures don't alter endpoint results
# ============================================================================

def safe_log_timing_value(key, value):
    """
    Safely log a timing value - handles numeric and non-numeric values
    Never raises exceptions that could break verification flow
    
    Args:
        key: timing key name
        value: timing value (could be numeric, boolean, string, etc.)
    
    Returns:
        formatted string for logging
    """
    try:
        if isinstance(value, (int, float)):
            return f"{key}: {value:.1f}ms"
        elif isinstance(value, bool):
            return f"{key}: {value}"
        elif value is None:
            return f"{key}: None"
        else:
            return f"{key}: {value}"
    except Exception as e:
        # Fallback: just convert to string
        return f"{key}: {str(value)}"


def safe_log_timings_dict(timings_dict, prefix=""):
    """
    Safely log all entries in a timings dictionary
    Never raises exceptions that could break verification flow
    
    Args:
        timings_dict: dictionary with timing/metrics data
        prefix: optional prefix for log lines
    """
    try:
        for key, value in timings_dict.items():
            try:
                log_line = safe_log_timing_value(key, value)
                logger.info(f"{prefix}{log_line}")
            except Exception as inner_e:
                # Even the safe logger failed - just log key
                logger.warning(f"{prefix}{key}: <logging error: {inner_e}>")
    except Exception as e:
        logger.warning(f"⚠️ Diagnostics: Failed to log timings dict: {e}")


# ============================================================================
# FIRST-REQUEST TRACKING FOR DIAGNOSTICS
# ============================================================================
# Track whether this is the first API request after app startup
# Helps identify cold-start latency issues
# ============================================================================
_first_request_after_start = True
_first_request_lock = __import__('threading').Lock()

# ============================================================================
# STARTUP WARM-UP FOR PERFORMANCE
# ============================================================================
# Pre-fetch expensive dependencies on app startup to eliminate cold-start latency
# This ensures the first custom authentication extension request is fast
# ============================================================================

def warmup_caches():
    """
    Warm up all caches on application startup
    Pre-fetches JWKS keys, Graph tokens, and SharePoint site IDs
    Logs results but does not fail app startup on errors
    """
    import socket
    
    # Log worker/process identity
    worker_pid = os.getpid()
    hostname = socket.gethostname()
    startup_timestamp = datetime.now().isoformat()
    
    logger.info("="*80)
    logger.info("🔥 STARTUP WARM-UP: Beginning cache pre-population")
    logger.info(f"   Worker PID: {worker_pid}")
    logger.info(f"   Hostname: {hostname}")
    logger.info(f"   Startup time: {startup_timestamp}")
    logger.info("="*80)
    
    # Log auth config diagnostics
    log_auth_config_diagnostics()
    
    warmup_start = time.time()
    
    # 1. Warm up JWKS cache
    jwks_result = warmup_jwks_cache()
    if jwks_result['success']:
        logger.info(f"✅ JWKS warm-up: SUCCESS ({jwks_result['duration_ms']:.1f}ms)")
    else:
        logger.warning(f"⚠️ JWKS warm-up: FAILED ({jwks_result['error']})")
    
    # 2. Warm up Graph token cache
    token_result = warmup_graph_token()
    if token_result['success']:
        logger.info(f"✅ Graph token warm-up: SUCCESS ({token_result['duration_ms']:.1f}ms, TTL={token_result['ttl_s']:.0f}s)")
    else:
        logger.warning(f"⚠️ Graph token warm-up: FAILED ({token_result['error']})")
    
    # 3. Warm up Site ID cache
    site_result = warmup_site_id()
    if site_result['success']:
        logger.info(f"✅ Site ID warm-up: SUCCESS ({site_result['duration_ms']:.1f}ms, site={site_result['site_id'][:40]}...)")
    else:
        logger.warning(f"⚠️ Site ID warm-up: FAILED ({site_result['error']})")
    
    total_duration = (time.time() - warmup_start) * 1000
    
    logger.info("="*80)
    logger.info(f"🔥 STARTUP WARM-UP: Complete in {total_duration:.1f}ms")
    logger.info(f"   JWKS: {'SUCCESS' if jwks_result['success'] else 'FAILED'}")
    logger.info(f"   Graph token: {'SUCCESS' if token_result['success'] else 'FAILED'}")
    logger.info(f"   Site ID: {'SUCCESS' if site_result['success'] else 'FAILED'}")
    logger.info("="*80)
    
    # Concise one-line summary
    summary = (
        f"📊 STARTUP SUMMARY: "
        f"worker_pid={worker_pid} | "
        f"hostname={hostname} | "
        f"jwks_warmup={'success' if jwks_result['success'] else 'fail'} | "
        f"graph_token_warmup={'success' if token_result['success'] else 'fail'} | "
        f"site_id_warmup={'success' if site_result['success'] else 'fail'} | "
        f"total_startup_warmup_ms={total_duration:.0f}"
    )
    logger.info(summary)
    logger.info("="*80)

# Run warm-up on module load (when app starts)
try:
    warmup_caches()
except Exception as warmup_error:
    logger.error(f"❌ Startup warm-up failed with exception: {warmup_error}", exc_info=True)
    logger.warning("⚠️ Continuing app startup despite warm-up failure. Caches will populate on first request.")

# Custom Jinja filter for currency formatting with commas
@app.template_filter('currency')
def currency_filter(value):
    """Format number as currency with dollar sign and commas"""
    try:
        return "${:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return "$0.00"

# Custom Jinja filter for date formatting
@app.template_filter('date_format')
def date_format_filter(value):
    """Format date as MM-DD-YY"""
    if not value:
        return ''
    try:
        # Handle different input formats
        if isinstance(value, str):
            # Try parsing YYYY-MM-DD format
            if len(value) >= 10 and value[4] == '-':
                date_obj = datetime.strptime(value[:10], '%Y-%m-%d')
            # Try parsing other common formats
            else:
                date_obj = datetime.strptime(value, '%Y-%m-%d')
        else:
            date_obj = value
        return date_obj.strftime('%m-%d-%y')
    except (ValueError, TypeError, AttributeError):
        return value

# Custom Jinja filter for masking DOB
@app.template_filter('mask_dob')
def mask_dob_filter(value):
    """Mask date of birth for privacy"""
    if not value:
        return ''
    return '**/**/****'

# Custom Jinja filter to filter payments during enrollment
@app.template_filter('enrolled_payments')
def enrolled_payments_filter(payments, enrollment_history):
    """Filter payments to only show those that occurred during enrolled periods"""
    if not payments or not enrollment_history:
        return []
    
    # Find the first enrollment date
    enrollment_date = None
    for event in enrollment_history:
        if event.get('action') == 'enrolled':
            enrollment_date = event.get('timestamp')
            break
    
    if not enrollment_date:
        return []
    
    # Parse enrollment date (could be datetime string or date string)
    try:
        if ' ' in enrollment_date:  # datetime format
            enrollment_dt = datetime.strptime(enrollment_date, '%Y-%m-%d %H:%M:%S')
        else:  # date only format
            enrollment_dt = datetime.strptime(enrollment_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return payments  # If we can't parse, return all payments
    
    # Filter payments to only those on or after enrollment date
    filtered_payments = []
    for payment in payments:
        payment_date_str = payment.get('payment_date')
        if payment_date_str:
            try:
                payment_dt = datetime.strptime(payment_date_str, '%Y-%m-%d')
                if payment_dt >= enrollment_dt:
                    filtered_payments.append(payment)
            except (ValueError, TypeError):
                continue
    
    return filtered_payments

# Load test data from JSON file (fallback)
def load_test_data():
    """Load resident data from test_data.json"""
    data_file = os.path.join(os.path.dirname(__file__), 'test_data.json')
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
            return data.get('residents', [])
    except FileNotFoundError:
        print(f"Warning: {data_file} not found. Using empty resident list.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing test_data.json: {e}")
        return []

# In-memory data structures (loaded from Excel with encrypted SSNs)
CURRENT_RESIDENT_ID = 1

# Lazy-load residents on first access to avoid blocking worker startup
_residents_cache = None
_residents_loading = False

def get_residents():
    """Lazy-load residents on first access to avoid blocking Gunicorn worker startup"""
    global _residents_cache, _residents_loading
    
    if _residents_cache is not None:
        return _residents_cache
    
    if _residents_loading:
        # Prevent re-entrant loading
        return []
    
    _residents_loading = True
    try:
        logger.info("Loading residents from Excel file...")
        _residents_cache = load_residents_from_excel('Resident PII Test.xlsx')
        if not _residents_cache:
            logger.warning("Excel file empty or not found, falling back to JSON")
            _residents_cache = load_test_data()
        logger.info(f"Loaded {len(_residents_cache)} residents from data source")
    except Exception as e:
        logger.error(f"Error loading Excel file: {e}, falling back to JSON", exc_info=True)
        _residents_cache = load_test_data()
    finally:
        _residents_loading = False
    
    return _residents_cache

# Compatibility wrapper - use get_residents() for lazy loading
@property
def residents_property():
    return get_residents()

# For backwards compatibility, create a class that acts like a list
class LazyResidentsList:
    def __getitem__(self, key):
        return get_residents()[key]
    
    def __iter__(self):
        return iter(get_residents())
    
    def __len__(self):
        return len(get_residents())
    
    def __bool__(self):
        return True

residents = LazyResidentsList()


def get_resident_by_id(resident_id):
    """Get resident by ID"""
    for resident in residents:
        if resident['id'] == resident_id:
            return resident
    return None


def get_last_reported_month(resident):
    """Get the last reported month for a resident"""
    reported_payments = [p for p in resident['payments'] if p.get('reported', False)]
    if reported_payments:
        return reported_payments[0]['month']
    return "N/A"


# ============= AUTHORIZATION DECORATORS =============

def require_admin(f):
    """
    Decorator to require admin role for a route.
    Returns 403 error if user is not an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            logger.warning(f"🚨 SECURITY: Unauthorized admin access attempt")
            logger.warning(f"   Route: {request.path}")
            logger.warning(f"   User: {session.get('user_email', 'unknown')}")
            logger.warning(f"   Role: {session.get('role', 'none')}")
            return render_template('error.html',
                                 message='Access Denied',
                                 details='You are not authorized to access this page.'), 403
        return f(*args, **kwargs)
    return decorated_function


def require_resident(f):
    """
    Decorator to require resident role for a route.
    Returns 403 error if user is not a resident or if resident_id is missing.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'resident':
            logger.warning(f"🚨 SECURITY: Unauthorized resident access attempt")
            logger.warning(f"   Route: {request.path}")
            logger.warning(f"   User: {session.get('user_email', 'unknown')}")
            logger.warning(f"   Role: {session.get('role', 'none')}")
            return render_template('error.html',
                                 message='Access Denied',
                                 details='You are not authorized to access this page.'), 403
        
        # Verify resident_id is in session
        if not session.get('resident_id'):
            logger.error(f"🚨 SECURITY: Resident role set but no resident_id in session")
            logger.error(f"   Route: {request.path}")
            logger.error(f"   User: {session.get('user_email', 'unknown')}")
            return render_template('error.html',
                                 message='Session Error',
                                 details='Your session is invalid. Please log out and log in again.'), 403
        
        return f(*args, **kwargs)
    return decorated_function


# ============= EASY AUTH INTEGRATION =============

def get_easy_auth_claims():
    """
    Extract claims from Azure Easy Auth headers.
    Returns dict with user info or None if not authenticated.
    """
    # Easy Auth passes the authenticated user in this header
    principal_header = request.headers.get('X-MS-CLIENT-PRINCIPAL')
    
    if not principal_header:
        return None
    
    try:
        # Decode the base64-encoded JSON
        decoded = base64.b64decode(principal_header).decode('utf-8')
        claims = json.loads(decoded)
        
        # Extract useful information
        user_email = None
        user_name = None
        object_id = None
        tenant_id = None
        
        # Log all claims for debugging (first time only per session)
        all_claim_types = [claim.get('typ') for claim in claims.get('claims', [])]
        logger.info(f"🔍 Easy Auth claims received: {all_claim_types[:10]}")  # Show first 10 claim types
        
        # DEBUG: Log ALL claim type-value pairs to diagnose email claim issue
        logger.info(f"🔍 ALL CLAIMS DEBUG:")
        for claim in claims.get('claims', []):
            logger.info(f"   {claim.get('typ')}: {claim.get('val')}")
        
        # Extract OID and Tenant ID first (primary identity)
        roles = []  # Initialize roles list
        
        for claim in claims.get('claims', []):
            claim_type = claim.get('typ')
            claim_value = claim.get('val')
            
            if claim_type == 'http://schemas.microsoft.com/identity/claims/objectidentifier':
                object_id = claim_value
                logger.info(f"🔑 Extracted OID: {object_id[:16]}...")
            
            if claim_type == 'http://schemas.microsoft.com/identity/claims/tenantid':
                tenant_id = claim_value
                logger.info(f"🔑 Extracted Tenant ID: {tenant_id[:16]}...")
            
            # Extract Azure AD app roles
            if claim_type == 'roles':
                roles.append(claim_value)
                logger.info(f"🎭 Found role: {claim_value}")
        
        # Look for email claim and other user info
        for claim in claims.get('claims', []):
            claim_type = claim.get('typ')
            claim_value = claim.get('val')
            
            # Check for email-related claims
            if claim_type in ['emails', 'email', 'preferred_username', 'upn', 'signInNames.emailAddress']:
                if not user_email:  # Take first email found
                    user_email = claim_value
                    logger.info(f"✅ Found email in claim type '{claim_type}': {user_email}")
            
            # Check for name claim
            if claim_type == 'name':
                user_name = claim_value
        
        # Fallback to simple headers if claims parsing fails
        if not user_email:
            logger.warning(f"⚠️ No email found in claims, trying fallback headers")
            fallback_email = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
            # Reject invalid fallback values
            if fallback_email and fallback_email != 'unknown' and '@' in fallback_email:
                user_email = fallback_email
                logger.info(f"✅ Found email in X-MS-CLIENT-PRINCIPAL-NAME header: {user_email}")
            else:
                logger.info(f"⚠️ X-MS-CLIENT-PRINCIPAL-NAME is invalid: {fallback_email}")
        
        # Final fallback: Query Microsoft Graph API using object identifier
        # This is needed for External ID local accounts where email is stored as an identity
        if not user_email or user_email == 'unknown':
            if object_id:
                logger.info(f"🔍 No valid email in claims, querying Graph API for user {object_id[:8]}...")
                user_email = get_user_email_from_graph(object_id)
                if user_email and user_email != 'unknown':
                    logger.info(f"✅ Retrieved email from Graph API: {user_email}")
                else:
                    logger.warning(f"⚠️ Graph API lookup returned no valid email for {object_id[:8]}...")
            else:
                logger.warning(f"⚠️ No object identifier found in claims, cannot query Graph API")
        
        return {
            'email': user_email,
            'name': user_name or user_email,
            'object_id': object_id,
            'tenant_id': tenant_id,
            'roles': roles,  # Include Azure AD app roles
            'identity_provider': claims.get('identity_provider', 'aad'),
            'raw_claims': claims
        }
    except Exception as e:
        logger.error(f"Error parsing Easy Auth claims: {e}")
        # Fallback to simpler header
        email = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
        if email:
            return {
                'email': email,
                'name': email,
                'identity_provider': 'aad',
                'raw_claims': None
            }
        return None


@app.before_request
def setup_session_from_easy_auth_middleware():
    """
    Middleware to populate Flask session from Easy Auth on every request.
    This runs before every route handler.
    """
    try:
        # Skip for health check and debug endpoints (must work without auth)
        if request.path in ['/health', '/debug-ping', '/debug-auth']:
            return
        
        # Allow anonymous access to landing page (for login selection)
        if request.path in ['/', '/login']:
            # Only proceed with auth if user is already authenticated
            # This allows the landing page to be shown without forcing login
            claims = get_easy_auth_claims()
            if not claims:
                # Not authenticated - allow landing page to show
                return
            # Authenticated - continue processing to set role
        
        # Skip for static files
        if request.path.startswith('/static/'):
            return
        
        # ALWAYS re-run authentication check if path is not cached-friendly
        # This prevents stale session data from causing authorization mismatches
        should_recheck = False
        
        # For admin dashboard or admin routes, always recheck
        if request.path.startswith('/admin'):
            should_recheck = True
        
        # Skip if session is already fully set (performance optimization)
        # But re-run if resident_id is missing (to fix missing matches)
        if not should_recheck and 'user_email' in session and 'role' in session:
            if session.get('role') == 'admin' or 'resident_id' in session:
                return
            # If role is resident but no resident_id, continue to try matching again
        
        # Get Easy Auth claims
        claims = get_easy_auth_claims()
        
        if not claims:
            # No authentication - Easy Auth should have caught this
            # This might happen in local dev without Easy Auth
            if app.debug:
                logger.warning("⚠️ No Easy Auth claims found - using fallback for local dev")
            return
        
        user_email = claims.get('email')
        object_id = claims.get('object_id')
        tenant_id = claims.get('tenant_id')
        
        # Reject invalid email values
        if user_email and user_email == 'unknown':
            logger.warning(f"⚠️ Email claim is 'unknown' - treating as missing")
            user_email = None
        
        logger.info(f"🔍 Extracted from claims: email={user_email}, oid={object_id[:16] if object_id else None}...")
        
        # Set session data (store only serializable data)
        session['user_name'] = claims.get('name', user_email or 'Unknown User')
        session['identity_provider'] = claims.get('identity_provider', 'unknown')
        if user_email:
            session['user_email'] = user_email
        if object_id:
            session['object_id'] = object_id
        if tenant_id:
            session['tenant_id'] = tenant_id
        
        # === STEP 1: Try OID-based lookup first (primary identity) ===
        resident_id = None
        resident = None
        resolution_path = None
        
        if object_id:
            logger.info(f"🔍 STEP 1: Looking up resident by OID: {object_id[:16]}...")
            for r in residents:
                r_oid = r.get('external_oid')
                if r_oid and r_oid == object_id:
                    resident = r
                    resident_id = r['id']
                    resolution_path = 'resolved_by_oid'
                    logger.info(f"✅ OID MATCH: {object_id[:16]}... → {r.get('name')} (ID: {resident_id})")
                    break
            
            if not resident:
                logger.info(f"⚠️ No resident found with OID {object_id[:16]}...")
        else:
            logger.warning(f"⚠️ No OID in claims - cannot use OID-based lookup")
        
        # === STEP 2: If not found by OID, try email fallback ===
        if not resident and user_email and user_email != 'unknown':
            logger.info(f"🔍 STEP 2: Looking up resident by email: {user_email}")
            logger.info(f"🔍 Checking against {len(list(residents))} residents in cache")
            
            for r in residents:
                r_email = r.get('email', '').lower()
                if r_email == user_email.lower():
                    resident = r
                    resident_id = r['id']
                    logger.info(f"✅ EMAIL MATCH: {user_email} → {r.get('name')} (ID: {resident_id})")
                    
                    # === STEP 3: Link OID if this is first login with OID ===
                    if object_id and not r.get('external_oid'):
                        logger.info(f"🔗 LINKING OID: Resident {resident_id} ({r.get('name')}) has no OID - linking now")
                        from utils.data_loader import link_resident_external_oid
                        if link_resident_external_oid(resident_id, object_id, tenant_id):
                            # Update in-memory cache
                            r['external_oid'] = object_id
                            r['external_tenant_id'] = tenant_id
                            resolution_path = 'resolved_by_email_then_linked_oid'
                            logger.info(f"✅ OID LINKED: Future logins will resolve directly by OID")
                        else:
                            logger.error(f"❌ Failed to link OID to resident {resident_id}")
                            resolution_path = 'resolved_by_email_only'
                    elif r.get('external_oid'):
                        logger.info(f"ℹ️ Resident already has OID: {r.get('external_oid')[:16]}...")
                        resolution_path = 'resolved_by_email_existing_oid'
                    else:
                        resolution_path = 'resolved_by_email_no_oid'
                    
                    break
            
            if not resident:
                logger.info(f"⚠️ NO EMAIL MATCH: {user_email} not found in resident data")
                logger.info(f"⚠️ Sample emails in cache: {[r.get('email', '') for r in list(residents)[:5]]}")
        
        # === FINAL: Set session and determine role ===
        # CRITICAL SECURITY: Check admin FIRST, before checking resident match
        # This ensures admins are recognized even if they also have a resident record
        is_admin = False
        
        # METHOD 1: Check Azure AD app roles (PREFERRED)
        user_roles = claims.get('roles', [])
        if 'Admin' in user_roles:
            is_admin = True
            logger.info(f"✅ ADMIN AUTHORIZED via Azure AD app role: {user_email}")
            logger.info(f"   User roles: {user_roles}")
        
        # METHOD 2: Fallback to SharePoint admin list check (if not already admin)
        if not is_admin and user_email:
            from utils.sharepoint_verification import check_admin_authorization
            is_admin = check_admin_authorization(user_email)
            
            if is_admin:
                session['role'] = 'admin'
                session['user_email'] = user_email
                logger.info(f"✅ ADMIN AUTHORIZED: email={user_email}")
                return
        
        # User is not admin - check if they have a valid resident record
        if resident:
            # Regular resident user with matched record
            session['role'] = 'resident'
            session['resident_id'] = resident_id
            session['user_email'] = user_email
            logger.info(f"✅ RESIDENT AUTHORIZED: path={resolution_path} | resident_id={resident_id} | name={resident.get('name')} | email={user_email}")
        else:
            # CRITICAL SECURITY: No match found - DENY ACCESS
            # Do NOT default to any resident account
            # User is authenticated but not authorized for this application
            session['role'] = 'unauthorized'
            session['user_email'] = user_email
            logger.warning(f"🚨 SECURITY: Unauthorized access attempt - authenticated user not found in system")
            logger.warning(f"   Email: {user_email}")
            logger.warning(f"   OID: {object_id[:16] if object_id else 'None'}...")
            logger.warning(f"   Resolution path: {resolution_path or 'unresolved_no_match'}")
            logger.warning(f"   Action: Access denied - redirecting to unauthorized page")

    
    except Exception as e:
        logger.error(f"❌ Error in Easy Auth middleware: {str(e)}", exc_info=True)
        # Don't block the request, just log the error
        return


# Flask 3.x compatible: Use before_request with one-time guard instead of before_first_request
_first_request_handled = False

def log_application_startup():
    """Log startup info after first request, not at import time"""
    global _first_request_handled
    
    if _first_request_handled:
        return
    
    _first_request_handled = True
    
    logger.info("=" * 60)
    logger.info("Flask app received first request")
    logger.info(f"Environment: {'Development' if app.debug else 'Production'}")
    logger.info(f"Debug mode: {app.debug}")
    logger.info(f"Secret key: {'Set' if app.secret_key else 'NOT SET'}")
    # Note: Residents will be loaded on-demand when first needed by a business route
    logger.info("=" * 60)


# ============= API ROUTES (Azure Entra External ID Custom Authentication Extension) =============

@app.route('/api/verify-resident', methods=['POST', 'OPTIONS'])
@cross_origin(origins="*", methods=['POST', 'OPTIONS'], allow_headers=['Content-Type', 'Authorization'])
@require_bearer_token
def verify_resident_signup():
    """
    API endpoint called by Azure Entra External ID custom authentication extension.
    
    **COMPREHENSIVE DIAGNOSTIC MODE - CANONICAL RESPONSE ENFORCEMENT**
    
    This version implements:
    - CANONICAL success response (get_canonical_success_response) used for ALL success paths
    - SHA-256 hashing of response body for byte-for-byte comparison
    - Comprehensive timing breakdown (token acquisition, site resolution, list query, serialization)
    - Graph API diagnostics (endpoint URLs, status codes, request IDs, elapsed times)
    - OData type logging (incoming vs outgoing for comparison)
    
    Goal: Determine whether SharePoint verification logic is causing response format issues
    
    How to compare responses:
    1. Look for "🔐 Response SHA-256 hash" in logs
    2. Compare hash between minimal test (if any) and SharePoint success path
    3. If hashes differ, compare the "📡 ACTUAL DATA being sent" sections
    4. Check OData types: incoming (@odata.type) vs outgoing (data, action)
    5. Review timing breakdown to find bottlenecks
    
    Expected timings:
    - Token acquisition: <500ms typical
    - Site resolution: <500ms typical
    - List query: <1000ms typical
    - Total: <2000ms typical
    
    Authentication:
        - Bearer token (OAuth 2.0 client credentials)
        - Token validated via @require_bearer_token decorator
    
    Request payload:
        Custom authentication extension format with type, source, and data containing:
        - attributes: user-submitted sign-up data (email, givenName, surname, custom fields)
        - identities: array with email addresses
        - tenantId, authenticationEventListenerId, customAuthenticationExtensionId
    
    Response:
        - ContinueWithDefaultBehavior: Allow sign-up (verification passed) - CANONICAL RESPONSE
        - ShowValidationError: Display validation errors (verification failed)
        - ShowBlockPage: Hard block (service unavailable)
    
    Note:
        This endpoint is isolated from the rest of the app's authentication flow.
        It does not depend on Flask sessions, Easy Auth headers, or browser cookies.
    """
    # ============================================================================
    # TRUE END-TO-END WALL-CLOCK TIMING (set by decorator)
    # request.request_start_time is captured at decorator entry (before token validation)
    # This gives us true wall-clock timing including all decorator overhead
    # ============================================================================
    request_start_time = getattr(request, 'request_start_time', time.time())
    request_start_iso = datetime.now().isoformat()
    
    # ============================================================================
    # FIRST-REQUEST TRACKING
    # Track whether this is the first request after app startup
    # Helps diagnose cold-start latency vs warm performance
    # ============================================================================
    global _first_request_after_start
    with _first_request_lock:
        is_first_request = _first_request_after_start
        if _first_request_after_start:
            _first_request_after_start = False
            logger.info("🆕 FIRST REQUEST AFTER STARTUP")
    
    # Request correlation tracking for retry detection
    request_correlation = {
        'request_id': None,
        'extension_id': None,
        'listener_id': None,
        'tenant_id': None,
        'event_type': None
    }
    
    logger.info("="*80)
    logger.info(f"🔐 Custom authentication extension endpoint called (first_request={is_first_request})")
    logger.info(f"📅 Start time: {request_start_iso}")
    
    # ============================================================================
    # WORKER/PROCESS IDENTITY
    # Confirm same process handling warmup and requests
    # ============================================================================
    import socket
    worker_pid = os.getpid()
    hostname = socket.gethostname()
    logger.info(f"🔧 Worker PID: {worker_pid}, Hostname: {hostname}")
    
    # ============================================================================
    # CACHE STATE DIAGNOSTICS
    # Check if caches were populated by startup warm-up
    # ============================================================================
    jwks_cache_state = get_jwks_cache_state()
    graph_cache_state = get_graph_token_cache_state()
    site_cache_state = get_site_id_cache_state()
    
    logger.info("📦 CACHE STATE AT REQUEST START:")
    logger.info(f"   JWKS cache: present={jwks_cache_state['present']}, source={jwks_cache_state.get('source', 'N/A')}, age={jwks_cache_state['age_s']:.0f}s, expired={jwks_cache_state['expired']}")
    logger.info(f"   Graph token cache: present={graph_cache_state['present']}, source={graph_cache_state.get('source', 'N/A')}, age={graph_cache_state['age_s']:.0f}s, expired={graph_cache_state['expired']}")
    logger.info(f"   Site ID cache: present={site_cache_state['present']}, source={site_cache_state.get('source', 'N/A')}, age={site_cache_state['age_s']:.0f}s")
    
    try:
        # Parse the custom extension request payload
        parsing_start = time.time()
        request_data = request.get_json()
        parsing_elapsed_ms = (time.time() - parsing_start) * 1000
        
        if not request_data:
            logger.error("❌ Empty request body")
            wall_clock_ms = (time.time() - request_start_time) * 1000
            
            error_response = build_block_page_response(
                "Service temporarily unavailable. Please try again later."
            )
            validate_response_schema(error_response, diagnostic_mode=True)
            
            logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.1f}ms | first_request={is_first_request} | verification_result=error_empty_body | diagnostic_error=false | status=error_empty_body")
            return jsonify(error_response), 200
        
        # Extract correlation IDs for retry detection
        data = request_data.get('data', {})
        request_correlation['event_type'] = request_data.get('type', 'unknown')
        request_correlation['extension_id'] = data.get('customAuthenticationExtensionId', 'N/A')[:20]
        request_correlation['listener_id'] = data.get('authenticationEventListenerId', 'N/A')[:20]
        request_correlation['tenant_id'] = data.get('tenantId', 'N/A')[:20]
        
        # Log correlation info
        logger.info(f"📋 Event type: {request_correlation['event_type']}")
        logger.info(f"📋 Extension ID: {request_correlation['extension_id']}...")
        logger.info(f"📋 Listener ID: {request_correlation['listener_id']}...")
        logger.info(f"📋 Tenant ID: {request_correlation['tenant_id']}...")
        logger.info(f"📋 Incoming @odata.type: {data.get('@odata.type', 'N/A')}")
        logger.info(f"⏱️ Request parsing: {parsing_elapsed_ms:.1f}ms")
        event_type = request_data.get('type', 'unknown')
        logger.info(f"📋 Event type: {event_type}")
        
        # Log data structure if present
        data = request_data.get('data', {})
        if data:
            logger.info(f"📋 Data payload keys: {list(data.keys())}")
            logger.info(f"📋 Incoming @odata.type: {data.get('@odata.type', 'N/A')}")
            logger.info(f"📋 Tenant ID: {data.get('tenantId', 'N/A')[:20]}...")
            logger.info(f"📋 Extension ID: {data.get('customAuthenticationExtensionId', 'N/A')[:20]}...")
        
        # Parse attributes from the custom extension payload
        parsed_attrs = parse_custom_extension_request(request_data)
        
        if parsed_attrs is None:
            logger.error("❌ Failed to parse custom extension request")
            wall_clock_ms = (time.time() - request_start_time) * 1000
            
            error_response = build_block_page_response(
                "Service temporarily unavailable. Please try again later."
            )
            validate_response_schema(error_response, diagnostic_mode=True)
            
            logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.0f}ms | first_request={is_first_request} | verification_result=error_parse_failed | diagnostic_error=false | status=error_parse_failed")
            return jsonify(error_response), 200
        
        # Extract user-submitted data
        email = parsed_attrs.get('email', '')
        first_name = parsed_attrs.get('given_name', '')
        last_name = parsed_attrs.get('surname', '')
        date_of_birth = parsed_attrs.get('date_of_birth', '')
        
        logger.info(f"👤 User data received:")
        logger.info(f"   Email: {email}")
        logger.info(f"   Name: {first_name} {last_name}")
        logger.info(f"   DOB: {'***' if date_of_birth else 'missing'}")
        
        # Validate required fields
        missing_fields = []
        if not email:
            missing_fields.append('email')
        if not first_name:
            missing_fields.append('first name')
        if not last_name:
            missing_fields.append('last name')
        if not date_of_birth:
            missing_fields.append('date of birth')
        
        if missing_fields:
            logger.warning(f"⚠️ Missing required fields: {', '.join(missing_fields)}")
            wall_clock_ms = (time.time() - request_start_time) * 1000
            
            error_response = build_validation_error_response(
                f"Please provide all required information: {', '.join(missing_fields)}."
            )
            validate_response_schema(error_response, diagnostic_mode=True)
            
            logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.0f}ms | first_request={is_first_request} | verification_result=error_missing_fields | diagnostic_error=false | status=error_missing_fields")
            return jsonify(error_response), 200
        
        # ========================================================================
        # SHAREPOINT VERIFICATION WITH COMPREHENSIVE DIAGNOSTICS
        # ========================================================================
        
        logger.info("="*80)
        logger.info("🔍 Starting SharePoint resident verification")
        logger.info(f"   Looking for: {first_name} {last_name} ({email})")
        logger.info("="*80)
        
        try:
            # Call SharePoint verification (returns timings)
            verification_result = verify_resident_sharepoint(
                email=email,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth
            )
            
            # ============================================================
            # SAFE DIAGNOSTIC LOGGING - MUST NOT BREAK VERIFICATION FLOW
            # ============================================================
            diagnostic_error = False
            try:
                # Extract timings
                sp_timings = verification_result.get('timings', {})
                logger.info("⏱️ SharePoint timing breakdown:")
                safe_log_timings_dict(sp_timings, prefix="   ")
            except Exception as diagnostic_ex:
                diagnostic_error = True
                logger.error(f"❌ Diagnostics error (non-fatal): {diagnostic_ex}", exc_info=True)
            
            if verification_result['verified']:
                logger.info("✅ Resident verification PASSED")
                logger.info(f"   Match details: {verification_result.get('match_details', 'N/A')}")
                
                # ============================================================
                # CANONICAL SUCCESS RESPONSE - EXACT SAME RESPONSE EVERY TIME
                # ============================================================
                logger.info("="*80)
                logger.info("🔨 Building CANONICAL success response")
                logger.info("="*80)
                
                # Get the canonical response (returns fresh copy)
                response_build_start = time.time()
                success_response = get_canonical_success_response()
                response_build_ms = (time.time() - response_build_start) * 1000
                
                logger.info(f"✅ Response object created: {response_build_ms:.3f}ms")
                logger.info(f"   Type: {type(success_response)}")
                logger.info(f"   Keys: {list(success_response.keys())}")
                
                # ========================================================
                # VALIDATE RESPONSE SCHEMA (DIAGNOSTIC)
                # ========================================================
                # Catches schema regressions before Entra rejects with error 1003003
                logger.info("🔍 Validating response schema...")
                validation_result = validate_response_schema(success_response, diagnostic_mode=True)
                if not validation_result['valid']:
                    logger.error(f"❌ RESPONSE SCHEMA INVALID - This will cause Entra error 1003003!")
                    logger.error(f"   Errors: {validation_result['errors']}")
                else:
                    logger.info("✅ Response schema is valid")
                
                # Log OData types for comparison
                logger.info(f"📋 Outgoing @odata.type (data): {success_response.get('data', {}).get('@odata.type', 'N/A')}")
                logger.info(f"📋 Outgoing @odata.type (action): {success_response.get('data', {}).get('actions', [{}])[0].get('@odata.type', 'N/A')}")
                
                # Pretty-print the response structure
                logger.info(f"📤 Response payload to External ID:")
                logger.info(f"{json.dumps(success_response, indent=2)}")
                
                # Create Flask response - THIS IS THE CRITICAL SERIALIZATION STEP
                logger.info("🔨 Creating Flask response with jsonify...")
                flask_response_start = time.time()
                
                try:
                    flask_response = jsonify(success_response)
                    flask_response_ms = (time.time() - flask_response_start) * 1000
                    
                    logger.info(f"✅ Flask response created: {flask_response_ms:.3f}ms")
                    logger.info(f"   Response type: {type(flask_response)}")
                    logger.info(f"   Status code: 200")
                    logger.info(f"   Content-Type: {flask_response.content_type}")
                    
                    # ========================================================
                    # CRITICAL: Get the EXACT serialized response body
                    # ========================================================
                    response_data = flask_response.get_data(as_text=True)
                    response_bytes = flask_response.get_data(as_text=False)
                    
                    # Calculate SHA-256 hash for comparison
                    response_hash = hashlib.sha256(response_bytes).hexdigest()
                    
                    logger.info(f"📡 ACTUAL DATA being sent to External ID:")
                    logger.info(f"{response_data}")
                    logger.info(f"")
                    logger.info(f"🔐 Response SHA-256 hash: {response_hash}")
                    logger.info(f"📏 Response size: {len(response_bytes)} bytes")
                    
                    # Log response headers
                    logger.info(f"📋 Response headers:")
                    for header, value in flask_response.headers:
                        logger.info(f"   {header}: {value}")
                    
                    # ========================================================
                    # COMPREHENSIVE TIMING BREAKDOWN WITH CACHE HIT TRACKING
                    # WRAPPED IN TRY-EXCEPT TO PREVENT DIAGNOSTIC EXCEPTIONS
                    # ========================================================
                    try:
                        wall_clock_ms = (time.time() - request_start_time) * 1000
                        
                        # Get token validation metrics from decorator
                        entra_metrics = getattr(request, 'entra_metrics', {})
                        
                        logger.info(f"")
                        logger.info(f"⏱️ TIMING BREAKDOWN:")
                        logger.info(f"   Token validation: {entra_metrics.get('total_validation_ms', 0):.1f}ms")
                        logger.info(f"      - Header parse: {entra_metrics.get('header_parse_ms', 0):.1f}ms")
                        logger.info(f"      - JWKS fetch: {entra_metrics.get('jwks_fetch_ms', 0):.1f}ms (cache={'HIT' if entra_metrics.get('jwks_cache_hit') else 'MISS'})")
                        if entra_metrics.get('jwks_cache_hit'):
                            logger.info(f"         * JWKS cache age: {entra_metrics.get('jwks_cache_age_s', 0):.0f}s, TTL: {entra_metrics.get('jwks_ttl_remaining_s', 0):.0f}s")
                        logger.info(f"      - Key lookup: {entra_metrics.get('key_lookup_ms', 0):.1f}ms (cache={'HIT' if entra_metrics.get('key_cache_hit') else 'MISS'})")
                        if not entra_metrics.get('key_cache_hit'):
                            logger.info(f"         * Key construction: {entra_metrics.get('key_construction_ms', 0):.1f}ms")
                        logger.info(f"      - Signature verify: {entra_metrics.get('signature_verify_ms', 0):.1f}ms")
                        logger.info(f"   Request parsing: {parsing_elapsed_ms:.1f}ms")
                        logger.info(f"   SharePoint token: {sp_timings.get('token_acquisition_ms', 0):.1f}ms (cache={'HIT' if sp_timings.get('graph_token_cache_hit') else 'MISS'})")
                        if sp_timings.get('graph_token_cache_hit'):
                            logger.info(f"      - Token cache age: {sp_timings.get('token_cache_age_s', 0):.0f}s, TTL remaining: {sp_timings.get('token_ttl_remaining_s', 0):.0f}s")
                        logger.info(f"   Site resolution: {sp_timings.get('site_resolution_ms', 0):.1f}ms (cache={'HIT' if sp_timings.get('site_id_cache_hit') else 'MISS'})")
                        if sp_timings.get('site_id_cache_hit'):
                            logger.info(f"      - Site cache age: {sp_timings.get('site_cache_age_s', 0):.0f}s")
                        logger.info(f"   List query: {sp_timings.get('list_query_ms', 0):.1f}ms")
                        logger.info(f"   Response building: {response_build_ms:.1f}ms")
                        logger.info(f"   Response serialization: {flask_response_ms:.1f}ms")
                        logger.info(f"   TRUE WALL-CLOCK TOTAL: {wall_clock_ms:.1f}ms (includes decorator overhead)")
                    except Exception as timing_ex:
                        diagnostic_error = True
                        logger.error(f"❌ Timing breakdown diagnostics failed (non-fatal): {timing_ex}", exc_info=True)
                    
                    # ========================================================
                    # COMPACT SUMMARY LINE FOR EASY COMPARISON
                    # WRAPPED IN TRY-EXCEPT TO PREVENT DIAGNOSTIC EXCEPTIONS
                    # ========================================================
                    try:
                        summary = (
                            f"📊 SUMMARY: "
                            f"wall_clock={wall_clock_ms:.0f}ms | "
                            f"token_validation={entra_metrics.get('total_validation_ms', 0):.0f}ms | "
                            f"jwks_cache={'HIT' if entra_metrics.get('jwks_cache_hit') else 'MISS'} | "
                            f"key_cache={'HIT' if entra_metrics.get('key_cache_hit') else 'MISS'} | "
                            f"signature_verify={entra_metrics.get('signature_verify_ms', 0):.0f}ms | "
                            f"graph_token={sp_timings.get('token_acquisition_ms', 0):.0f}ms | "
                            f"graph_token_cache={'HIT' if sp_timings.get('graph_token_cache_hit') else 'MISS'} | "
                            f"site_resolution={sp_timings.get('site_resolution_ms', 0):.0f}ms | "
                            f"site_id_cache={'HIT' if sp_timings.get('site_id_cache_hit') else 'MISS'} | "
                            f"list_query={sp_timings.get('list_query_ms', 0):.0f}ms | "
                            f"sharepoint_total={sp_timings.get('total_verification_ms', 0):.0f}ms | "
                            f"first_request={is_first_request} | "
                            f"verification_result=success | "
                            f"diagnostic_error={diagnostic_error} | "
                            f"status=success | "
                            f"hash={response_hash[:16]}..."
                        )
                        logger.info(summary)
                    except Exception as summary_ex:
                        diagnostic_error = True
                        logger.error(f"❌ Summary logging failed (non-fatal): {summary_ex}", exc_info=True)
                        # Minimal fallback summary
                        logger.info(f"📊 SUMMARY: verification_result=success | diagnostic_error=true | status=success")
                    
                    logger.info("="*80)
                    
                    return flask_response, 200
                
                except Exception as jsonify_error:
                    logger.error(f"❌ Error creating Flask response: {jsonify_error}", exc_info=True)
                    raise
            
            else:
                # Verification failed
                logger.warning("❌ Resident verification FAILED")
                logger.warning(f"   Reason: {verification_result.get('reason', 'Unknown')}")
                
                # Build validation error response
                error_message = "We couldn't verify your information. Please check that your details match our records or contact support."
                
                # Provide specific error if available
                if 'reason' in verification_result:
                    reason = verification_result['reason']
                    if 'not found' in reason.lower():
                        error_message = "We couldn't find your information in our system. Please contact support to enroll in rent reporting."
                    elif 'date of birth' in reason.lower():
                        error_message = "The date of birth doesn't match our records. Please verify and try again."
                    elif 'name' in reason.lower():
                        error_message = "The name doesn't match our records. Please verify your first and last name."
                
                logger.info("🔨 Building validation error response...")
                error_response = build_validation_error_response(error_message)
                
                # Validate schema before returning
                logger.info("🔍 Validating error response schema...")
                validation_result = validate_response_schema(error_response, diagnostic_mode=True)
                
                logger.info(f"📤 Validation error response payload:")
                logger.info(f"{json.dumps(error_response, indent=2)}")
                
                logger.info("🔨 Creating Flask error response...")
                flask_response = jsonify(error_response)
                logger.info(f"📡 Actual error data being sent:")
                logger.info(f"{flask_response.get_data(as_text=True)}")
                
                wall_clock_ms = (time.time() - request_start_time) * 1000
                logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.0f}ms | first_request={is_first_request} | verification_result=failed | diagnostic_error={diagnostic_error} | status=verification_failed")
                logger.info("="*80)
                
                return flask_response, 200
        
        except Exception as verify_error:
            # SharePoint verification failed (service error, not verification failure)
            logger.error(f"❌ SharePoint verification service error: {verify_error}", exc_info=True)
            
            # Return block page for service errors
            logger.info("🔨 Building block page response (service error)...")
            error_response = build_block_page_response(
                "Our verification service is temporarily unavailable. Please try again later."
            )
            
            # Validate schema before returning
            logger.info("🔍 Validating block page response schema...")
            validation_result = validate_response_schema(error_response, diagnostic_mode=True)
            
            logger.info(f"📤 Block page response payload:")
            logger.info(f"{json.dumps(error_response, indent=2)}")
            
            logger.info("🔨 Creating Flask block response...")
            flask_response = jsonify(error_response)
            logger.info(f"📡 Actual block page data being sent:")
            logger.info(f"{flask_response.get_data(as_text=True)}")
            
            wall_clock_ms = (time.time() - request_start_time) * 1000
            logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.0f}ms | first_request={is_first_request} | verification_result=service_error | diagnostic_error=false | status=service_error")
            logger.info("="*80)
            
            return flask_response, 200
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ Unexpected error in verification endpoint: {e}", exc_info=True)
        
        logger.info("🔨 Building block page response (unexpected error)...")
        error_response = build_block_page_response(
            "Service temporarily unavailable. Please try again later."
        )
        
        # Validate schema before returning
        logger.info("🔍 Validating block page response schema...")
        validation_result = validate_response_schema(error_response, diagnostic_mode=True)
        
        logger.info(f"📤 Block page response payload:")
        logger.info(f"{json.dumps(error_response, indent=2)}")
        
        flask_response = jsonify(error_response)
        logger.info(f"📡 Actual data being sent:")
        logger.info(f"{flask_response.get_data(as_text=True)}")
        
        wall_clock_ms = (time.time() - request_start_time) * 1000
        logger.info(f"⚠️ SUMMARY: wall_clock={wall_clock_ms:.0f}ms | first_request={is_first_request} | verification_result=unexpected_error | diagnostic_error=false | status=unexpected_error")
        logger.info("="*80)
        
        return flask_response, 200


# ============= DIAGNOSTIC ROUTES =============

@app.route('/.auth/login/done')
def auth_login_done():
    """
    Handle Azure Easy Auth post-login redirect.
    Redirects user to appropriate dashboard based on their role.
    """
    logger.info("Post-login redirect handler called")
    return redirect(url_for('landing'))


@app.route('/health')
def health_check():
    """
    Minimal health check endpoint for Azure monitoring.
    Must return immediately without any heavy operations.
    """
    logger.info("HEALTH ROUTE HIT")
    return {'status': 'ok'}, 200


@app.route('/debug-ping')
def debug_ping():
    """
    Simplest possible diagnostic route.
    Returns plain text immediately.
    """
    logger.info("DEBUG PING HIT")
    return 'pong', 200


@app.route('/debug-auth')
def debug_auth():
    """
    Diagnostic endpoint to inspect Easy Auth state and Azure AD roles.
    Shows all claims including app roles for debugging authorization.
    """
    try:
        claims = get_easy_auth_claims()
        
        # Extract roles specifically for display
        user_roles = claims.get('roles', []) if claims else []
        has_admin_role = 'Admin' in user_roles if user_roles else False
        
        return {
            'authentication_status': 'Authenticated' if claims else 'Not Authenticated',
            'user_info': {
                'email': claims.get('email') if claims else 'Not available',
                'name': claims.get('name') if claims else 'Not available',
                'object_id': claims.get('object_id', 'Not available')[:16] + '...' if claims and claims.get('object_id') else 'Not available',
            },
            'azure_ad_roles': {
                'roles_found': user_roles,
                'has_admin_role': has_admin_role,
                'role_count': len(user_roles),
                'interpretation': 'Admin role assigned' if has_admin_role else 'No Admin role - only Default Access' if not user_roles else 'Other roles assigned'
            },
            'session_data': {
                'role': session.get('role'),
                'user_email': session.get('user_email'),
                'resident_id': session.get('resident_id')
            },
            'easy_auth_headers': {
                'X-MS-CLIENT-PRINCIPAL': 'Present (base64 decoded above)' if request.headers.get('X-MS-CLIENT-PRINCIPAL') else 'Not present',
                'X-MS-CLIENT-PRINCIPAL-NAME': request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'Not present'),
                'X-MS-CLIENT-PRINCIPAL-ID': request.headers.get('X-MS-CLIENT-PRINCIPAL-ID', 'Not present'),
                'X-MS-CLIENT-PRINCIPAL-IDP': request.headers.get('X-MS-CLIENT-PRINCIPAL-IDP', 'Not present')
            },
            'raw_claims_summary': {
                'claim_count': len(claims.get('raw_claims', {}).get('claims', [])) if claims and claims.get('raw_claims') else 0,
                'claim_types': [c.get('typ') for c in claims.get('raw_claims', {}).get('claims', [])][:20] if claims and claims.get('raw_claims') else []
            },
            'full_claims': claims,
            'request_path': request.path,
            'debug_mode': app.debug
        }, 200
    except Exception as e:
        logger.error(f"❌ Error in debug-auth route: {str(e)}", exc_info=True)
        return {
            'error': str(e),
            'status': 'error',
            'traceback': str(e)
        }, 500


@app.route('/.auth/me')
def auth_me():
    """
    Mirror Azure's /.auth/me endpoint for local debugging.
    In production, Easy Auth provides this automatically.
    """
    try:
        claims = get_easy_auth_claims()
        if not claims:
            return {'error': 'Not authenticated'}, 401
        
        # Format similar to Azure's /.auth/me endpoint
        return [{
            'provider_name': claims.get('identity_provider', 'aad'),
            'user_id': claims.get('object_id'),
            'user_claims': claims.get('raw_claims', {}).get('claims', []) if claims.get('raw_claims') else [],
            'access_token': None,  # Not exposed for security
            'expires_on': None,
            'id_token': None,  # Not exposed for security
        }], 200
    except Exception as e:
        logger.error(f"❌ Error in /.auth/me route: {str(e)}", exc_info=True)
        return {'error': str(e)}, 500


# ============= GLOBAL ERROR HANDLERS =============

@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Handle HTTP exceptions (404, 403, etc.) and preserve their status codes"""
    # Log at info level for common errors like 404, warn for others
    if error.code == 404:
        logger.info(f"HTTP {error.code}: {request.method} {request.path}")
    else:
        logger.warning(f"HTTP {error.code}: {request.method} {request.path} - {error.description}")
    
    return {
        'error': error.name,
        'message': error.description,
        'code': error.code
    }, error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Catch-all for true unexpected errors (not HTTP exceptions)"""
    # This will only catch non-HTTP exceptions due to HTTPException handler above
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    return {
        'error': 'Internal server error',
        'message': str(error),
        'type': type(error).__name__
    }, 500


@app.before_request
def log_request_info():
    """Log all incoming requests for debugging"""
    # Skip heavy startup logging for health/debug endpoints to prevent timeout
    if request.path not in ['/health', '/debug-ping']:
        # Flask 3.x compatible: Call first-request handler here instead of @before_first_request
        log_application_startup()
    
    logger.info(f"REQUEST: {request.method} {request.path} from {request.remote_addr}")


@app.after_request
def log_response_info(response):
    """Log all outgoing responses for debugging"""
    logger.info(f"RESPONSE: {request.method} {request.path} -> {response.status_code}")
    return response


# Landing / Role selection
@app.route('/')
@app.route('/login')
def landing():
    """
    Root route - shows login options or redirects to appropriate dashboard if authenticated
    """
    try:
        # Check if user is authenticated via Easy Auth
        claims = get_easy_auth_claims()
        
        # If authenticated AND has valid role in session, redirect automatically
        if claims and 'role' in session:
            role = session.get('role')
            
            # Only auto-redirect if explicitly requested via query param
            # This allows users to see landing page even when authenticated
            auto_redirect = request.args.get('auto', 'true').lower() == 'true'
            
            if auto_redirect:
                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif role == 'resident':
                    return redirect(url_for('resident_dashboard'))
                elif role == 'unauthorized':
                    user_email = claims.get('email', 'Unknown')
                    logger.warning(f"🚨 Unauthorized user attempted access: {user_email}")
                    return render_template('error.html', 
                                         message='Access Denied',
                                         details=f'Your account ({user_email}) is authenticated but not authorized to access this application. Please contact your administrator.'), 403
        
        # Show landing page with login options
        # This allows anonymous users to choose their login method
        # And allows authenticated users to see a welcome page if auto=false
        return render_template('landing.html', authenticated=claims is not None, user_email=claims.get('email') if claims else None)
        
    except Exception as e:
        logger.error(f"❌ Error in landing route: {str(e)}", exc_info=True)
        return render_template('error.html',
                             message='Application Error',
                             details=f'An error occurred: {str(e)}'), 500


@app.route('/login', methods=['POST'])
def login():
    """
    Old manual login route - now deactivated with Easy Auth.
    Kept for local development fallback only.
    """
    # In production with Easy Auth, this should not be used
    if not app.debug:
        return render_template('error.html',
                             message='Manual login is disabled',
                             details='This application uses Azure Easy Auth. Please access the root URL to authenticate.'), 403
    
    # Local development fallback (when Easy Auth is not available)
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    # Check admin authorization via SharePoint
    from utils.sharepoint_verification import check_admin_authorization
    if password == 'admin' and check_admin_authorization(email):
        session['role'] = 'admin'
        session['user_email'] = email
        return redirect(url_for('admin_dashboard'))
    elif password == 'resident':
        # All users with correct password become residents
        session['role'] = 'resident'
        session['user_email'] = email
        
        # Look up resident ID if available in data
        resident_id = None
        for resident in residents:
            if resident.get('email', '').lower() == email.lower():
                resident_id = resident['id']
                break
        
        if resident_id:
            session['resident_id'] = resident_id
        
        return redirect(url_for('resident_dashboard'))
    else:
        return render_template('landing.html', error='Invalid email or password')


@app.route('/select-role', methods=['POST'])
def select_role():
    role = request.form.get('role')
    if role == 'resident':
        session['role'] = 'resident'
        return redirect(url_for('resident_dashboard'))
    elif role == 'admin':
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Please select a role', 'danger')
        return redirect(url_for('landing'))


@app.route('/logout')
def logout():
    """
    Logout route - clears Flask session and redirects to Easy Auth logout.
    """
    user_email = session.get('user_email', 'unknown')
    user_role = session.get('role', 'unknown')
    resident_id = session.get('resident_id', 'N/A')
    
    # Clear ALL session data
    session.clear()
    
    logger.info(f"🔓 User logged out: email={user_email}, role={user_role}, resident_id={resident_id}")
    logger.info(f"   Session cleared completely")
    
    # Easy Auth logout endpoint with redirect back to landing page
    # Build the post-logout redirect URL dynamically
    post_logout_url = request.host_url.rstrip('/')  # Get base URL (works for both local and production)
    logout_url = f'/.auth/logout?post_logout_redirect_uri={post_logout_url}'
    
    return redirect(logout_url)


@app.route('/clear-session')
def clear_session():
    """
    Development/diagnostic route to force clear session without full logout.
    Useful for debugging session caching issues.
    """
    user_email = session.get('user_email', 'unknown')
    user_role = session.get('role', 'unknown')
    
    session.clear()
    
    logger.info(f"🧹 Session manually cleared: email={user_email}, role={user_role}")
    flash('Session cleared successfully. Please log in again.', 'info')
    return redirect(url_for('landing'))


# ============= RESIDENT ROUTES =============

@app.route('/resident/dashboard')
@require_resident
def resident_dashboard():
    resident_id = session.get('resident_id')
    resident = get_resident_by_id(resident_id)
    if not resident:
        logger.error(f"🚨 SECURITY: Invalid resident_id in session: {resident_id}")
        return render_template('error.html',
                             message='Account Error',
                             details='Your account information could not be found. Please contact support.'), 404
    
    # Calculate current reporting cycle (current month)
    current_date = datetime.now()
    current_cycle = current_date.strftime('%b %Y')
    
    # Calculate next reporting run (last day of current month)
    from calendar import monthrange
    last_day = monthrange(current_date.year, current_date.month)[1]
    next_run_date = current_date.replace(day=last_day).strftime('%b %d, %Y')
    
    return render_template('resident/dashboard.html', 
                          resident=resident,
                          current_cycle=current_cycle,
                          next_run_date=next_run_date)


@app.route('/resident/enroll', methods=['GET', 'POST'])
def resident_enroll():
    # Get resident from session or default to first resident
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        dob = request.form.get('dob', '').strip()
        address = request.form.get('address', '').strip()
        last4_ssn = request.form.get('last4_ssn', '').strip()
        
        # Validate against resident record
        if (name.lower() == resident['name'].lower() and
            dob == resident['dob'] and
            address.lower() == resident['address'].lower() and
            last4_ssn == resident['last4_ssn']):
            
            # Match successful - enroll resident
            resident['enrolled'] = True
            resident['enrollment_status'] = 'enrolled'
            resident['tradeline_created'] = True
            resident['enrollment_history'].append({
                'action': 'enrolled',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            flash('Enrollment successful! Your rent payments will now be reported.', 'success')
            return redirect(url_for('resident_enroll_success'))
        else:
            # Mismatch
            flash('We couldn\'t match your information. Please verify and try again or contact support.', 'danger')
            return render_template('resident/enroll.html', 
                                   resident=resident, 
                                   show_form=True,
                                   form_data={
                                       'name': name,
                                       'dob': dob,
                                       'address': address,
                                       'last4_ssn': last4_ssn
                                   })
    
    return render_template('resident/enroll.html', resident=resident, show_form=False)


@app.route('/resident/enroll/success')
def resident_enroll_success():
    return render_template('resident/enroll_success.html')


@app.route('/resident/rent-reporting')
@require_resident
def resident_rent_reporting():
    resident_id = session.get('resident_id')
    resident = get_resident_by_id(resident_id)
    return render_template('resident/rent_reporting.html', resident=resident)


@app.route('/resident/settings')
@require_resident
def resident_settings():
    resident_id = session.get('resident_id')
    resident = get_resident_by_id(resident_id)
    return render_template('resident/settings.html', resident=resident)


@app.route('/resident/profile', methods=['GET', 'POST'])
@require_resident
def resident_profile():
    resident_id = session.get('resident_id')
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        resident['name'] = request.form.get('name', resident['name'])
        resident['dob'] = request.form.get('dob', resident['dob'])
        resident['address'] = request.form.get('address', resident['address'])
        resident['last4_ssn'] = request.form.get('last4_ssn', resident['last4_ssn'])
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('resident_rent_reporting'))
    
    return render_template('resident/profile.html', resident=resident)


@app.route('/resident/opt-out', methods=['GET', 'POST'])
@require_resident
def resident_opt_out():
    resident_id = session.get('resident_id')
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        resident['enrolled'] = False
        resident['enrollment_status'] = 'not enrolled'
        resident['enrollment_history'].append({
            'action': 'revoked consent',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        flash('You have successfully opted out. Future rent payments will not be reported.', 'info')
        return redirect(url_for('resident_rent_reporting'))
    
    return render_template('resident/opt_out.html', resident=resident)


# ============= ADMIN ROUTES =============

@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    data_source = request.args.get('data_source', 'credhub')  # Default to 'credhub', also supports 'test', 'sharepoint'
    
    # Load data based on selected source
    if data_source == 'sharepoint':
        # Load from SharePoint List (Credit Boost - Tenants)
        source_residents = load_residents_from_sharepoint_list()
        if not source_residents:
            flash('Failed to load SharePoint data. Falling back to test data.', 'warning')
            source_residents = residents
    elif data_source == 'credhub':
        # Load from CredHub SharePoint Lists
        source_residents = load_residents_from_credhub_lists()
        if not source_residents:
            flash('Failed to load CredHub data. Falling back to test data.', 'warning')
            source_residents = residents
    else:
        # Use test data
        source_residents = residents
    
    # Calculate statistics from resident data
    total_residents = len(source_residents)
    enrolled_residents = [r for r in source_residents if r.get('enrolled', False)]
    
    # Active leases - residents with active status
    active_leases = [r for r in source_residents if r.get('resident_status', '').lower() in ['active', 'current', ''] or r.get('enrollment_status') == 'enrolled']
    
    # Reporting this cycle - enrolled residents who are set to report
    reporting_this_cycle = [r for r in source_residents if r.get('enrolled', False) and r.get('tradeline_created', False)]
    
    # Account status breakdowns
    current_accounts = [r for r in source_residents if r.get('account_status', '') == 'Current']
    
    # Delinquent 30-89 days (early stage)
    delinquent_30_89 = [r for r in source_residents if r.get('days_late', 0) >= 30 and r.get('days_late', 0) < 90]
    
    # Severely delinquent 90+ days
    delinquent_90_plus = [r for r in source_residents if r.get('days_late', 0) >= 90]
    
    # Calculate total outstanding balance
    total_outstanding = sum(r.get('total_balance', 0) if r.get('total_balance', 0) > 0 else r.get('amount_past_due', 0) for r in source_residents)
    
    # Calculate average days late (only for delinquent accounts)
    delinquent_with_days = [r.get('days_late', 0) for r in source_residents if r.get('days_late', 0) > 0]
    avg_days_late = sum(delinquent_with_days) / len(delinquent_with_days) if delinquent_with_days else 0
    
    # Monthly revenue potential
    total_monthly_revenue = sum(r.get('scheduled_monthly_payment', 0) for r in source_residents)
    
    # Total last payment amounts
    total_last_payments = sum(r.get('last_payment_amount', 0) for r in source_residents)
    
    # Collection rate - calculate based on expected vs collected
    expected_revenue = total_monthly_revenue
    collection_rate = (total_last_payments / expected_revenue * 100) if expected_revenue > 0 else 0
    
    # Aging bucket details
    aged_30_59_residents = [r for r in source_residents if r.get('aged_30_59', 0) > 0 or (r.get('days_late', 0) >= 30 and r.get('days_late', 0) < 60)]
    aged_30_59_amount = sum(r.get('aged_30_59', 0) if r.get('aged_30_59', 0) > 0 else r.get('amount_past_due', 0) for r in aged_30_59_residents)
    
    aged_60_89_residents = [r for r in source_residents if r.get('aged_60_89', 0) > 0 or (r.get('days_late', 0) >= 60 and r.get('days_late', 0) < 90)]
    aged_60_89_amount = sum(r.get('aged_60_89', 0) if r.get('aged_60_89', 0) > 0 else r.get('amount_past_due', 0) for r in aged_60_89_residents)
    
    aged_90_plus_residents = [r for r in source_residents if r.get('aged_90_plus', 0) > 0 or r.get('days_late', 0) >= 90]
    aged_90_plus_amount = sum(r.get('aged_90_plus', 0) if r.get('aged_90_plus', 0) > 0 else r.get('amount_past_due', 0) for r in aged_90_plus_residents)
    
    stats = {
        'total_residents': total_residents,
        'enrolled_count': len(enrolled_residents),
        'active_leases': len(active_leases),
        'reporting_this_cycle': len(reporting_this_cycle),
        'current_accounts': len(current_accounts),
        'delinquent_30_89': len(delinquent_30_89),
        'delinquent_90_plus': len(delinquent_90_plus),
        'total_outstanding': total_outstanding,
        'avg_days_late': round(avg_days_late, 1),
        'total_monthly_revenue': total_monthly_revenue,
        'total_last_payments': total_last_payments,
        'collection_rate': round(collection_rate, 1),
        # Aging details
        'aged_30_59_count': len(aged_30_59_residents),
        'aged_30_59_amount': aged_30_59_amount,
        'aged_60_89_count': len(aged_60_89_residents),
        'aged_60_89_amount': aged_60_89_amount,
        'aged_90_plus_count': len(aged_90_plus_residents),
        'aged_90_plus_amount': aged_90_plus_amount,
    }
    return render_template('admin/dashboard.html', residents=source_residents, stats=stats, data_source=data_source)


@app.route('/admin/rent-reporting')
@require_admin
def admin_rent_reporting():
    search_query = request.args.get('search', '').lower()
    data_source = request.args.get('data_source', 'test')  # 'test', 'sharepoint', or 'credhub'
    
    # Load data based on selected source
    if data_source == 'sharepoint':
        # Load from SharePoint List (Credit Boost - Tenants)
        source_residents = load_residents_from_sharepoint_list()
        if not source_residents:
            flash('Failed to load SharePoint data. Falling back to test data.', 'warning')
            source_residents = residents
    elif data_source == 'credhub':
        # Load from CredHub SharePoint Lists
        source_residents = load_residents_from_credhub_lists()
        if not source_residents:
            flash('Failed to load CredHub data. Falling back to test data.', 'warning')
            source_residents = residents
    else:
        # Use test data
        source_residents = residents
    
    filtered_residents = source_residents
    
    # Filter by search query (searches name, property, and unit)
    if search_query:
        filtered_residents = [
            r for r in filtered_residents 
            if search_query in r['name'].lower() or 
               search_query in r.get('property', '').lower() or 
               search_query in r.get('unit', '').lower()
        ]
    
    # Add last reported month to each resident
    residents_with_info = []
    for r in filtered_residents:
        resident_copy = r.copy()
        resident_copy['last_reported'] = get_last_reported_month(r)
        residents_with_info.append(resident_copy)
    
    # Calculate current reporting cycle (current month)
    current_date = datetime.now()
    current_cycle = current_date.strftime('%b %Y')
    
    # Calculate next reporting run (last day of current month)
    from calendar import monthrange
    last_day = monthrange(current_date.year, current_date.month)[1]
    next_run_date = current_date.replace(day=last_day).strftime('%b %d, %Y')
    
    return render_template('admin/rent_reporting.html', 
                          residents=residents_with_info, 
                          current_cycle=current_cycle,
                          next_run_date=next_run_date,
                          data_source=data_source)


@app.route('/admin/resident/<int:resident_id>')
@require_admin
def admin_resident_detail(resident_id):
    data_source = request.args.get('data_source', 'test')  # 'test', 'sharepoint', or 'credhub'
    
    # Load data based on selected source
    if data_source == 'sharepoint':
        # Load from SharePoint List (Credit Boost - Tenants)
        source_residents = load_residents_from_sharepoint_list()
        if not source_residents:
            flash('Failed to load SharePoint data. Falling back to test data.', 'warning')
            source_residents = residents
    elif data_source == 'credhub':
        # Load from CredHub SharePoint Lists
        source_residents = load_residents_from_credhub_lists()
        if not source_residents:
            flash('Failed to load CredHub data. Falling back to test data.', 'warning')
            source_residents = residents
    else:
        # Use test data
        source_residents = residents
    
    # Find the specific resident
    resident = None
    for r in source_residents:
        if r['id'] == resident_id:
            resident = r
            break
    
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting', data_source=data_source))
    
    return render_template('admin/resident_detail.html', resident=resident, data_source=data_source)


@app.route('/admin/resident/<int:resident_id>/data-mismatch', methods=['GET', 'POST'])
@require_admin
def admin_data_mismatch(resident_id):
    resident = get_resident_by_id(resident_id)
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'fix':
            flash('Data has been corrected successfully.', 'success')
        elif action == 'notify':
            flash('Resident has been notified to update their information.', 'info')
        elif action == 'escalate':
            flash('Issue has been escalated to support team.', 'warning')
        
        return redirect(url_for('admin_resident_detail', resident_id=resident_id))
    
    # Simulate mismatch data
    mismatch_data = {
        'ssn_bureau': '****1111',
        'ssn_system': f"****{resident['last4_ssn']}",
        'name_bureau': resident['name'].upper(),
        'name_system': resident['name'],
        'dob_bureau': resident['dob'],
        'dob_system': resident['dob']
    }
    
    return render_template('admin/data_mismatch.html', 
                          resident=resident, 
                          mismatch_data=mismatch_data)


@app.route('/admin/resident/<int:resident_id>/payment-issue', methods=['GET', 'POST'])
@require_admin
def admin_payment_issue(resident_id):
    resident = get_resident_by_id(resident_id)
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        month = request.form.get('month')
        new_status = request.form.get('new_status')
        
        if action == 'change_status' and month and new_status:
            # Find and update payment
            for payment in resident['payments']:
                if payment['month'] == month:
                    payment['status'] = new_status
                    flash(f'Payment status for {month} updated to {new_status}.', 'success')
                    break
        elif action == 'confirm':
            flash('Payment status confirmed.', 'success')
        
        return redirect(url_for('admin_payment_issue', resident_id=resident_id))
    
    return render_template('admin/payment_issue.html', resident=resident)


@app.route('/admin/reporting-runs')
@require_admin
def admin_reporting_runs():
    runs = [
        {
            'id': 'RUN-2026-001',
            'date': '2026-01-20 14:30:00',
            'type': 'Monthly Full',
            'period': 'January 2026',
            'accounts': 3,
            'status': 'Completed',
            'file': 'metro2_jan2026.dat'
        },
        {
            'id': 'RUN-2025-012',
            'date': '2025-12-20 15:15:00',
            'type': 'Monthly Full',
            'period': 'December 2025',
            'accounts': 3,
            'status': 'Completed',
            'file': 'metro2_dec2025.dat'
        },
        {
            'id': 'RUN-2025-011',
            'date': '2025-11-22 10:45:00',
            'type': 'Correction',
            'period': 'November 2025',
            'accounts': 1,
            'status': 'Completed',
            'file': 'metro2_nov2025_corr.dat'
        },
        {
            'id': 'RUN-2025-010',
            'date': '2025-11-20 14:00:00',
            'type': 'Monthly Full',
            'period': 'November 2025',
            'accounts': 3,
            'status': 'Failed',
            'file': None
        },
        {
            'id': 'RUN-2025-009',
            'date': '2025-10-20 13:30:00',
            'type': 'Monthly Full',
            'period': 'October 2025',
            'accounts': 2,
            'status': 'Completed',
            'file': 'metro2_oct2025.dat'
        }
    ]
    successful_runs = len([r for r in runs if r['status'] == 'Completed'])
    failed_runs = len([r for r in runs if r['status'] == 'Failed'])
    total_accounts = sum(r['accounts'] for r in runs if r['status'] == 'Completed')
    return render_template('admin/reporting_runs.html',
                          runs=runs,
                          successful_runs=successful_runs,
                          failed_runs=failed_runs,
                          total_accounts=total_accounts)

@app.route('/admin/disputes')
@require_admin
def admin_disputes():
    import random
    from datetime import timedelta
    
    # Generate realistic disputes with real residents and dynamic due dates
    current_date = datetime.now()
    disputes = []
    
    # Create 15 sample disputes (only Open and In Progress)
    dispute_types = ['Data Mismatch', 'Payment Error', 'Identity Dispute', 'Incorrect Amount', 'Late Payment Dispute']
    statuses = ['Open', 'Open', 'Open', 'In Progress', 'In Progress']
    
    for i in range(15):
        # Random case ID
        case_id = f"DSP-{random.randint(1000, 9999)}"
        
        # Assign a random resident
        resident = random.choice(residents)
        
        # Random date filed (between 5 and 60 days ago)
        days_ago = random.randint(5, 60)
        date_filed = (current_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        # Random due date (between 1 and 30 days from today)
        days_until_due = random.randint(1, 30)
        due_date = (current_date + timedelta(days=days_until_due)).strftime('%Y-%m-%d')
        
        # Calculate priority based on days remaining (changed labels)
        if days_until_due >= 20:
            priority = 'Low'  # was Medium
        elif days_until_due >= 10:
            priority = 'Medium'  # was High
        else:
            priority = 'High'  # was Critical
        
        # Random status (no resolved)
        status = random.choice(statuses)
        
        disputes.append({
            'id': case_id,
            'date_filed': date_filed,
            'due_date': due_date,
            'days_until_due': days_until_due,
            'resident': f"{resident.get('name')} - Unit {resident.get('unit')}",
            'resident_id': resident.get('id'),
            'type': random.choice(dispute_types),
            'priority': priority,
            'status': status,
            'details': f"Dispute regarding {random.choice(['rent amount', 'payment date', 'account information', 'reporting accuracy'])}"
        })
    
    # Sort by priority (High first, then Medium, Low) and then by due date
    priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
    disputes.sort(key=lambda x: (priority_order.get(x['priority'], 99), x['due_date']))
    
    open_disputes = len([d for d in disputes if d['status'] == 'Open'])
    in_progress_disputes = len([d for d in disputes if d['status'] == 'In Progress'])
    resolved_disputes = 0  # No resolved disputes
    
    return render_template('admin/disputes.html',
                          disputes=disputes,
                          open_disputes=open_disputes,
                          in_progress_disputes=in_progress_disputes,
                          resolved_disputes=resolved_disputes)

@app.route('/admin/audit-logs')
@require_admin
def admin_audit_logs():
    audit_logs = [
        {'id': 1, 'timestamp': '2026-01-10 10:00:00', 'user': 'admin', 'action': 'Viewed resident PII', 'details': 'Jane Doe'},
        {'id': 2, 'timestamp': '2026-01-11 14:30:00', 'user': 'admin', 'action': 'Exported report', 'details': 'Monthly Metro2'},
        {'id': 3, 'timestamp': '2026-01-12 09:15:00', 'user': 'admin', 'action': 'Resolved dispute', 'details': 'D-001'}
    ]
    return render_template('admin/audit_logs.html', audit_logs=audit_logs)

# Excel Export Routes
@app.route('/admin/export/residents', methods=['GET', 'POST'])
@require_admin
def export_residents():
    """Export resident list to Excel"""
    if request.method == 'POST':
        # Get filtered resident IDs from POST data
        import json
        resident_ids_json = request.form.get('resident_ids', '[]')
        resident_ids = json.loads(resident_ids_json)
        
        # Convert to integers
        resident_ids = [int(id) for id in resident_ids]
        
        # Filter residents by IDs
        filtered_residents = [r for r in residents if r.get('id') in resident_ids]
    else:
        # No filter - export all enrolled residents
        filtered_residents = [r for r in residents if r.get('enrollment_status', '').lower() == 'enrolled' or r.get('enrolled') == True]
    
    excel_file = create_resident_list_export(filtered_residents)
    filename = f"residents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/reporting-runs')
@require_admin
def export_reporting_runs():
    """Export reporting runs to Excel"""
    # Get the same data as the reporting runs page
    runs = [
        {'id': 'RUN-2026-001', 'date': '2026-02-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 147, 'success_rate': '99.3%', 'notes': 'Successfully processed'},
        {'id': 'RUN-2026-002', 'date': '2026-01-15', 'type': 'Supplemental', 'status': 'Completed', 'records': 23, 'success_rate': '100%', 'notes': 'New enrollments'},
        {'id': 'RUN-2026-003', 'date': '2026-01-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 145, 'success_rate': '98.6%', 'notes': '2 payment disputes pending'},
        {'id': 'RUN-2025-012', 'date': '2025-12-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 142, 'success_rate': '99.3%', 'notes': 'Year-end reporting'},
    ]
    excel_file = create_reporting_runs_export(runs)
    filename = f"reporting_runs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/disputes')
@require_admin
def export_disputes():
    """Export disputes to Excel"""
    disputes = [
        {'id': 'D-001', 'date': '2026-02-03', 'resident': 'John Smith - Unit 301', 'issue': 'Incorrect rent amount', 'status': 'Open', 'priority': 'High', 'details': 'Resident claims reported amount is $50 higher than actual rent'},
        {'id': 'D-002', 'date': '2026-01-28', 'resident': 'Sarah Johnson - Unit 205', 'issue': 'Late payment dispute', 'status': 'In Progress', 'priority': 'Medium', 'details': 'Payment was made on time but not processed until the 6th'},
        {'id': 'D-003', 'date': '2026-01-15', 'resident': 'Mike Davis - Unit 102', 'issue': 'Payment not reported', 'status': 'Resolved', 'priority': 'High', 'details': 'December payment was not included in monthly report. Added to supplemental file.'},
    ]
    excel_file = create_disputes_export(disputes)
    filename = f"disputes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/audit-logs')
@require_admin
def export_audit_logs():
    """Export audit logs to Excel"""
    audit_logs = [
        {'id': 1, 'timestamp': '2026-01-10 10:00:00', 'user': 'admin', 'action': 'Viewed resident PII', 'details': 'Jane Doe'},
        {'id': 2, 'timestamp': '2026-01-11 14:30:00', 'user': 'admin', 'action': 'Exported report', 'details': 'Monthly Metro2'},
        {'id': 3, 'timestamp': '2026-01-12 09:15:00', 'user': 'admin', 'action': 'Resolved dispute', 'details': 'D-001'}
    ]
    excel_file = create_audit_logs_export(audit_logs)
    filename = f"audit_logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    # Get configuration from environment variables
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

