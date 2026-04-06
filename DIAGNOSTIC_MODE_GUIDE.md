# Custom Authentication Extension - Diagnostic Mode

**Status: ACTIVE**  
**Purpose: Isolate External ID custom authentication extension failure**

## What Changed

The `/api/verify-resident` endpoint has been temporarily modified to run in **diagnostic mode**.

### Current Behavior

1. **Token validation**: Still active and logged extensively
2. **Request parsing**: Still active and logged
3. **SharePoint verification**: **BYPASSED**
4. **Entrata API verification**: **BYPASSED**
5. **Resident data validation**: **BYPASSED**
6. **Response**: Hard-coded success (ContinueWithDefaultBehavior)

### Files Modified

- `app.py` - `/api/verify-resident` endpoint
- `utils/entra_token_validation.py` - `require_bearer_token` decorator

## Test Procedure

### 1. Run a Sign-Up Test

1. Navigate to External ID sign-up flow
2. Fill in sign-up form with ANY data:
   - Email: any valid email
   - Name: any name
   - DOB: any date in MM-DD-YYYY format
   - Password: create password
3. Submit the form
4. Observe the result

### 2. Check Azure App Service Logs

Look for these log lines (in order):

#### Token Validation Start
```
🔐 DIAGNOSTIC: Starting bearer token validation
✅ DIAGNOSTIC: Bearer token extracted (length: XXX chars)
🔍 DIAGNOSTIC: Token validation config:
   Expected audience: api://creditboostportal.azurewebsites.net/0bd40a8e-f0df-4e0b-ad88-9eee42e13b1e
   Expected issuer: https://login.microsoftonline.com/e304c237-65be-496e-9d30-ae875f131322/v2.0
```

#### Token Validation Success
```
✅ DIAGNOSTIC: Token validation SUCCEEDED
   Token claims:
   - aud (audience): ...
   - iss (issuer): ...
   - appid: ...
```

#### Endpoint Execution
```
🔐 DIAGNOSTIC: Custom authentication extension endpoint called
Timestamp: ...
Method: POST
Path: /api/verify-resident
```

#### Request Data Received
```
📦 Request payload keys: ['type', 'source', 'data']
📋 Event type: microsoft.graph.authenticationEvent.attributeCollectionSubmit
👤 User data received:
   Email: test@example.com
   Name: John Doe
   DOB: ***
```

#### Verification Bypassed
```
🧪 DIAGNOSTIC MODE: Skipping all verification logic
🧪 SharePoint/Graph API calls: BYPASSED
🧪 Entrata API calls: BYPASSED
🧪 Resident data validation: BYPASSED
🧪 Returning hard-coded SUCCESS response
```

#### Success Response
```
✅ DIAGNOSTIC: Returning ContinueWithDefaultBehavior
📤 Response payload: {...}
⏱️ Total request processing time: 0.XXXs
```

## Interpreting Results

### SUCCESS: User Flow Completes

**What you'll see:**
- Sign-up completes successfully
- User gets confirmation
- All diagnostic logs appear in order

**What this means:**
✅ Extension plumbing works correctly  
✅ Bearer token validation works  
✅ App Service routing works  
✅ CORS configuration works  
✅ Response contract is correct  

**The problem is:** SharePoint/verification logic or performance

**Next steps:**
1. Restore normal verification logic
2. Add detailed logging to SharePoint verification
3. Check SharePoint permissions
4. Check verification list data format
5. Test with real resident data

### FAILURE: Generic Error Still Appears

**What you'll see:**
- Sign-up fails with generic error
- AADSTS or other error codes

**Check logs for:**

#### Scenario A: No logs at all
**Means:** Request never reached Flask
**Next steps:**
- Check custom extension configuration URL
- Check App Service deployment status
- Check if endpoint is publicly accessible
- Test endpoint directly with curl/Postman

#### Scenario B: Token validation fails
**Look for:**
```
❌ DIAGNOSTIC: Token validation FAILED
⚠️ Invalid audience. Expected: ...
⚠️ Invalid issuer. Expected: ...
```

**Means:** Token configuration mismatch
**Next steps:**
- Verify `AUTH_EXTENSION_API_CLIENT_ID` in App Service settings
- Verify `AUTH_EXTENSION_TENANT_ID` in App Service settings
- Check Application ID URI in app registration
- Check custom extension "Required app ID URI" matches

#### Scenario C: Request parsing fails
**Look for:**
```
❌ Empty request body
❌ Failed to parse custom extension request
```

**Means:** Request format issue
**Next steps:**
- Check custom extension event type configuration
- Verify it's attached to OnAttributeCollectionSubmit
- Check payload structure in logs

#### Scenario D: Response returns but user flow fails
**Look for:**
```
✅ DIAGNOSTIC: Returning ContinueWithDefaultBehavior
```

**Means:** Response contract mismatch
**Next steps:**
- Verify response format matches Microsoft schema
- Check if custom extension expects different response structure
- Review Microsoft documentation for OnAttributeCollectionSubmit

## Quick Diagnostics Commands

### View Real-Time Logs (Azure CLI)
```bash
az webapp log tail --name creditboostportal --resource-group <your-rg>
```

### Test Endpoint Directly (Requires Bearer Token)
```bash
curl -X POST https://creditboostportal.azurewebsites.net/api/verify-resident \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"type":"microsoft.graph.authenticationEvent.attributeCollectionSubmit","data":{"attributes":{"email":"test@test.com","givenName":"Test","surname":"User"}}}'
```

## Restoring Normal Operation

Once testing is complete, **restore normal verification logic** by:

1. Remove diagnostic comments and logging
2. Restore SharePoint/Entrata verification calls
3. Remove hard-coded success response
4. Keep useful enhanced logging if helpful

Search for: `DIAGNOSTIC MODE` in code to find all changes.

## Security Note

⚠️ **This diagnostic mode skips all verification logic**

- Any email can sign up (no resident verification)
- This is for testing the extension plumbing ONLY
- Restore normal verification before production use
- Do NOT leave diagnostic mode active in production

## Expected Timeline

1. **Deploy diagnostic version** - 2-3 minutes
2. **Run single test sign-up** - 1 minute
3. **Review logs** - 2-5 minutes
4. **Determine root cause** - Immediate
5. **Restore or fix based on findings** - varies

Total diagnostic session: **10-15 minutes**
