# CredHub Data Integration Summary

## Overview
Successfully integrated 6 new SharePoint lists from the CredHub reporting system into the Credit Boost Portal. This new dataset provides detailed financial and delinquency information for residents.

## Implementation Date
March 12, 2026

## SharePoint Lists Integrated

### 1. Program Participants
- **List ID:** `bbe01515-0941-4e67-9381-f662fcfb6aa0`
- **Purpose:** Individual participant/resident information
- **Key Fields:**
  - ParticipantID, ResidentID, PropertyID
  - FirstName, MiddleName, LastName, DateOfBirth
  - Email, PhoneNumber
  - IsProgramEnrolled, ProgramStatus, EnrollmentDate, OptOutDate
  - DefaultReportToCreditBureaus

### 2. Leases
- **List ID:** `af09428a-7859-456d-a4be-f8f32c66fb27`
- **Purpose:** Lease/account information with addresses
- **Key Fields:**
  - LeaseId, EntrataLeaseId, PropertyId, AccountNumber
  - LeaseStatus, MoveInDate, MoveOutDate
  - CurrentLeaseStartDate, CurrentLeaseEndDate
  - AddressLine1, AddressLine2, City, State, PostalCode
  - UnitNumber

### 3. Lease Residents
- **List ID:** `73931c62-e631-4a27-9cbc-8dc5371f8bbc`
- **Purpose:** Junction table linking participants to leases
- **Key Fields:**
  - LeaseResidentId, LeaseId, ParticipantId
  - LeaseRelationship (Primary, CoTenant, Guarantor, Maker, Individual)
  - ResidentStatus (Active, Former, Pending)
  - ReportToCreditBureaus, IsAddressSameAsPrimary
  - LastValidationStatus, ExclusionReason

### 4. Monthly Financial Snapshots
- **List ID:** `bcf0d7cb-00db-4755-8898-a24dcf83702f`
- **Purpose:** Financial data showing delinquency and payment status
- **Key Fields:**
  - SnapshotId, LeaseId, AsOfDate
  - MonthlyRentAmount, TotalMonthlyRecurringCharges
  - TotalLedgerBalance (current balance)
  - **Aging Buckets:**
    - BalanceAged30To59
    - BalanceAged60To89
    - BalanceAged90To119
    - BalanceAged120To149
    - BalanceAged150To179
    - BalanceAged180Plus
  - OldestOpenChargeDate
  - LastPaymentDate, LastPaymentAmount
  - TotalPaymentAmountInPeriod

### 5. Reporting Cycles
- **List ID:** `c2545153-1aa1-409b-aad4-a6361966af0a`
- **Purpose:** Monthly reporting cycle tracking
- **Key Fields:**
  - ReportingCycleId, CycleName, AsOfDate
  - CredHubCompanyId, CycleStatus
  - ParticipantCount, LeaseCount, JobCount
  - LastCredHubJobId, SubmittedAt, CompletedAt

### 6. CredHub Job Runs
- **List ID:** `097d06bb-0bc6-4fb3-9188-d7afa3773b26`
- **Purpose:** Track CredHub API job submissions
- **Key Fields:**
  - CredHubJobRunId, ReportingCycleId, JobId
  - JobType (RentalAccounts, ReRun, GenerateMetro2, StatusSync)
  - JobStatus, SubmissionStatus, SubmittedAt
  - Metro2Generated, ErrorCount, WarningCount
  - RawRequestJson, RawResponseJson, StatusSummary

## Data Mapping Strategy

### Joining Logic
The system joins data from multiple lists to create complete resident records:

1. **Start with Lease Residents** (junction table) - Links participants to leases
2. **Join Program Participants** - Get personal information (name, DOB, email, etc.)
3. **Join Leases** - Get address and lease details
4. **Join Monthly Financial Snapshots** - Get most recent financial data per lease
5. **Optionally join Reporting Cycles and Job Runs** - For audit trail

### Key Mappings

| Portal Field | Source |
|-------------|---------|
| `name` | Participant: FirstName + MiddleName + LastName |
| `email` | Participant: Email |
| `phone` | Participant: PhoneNumber |
| `address` | Lease: AddressLine1 + AddressLine2 |
| `city`, `state`, `zip` | Lease: City, State, PostalCode |
| `property` | Participant: PropertyID or Lease: PropertyId |
| `unit` | Lease: UnitNumber or AddressLine2 |
| `dob` | Participant: DateOfBirth |
| `enrolled` | Participant: IsProgramEnrolled AND LeaseResident: ReportToCreditBureaus |
| `account_status` | Calculated from Snapshot: TotalLedgerBalance + Aging Buckets |
| `amount_past_due` | Snapshot: TotalLedgerBalance (if positive) |
| `scheduled_monthly_payment` | Snapshot: MonthlyRentAmount |
| `lease_start_date` | Lease: CurrentLeaseStartDate |
| `lease_end_date` | Lease: CurrentLeaseEndDate |

### Delinquency Calculation

The system calculates delinquency status based on aging buckets:

```
TotalLedgerBalance <= 0 → "Current"
BalanceAged180Plus > 0 → "Delinquent 180+ days"
BalanceAged150To179 > 0 → "Delinquent 150-179 days"
BalanceAged120To149 > 0 → "Delinquent 120-149 days"
BalanceAged90To119 > 0 → "Delinquent 90-119 days"
BalanceAged60To89 > 0 → "Delinquent 60-89 days"
BalanceAged30To59 > 0 → "Delinquent 30-59 days"
TotalLedgerBalance > 0 (no aging) → "Delinquent 1-29 days"
```

