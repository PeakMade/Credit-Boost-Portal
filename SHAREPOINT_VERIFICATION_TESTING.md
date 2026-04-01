# SharePoint Verification Testing Setup

Since the Entrata test environment is undergoing a data refresh, you can use SharePoint for resident verification testing.

## Quick Start

**The code is already configured to use SharePoint!** Just follow the Azure setup steps in [RESIDENT_VERIFICATION_SETUP.md](RESIDENT_VERIFICATION_SETUP.md) - everything works the same, the backend just queries SharePoint instead of Entrata.

---

## SharePoint List Requirements

Your SharePoint list for verification testing must have these columns:

### Required Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `Email` or `EmailAddress` | Single line of text | Resident email address |
| `FirstName` | Single line of text | Resident first name |
| `LastName` | Single line of text | Resident last name |
| `DateofBirth` or `DateOfBirth` or `DOB` | Date | Date of birth (YYYY-MM-DD) |

### Optional Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `ResidentID` | Single line of text or Number | Resident identifier |
| `ID` | Number | SharePoint item ID (used if ResidentID not present) |

---

## Which List to Use?

### Option 1: Use Existing "Credit Boost - Tenants" List (Default)

**List ID:** `7569dfb7-5d2f-452d-a384-0af63b38b559`

**Pros:**
- Already exists
- No additional configuration needed
- Code defaults to this list

**Cons:**
- Contains production/real data (if already populated)

### Option 2: Create Dedicated "Verification Test" List (Recommended)

**Steps:**
1. In SharePoint, create new list: "Credit Boost - Verification Test"
2. Add the required columns above
3. Add your test resident data
4. Copy the List ID from the list URL
5. Set environment variable: `SHAREPOINT_VERIFICATION_LIST_ID=your-list-id-here`

**Pros:**
- Clean test data
- Won't interfere with production lists
- Easy to reset/modify

---

## Example Test Resident Data

Add a test resident to your SharePoint list:

| Email | FirstName | LastName | DateofBirth | ResidentID |
|-------|-----------|----------|-------------|------------|
| test@example.com | John | Smith | 1990-01-15 | TEST001 |

Then test sign-up with:
- **Email:** test@example.com
- **First Name:** John
- **Last Name:** Smith  
- **Date of Birth:** 1990-01-15

**Expected:** Account created successfully ✅

---

## Configuration

### Environment Variables

In your `.env` file (already configured):

```env
# Use SharePoint for verification (testing mode)
USE_SHAREPOINT_VERIFICATION=true

# Optional: Custom verification list ID
# SHAREPOINT_VERIFICATION_LIST_ID=your-custom-list-id-here
```

### Azure App Service Settings

Add these to Azure App Service → Configuration → Application Settings:

1. `USE_SHAREPOINT_VERIFICATION` = `true`
2. `AZURE_API_CONNECTOR_KEY` = `i4df6gcmoOn-xIfdspdkiBcUnOiOO0Vx92Vqrmb8xbE`
3. (Optional) `SHAREPOINT_VERIFICATION_LIST_ID` = `your-custom-list-id`

**Note:** Azure credentials (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`) are already configured for SharePoint access.

---

## Testing the Verification

### 1. Add Test Data to SharePoint

Create at least one test resident in your SharePoint list with all required fields.

### 2. Follow Azure Setup (Same as Before!)

Complete all steps in [RESIDENT_VERIFICATION_SETUP.md](RESIDENT_VERIFICATION_SETUP.md):
- ✅ Part 2: Add Date of Birth custom attribute
- ✅ Part 3: Create API Connector  
- ✅ Part 4: Test the integration

**Nothing changes** - the Azure configuration is identical whether using SharePoint or Entrata!

### 3. Test Valid Resident

Sign up with data matching your SharePoint test resident:
- **Expected:** ✅ Account created, user can login

### 4. Test Invalid Data

Sign up with data NOT in SharePoint:
- **Expected:** ❌ Error: "The data you provided could not be verified..."

### 5. Monitor Logs

Azure App Service → Log Stream:

**SharePoint verification logs:**
```
🔍 Verifying resident sign-up: test@example.com (John Smith, DOB: 1990-01-15)
Using SharePoint for verification (test mode)
🔍 Querying SharePoint list 7569dfb7-5d2f-452d-a384-0af63b38b559 for verification
Found 1 records in SharePoint list
✅ Resident verified via SharePoint: test@example.com (ID: TEST001)
✅ Resident verified for sign-up: test@example.com
```

---

## Switching to Entrata Later

When Entrata test environment is ready:

### In `.env` and Azure App Settings:

```env
# Switch to Entrata for verification (production mode)
USE_SHAREPOINT_VERIFICATION=false

# Add Entrata credentials
ENTRATA_API_USERNAME=your_actual_username
ENTRATA_API_PASSWORD=your_actual_password
ENTRATA_PROPERTY_ID=your_property_id
```

No code changes needed! Just flip the environment variable.

---

## Troubleshooting

### "Unable to verify at this time"

**Possible causes:**
1. Azure credentials not configured
2. SharePoint list ID incorrect
3. Network/permission issue

**Check logs for:**
- `❌ Azure credentials not configured`
- `❌ SharePoint API error`

### "The data you provided could not be verified"

**Possible causes:**
1. Email doesn't match (case-sensitive comparison)
2. Name doesn't match (check for typos)
3. Date of birth doesn't match (must be exact)
4. Test data not in SharePoint list

**Check logs for:**
- `Email match but name mismatch`
- `Email/name match but DOB mismatch`
- `No matching resident found in SharePoint`

### Verification succeeds but data seems wrong

Check which list is being queried:
- Look for log: `🔍 Querying SharePoint list [list-id] for verification`
- Verify list ID matches your test list
- Set `SHAREPOINT_VERIFICATION_LIST_ID` if using custom list

---

## Field Name Variations Supported

The code checks multiple field name variations:

**Email field:**
- `Email`
- `EmailAddress`
- `email`

**Date of Birth field:**
- `DateofBirth`
- `DateOfBirth`
- `DOB`

**Resident ID field:**
- `ResidentID`
- `ID` (SharePoint item ID)

Use whichever naming convention matches your SharePoint list!

---

## Summary

✅ **You can proceed with all Azure setup steps** - nothing changes from [RESIDENT_VERIFICATION_SETUP.md](RESIDENT_VERIFICATION_SETUP.md)

✅ **Code is already configured** to use SharePoint (via `USE_SHAREPOINT_VERIFICATION=true`)

✅ **Add test resident to SharePoint** with Email, FirstName, LastName, DateofBirth

✅ **Test the full flow** - should work exactly like Entrata verification

✅ **Switch back to Entrata** when ready by changing one environment variable

The verification backend is now **flexible** - same Azure setup, same API endpoint, just different data source!
