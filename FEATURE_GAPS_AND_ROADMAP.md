# Credit Boost Portal - Feature Gaps & Implementation Roadmap

## Current Status vs Industry Standard

Based on analysis of industry-standard rent reporting portals (RentPlus, Esusu, Experian RentBureau), here are the gaps in our current MVP.

---

## 🔴 CRITICAL MVP GAPS (Implement First)

### 1. **Reporting Runs/Cycles Management**
**Current:** None  
**Needed:**
- Monthly reporting cycle tracking
- Metro 2 file generation history
- Run status (pending, generated, submitted, accepted, rejected)
- Manual run controls (Admin only)
- Prevent double-submission (idempotency)

**Data Model Addition:**
```json
{
  "reporting_runs": [
    {
      "run_id": "RUN-2026-01-001",
      "cycle_month": "2026-01",
      "status": "submitted",  // pending, generated, submitted, accepted, rejected
      "generated_timestamp": "2026-01-15T10:30:00Z",
      "submitted_timestamp": "2026-01-15T11:00:00Z",
      "expected_record_count": 3,
      "actual_record_count": 3,
      "file_hash": "sha256:abc123...",
      "errors": [],
      "generated_by_user_id": "admin-001"
    }
  ]
}
```

**UI Pages Needed:**
- Admin: Reporting Runs History page
- Admin: Manual Run Control page (with dry-run option)
- Admin: Run Detail page (show file details, errors, status)

---

### 2. **Dispute Tracking & Guidance**
**Current:** None  
**Needed:**
- Read-only dispute case tracking
- Dispute guidance for residents
- Link to E-Oscar process
- Dispute status timeline

**Data Model Addition:**
```json
{
  "disputes": [
    {
      "dispute_id": "DISP-2026-001",
      "resident_id": 1,
      "case_id": "E-OSCAR-123456",
      "month_disputed": "2025-12",
      "status": "pending",  // pending, resolved, rejected
      "filed_date": "2026-01-10",
      "resolution_date": null,
      "notes": "Resident disputes late payment marking",
      "bureau": "Experian"
    }
  ]
}
```

**UI Pages Needed:**
- Resident: "How to Dispute" information page
- Resident: My Disputes (read-only list)
- Admin: Dispute Cases list
- Admin: Dispute Detail page

---

### 3. **Notification Preferences**
**Current:** None  
**Needed:**
- Email notification preferences
- "Reported this month" notifications
- Late payment alerts
- Enrollment confirmation emails

**Data Model Addition:**
```json
{
  "notification_preferences": {
    "resident_id": 1,
    "email_on_report": true,
    "email_on_late": true,
    "email_on_enrollment_change": true,
    "email_address": "jane.doe@example.com"
  }
}
```

**UI Pages Needed:**
- Resident: Notification Preferences page
- Admin: Send notification to resident

---

### 4. **Configuration Management**
**Current:** None  
**Needed:**
- Property-level enable/disable
- Rent charge code mapping
- Reporting cadence settings

**Data Model Addition:**
```json
{
  "system_config": {
    "properties": [
      {
        "property_id": "PROP-001",
        "property_name": "Main Street Apartments",
        "enabled_for_reporting": true,
        "rent_charge_codes": ["RENT", "BASE_RENT"],
        "reporting_day": 15  // Day of month to run report
      }
    ],
    "reporting_settings": {
      "cadence": "monthly",
      "auto_submit": false,
      "require_approval": true
    }
  }
}
```

**UI Pages Needed:**
- Admin: Configuration Settings page
- Admin: Property Management page

---

### 5. **Audit Logging**
**Current:** None  
**Needed:**
- Log all PII views
- Log all exports
- Log all configuration changes
- Log reporting run actions

**Data Model Addition:**
```json
{
  "audit_logs": [
    {
      "log_id": "AUD-2026-001",
      "timestamp": "2026-01-15T10:30:00Z",
      "user_id": "admin-001",
      "user_role": "Admin",
      "action": "VIEW_PII",
      "resource_type": "resident",
      "resource_id": 1,
      "ip_address": "192.168.1.100",
      "details": "Viewed resident detail page"
    }
  ]
}
```

**UI Pages Needed:**
- Admin: Audit Log viewer (filterable by user, action, date)

---

### 6. **CSV Export Functionality**
**Current:** None  
**Needed:**
- Export dashboard summary
- Export resident status list
- Export payment history
- All exports must be audit-logged

**UI Pages Needed:**
- Admin: Export buttons on dashboard and rent reporting pages
- Admin: Export History page

---

## 🟡 IMPORTANT ENHANCEMENTS (MVP Phase 2)

### 7. **Enhanced Resident Portal**
**Current:** Basic payment history  
**Needed:**
- Clear "What is Reported" explainer
- "What is NOT Reported" (fees, deposits, utilities)
- Next scheduled reporting date
- Visual timeline of reporting status

**UI Pages Needed:**
- Resident: "About Rent Reporting" information page
- Resident: Enhanced payment history with status badges (ON_TIME, LATE, UNPAID, NOT_REPORTED, OPTED_OUT)

---

### 8. **RBAC & Authentication**
**Current:** Simple role selection (no auth)  
**Needed:**
- User accounts with passwords
- Role levels: Admin, Support, ReadOnlyAdmin, Renter
- Session management
- Password reset flow

**Data Model Addition:**
```json
{
  "users": [
    {
      "user_id": "USR-001",
      "email": "admin@company.com",
      "password_hash": "bcrypt$...",
      "role": "Admin",  // Admin, Support, ReadOnlyAdmin
      "active": true,
      "last_login": "2026-01-15T10:30:00Z"
    }
  ]
}
```

