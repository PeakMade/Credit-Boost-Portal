# Custom Authentication Extension Migration Guide

This document explains the migration from **API Connectors** to **Custom Authentication Extensions** for resident verification during sign-up.

## What Changed

### Old Architecture (API Connector)
- ❌ Simple API key authentication (`X-API-Key` header)
- ❌ Basic JSON request/response
- ❌ Limited to simple Continue/Block actions
- ❌ Deprecated by Microsoft

### New Architecture (Custom Authentication Extension)
- ✅ OAuth 2.0 bearer token authentication
- ✅ Structured event payload with metadata
- ✅ Rich response options (validation errors, attribute modification)
- ✅ Modern, supported approach
- ✅ Event-driven architecture (OnAttributeCollectionSubmit)

---

## Implementation Summary

### New Components

1. **Bearer Token Validation** ([utils/entra_token_validation.py](utils/entra_token_validation.py))
   - Validates Microsoft Entra-issued OAuth 2.0 tokens
   - Uses JWKS (JSON Web Key Set) for signature verification
   - Validates issuer, audience, expiration, and signature
   - Decorator `@require_bearer_token` for endpoint protection

2. **Custom Extension Response Builders** ([utils/custom_extension_responses.py](utils/custom_extension_responses.py))
   - `build_continue_response()` - Allow sign-up
   - `build_validation_error_response()` - Show field-level errors
   - `build_block_page_response()` - Hard block
   - `parse_custom_extension_request()` - Extract user attributes

