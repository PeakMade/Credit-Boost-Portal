# Azure Entra External ID - Resident Verification Setup

This guide explains how to implement resident verification during sign-up using Azure Entra External ID API Connectors and Entrata PMS integration.

## Overview

**Goal:** Prevent unauthorized users from creating accounts by verifying resident data (email, name, DOB) against Entrata PMS during the sign-up process.

**Flow:**
1. User visits sign-up page and enters: First Name, Last Name, Email, **Date of Birth**
2. Azure Entra External ID calls your Flask API endpoint **before creating the account**
3. Your Flask app queries Entrata API to verify the resident exists with matching details
4. If verified → Account created, user can login
5. If not verified → Error shown, account NOT created

---

## Part 1: Configure Environment Variables

### 1.1 Update `.env` with Entrata Credentials

Replace the placeholder values in your `.env` file:

```env
# Entrata PMS API Configuration (Test Environment)
ENTRATA_API_URL=https://api.entrata.com/api/v1
ENTRATA_API_USERNAME=your_actual_test_username
ENTRATA_API_PASSWORD=your_actual_test_password
ENTRATA_PROPERTY_ID=your_actual_property_id

# Azure API Connector Security
AZURE_API_CONNECTOR_KEY=i4df6gcmoOn-xIfdspdkiBcUnOiOO0Vx92Vqrmb8xbE
```

**Where to find Entrata credentials:**
- Contact your Entrata account manager or check your Entrata admin portal
- You mentioned having test environment credentials - use those
- Property ID is typically a numeric identifier for your specific property

### 1.2 Add to Azure App Service Configuration

In Azure Portal → App Service → Configuration → Application Settings:
1. Click "New application setting" for each:
   - `ENTRATA_API_URL` = `https://api.entrata.com/api/v1`
   - `ENTRATA_API_USERNAME` = `your_username`
   - `ENTRATA_API_PASSWORD` = `your_password`
   - `ENTRATA_PROPERTY_ID` = `your_property_id`
   - `AZURE_API_CONNECTOR_KEY` = `i4df6gcmoOn-xIfdspdkiBcUnOiOO0Vx92Vqrmb8xbE`

2. Click "Save" at the top
3. Restart your App Service

---

## Part 2: Add Custom User Attribute in Azure

### 2.1 Create Date of Birth Attribute