**UI Pages Needed:**
- Login page (replace simple role selection)
- Password reset flow
- User management (Admin only)

---

### 9. **Property & Lease Management**
**Current:** Unit field only  
**Needed:**
- Property hierarchy
- Lease start/end dates
- Lease status
- Multiple residents per unit

**Data Model Addition:**
```json
{
  "properties": [
    {
      "property_id": "PROP-001",
      "property_name": "Main Street Apartments",
      "address": "123 Main Street",
      "units": ["A-101", "B-203", "C-305"],
      "enabled_for_reporting": true
    }
  ],
  "leases": [
    {
      "lease_id": "LEASE-001",
      "property_id": "PROP-001",
      "unit": "A-101",
      "resident_ids": [1],
      "lease_start": "2023-06-15",
      "lease_end": "2024-06-14",
      "status": "active",  // active, expired, terminated
      "rent_amount": 1200.0
    }
  ]
}
```

---

## 🟢 PHASE 2 FEATURES (Future)

### 10. **Advanced Analytics**
- Average days late
- Penetration rate by property
- Trend analysis
- Delinquency rate tracking

### 11. **Alerts & Monitoring**
- Failed run alerts
- Anomaly detection
- Unusual delinquency spikes
- Missing data alerts

### 12. **Resident Education**
- Credit literacy modules
- Budgeting resources
- FAQ section
- Downloadable confirmation letters (PDF)

### 13. **Multi-Tenant Support**
- Separate property management companies
- Branded portals
- Tenant isolation

---

## 📋 IMPLEMENTATION PRIORITY

### **Immediate (Week 1-2):**
1. Reporting Runs/Cycles tracking UI
2. Dispute guidance page for residents
3. "What is Reported" explainer content
4. Basic audit logging for PII views

### **Short-term (Week 3-4):**
5. CSV export functionality
6. Notification preferences
7. Configuration management page
8. Dispute tracking in admin

### **Medium-term (Month 2):**
9. Full RBAC & authentication system
10. Enhanced property/lease management
11. Audit log viewer
12. Advanced filtering/search

### **Long-term (Month 3+):**
13. Analytics dashboard
14. Alerts & monitoring
15. Resident education modules
16. Multi-tenant support

---

## 🎯 QUICK WINS (Can implement today)

1. **Add "What is Reported" section** to resident rent_reporting.html
   - Simple info card explaining only rent is reported
   - List what is NOT reported (fees, utilities, deposits)

2. **Add "Next Reporting Date"** to resident dashboard
   - Calculate based on current date + reporting cadence

3. **Add payment status badges** with standardized statuses:
   - ON_TIME (green)
   - LATE (yellow)
   - UNPAID (red)
   - NOT_REPORTED (gray)
   - OPTED_OUT (gray)

4. **Create placeholder dispute page** for residents
   - Static HTML with dispute process
   - Link to credit bureau dispute pages

5. **Add basic export buttons** (start with client-side CSV generation)
   - Dashboard summary export
   - Resident list export

---

## 🔍 DATA MODEL SUMMARY

**New Entities Needed:**
- `reporting_runs` - Track monthly Metro 2 file generation
- `disputes` - Track resident dispute cases
- `audit_logs` - Security audit trail
- `notification_preferences` - Resident email preferences
- `system_config` - Property and system settings
- `users` - User accounts for RBAC
- `properties` - Property hierarchy
- `leases` - Lease details with start/end dates

**Existing Entities to Enhance:**
- `residents` - Add lease_id, property_id references
- `payments` - Add standardized status enum (ON_TIME, LATE, UNPAID, NOT_REPORTED)

---

## 📄 API ENDPOINTS NEEDED (Future REST API)

### Admin Endpoints:
```
GET  /api/reporting-runs              - List all reporting runs
POST /api/reporting-runs              - Create new run (dry or live)
GET  /api/reporting-runs/{id}         - Run details
GET  /api/disputes                    - List disputes
GET  /api/disputes/{id}               - Dispute details
POST /api/config                      - Update configuration
GET  /api/audit-logs                  - View audit logs
GET  /api/exports/dashboard           - Export dashboard CSV
GET  /api/exports/residents           - Export residents CSV
```

### Resident Endpoints:
```
GET  /api/resident/{id}/timeline      - Payment timeline
GET  /api/resident/{id}/disputes      - My disputes
PUT  /api/resident/{id}/notifications - Update notification prefs
GET  /api/resident/{id}/next-report   - Next scheduled report date
```

---

## ✅ WHAT WE ALREADY HAVE (Good!)

- ✅ Resident enrollment/opt-out flow
- ✅ Payment history tracking
- ✅ Enrollment history timeline
- ✅ Account status tracking (Current/Delinquent)
- ✅ Days late tracking
- ✅ Amount past due tracking
- ✅ Admin resident management
- ✅ Data mismatch handling
- ✅ Payment issue management
- ✅ Dashboard with statistics
- ✅ Masked SSN display (PII protection)
- ✅ Search/filter by property and name

---

## 🎨 UI/UX Enhancements Needed

1. **Status indicators** should use consistent color scheme:
   - Green: ON_TIME, Current, Active
   - Yellow/Orange: LATE, Pending
   - Red: UNPAID, Delinquent, Rejected
   - Gray: NOT_REPORTED, Inactive, Opted Out

2. **Timeline visualization** for reporting history (monthly cards)

3. **Modal confirmations** for sensitive actions (opt-out, disputes)

4. **Loading states** for async operations

5. **Error handling** improvements with clear user messaging

---

This document serves as our roadmap for bringing the portal to industry-standard feature parity.
