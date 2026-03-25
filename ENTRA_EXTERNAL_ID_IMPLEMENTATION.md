# Microsoft Entra External ID Implementation Guide

## Overview

This guide details how to implement **Microsoft Entra External ID** (formerly Azure AD B2C) for the Credit Boost Portal to support external user authentication for students and residents.

## What is Entra External ID?

Microsoft Entra External ID is a customer identity and access management (CIAM) solution that allows external users to sign in using:
- Social identity providers (Google, Facebook, Microsoft Account)
- Email and password (local accounts)
- Magic links or one-time passwords
- Multi-factor authentication
- Custom branding and user flows

**Perfect for your use case:** Students with external email addresses (@gmail.com, @yahoo.com, etc.) can register and authenticate.

---

## Architecture Overview

```
Student Browser
    ↓
Flask App (Credit Boost Portal)
    ↓
Microsoft Entra External ID Tenant
    ↓
Authentication & User Profile
    ↓
Return to Flask App with Token
    ↓
SharePoint Data Access
```

---

## Prerequisites

1. **Azure Subscription** - Active subscription with appropriate permissions
2. **Python Packages:**
   ```bash
   pip install msal flask-session identity
   ```
3. **Environment Variables:**
   - `ENTRA_CLIENT_ID`
   - `ENTRA_CLIENT_SECRET`
   - `ENTRA_TENANT_ID`
   - `ENTRA_AUTHORITY` (e.g., `https://yourtenantname.ciamlogin.com`)

---

## Step 1: Create Entra External ID Tenant

### In Azure Portal:

1. Navigate to **Microsoft Entra External ID** (search in Azure Portal)
2. Click **Create a tenant** → Select **External ID**
3. Configure:
   - **Tenant name:** `creditboost-students` (or your choice)
   - **Domain name:** `creditboost.ciamlogin.com` (must be unique)
   - **Country/Region:** United States
   - **Data location:** Choose closest to your users
4. Click **Create** (takes 5-10 minutes)

### Key Differences from Regular Entra ID:
- External ID is optimized for customer-facing apps
- Supports self-service registration
- Simplified user flows
- Better branding customization
- Lower cost for external users

---

## Step 2: Register Your Application

1. In your new External ID tenant, go to **App registrations**
2. Click **New registration**
3. Configure:
   - **Name:** `Credit Boost Portal`
   - **Supported account types:** "Accounts in this organizational directory only"
   - **Redirect URI:** 
     - Platform: `Web`
     - URI: `http://localhost:5000/auth/callback` (dev)
     - Add production URL later: `https://yourapp.azurewebsites.net/auth/callback`
4. Click **Register**

### Save These Values:
- **Application (client) ID** → This is `ENTRA_CLIENT_ID`
- **Directory (tenant) ID** → This is `ENTRA_TENANT_ID`

### Create Client Secret:
1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Description: `Flask App Secret`
4. Expires: Choose duration (recommend 24 months)
5. **Copy the secret value immediately** → This is `ENTRA_CLIENT_SECRET`

---

## Step 3: Configure Authentication & User Flows

### Enable Email/Password Authentication:

1. Go to **Authentication methods** (in External ID settings)
2. Enable:
   - ✅ Email with password
   - ✅ Email one-time passcode (optional, for passwordless)
   - ✅ Google (optional, for social login)
   - ✅ Microsoft account (optional)

### Create Sign-up/Sign-in User Flow:

1. Navigate to **User flows**
2. Click **New user flow**
3. Select **Sign up and sign in**
4. Configure:
   - **Name:** `signup_signin` (will become `B2C_1_signup_signin`)
   - **Identity providers:**
     - ✅ Email signup
     - ✅ Google (if configured)
   - **User attributes to collect:**
     - ✅ Email Address (always required)
     - ✅ Given Name
     - ✅ Surname
     - ✅ Display Name
     - 🔧 Custom: Student ID (if needed)
     - 🔧 Custom: Phone Number
   - **Application claims to return:**
     - ✅ Email Addresses
     - ✅ Given Name
     - ✅ Surname
     - ✅ User's Object ID
     - ✅ Display Name
