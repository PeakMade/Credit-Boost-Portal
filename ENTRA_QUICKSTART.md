# Entra External ID - Quick Start Guide

This is a condensed guide to get Microsoft Entra External ID authentication running quickly.

## What You Need

1. **Azure account** with permissions to create tenants
2. **5 environment variables** added to your `.env` file
3. **20 minutes** to set up

---

## Quick Setup (5 Steps)

### 1️⃣ Create External ID Tenant (Azure Portal)

```
Azure Portal → Search "Microsoft Entra External ID" 
→ Create tenant → External ID
→ Name: creditboost-students
→ Domain: creditboost.ciamlogin.com
→ Create (wait 5-10 min)
```

### 2️⃣ Register Your App

```
New tenant → App registrations → New registration
→ Name: Credit Boost Portal
→ Redirect URI: http://localhost:5000/auth/callback
→ Register
```

**Save these values:**
- Application (client) ID
- Directory (tenant) ID

**Create secret:**
```
Certificates & secrets → New client secret
→ Copy secret value immediately
```

### 3️⃣ Configure User Flow

```
User flows → New user flow → Sign up and sign in
→ Name: signup_signin
→ Identity providers: ✅ Email signup
→ User attributes: ✅ Email, Given Name, Surname
→ Create
```

### 4️⃣ Update `.env` File

Add these to your `.env`:

```env
# Entra External ID Configuration
ENTRA_CLIENT_ID=your-client-id-from-step-2
ENTRA_CLIENT_SECRET=your-client-secret-from-step-2
ENTRA_TENANT_NAME=creditboost
ENTRA_DOMAIN=creditboost.ciamlogin.com
ENTRA_TENANT_ID=your-tenant-id-from-step-2

# User Flow
ENTRA_SIGNUP_SIGNIN_FLOW=B2C_1_signup_signin

# Redirect URIs
ENTRA_REDIRECT_URI=http://localhost:5000/auth/callback
ENTRA_POST_LOGOUT_REDIRECT_URI=http://localhost:5000/
```

### 5️⃣ Update Your Flask App

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Minimal app.py changes:**

```python
# Add at top
from utils.entra_auth import EntraExternalAuth

# After app = Flask(__name__)
entra_auth = EntraExternalAuth(app)

# Update landing route
@app.route('/login')
def landing():
    entra_signin_url = entra_auth.get_sign_in_url()
    return render_template('landing.html', entra_signin_url=entra_signin_url)

# Add callback route
@app.route('/auth/callback')
def auth_callback():
    auth_code = request.args.get('code')
    if not auth_code:
        flash('Authentication failed', 'danger')
        return redirect(url_for('landing'))
    
    user_info = entra_auth.handle_auth_callback(auth_code)
    if not user_info:
        flash('Failed to authenticate', 'danger')
        return redirect(url_for('landing'))
    
    # Store in session
    session['authenticated'] = True
    session['user_email'] = user_info['email']
    session['user_name'] = user_info['name']
    
    # Check if admin or resident
    if user_info['email'] == 'pbatson@peakmade.com':
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    
    # Find resident by email
    for resident in residents:
        if resident.get('email', '').lower() == user_info['email'].lower():
            session['role'] = 'resident'
            session['resident_id'] = resident['id']
            return redirect(url_for('resident_dashboard'))
    
    # New user - needs profile
    return redirect(url_for('complete_profile'))

# Add logout route
@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect(entra_auth.get_sign_out_url())
```

**Update landing.html template:**

```html
<!-- Add this button in your login card -->
<a href="{{ entra_signin_url }}" class="btn btn-primary btn-lg w-100">
    <i class="bi bi-box-arrow-in-right"></i> Sign In with Microsoft
</a>
```

---

## Testing Locally

**For local testing with HTTPS (required by Entra):**

```bash
# Terminal 1: Run ngrok
ngrok http 5000

# Copy the HTTPS URL (e.g. https://abc123.ngrok.io)
```

**Update Azure Portal:**
```
App registration → Authentication
→ Add redirect URI: https://abc123.ngrok.io/auth/callback
```

**Update .env:**
```env
ENTRA_REDIRECT_URI=https://abc123.ngrok.io/auth/callback
```

**Terminal 2: Run Flask app:**
```bash
python app.py
```

**Test:**
1. Go to `https://abc123.ngrok.io/login`
2. Click "Sign In with Microsoft"
3. Register with test email (e.g., test@gmail.com)
4. Should redirect back to your app

---

## Common Issues

### Issue: "Redirect URI mismatch"
**Solution:** Make sure redirect URI in Azure Portal exactly matches your `.env` file

### Issue: "Invalid authority"
**Solution:** Check that tenant name and domain are correct in `.env`

### Issue: "Unable to get token"
**Solution:** Verify client secret hasn't expired (max 24 months)

### Issue: "HTTP callback not working"
**Solution:** Use ngrok for HTTPS during development

---

## What Students Will See

1. **Login page** with "Sign In with Microsoft" button
2. **Microsoft login screen** (branded with your logo)
3. **Registration form** (first time only)
   - Email, name, password
   - Optional: Google/Facebook sign-in
4. **Redirect back** to your portal
5. **Complete profile** page (if new user)

---

## Production Deployment

When deploying to Azure App Service:

1. **Add App Settings** in Azure Portal (not .env)
2. **Update redirect URI** to production URL
3. **Enable HTTPS only** in App Service
4. **Configure custom domain** (optional)

---

## Key Features You Get

✅ **Any email domain** - @gmail.com, @yahoo.com, @outlook.com, etc.  
✅ **Self-registration** - Students sign up themselves  
✅ **Password reset** - Microsoft handles it  
✅ **Social login** - Google, Facebook (if enabled)  
✅ **MFA support** - Can enable 2-factor auth  
✅ **Secure** - Microsoft-managed security  
✅ **Free** - Up to 50,000 monthly active users  

---

## Files Provided

- ✅ `utils/entra_auth.py` - Ready-to-use authentication module
- ✅ `ENTRA_EXTERNAL_ID_IMPLEMENTATION.md` - Full detailed guide
- ✅ `requirements.txt` - Updated with needed packages

---

## Next Steps

1. Follow the 5 steps above
2. Test locally with ngrok
3. Update your login page UI
4. Deploy to production
5. Update production redirect URIs

---

## Support

For issues:
1. Check Azure Portal → External ID → Sign-in logs
2. Check Flask app console for error messages
3. Verify all environment variables are set
4. Review [ENTRA_EXTERNAL_ID_IMPLEMENTATION.md](ENTRA_EXTERNAL_ID_IMPLEMENTATION.md) for details

---

**Total setup time:** ~20 minutes  
**Monthly cost:** $0 (free tier for <50K users)  
**Maintenance:** Minimal (Microsoft-managed)
