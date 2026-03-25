# SharePoint Data Migration Summary

## Overview
Updated the Credit Boost Portal to load data from **three separate SharePoint lists** instead of one unified list.

## Previous Architecture
- **Single List:** Credit Boost - Residents (ID: dca29e9a-1c69-46cb-86b5-8111b5034c1b)
- All resident info, account details, and payment history in one list

## New Architecture
Data is now split across three normalized lists:

### 1. Credit Boost - Tenants
**List ID:** `7569dfb7-5d2f-452d-a384-0af63b38b559`

**Purpose:** Store resident/tenant personal information

**Key Fields:**
- ResidentID (primary key)
- FirstName, MiddleName, LastName, GenerationCode
- DateofBirth
- SSNLast4
- AddressLine1, AddressLine2, City, StateCode, ZipCode, PrimaryAddress
- Property, Unit
- BloomConsumerID, BloomConsumerStatus, BloomConsumerCreatedAt
- LastSyncAt

### 2. Credit Boost - Accounts
**List ID:** `f836ae36-efe3-47e5-8f11-d191422ca5d4`

**Purpose:** Store account enrollment and status information

**Key Fields:**
- AccountID (primary key)
- ResidentID (foreign key → Tenants)
- CreditProductID
- ExternalAccountIdentifier
- AccountType (Individual, Joint)
- OpenedData (account opened date)
- TermsDuration
- ConsumerAccountNumber
- BloomAccountID, BloomAccountStatus, BloomAccountCreatedAt
- LastSyncAt

### 3. Credit Boost - Statements
**List ID:** `15cdc70e-ba08-4f9b-9ba2-79d66e8c6552`

**Purpose:** Store monthly payment statements and reporting history

**Key Fields:**
- StatementID (primary key)
- AccountID (lookup → Accounts)
- ResidentID (foreign key → Tenants)
- StatementDate, LastPaymentDate
- CurrentBalance, DaysDelinquent
- CreditLimit
- ScheduledMonthlyPayment, ActualMonthlyPayment
- AmountPastDue
- StatementIdentifier
- BloomStatementID, FurnishmentStatus, FurnishedAt
- SubmissionBatchID

## Data Relationships

```
Tenants (1) ←→ (1) Accounts (1) ←→ (Many) Statements

ResidentID is the linking field between all three lists
```

## Code Changes

### Updated Files
1. **utils/sharepoint_data_loader.py** - Core changes to load from three lists
2. **inspect_sharepoint_lists.py** - New utility to inspect list schemas
3. **SHAREPOINT_FIELD_MAPPING.md** - Comprehensive field mapping documentation

### New Functions Added

#### `load_tenants_from_sharepoint(access_token, site_id)`
- Loads tenant personal info from Credit Boost - Tenants list
- Returns dict mapping ResidentID → tenant data

#### `load_accounts_from_sharepoint(access_token, site_id)`
- Loads account info from Credit Boost - Accounts list
- Returns dict mapping ResidentID → account data

#### `load_statements_from_sharepoint(access_token, site_id)`
- Loads payment statements from Credit Boost - Statements list
- Returns dict mapping ResidentID → list of statements
- Statements are sorted by date (most recent first)

### Modified Functions

#### `load_residents_and_payments_from_sharepoint_list(access_token, site_id)`
- **Changed:** Now loads from three lists instead of one
- Calls the three new load functions
- Combines tenant and account data into unified residents_dict
- Returns (residents_dict, statements_dict) tuple

#### `load_residents_from_sharepoint_list()`
- Updated to use data from three lists
- Now uses `OpenedDate` from Accounts list for `date_opened` field
- Uses account opened date for enrollment history when available
- All field mappings updated to handle new data structure

### Deprecated Functions

#### `load_statements_from_sharepoint_list(access_token, site_id)`
- Marked as DEPRECATED (was already deprecated for old unified list)
- Now references new Statements list in comment
- Returns empty dict for backward compatibility

## Data Flow