5. Click **Create**

### Customize Branding:

1. Go to **Company branding**
2. Upload:
   - Logo (for login page)
   - Background image
   - Customize colors to match your portal
3. Edit page templates for consistent UX

---

## Step 4: Configure API Permissions

1. In your app registration, go to **API permissions**
2. Add these Microsoft Graph permissions:
   - ✅ `User.Read` (Delegated) - Read user profile
   - ✅ `email` (Delegated)
   - ✅ `openid` (Delegated)
   - ✅ `profile` (Delegated)
3. Click **Grant admin consent**

---

## Step 5: Implement Flask Integration

### Update requirements.txt:

```txt
Flask==3.0.0
msal==1.28.0
flask-session==0.8.0
requests==2.31.0
python-dotenv==1.0.0
```

### Update .env file:

```env
# Existing credentials
AZURE_CLIENT_ID=your-existing-client-id
AZURE_CLIENT_SECRET=your-existing-secret
AZURE_TENANT_ID=your-existing-tenant-id

# NEW: Entra External ID credentials
ENTRA_CLIENT_ID=your-external-id-client-id
ENTRA_CLIENT_SECRET=your-external-id-client-secret
ENTRA_TENANT_NAME=creditboost
ENTRA_DOMAIN=creditboost.ciamlogin.com
ENTRA_AUTHORITY=https://creditboost.ciamlogin.com
ENTRA_TENANT_ID=your-external-id-tenant-id

# User Flow Name
ENTRA_SIGNUP_SIGNIN_FLOW=B2C_1_signup_signin

# Redirect URIs
ENTRA_REDIRECT_URI=http://localhost:5000/auth/callback
ENTRA_POST_LOGOUT_REDIRECT_URI=http://localhost:5000/
```

### Create new file: `utils/entra_auth.py`

```python
import os
import msal
from flask import session, url_for
import requests

class EntraExternalAuth:
    """
    Microsoft Entra External ID authentication handler
    """
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.client_id = os.environ.get('ENTRA_CLIENT_ID')
        self.client_secret = os.environ.get('ENTRA_CLIENT_SECRET')
        self.tenant_name = os.environ.get('ENTRA_TENANT_NAME')
        self.domain = os.environ.get('ENTRA_DOMAIN')
        self.authority = f"https://{self.domain}/{self.tenant_name}.onmicrosoft.com"
        
        # User flow
        self.signup_signin_flow = os.environ.get('ENTRA_SIGNUP_SIGNIN_FLOW', 'B2C_1_signup_signin')
        
        # Redirect URIs
        self.redirect_uri = os.environ.get('ENTRA_REDIRECT_URI', 'http://localhost:5000/auth/callback')
        self.post_logout_redirect = os.environ.get('ENTRA_POST_LOGOUT_REDIRECT_URI', 'http://localhost:5000/')
        
        # Scopes
        self.scope = [
            f"https://{self.domain}/{self.client_id}/access_as_user"
        ]
    
    def get_msal_app(self, flow_name=None):
        """Create MSAL application instance"""
        if not flow_name:
            flow_name = self.signup_signin_flow
        
        authority_url = f"https://{self.domain}/{self.tenant_name}.onmicrosoft.com/{flow_name}"
        
        return msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority_url,
            client_credential=self.client_secret
        )
    
    def get_sign_in_url(self):
        """Generate sign-in authorization URL"""
        msal_app = self.get_msal_app()
        
        auth_url = msal_app.get_authorization_request_url(
            scopes=["openid", "profile", "email"],
            redirect_uri=self.redirect_uri,
            response_type="code"
        )
        
        return auth_url
    
    def handle_auth_callback(self, auth_code):
        """
        Handle the OAuth callback and exchange code for tokens
        
        Args:
            auth_code: Authorization code from redirect
            
        Returns:
            dict: User claims and tokens, or None if failed
        """
        msal_app = self.get_msal_app()
        
        result = msal_app.acquire_token_by_authorization_code(
            auth_code,
            scopes=["openid", "profile", "email"],
            redirect_uri=self.redirect_uri
        )
        
        if "error" in result:
            print(f"Authentication error: {result.get('error_description')}")
            return None
        
        # Extract user claims from ID token
        id_token_claims = result.get('id_token_claims', {})
        
        user_info = {
            'user_id': id_token_claims.get('sub') or id_token_claims.get('oid'),
            'email': id_token_claims.get('emails', [None])[0] or id_token_claims.get('email'),
            'name': id_token_claims.get('name'),
            'given_name': id_token_claims.get('given_name'),
            'family_name': id_token_claims.get('family_name'),
            'access_token': result.get('access_token'),
            'id_token': result.get('id_token'),
            'refresh_token': result.get('refresh_token')
        }
        
        return user_info
    
    def get_sign_out_url(self):
        """Generate sign-out URL"""
        return f"https://{self.domain}/{self.tenant_name}.onmicrosoft.com/{self.signup_signin_flow}/oauth2/v2.0/logout?post_logout_redirect_uri={self.post_logout_redirect}"
    
    def get_user_from_token(self, access_token):
        """
        Get user information from Microsoft Graph (if needed)
        
        Args:
            access_token: Valid access token
            
        Returns:
            dict: User profile information
        """
        graph_url = "https://graph.microsoft.com/v1.0/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(graph_url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        
        return None
```