3. **Updated API Endpoint** ([app.py](app.py#L346-L496))
   - `/api/verify-resident` now uses bearer token auth
   - Parses custom extension event payload
   - Returns proper response format
   - Isolated from session/cookie-based auth

---

## Required Environment Variables

### Existing (Already Configured)
```env
AZURE_TENANT_ID=ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5
AZURE_CLIENT_ID=b6da2abb-3009-46df-aec9-3d278de59a46
```

### No Longer Needed
```env
# AZURE_API_CONNECTOR_KEY - removed, OAuth 2.0 used instead
```

### Verification Configuration (Already Set)
```env
USE_SHAREPOINT_VERIFICATION=true  # or false for Entrata
```

---

## Azure Configuration Steps

### 1. Create Custom Authentication Extension

1. Navigate to **Azure Portal** → **Microsoft Entra External ID** → **Custom authentication extensions**
2. Click **Create a custom extension**
3. Configure:
   - **Name:** `Verify Resident - Custom Extension`
   - **Endpoint URL:** `https://your-app-name.azurewebsites.net/api/verify-resident`
   - **Target resource:** Select your External ID app registration
   - **Event type:** `OnAttributeCollectionSubmit`

4. **Authentication:**
   - **Type:** OAuth 2.0
   - **Resource:** Your Flask API app registration (the same one receiving the request)
   - Azure will automatically handle token acquisition

5. Click **Create**

### 2. Attach to User Flow

1. Go to **User flows** → Select your External ID sign-up flow
2. Click **Custom authentication extensions** (or **API connectors** section if migrating)
3. Under **On attribute collection submit**, select dropdown:
   - Choose: `Verify Resident - Custom Extension`

4. Click **Save**

### 3. Configure User Attributes

Ensure your user flow collects these attributes:

| Attribute | Type | Required |
|-----------|------|----------|
| Email | Built-in | Yes |
| Given Name | Built-in | Yes |
| Surname | Built-in | Yes |
| Date of Birth | Custom | Yes |

**To add Date of Birth:**
1. **User attributes** → **Add**
2. Name: `DateOfBirth`
3. Data type: `String`
4. Description: `Date of birth for verification`

Add to user flow:
1. **User flows** → Your flow → **User attributes**
2. Check: Email, Given Name, Surname, **DateOfBirth**
3. **Save**

### 4. Grant API Permissions (if needed)

If Azure shows permission errors:

1. **App registrations** → Your Flask API app
2. **API permissions** → **Add a permission**
3. **Microsoft Graph** → **Application permissions**
4. No specific Graph permissions needed for this flow
5. Ensure the custom extension app registration can authenticate to your API

---

## Request/Response Format

### Incoming Request (from Entra)

```json
{
  "type": "microsoft.graph.authenticationEvent.attributeCollectionSubmit",
  "source": "/tenants/<tenant-id>/applications/<app-id>",
  "data": {
    "@odata.type": "microsoft.graph.onAttributeCollectionSubmitCalloutData",
    "tenantId": "<tenant-id>",
    "authenticationEventListenerId": "<listener-id>",
    "customAuthenticationExtensionId": "<extension-id>",
    "userPrincipalName": "user@domain.com",
    "attributes": {
      "email": "resident@example.com",
      "givenName": "John",
      "surname": "Doe",
      "extension_<guid>_DateOfBirth": "1990-01-15"
    }
  }
}
```

### Response - Continue (Allow Sign-Up)

```json
{
  "data": {
    "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
    "actions": [
      {
        "@odata.type": "microsoft.graph.attributeCollectionSubmit.continueWithDefaultBehavior"
      }
    ]
  }
}
```

### Response - Validation Error

```json
{
  "data": {
    "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
    "actions": [
      {
        "@odata.type": "microsoft.graph.attributeCollectionSubmit.showValidationError",
        "message": "The data you provided could not be verified.",
        "attributeErrors": [
          {
            "attribute": "email",
            "message": "Unable to verify your information in our system."
          }
        ]
      }
    ]
  }
}
```

### Response - Block Page

```json
{
  "data": {
    "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
    "actions": [
      {
        "@odata.type": "microsoft.graph.attributeCollectionSubmit.showBlockPage",
        "message": "Service temporarily unavailable. Please try again later."
      }
    ]
  }
}
```

---

## Testing

### 1. Test Bearer Token Validation

```bash
# Should fail with 401 (no token)
curl -X POST https://your-app-name.azurewebsites.net/api/verify-resident \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected:
```json
{
  "error": "unauthorized",
  "error_description": "Bearer token required"
}
```

### 2. Test with Valid Token

You cannot easily generate a valid Entra token manually. Instead:

1. Configure the custom authentication extension in Azure
2. Trigger sign-up flow via the app
3. Monitor Azure App Service logs

### 3. Monitor Logs

Azure Portal → App Service → Log Stream

**Successful verification:**
```
🔐 Custom authentication extension endpoint called
📥 Received custom extension event: microsoft.graph.authenticationEvent.attributeCollectionSubmit
✅ Parsed attributes: email=test@example.com, name=John Doe, dob=***
🔍 Verifying resident sign-up: test@example.com (John Doe)
✅ Resident verified for sign-up: test@example.com
Action: ContinueWithDefaultBehavior
```

**Failed verification:**
```
🔐 Custom authentication extension endpoint called
📥 Received custom extension event: microsoft.graph.authenticationEvent.attributeCollectionSubmit
✅ Parsed attributes: email=invalid@example.com, name=Test User, dob=***
🔍 Verifying resident sign-up: invalid@example.com (Test User)
❌ Resident verification failed: invalid@example.com
Action: ShowValidationError
```

**Token validation failure:**
```
⚠️ Token validation failed
```

---

## Troubleshooting

### "Bearer token required" (401)

**Cause:** Azure is not sending the bearer token

**Fix:**
1. Verify custom authentication extension is configured with OAuth 2.0
2. Ensure target resource is set correctly
3. Check Azure Event Log for authentication extension errors

### "Invalid token" (401)

**Cause:** Token validation failed

**Fix:**
1. Verify `AZURE_TENANT_ID` matches your Entra tenant
2. Verify `AZURE_CLIENT_ID` matches your API app registration
3. Check token issuer and audience in logs
4. Ensure app registration has correct reply URLs

### "Service temporarily unavailable"

**Cause:** Internal error or missing configuration

**Check logs for:**
- `❌ Azure credentials not configured`
- `❌ Failed to parse custom extension request`
- `❌ Unexpected error in verification endpoint`

### Custom attributes not found

**Cause:** Attribute names may be namespaced

**Solution:**
The parser searches for DOB-related keys with flexible matching:
- `extension_<guid>_DateOfBirth`
- `extension_DateOfBirth`
- `DateOfBirth`
- Any key containing "dateofbirth" or "dob" (case-insensitive)

Check logs for: `Found DOB attribute: <actual-key-name>`

---

## Security Notes

### Token Validation

- Tokens are validated using Microsoft's JWKS endpoint
- Signature, expiration, issuer, and audience are all verified
- Invalid tokens are rejected with 401
- No API keys to rotate or manage

### Logging

- Full tokens are never logged
- PII is masked in logs (DOB shows as `***`)
- Attribute names are logged for debugging
- Structured logging with emoji indicators for easy scanning

### Isolation

- Endpoint does not depend on session cookies
- No Flask-Login or Easy Auth headers required
- Completely isolated from admin/resident login flows
- Can be called only by Entra with valid bearer token

---

## Migration Checklist

- [x] Implement bearer token validation
- [x] Create custom extension response builders
- [x] Update `/api/verify-resident` endpoint
- [x] Add PyJWT dependency to requirements.txt
- [x] Remove API key authentication
- [ ] Deploy to Azure App Service
- [ ] Create custom authentication extension in Azure Portal
- [ ] Attach extension to user flow at OnAttributeCollectionSubmit
- [ ] Test sign-up with valid resident data
- [ ] Test sign-up with invalid data
- [ ] Monitor logs for successful flow

---

## References

- [Microsoft Learn: Custom Authentication Extensions](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-custom-extensions)
- [OnAttributeCollectionSubmit Event](https://learn.microsoft.com/en-us/graph/api/resources/onattributecollectionsubmit)
- [Response Actions](https://learn.microsoft.com/en-us/graph/api/resources/attributecollectionsubmit)

---

## Summary

**Before:** Simple API connector with API key
**After:** Enterprise-grade custom authentication extension with OAuth 2.0

**Benefits:**
- ✅ More secure (OAuth 2.0 vs static API key)
- ✅ Richer validation (field-level errors)
- ✅ Better logging and debugging
- ✅ Microsoft-supported modern approach
- ✅ Future-proof for additional features

**No breaking changes to:**
- Admin login flow
- Resident login flow (after account creation)
- Landing page
- Dashboard functionality
- Existing authentication middleware