1. Navigate to **Azure Portal** → **Entra External ID** → **User flows**
2. Click **User attributes** in left menu
3. Click **Add**
4. Configure:
   - **Name:** `DateOfBirth`
   - **Description:** `Date of birth for resident verification`
   - **Data type:** `String` (we'll validate format in API)
   - **User flow type:** `Sign up`

5. Click **Create**

### 2.2 Update Sign-Up User Flow

1. Click **User flows** in left menu
2. Select your External ID sign-up flow (e.g., `external_oidc_signup`)
3. Click **User attributes** in left menu
4. Check the following attributes to **collect** during sign-up:
   - ✅ Email Address
   - ✅ First Name (Given Name)
   - ✅ Last Name (Surname)
   - ✅ **Date of Birth** (your custom attribute)

5. Click **Save**

### 2.3 Configure Attribute Display

1. Still in your user flow, click **Page layouts**
2. Select **Local account sign up page**
3. Find **Date of Birth** and configure:
   - **Required:** Yes
   - **User input type:** `TextBox` or `Date Picker`
   - **Display name:** `Date of Birth`
   - **Placeholder:** `YYYY-MM-DD` (if using TextBox)

4. Click **Save**

---

## Part 3: Create API Connector in Azure

### 3.1 Configure API Endpoint

1. Navigate to **Azure Portal** → **Entra External ID** → **API connectors**
2. Click **New API connector**
3. Configure:
   - **Name:** `Verify Resident - Entrata`
   - **Endpoint URL:** `https://your-app-name.azurewebsites.net/api/verify-resident`
     - Replace `your-app-name` with your actual Azure App Service name
   - **Authentication type:** `API key`
   - **Header name:** `X-API-Key`
   - **Header value:** `i4df6gcmoOn-xIfdspdkiBcUnOiOO0Vx92Vqrmb8xbE`

4. Click **Create**

### 3.2 Attach to Sign-Up Flow

1. Go to **User flows** → Select your External ID flow
2. Click **API connectors** in left menu
3. For **Before creating the user**, select dropdown:
   - Choose: `Verify Resident - Entrata`

4. Click **Save**

### 3.3 Configure Claims Mapping

1. Still in API connectors settings
2. Click **Attribute mapping** (if available)
3. Ensure these mappings:
   - Azure claim `extension_DateOfBirth` → API parameter `extension_DateOfBirth`
   - Azure claim `email` → API parameter `email`
   - Azure claim `givenName` → API parameter `givenName`
   - Azure claim `surname` → API parameter `surname`

4. Click **Save**

---

## Part 4: Test the Integration

### 4.1 Test with Valid Resident Data

1. Navigate to your app's sign-up page: `https://your-app-name.azurewebsites.net/`
2. Click **Resident Login** → **Sign up now**
3. Enter **valid** resident data from Entrata:
   - First Name: (from Entrata)
   - Last Name: (from Entrata)
   - Email: (from Entrata)
   - Date of Birth: (from Entrata, format: YYYY-MM-DD)

4. Click **Create**
5. **Expected:** Account created successfully, redirect to dashboard

### 4.2 Test with Invalid Data

1. Try signing up with:
   - Email: `fake@example.com`
   - First Name: `Test`
   - Last Name: `User`
   - DOB: `1990-01-01`

2. **Expected:** Error message shown:
   > "The data you provided could not be verified. Please contact property management to enroll in the Credit Boost Program or verify your information is correct."

### 4.3 Monitor Logs

Check Azure App Service logs:
1. Azure Portal → App Service → **Log stream**
2. Watch for verification attempts:
   - `🔍 Verifying resident sign-up: email@example.com`
   - `✅ Resident verified for sign-up: email@example.com` (success)
   - `❌ Resident verification failed: email@example.com` (failure)

---

## Part 5: Troubleshooting

### API Connector Not Calling Endpoint

**Check:**
1. Endpoint URL is correct and publicly accessible
2. API key matches in both Azure and `.env`
3. App Service is running and healthy (`/health` endpoint returns 200)

**Test endpoint directly:**
```bash
curl -X POST https://your-app-name.azurewebsites.net/api/verify-resident \
  -H "Content-Type: application/json" \
  -H "X-API-Key: i4df6gcmoOn-xIfdspdkiBcUnOiOO0Vx92Vqrmb8xbE" \
  -d '{
    "email": "test@example.com",
    "givenName": "John",
    "surname": "Doe",
    "extension_DateOfBirth": "1990-01-15"
  }'
```

Expected response:
```json
{
  "version": "1.0.0",
  "action": "ShowBlockPage",
  "userMessage": "The data you provided could not be verified..."
}
```

### Entrata API Not Responding

**Check:**
1. Entrata credentials are correct in Azure App Settings
2. Property ID is valid
3. Test network connectivity from Azure

**Check logs for:**
- `❌ Entrata API credentials not configured`
- `❌ Entrata API request failed`
- `❌ Entrata API request timeout`

### Users Can Still Sign Up Without Verification

**Check:**
1. API connector is attached to **"Before creating the user"** step
2. User flow is saved after adding API connector
3. Correct user flow is being used by your application

---

## Part 6: Security Considerations

### 6.1 Production Recommendations

1. **Rotate API Key:** Generate new `AZURE_API_CONNECTOR_KEY` for production
2. **Use Azure Key Vault:** Store `ENTRATA_API_PASSWORD` in Key Vault
3. **Enable HTTPS Only:** Ensure App Service enforces HTTPS
4. **Rate Limiting:** Consider adding rate limits to `/api/verify-resident`
5. **Audit Logging:** Log all verification attempts (already implemented)

### 6.2 Error Handling

The API is designed to **fail securely**:
- If Entrata API is down → User sees "Service temporarily unavailable"
- If credentials missing → Blocked with generic message
- If network timeout → Blocked with generic message
- Only specific verification failures show the verification error

---

## Part 7: Next Steps

### Optional Enhancements

1. **Add Unit Number Field:** Additional verification factor
2. **Email Verification:** Send code to email on file in Entrata
3. **Multiple Property Support:** Handle residents across different properties
4. **Fuzzy Name Matching:** Handle typos or alternate names (e.g., "Bob" vs "Robert")
5. **Cache Verification Results:** Reduce Entrata API calls for repeated attempts

### Migration Path

Once verified working in test environment:
1. Update `ENTRATA_API_URL` to production endpoint
2. Update credentials to production Entrata account
3. Test thoroughly with real resident data
4. Monitor verification success rate
5. Adjust error messages based on user feedback

---

## API Reference

### Request Format (from Azure)

```json
{
  "email": "resident@example.com",
  "givenName": "John",
  "surname": "Doe",
  "extension_DateOfBirth": "1990-01-15"
}
```

### Response Format (to Azure)

**Success (Allow Sign-Up):**
```json
{
  "version": "1.0.0",
  "action": "Continue"
}
```

**Failure (Block Sign-Up):**
```json
{
  "version": "1.0.0",
  "action": "ShowBlockPage",
  "userMessage": "The data you provided could not be verified. Please contact property management to enroll in the Credit Boost Program or verify your information is correct."
}
```

---

## Support

For issues or questions:
1. Check Azure App Service logs for detailed error messages
2. Review Entrata API documentation for field mappings
3. Test the `/api/verify-resident` endpoint directly with curl
4. Verify all environment variables are set correctly in Azure