### Update app.py:

```python
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from utils.entra_auth import EntraExternalAuth
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Entra External ID
entra_auth = EntraExternalAuth(app)

# ... existing imports and setup ...

@app.route('/login')
def landing():
    """Landing page with Entra External ID login option"""
    # Generate Entra sign-in URL
    entra_signin_url = entra_auth.get_sign_in_url()
    return render_template('landing.html', entra_signin_url=entra_signin_url)


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback from Entra External ID"""
    # Get authorization code from query parameters
    auth_code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f'Authentication failed: {error}', 'danger')
        return redirect(url_for('landing'))
    
    if not auth_code:
        flash('No authorization code received', 'danger')
        return redirect(url_for('landing'))
    
    # Exchange code for tokens
    user_info = entra_auth.handle_auth_callback(auth_code)
    
    if not user_info:
        flash('Failed to authenticate. Please try again.', 'danger')
        return redirect(url_for('landing'))
    
    # Store user information in session
    session['user_id'] = user_info['user_id']
    session['user_email'] = user_info['email']
    session['user_name'] = user_info['name']
    session['access_token'] = user_info['access_token']
    session['authenticated'] = True
    
    # Determine user role based on email or database lookup
    # Check if user is admin
    if user_info['email'] in ['pbatson@peakmade.com', 'admin@creditboost.com']:
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    
    # Check if user is a registered resident/student
    resident_found = None
    for resident in residents:
        if resident.get('email', '').lower() == user_info['email'].lower():
            resident_found = resident
            break
    
    if resident_found:
        session['role'] = 'resident'
        session['resident_id'] = resident_found['id']
        return redirect(url_for('resident_dashboard'))
    
    # New user - redirect to enrollment/registration
    flash('Welcome! Please complete your profile to access the portal.', 'info')
    return redirect(url_for('complete_profile'))


@app.route('/auth/logout')
def logout():
    """Logout and clear session"""
    # Clear Flask session
    session.clear()
    
    # Redirect to Entra logout
    logout_url = entra_auth.get_sign_out_url()
    return redirect(logout_url)


@app.route('/complete-profile')
def complete_profile():
    """
    New user profile completion page
    Collect additional information for residents/students
    """
    if not session.get('authenticated'):
        return redirect(url_for('landing'))
    
    return render_template('resident/complete_profile.html', 
                          user_email=session.get('user_email'),
                          user_name=session.get('user_name'))


@app.route('/complete-profile', methods=['POST'])
def submit_profile():
    """Handle new user profile submission"""
    if not session.get('authenticated'):
        return redirect(url_for('landing'))
    
    # Collect form data
    student_id = request.form.get('student_id')
    phone = request.form.get('phone')
    dob = request.form.get('dob')
    property_name = request.form.get('property')
    unit = request.form.get('unit')
    
    # TODO: Create new resident record in SharePoint
    # This would integrate with your SharePoint data loader
    
    # For now, create a temporary resident record
    new_resident = {
        'id': len(residents) + 1,
        'email': session.get('user_email'),
        'name': session.get('user_name'),
        'phone': phone,
        'dob': dob,
        'property': property_name,
        'unit': unit,
        'enrolled': False,
        'enrollment_status': 'pending'
    }
    
    # TODO: Save to database/SharePoint
    # residents.append(new_resident)
    
    session['role'] = 'resident'
    session['resident_id'] = new_resident['id']
    
    flash('Profile created successfully!', 'success')
    return redirect(url_for('resident_dashboard'))


# ... rest of your existing routes ...
```