1. **Authentication:** Authenticate with Microsoft Graph API using Azure credentials
2. **Site Resolution:** Resolve SharePoint site to get site_id
3. **Three-List Load:**
   - Load tenants from Tenants list
   - Load accounts from Accounts list  
   - Load statements from Statements list
4. **Data Combination:**
   - Merge tenant + account data by ResidentID
   - Keep statements separate, indexed by ResidentID
5. **Transformation:** Convert combined data to app's resident dictionary format
6. **Return:** List of resident objects with embedded payment history

## Key Improvements

### Better Data Normalization
- Separated concerns: personal info, account info, payment history
- Reduced data duplication
- Easier to maintain and update

### Enhanced Bloom Integration Fields
- BloomConsumerID, BloomConsumerStatus (in Tenants)
- BloomAccountID, BloomAccountStatus (in Accounts)
- BloomStatementID, FurnishmentStatus (in Statements)
- LastError and LastSyncAt fields for tracking

### More Accurate Account Dates
- Now uses actual `OpenedDate` from Accounts list
- Falls back to move-in date or default if not available

### Better Statement Tracking
- StatementIdentifier for unique identification
- FurnishmentStatus tracks reporting status (Pending, Submitted, Accepted, Rejected, Error)
- SubmissionBatchID for batch tracking

## Missing Fields Identified

The following fields are used by the app but not currently in any SharePoint list:

### Recommended to Add to Tenants List:
- Email (Text)
- Phone (Text)
- MoveInDate (DateTime)

### Recommended to Add to Accounts List:
- EnrollmentStatus (Choice: Enrolled, Pending, Opted Out)
- RentReportingStatus (Choice: Enrolled, Paused, Stopped)
- TradelineCreated (Boolean)
- LeaseStartDate (DateTime)
- LeaseEndDate (DateTime)
- PaymentSchedule (Choice: Monthly, Bi-weekly, etc.)
- AccountStatus (Choice: Current, Late, Delinquent, Charged Off)
- DateFirstDelinquency (DateTime)
- CreditScore (Number)

### Current Workarounds:
- **Email:** Derived from first/last name (firstname.lastname@example.com)
- **Phone:** Left empty
- **Credit Score:** Defaults to 650
- **Lease Dates:** Left empty
- **Payment Schedule:** Defaults to "Monthly"
- **Account Status:** Derived from latest statement's DaysDelinquent
- **Enrollment Status:** Hardcoded to "enrolled"
- **Tradeline Created:** Hardcoded to True

## Testing

### To Test the Changes:

1. **Inspect List Schemas:**
   ```powershell
   python inspect_sharepoint_lists.py
   ```

2. **Test Data Loading:**
   ```powershell
   python show_test_emails.py
   ```
   or
   ```powershell
   python app.py
   ```

3. **Verify in App:**
   - Login to admin dashboard
   - Check that all residents are loading correctly
   - Verify payment statements are showing
   - Confirm account details are accurate

## Next Steps

1. **Review Field Mapping:** Check SHAREPOINT_FIELD_MAPPING.md to see if any fields should be added to the SharePoint lists

2. **Add Missing Fields:** Consider adding the recommended fields to the SharePoint lists for better data tracking

3. **Test Thoroughly:** Ensure all app features work correctly with the new three-list structure

4. **Update Any Direct List References:** Search codebase for any hardcoded references to the old unified list ID

5. **Consider Data Migration:** If the old unified list has data that needs to be migrated to the three new lists, create a migration script

## Compatibility

- **Backward Compatible:** Old code that doesn't use SharePoint will continue to work with test data
- **Environment Variable:** USE_TEST_DATA=true continues to use test data, USE_TEST_DATA=false uses SharePoint
- **No App Changes Required:** The app's data structure remains unchanged; only the data loading changed

## Files Created/Modified

### Created:
- `inspect_sharepoint_lists.py` - Utility to inspect SharePoint list schemas
- `SHAREPOINT_FIELD_MAPPING.md` - Comprehensive field mapping documentation
- `SHAREPOINT_MIGRATION_SUMMARY.md` - This file

### Modified:
- `utils/sharepoint_data_loader.py` - Updated to load from three lists
