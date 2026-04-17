# Azure AD App Roles Authorization Guide

## Overview

This application now uses **Azure AD App Roles** for authorization instead of SharePoint lists. This is more secure, reliable, and follows Azure best practices.

## How It Works

### 1. Authentication Flow
```
User → Easy Auth (Azure AD) → Token with Roles → Flask App → Check 'Admin' role
```

### 2. Authorization Hierarchy
The app checks for admin authorization in this order:
1. **Azure AD App Roles** (PREFERRED) - Checks if token contains `Admin` role
2. **SharePoint Admin List** (FALLBACK) - Queries SharePoint list for admin records
3. **Hardcoded Admin List** (EMERGENCY) - Hardcoded emails for fail-safe access

## Verification Steps

### Step 1: Check Your Current Authentication

Visit these diagnostic endpoints in your deployed app:

**Primary Diagnostic:**
```
https://your-app.azurewebsites.net/debug-auth
```

This will show:
- ✅ Your authentication status
- ✅ Your email and user ID
- ✅ **Azure AD roles assigned to you**
- ✅ Whether `Admin` role is present
- ✅ Current session role

**Azure's Built-in Endpoint:**
```
https://your-app.azurewebsites.net/.auth/me
```

This shows all claims in your token including `roles`.

### Step 2: Interpret the Results

#### ✅ SUCCESS - You Have Admin Role
```json
{
  "azure_ad_roles": {
    "roles_found": ["Admin"],
    "has_admin_role": true,
    "interpretation": "Admin role assigned"
  }
}
```
**Meaning:** You're good! Admin access will work automatically.

#### ⚠️ NO ADMIN ROLE - Only Default Access
```json
{
  "azure_ad_roles": {
    "roles_found": [],
    "has_admin_role": false,
    "interpretation": "No Admin role - only Default Access"
  }
}
```
**Meaning:** The `Admin` role hasn't been assigned to you yet. See Step 3 below.

#### ⚠️ ROLES CLAIM MISSING
```json
{
  "azure_ad_roles": {
    "roles_found": [],
    "role_count": 0
  }
}
```
**Meaning:** Either:
- No app roles are defined in the app registration
- App roles exist but haven't been assigned to any users
- Token doesn't include the roles claim (configuration issue)

## Step 3: Configure Azure AD App Roles

### Part A: Define App Roles in App Registration

1. **Go to Azure Portal** → App Registrations → [Your App]
2. **Click "App roles"** in the left sidebar
3. **Create a new app role:**
   - Display name: `Admin`
   - Allowed member types: `Users/Groups`
   - Value: `Admin` (must match exactly)
   - Description: `Full administrator access to the application`
   - Enable this app role: ☑️ Checked
4. **Click "Apply"**

### Part B: Assign Users to the Admin Role

**Option 1: Via Enterprise Applications (Recommended)**
1. Go to: Azure AD → Enterprise Applications
2. Find your app (search by name or client ID)
3. Click **"Users and groups"** in left sidebar
4. Click **"+ Add user/group"**
5. Select:
   - **Users**: Choose yourself (pbatson@peakmade.com)
   - **Select a role**: Choose **Admin**
6. Click **"Assign"**

**Option 2: Via App Registration (Alternative)**
1. Go to: App Registrations → [Your App]
2. Click **"Owners"** (to manage who can assign roles)
3. Then use Enterprise Applications (Option 1) to assign

### Part C: Verify Role Assignment

1. **Sign out** of your app completely
2. **Clear browser cache/cookies**
3. **Sign in again** 
4. Visit `/debug-auth` endpoint
5. **Verify** you see:
   ```json
   {
     "has_admin_role": true,
     "roles_found": ["Admin"]
   }
   ```

## Step 4: Remove SharePoint Dependency (Optional)

Once Azure AD roles are working, you can optionally remove the SharePoint fallback:

**Edit `app.py`** and change the authorization logic to ONLY check Azure AD roles:

```python
# METHOD 1: Check Azure AD app roles (ONLY METHOD)
user_roles = claims.get('roles', [])
if 'Admin' in user_roles:
    is_admin = True
    logger.info(f"✅ ADMIN AUTHORIZED via Azure AD app role: {user_email}")
# Remove or comment out METHOD 2 (SharePoint fallback)
```

## Troubleshooting

### Issue: "Default Access" shown but no Admin role

**Cause:** User has access to the app but no role assigned.

**Fix:**
1. App roles must be created (Part A above)
2. User must be explicitly assigned to Admin role (Part B above)
3. User must sign out and back in for new token with roles

### Issue: Roles claim is completely missing

**Cause 1:** No app roles defined in the app registration
- **Fix:** Complete Part A above to create the Admin role

**Cause 2:** Token doesn't include roles claim
- **Fix:** In App Registration → Token configuration → Add optional claim:
  - Token type: ID token
  - Claim: `roles`

**Cause 3:** Using the wrong app registration
- **Fix:** Verify Easy Auth is configured with the same app registration where you defined roles

### Issue: Role appears in /.auth/me but not recognized by app

**Cause:** Case sensitivity or spelling mismatch

**Fix:** Role value must be exactly `Admin` (capital A) in both:
- App role definition (Value field)
- Code check: `if 'Admin' in user_roles:`

## Benefits of Azure AD Roles vs SharePoint

| Feature | Azure AD Roles | SharePoint List |
|---------|---------------|-----------------|
| **Security** | Token-based, tamper-proof | API call, can fail |
| **Performance** | Instant (in token) | Network call required |
| **Reliability** | Always available | Depends on SharePoint access |
| **Management** | Azure Portal (centralized) | SharePoint list (scattered) |
| **Audit Trail** | Azure AD logs | Manual tracking |
| **Zero Trust** | ✅ Token validation | ❌ API dependency |

## Code Changes Summary

### What Changed

1. **`get_easy_auth_claims()`** now extracts `roles` claim from token
2. **`setup_session_from_easy_auth_middleware()`** checks Azure AD roles FIRST
3. **`/debug-auth`** endpoint shows role information clearly
4. **`/.auth/me`** endpoint mirrors Azure's authentication info
5. **Fallback chain** ensures access via multiple methods

### Authorization Decision Flow

```
Is 'Admin' in Azure AD roles?
  YES → Grant admin access ✅
  NO ↓
  
Is email in SharePoint admin list?
  YES → Grant admin access ✅
  NO ↓
  
Is email in hardcoded admin list?
  YES → Grant admin access ✅
  NO ↓
  
Check if user has resident record?
  YES → Grant resident access ✅
  NO ↓
  
DENY ACCESS ❌
```

## Testing Checklist

- [ ] App role "Admin" is defined in app registration
- [ ] Your user is assigned to Admin role in Enterprise Applications
- [ ] Sign out and back in to get new token
- [ ] Visit `/debug-auth` and verify `has_admin_role: true`
- [ ] Visit admin dashboard - should work without SharePoint
- [ ] Check logs for: `✅ ADMIN AUTHORIZED via Azure AD app role`
- [ ] Sign in with non-admin user - should be denied or see resident view

## Next Steps

1. ✅ **Test immediately:** Visit `/debug-auth` to see current state
2. ✅ **Configure roles:** Follow Step 3 if roles are missing
3. ✅ **Verify access:** Confirm admin dashboard works
4. ⚠️ **Remove SP fallback:** (Optional) Once working, remove SharePoint dependency
5. 🔒 **Deploy:** Push changes and test in production

---

**Benefits Achieved:**
- ✅ No dependency on SharePoint for auth (faster, more reliable)
- ✅ Role management in one place (Azure AD)
- ✅ Token-based authorization (more secure)
- ✅ Instant role checks (no API calls needed)
- ✅ Comprehensive audit trail via Azure AD

**Created:** 2026-04-17
**Status:** Implemented and ready for testing