---

## Step 6: Update Landing Page Template

Update `templates/landing.html`:

```html
{% extends "base.html" %}

{% block title %}Login - Rent Reporting Portal{% endblock %}

{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-5">
        <div class="card shadow">
            <div class="card-header bg-primary text-white text-center">
                <h4 class="mb-0">Rent Reporting Portal</h4>
            </div>
            <div class="card-body p-5">
                <div class="text-center mb-4">
                    <i class="bi bi-shield-lock text-primary" style="font-size: 3rem;"></i>
                    <h5 class="mt-3">Sign In</h5>
                    <p class="text-muted">Choose your sign-in method</p>
                </div>
                
                {% if error %}
                <div class="alert alert-danger" role="alert">
                    <i class="bi bi-exclamation-triangle"></i> {{ error }}
                </div>
                {% endif %}
                
                <!-- OPTION 1: Modern Sign-In with Entra External ID -->
                <div class="card mb-4 border-primary">
                    <div class="card-body text-center">
                        <h6 class="card-title">Students & Residents</h6>
                        <p class="card-text small text-muted">Sign in with your email or social account</p>
                        <a href="{{ entra_signin_url }}" class="btn btn-primary btn-lg w-100">
                            <i class="bi bi-box-arrow-in-right"></i> Sign In with Microsoft
                        </a>
                        <p class="mt-3 mb-0 small text-muted">
                            <i class="bi bi-check-circle text-success"></i> Secure authentication<br>
                            <i class="bi bi-check-circle text-success"></i> Works with any email
                        </p>
                    </div>
                </div>
                
                <div class="text-center mb-3">
                    <small class="text-muted">OR</small>
                </div>
                
                <!-- OPTION 2: Legacy Direct Login (for testing/admin) -->
                <div class="card border-secondary">
                    <div class="card-body">
                        <h6 class="card-title text-center">Direct Login</h6>
                        <form method="POST" action="{{ url_for('login') }}">
                            <div class="mb-3">
                                <label for="email" class="form-label">Email Address</label>
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text"><i class="bi bi-envelope"></i></span>
                                    <input type="email" class="form-control" id="email" name="email" 
                                           placeholder="Enter your email" required>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text"><i class="bi bi-lock"></i></span>
                                    <input type="password" class="form-control" id="password" name="password" 
                                           placeholder="Enter your password" required>
                                </div>
                            </div>
                            <button type="submit" class="btn btn-outline-secondary btn-sm w-100">
                                Legacy Login
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

---

## Step 7: Security Considerations

### Session Management:

```python
# app.py - Add these configurations
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
```

### Token Refresh:

Add token refresh logic in `utils/entra_auth.py`:

```python
def refresh_access_token(self, refresh_token):
    """Refresh expired access token"""
    msal_app = self.get_msal_app()
    
    result = msal_app.acquire_token_by_refresh_token(
        refresh_token,
        scopes=["openid", "profile", "email"]
    )
    
    if "error" in result:
        return None
    
    return result
