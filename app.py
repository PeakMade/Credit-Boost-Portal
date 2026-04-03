from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import HTTPException
from datetime import datetime
import json
import base64
import os
import logging
import sys
from dotenv import load_dotenv
from utils.data_loader import load_residents_from_excel
from utils.sharepoint_data_loader import load_residents_from_sharepoint_list, load_residents_from_credhub_lists
from utils.excel_export import (create_resident_list_export, create_reporting_runs_export,
                                create_disputes_export, create_audit_logs_export)
from utils.entrata_api import get_entrata_client
from utils.sharepoint_verification import verify_resident_sharepoint
from utils.entra_token_validation import require_bearer_token
from utils.custom_extension_responses import (
    build_continue_response,
    build_validation_error_response,
    build_block_page_response,
    parse_custom_extension_request
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
        
        # Look for email claim (varies by provider)
        for claim in claims.get('claims', []):
            if claim.get('typ') in ['emails', 'email', 'preferred_username']:
                user_email = claim.get('val')
            if claim.get('typ') == 'name':
                user_name = claim.get('val')
        
        # Fallback to simple headers if claims parsing fails
        if not user_email:
            user_email = request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME')
        
        return {
            'email': user_email,
            'name': user_name or user_email,
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
        
        # Skip for static files
        if request.path.startswith('/static/'):
            return
        
        # Skip if session is already set (performance optimization)
        if 'user_email' in session and 'role' in session:
            return
        
        # Get Easy Auth claims
        claims = get_easy_auth_claims()
        
        if not claims:
            # No authentication - Easy Auth should have caught this
            # This might happen in local dev without Easy Auth
            if app.debug:
                logger.warning("⚠️ No Easy Auth claims found - using fallback for local dev")
            return
        
        user_email = claims.get('email')
        if not user_email:
            logger.error("❌ Easy Auth claims present but no email found")
            return
        
        # Set session data (store only serializable data)
        session['user_email'] = user_email
        session['user_name'] = claims.get('name', user_email)
        session['identity_provider'] = claims.get('identity_provider', 'unknown')
        
        # Determine role based on email/resident lookup
        # Check if admin via SharePoint admin list
        from utils.sharepoint_verification import check_admin_authorization
        if check_admin_authorization(user_email):
            session['role'] = 'admin'
            logger.info(f"✅ Easy Auth: Admin user {user_email}")
            return
        
        # Hardcoded test users
        if user_email.lower() == 'jbatson444@gmail.com':
            session['role'] = 'resident'
            session['resident_id'] = 1  # Alexander Kelly
            logger.info(f"✅ Easy Auth: Test resident user {user_email} mapped to resident ID 1 (Alexander Kelly)")
            return
        
        if user_email.lower() == 'jeffeckard100@gmail.com':
            session['role'] = 'resident'
            session['resident_id'] = 2  # John Smith
            logger.info(f"✅ Easy Auth: Test resident user {user_email} mapped to resident ID 2 (John Smith)")
            return
        
        # Check if resident exists in data
        for resident in residents:
            if resident.get('email', '').lower() == user_email.lower():
                session['role'] = 'resident'
                session['resident_id'] = resident['id']
                logger.info(f"✅ Easy Auth: Resident user {user_email} (ID: {resident['id']})")
                return
        
        # User authenticated but not in our system
        session['role'] = 'unknown'
        logger.warning(f"⚠️ Easy Auth: Authenticated user {user_email} not found in resident/admin data")
    
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
    
    This endpoint is invoked during the OnAttributeCollectionSubmit event.
    It validates resident data against our business system before allowing account creation.
    
    Authentication:
        - Bearer token (OAuth 2.0 client credentials)
        - Token validated via @require_bearer_token decorator
    
    Request payload:
        Custom authentication extension format with type, source, and data containing:
        - attributes: user-submitted sign-up data (email, givenName, surname, custom fields)
        - tenantId, authenticationEventListenerId, customAuthenticationExtensionId
    
    Response:
        - ContinueWithDefaultBehavior: Allow sign-up (verification passed)
        - ShowValidationError: Display validation errors (verification failed)
        - ShowBlockPage: Hard block (service unavailable)
    
    Note:
        This endpoint is isolated from the rest of the app's authentication flow.
        It does not depend on Flask sessions, Easy Auth headers, or browser cookies.
    """
    logger.info("="*60)
    logger.info("🔐 Custom authentication extension endpoint called")
    logger.info("="*60)
    
    try:
        # Parse the custom extension request payload
        request_data = request.get_json()
        
        if not request_data:
            logger.error("❌ Empty request body")
            return jsonify(build_block_page_response(
                "Service temporarily unavailable. Please try again later."
            )), 200
        
        # Log the event type for debugging (safely)
        event_type = request_data.get('type', 'unknown')
        logger.info(f"📋 Event type: {event_type}")
        
        # Parse attributes from the custom extension payload
        parsed_attrs = parse_custom_extension_request(request_data)
        
        if parsed_attrs is None:
            logger.error("❌ Failed to parse custom extension request")
            return jsonify(build_block_page_response(
                "Service temporarily unavailable. Please try again later."
            )), 200
        
        # Extract user-submitted data
        email = parsed_attrs.get('email', '')
        first_name = parsed_attrs.get('given_name', '')
        last_name = parsed_attrs.get('surname', '')
        date_of_birth = parsed_attrs.get('date_of_birth', '')
        
        logger.info(f"🔍 Verifying resident sign-up: {email} ({first_name} {last_name})")
        
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
            return jsonify(build_validation_error_response(
                f"Please provide all required information: {', '.join(missing_fields)}."
            )), 200
        
        # Determine verification method: SharePoint (testing) or Entrata (production)
        use_sharepoint = os.environ.get('USE_SHAREPOINT_VERIFICATION', 'true').lower() == 'true'
        
        if use_sharepoint:
            logger.info("📊 Using SharePoint for verification (test mode)")
            verification_result = verify_resident_sharepoint(
                email=email,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth
            )
        else:
            logger.info("🏢 Using Entrata API for verification (production mode)")
            entrata_client = get_entrata_client()
            verification_result = entrata_client.verify_resident(
                email=email,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth
            )
        
        # Process verification result
        if verification_result['verified']:
            # Resident verified - allow account creation
            logger.info(f"✅ Resident verified for sign-up: {email}")
            logger.info(f"Action: ContinueWithDefaultBehavior")
            return jsonify(build_continue_response()), 200
        else:
            # Verification failed - show validation error
            error_message = verification_result.get('message', 'The data you provided could not be verified.')
            logger.warning(f"❌ Resident verification failed: {email}")
            logger.info(f"Action: ShowValidationError")
            
            # Return validation error with attribute-specific errors
            # Map the error to the email field as that's the primary identifier
            return jsonify(build_validation_error_response(
                "The data you provided could not be verified. Please contact property management to enroll in the Credit Boost Program or verify your information is correct.",
                attribute_errors={
                    "email": "Unable to verify your information in our system."
                }
            )), 200
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ Unexpected error in verification endpoint: {e}", exc_info=True)
        return jsonify(build_block_page_response(
            "Service temporarily unavailable. Please try again later."
        )), 200


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
    Diagnostic endpoint to inspect Easy Auth state.
    Remove or secure this in production!
    """
    try:
        claims = get_easy_auth_claims()
        
        return {
            'easy_auth_claims': claims,
            'session_data': {
                'role': session.get('role'),
                'user_email': session.get('user_email'),
                'resident_id': session.get('resident_id')
            },
            'easy_auth_headers': {
                'X-MS-CLIENT-PRINCIPAL': request.headers.get('X-MS-CLIENT-PRINCIPAL', 'Not present')[:100] if request.headers.get('X-MS-CLIENT-PRINCIPAL') else 'Not present',
                'X-MS-CLIENT-PRINCIPAL-NAME': request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'Not present'),
                'X-MS-CLIENT-PRINCIPAL-ID': request.headers.get('X-MS-CLIENT-PRINCIPAL-ID', 'Not present'),
                'X-MS-CLIENT-PRINCIPAL-IDP': request.headers.get('X-MS-CLIENT-PRINCIPAL-IDP', 'Not present')
            },
            'request_path': request.path,
            'debug_mode': app.debug,
            'residents_loaded': len(get_residents()) if _residents_cache is not None else 0,
            'residents_cache_initialized': _residents_cache is not None
        }, 200
    except Exception as e:
        logger.error(f"❌ Error in debug-auth route: {str(e)}", exc_info=True)
        return {
            'error': str(e),
            'status': 'error',
            'traceback': str(e)
        }, 500


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
        
        if claims and 'role' in session:
            # User is authenticated, redirect to appropriate dashboard
            role = session.get('role')
            if role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'resident':
                return redirect(url_for('resident_dashboard'))
            elif role == 'unknown':
                return render_template('error.html', 
                                     message='Your account is authenticated but not authorized to access this application.',
                                     details=f'Email: {claims.get("email", "Unknown")}')
        
        # Show landing page with login options
        return render_template('landing.html')
        
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
        # Check if email matches any resident in the data
        resident_found = None
        for resident in residents:
            if resident.get('email', '').lower() == email.lower():
                resident_found = resident
                break
        
        if resident_found:
            session['role'] = 'resident'
            session['user_email'] = email
            session['resident_id'] = resident_found['id']
            return redirect(url_for('resident_dashboard'))
        else:
            return render_template('landing.html', error='Email not found')
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
    session.clear()
    logger.info(f"User logged out: {session.get('user_email', 'unknown')}")
    
    # Easy Auth logout endpoint
    # This will clear the Easy Auth session and redirect to post-logout URL
    logout_url = '/.auth/logout'
    
    # Optional: specify post-logout redirect (uncomment to use)
    # logout_url = '/.auth/logout?post_logout_redirect_uri=https://creditboostportal-hde4crgcc2hyajh4.eastus-01.azurewebsites.net'
    
    return redirect(logout_url)


# ============= RESIDENT ROUTES =============

@app.route('/resident/dashboard')
def resident_dashboard():
    # Get resident from session or default to first resident
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
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
def resident_rent_reporting():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    return render_template('resident/rent_reporting.html', resident=resident)


@app.route('/resident/settings')
def resident_settings():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    return render_template('resident/settings.html', resident=resident)


@app.route('/resident/profile', methods=['GET', 'POST'])
def resident_profile():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
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
def resident_opt_out():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
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
def admin_audit_logs():
    audit_logs = [
        {'id': 1, 'timestamp': '2026-01-10 10:00:00', 'user': 'admin', 'action': 'Viewed resident PII', 'details': 'Jane Doe'},
        {'id': 2, 'timestamp': '2026-01-11 14:30:00', 'user': 'admin', 'action': 'Exported report', 'details': 'Monthly Metro2'},
        {'id': 3, 'timestamp': '2026-01-12 09:15:00', 'user': 'admin', 'action': 'Resolved dispute', 'details': 'D-001'}
    ]
    return render_template('admin/audit_logs.html', audit_logs=audit_logs)

# Excel Export Routes
@app.route('/admin/export/residents', methods=['GET', 'POST'])
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

