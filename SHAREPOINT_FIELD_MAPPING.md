# SharePoint Lists Field Mapping

## Current vs. New Data Structure

Previously, all data was stored in a single list: **Credit Boost - Residents** (ID: dca29e9a-1c69-46cb-86b5-8111b5034c1b)

Now data is split across three lists:
1. **Credit Boost - Tenants** - Resident/tenant personal information
2. **Credit Boost - Accounts** - Account enrollment and status information  
3. **Credit Boost - Statements** - Monthly payment statements and reporting

---

## List 1: Credit Boost - Tenants
**List ID:** 7569dfb7-5d2f-452d-a384-0af63b38b559

### Personal Information Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Resident ID | ResidentID | Text | account_number, ResidentID | Primary identifier |
| First Name | FirstName | Text | first_name, FirstName | |
| Middle Name | MiddleName | Text | - | NEW FIELD - not in current app |
| Last Name | LastName | Text | last_name, LastName | |
| Generation Code | GenerationCode | Text | - | NEW FIELD - e.g., Jr., Sr., III |
| Date of Birth | DateofBirth | DateTime | dob, DateofBirth | |
| SSN Last 4 | SSNLast4 | Text | last4_ssn, SSNLast4 | |

### Address Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Address Line 1 | AddressLine1 | Text | AddressLine1 | |
| Address Line 2 | AddressLine2 | Text | AddressLine2 | |
| City | City | Text | city, City | |
| State Code | StateCode | Text | state, StateCode | |
| Zip Code | ZipCode | Text | zip, ZipCode | |
| Primary Address | PrimaryAddress | Boolean | - | NEW FIELD - indicates primary address |

### Property/Unit Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Property | Property | Text | property, property_name, Property | |
| Unit | Unit | Text | unit, unit_number, Unit | |

### Bloom Integration Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Bloom Consumer ID | BloomConsumerID | Text | - | NEW FIELD - Bloom API consumer ID |
| Bloom Consumer Status | BloomConsumerStatus | Choice | - | NEW FIELD - Not Created, Created, Error |
| Bloom Consumer Created At | BloomConsumerCreatedAt | DateTime | - | NEW FIELD |
| Last Sync At | LastSyncAt | DateTime | - | NEW FIELD |
| Last Error | LastError | Multi-line Text | - | NEW FIELD |

---

## List 2: Credit Boost - Accounts
**List ID:** f836ae36-efe3-47e5-8f11-d191422ca5d4

### Account Information Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Account ID | AccountID | Text | - | Primary identifier for account |
| Resident ID | ResidentID | Text | account_number, ResidentID | Links to Tenants list |
| Credit Product ID | CreditProductID | Text | - | NEW FIELD |
| External Account Identifier | ExternalAccountIdentifier | Text | - | NEW FIELD |
| Account Type | AccountType | Choice | - | NEW FIELD - Individual, Joint |
| Opened Date | OpenedData | DateTime | date_opened | Note: typo in SharePoint field name |
| Terms Duration | TermsDuration | Text | - | NEW FIELD |
| Consumer Account Number | ConsumerAccountNumber | Text | - | NEW FIELD |

### Bloom Integration Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Bloom Account ID | BloomAccountID | Text | - | NEW FIELD - Bloom API account ID |
| Bloom Account Status | BloomAccountStatus | Choice | - | NEW FIELD - Not Created, Created, Error |
| Bloom Account Created At | BloomAccountCreatedAt | DateTime | - | NEW FIELD |
| Last Sync At | LastSyncAt | DateTime | - | NEW FIELD |
| Last Error | LastError | Multi-line Text | - | NEW FIELD |

---

## List 3: Credit Boost - Statements
**List ID:** 15cdc70e-ba08-4f9b-9ba2-79d66e8c6552