```

### Middleware for Protected Routes:

```python
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            flash('Please sign in to access this page', 'warning')
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated_function

# Use on routes:
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # ... existing code ...
```

---

## Step 8: Testing

### Local Development:

1. Set up ngrok for HTTPS callback (External ID requires HTTPS):
   ```bash
   ngrok http 5000
   ```

2. Update redirect URI in Azure Portal to ngrok URL:
   ```
   https://abc123.ngrok.io/auth/callback
   ```

3. Update `.env`:
   ```
   ENTRA_REDIRECT_URI=https://abc123.ngrok.io/auth/callback
   ```

4. Run your app:
   ```bash
   python app.py
   ```

5. Test authentication flow:
   - Navigate to login page
   - Click "Sign In with Microsoft"
   - Register with a test email (e.g., @gmail.com)
   - Complete profile
   - Verify session and access

---

## Step 9: Production Deployment

### Azure App Service Configuration:

1. **Add Application Settings** in Azure Portal:
   - `ENTRA_CLIENT_ID`
   - `ENTRA_CLIENT_SECRET`
   - `ENTRA_TENANT_NAME`
   - `ENTRA_DOMAIN`
   - `ENTRA_REDIRECT_URI` → `https://yourapp.azurewebsites.net/auth/callback`

2. **Update App Registration:**
   - Add production redirect URI
   - Update post-logout redirect URI

3. **Enable HTTPS Only** in App Service settings

4. **Configure Custom Domain** (optional):
   - Add custom domain in App Service
   - Configure SSL certificate
   - Update redirect URIs accordingly

---

## Benefits of This Approach

✅ **External User Support:** Students can use any email address  
✅ **Self-Service Registration:** No admin intervention needed  
✅ **Social Login:** Google, Facebook, Microsoft options  
✅ **Secure:** Microsoft-managed authentication  
✅ **Scalable:** Handles thousands of users  
✅ **Compliant:** GDPR, SOC 2, ISO 27001 certified  
✅ **MFA Support:** Built-in multi-factor authentication  
✅ **Password Reset:** Self-service password recovery  
✅ **Customizable:** Full branding control  

---

## Cost Considerations

**Microsoft Entra External ID Pricing (as of 2026):**
- First 50,000 monthly active users (MAUs): **Free**
- Additional MAUs: **$0.00325 per MAU**

For a student portal with 1,000 active users per month: **$0** (within free tier)

---

## Alternative: Simpler Email/Password (without Entra)

If you prefer a simpler approach without Microsoft dependency, you could implement:
- Flask-Login with email/password stored in SharePoint
- Flask-Mail for email verification
- Password hashing with bcrypt

But Entra External ID provides:
- Better security
- Professional user management
- Social login options
- MFA support
- No password management responsibility

---

## Next Steps

1. Create External ID tenant in Azure
2. Register application and configure user flows
3. Install required Python packages
4. Create `utils/entra_auth.py`
5. Update `app.py` with new authentication routes
6. Update landing page template
7. Test locally with ngrok
8. Deploy to production

---

## Support & Resources

- [Microsoft Entra External ID Documentation](https://learn.microsoft.com/en-us/entra/external-id/)
- [MSAL Python Documentation](https://msal-python.readthedocs.io/)
- [Azure AD B2C Samples](https://github.com/Azure-Samples/ms-identity-python-webapp)

---

## Questions?

This implementation provides enterprise-grade authentication for your student-facing portal. Let me know if you need help with any specific step!