## Files Modified

### 1. `utils/sharepoint_data_loader.py`
**Added Functions:**
- `load_residents_from_credhub_lists()` - Main data loader orchestrator
- `load_credhub_participants()` - Load Program Participants list
- `load_credhub_leases()` - Load Leases list
- `load_credhub_lease_residents()` - Load Lease Residents junction table
- `load_credhub_financial_snapshots()` - Load Monthly Financial Snapshots
- `load_credhub_reporting_cycles()` - Load Reporting Cycles list
- `load_credhub_job_runs()` - Load CredHub Job Runs list

**Lines Added:** ~500 lines

### 2. `app.py`
**Changes:**
- Added import: `load_residents_from_credhub_lists`
- Updated `admin_rent_reporting()` route to support `data_source='credhub'`
- Updated `admin_resident_detail()` route to support `data_source='credhub'`

**Key Logic:**
```python
if data_source == 'credhub':
    source_residents = load_residents_from_credhub_lists()
    if not source_residents:
        flash('Failed to load CredHub data. Falling back to test data.', 'warning')
        source_residents = residents
```

### 3. `templates/admin/rent_reporting.html`
**Changes:**
- Added new dropdown option: `<option value="credhub">CredHub Data (Reporting System)</option>`
- Updated status indicator to show CredHub connection info

## Testing Results

### Test Execution
- **Date:** March 12, 2026
- **Script:** `test_credhub_loader.py`

### Data Loaded
- ✓ 99 Program Participants
- ✓ 100 Leases
- ✓ 200 Lease-Resident Associations
- ✓ 78 Monthly Financial Snapshots
- ✓ 0 Reporting Cycles (empty list)
- ✓ 5 CredHub Job Runs

### Results
- **Total Residents Assembled:** 126
- **Enrolled Residents:** 126
- **Delinquent Residents:** 4
- **Total Past Due Amount:** $5,420.00

### Sample Records
```
Resident 1:
  Name: Kayden Lewis
  Property: PROP-001
  Unit: 18
  Enrolled: True
  Account Status: Current
  Total Balance: $0.00
  Lease Relationship: Maker

Resident 2:
  Name: Shelley Fay Lewis
  Property: PROP-001
  Unit: 18
  Enrolled: True
  Account Status: Current
  Total Balance: $0.00
  Lease Relationship: Co-maker or Guarantor
```

## Usage Instructions

### For Administrators

1. **Navigate to Rent Reporting page** in the Admin dashboard
2. **Select Data Source** from the dropdown:
   - "Test Data (Excel)" - Local test data
   - "Real Data (SharePoint List)" - Original Credit Boost lists
   - **"CredHub Data (Reporting System)"** - NEW! CredHub integrated lists
3. **View residents** with real-time financial and delinquency data
4. **Use filters** to find specific residents or view delinquent accounts

### Key Features Available with CredHub Data

- ✓ Real-time delinquency status based on financial snapshots
- ✓ Aging bucket breakdown (30-59, 60-89, 90+, etc.)
- ✓ Lease relationship tracking (Primary, CoTenant, Guarantor, etc.)
- ✓ Program enrollment status
- ✓ Most recent payment information
- ✓ Total ledger balance per resident
- ✓ Monthly rent amounts

## Additional CredHub Fields Available

The CredHub dataset includes additional fields beyond the standard portal structure:

```python
'participant_id': 'P-14759688'
'lease_id': 'L-14759688'
'resident_id': '2769'
'lease_relationship': 'Maker'
'resident_status': 'Active'
'program_status': 'Enrolled'
'last_payment_date': '2025-09-11'
'last_payment_amount': 1200.00
'total_balance': 0.00
'aged_30_59': 0.00
'aged_60_89': 0.00
'aged_90_plus': 0.00
```

These fields can be used for enhanced reporting and filtering in future updates.

## Future Enhancements

### Potential Additions
1. **Payment History Timeline** - Use historical snapshots to show payment trends
2. **Reporting Cycle Dashboard** - Display reporting cycle status and metrics
3. **Job Run Tracking** - Monitor CredHub API job submissions and responses
4. **Delinquency Alerts** - Flag residents with aging balances
5. **Export Enhancements** - Include CredHub-specific fields in CSV exports
6. **Filtering by Aging Bucket** - Filter residents by specific delinquency ranges
7. **Lease Relationship Grouping** - View all residents on the same lease
8. **Program Status Reporting** - Track enrollment/opt-out trends

## Technical Notes

### Performance
- All 6 lists are loaded in parallel using Microsoft Graph API
- Most recent financial snapshot is selected per lease to avoid duplicate data
- Data is assembled once per page load (consider caching for production)

### Error Handling
- Falls back to test data if CredHub data load fails
- Displays warning flash message to user
- Logs detailed error messages to console

### Data Freshness
- Data is pulled in real-time from SharePoint on each page load
- No local caching currently implemented
- Consider implementing caching for better performance in production

## Conclusion

The CredHub integration successfully adds comprehensive financial and delinquency tracking to the Credit Boost Portal. This enables administrators to:

1. **Identify delinquent residents** with detailed aging information
2. **Track program enrollment** status across all participants
3. **Monitor payment history** and current balances
4. **View lease relationships** (primary, co-tenant, guarantor)
5. **Access real-time data** from the CredHub reporting system

The implementation maintains compatibility with existing portal features while adding powerful new data sources for decision-making and reporting.