### Statement Identification Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Statement ID | StatementID | Text | - | Primary identifier |
| Account ID | AccountID | Lookup | - | Links to Accounts list |
| Resident ID | ResidentID | Text | ResidentID | Links to Tenants list |
| Statement Date | StatementDate | DateTime | - | NEW FIELD - statement generation date |
| Statement Identifier | StatementIdentifier | Text | - | NEW FIELD - formatted identifier |
| Last Payment Date | LastPaymentDate | DateTime | date_paid, payment_date, LastPaymentDate | Date payment was received |

### Payment Amount Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Current Balance | CurrentBalance | Number | current_balance, CurrentBalance | Outstanding balance |
| Days Delinquent | DaysDelinquent | Number | days_late, DaysDelinquent | Days past due |
| Credit Limit | CreditLimit | Number | - | NEW FIELD |
| Scheduled Monthly Payment | ScheduledMonthlyPayment | Number | scheduled_payment, monthly_rent, ScheduledMonthlyPayment | Expected payment amount |
| Actual Monthly Payment | ActualMonthlyPayment | Number | amount, ActualMonthlyPayment | Amount actually paid |
| Amount Past Due | AmountPastDue | Number | amount_past_due, AmountPastDue | Total past due |

### Bloom Furnishment Fields
| SharePoint Field | Internal Name | Type | App Field | Notes |
|-----------------|---------------|------|-----------|-------|
| Bloom Statement ID | BloomStatementID | Text | - | NEW FIELD - Bloom API statement ID |
| Furnishment Status | FurnishmentStatus | Choice | - | NEW FIELD - Pending, Submitted, Accepted, Rejected, Error |
| Furnished At | FurnishedAt | DateTime | report_date | When reported to credit bureau |
| Last Error | LastError | Multi-line Text | - | NEW FIELD |
| Submission Batch ID | SubmissionBatchID | Text | - | NEW FIELD |

---

## Fields Missing from New Lists (Need to Add or Derive)

### From Application but Not in Any SharePoint List:
1. **Email** - Currently derived from first/last name, could add to Tenants list
2. **Phone** - Not captured, could add to Tenants list
3. **Credit Score** - Currently using default 650, could add to Accounts list
4. **Lease Start Date** - Could add to Accounts list
5. **Lease End Date** - Could add to Accounts list
6. **Move In Date** - Could add to Tenants list
7. **Payment Schedule** - Currently defaults to "Monthly", could add to Accounts list
8. **Date First Delinquency** - Could derive from Statements or add to Accounts list
9. **Account Status** - Could derive from latest Statement's DaysDelinquent or add to Accounts list
10. **Enrollment Status** - Should add to Accounts list (enrolled, pending, opted_out)
11. **Rent Reporting Status** - Should add to Accounts list
12. **Tradeline Created** - Should add to Accounts list (boolean)

### Recommended Fields to Add:

#### To Tenants List:
- Email (Text)
- Phone (Text)
- MoveInDate (DateTime)

#### To Accounts List:
- EnrollmentStatus (Choice: Enrolled, Pending, Opted Out)
- RentReportingStatus (Choice: Enrolled, Paused, Stopped)
- TradelineCreated (Boolean)
- LeaseStartDate (DateTime)
- LeaseEndDate (DateTime)
- PaymentSchedule (Choice: Monthly, Bi-weekly, etc.)
- AccountStatus (Choice: Current, Late, Delinquent, Charged Off)
- DateFirstDelinquency (DateTime)
- CreditScore (Number) - if tracking

---

## Data Relationship

```
Credit Boost - Tenants (Resident Info)
    ResidentID (Primary Key)
    ↓
Credit Boost - Accounts (Account Info)
    AccountID (Primary Key)
    ResidentID (Foreign Key → Tenants)
    ↓
Credit Boost - Statements (Payment History)
    StatementID (Primary Key)
    AccountID (Lookup → Accounts)
    ResidentID (Foreign Key → Tenants)
```

**Relationship Type:**
- One Tenant → One Account (1:1)
- One Account → Many Statements (1:Many)
- One Tenant → Many Statements (1:Many through Account)
