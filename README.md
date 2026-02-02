# Credit Boost Rent Reporting Portal

A Flask-based web application for managing rent reporting with separate resident and admin interfaces.

## Current Status

This is an **MVP (Minimum Viable Product)** implementation with core rent reporting functionality. See [FEATURE_GAPS_AND_ROADMAP.md](FEATURE_GAPS_AND_ROADMAP.md) for a comprehensive list of features needed to reach industry-standard parity with solutions like RentPlus, Esusu, and Experian RentBureau.

## Features Implemented ✅

### Resident Portal
- Enroll in rent reporting with identity verification
- View payment history with delinquency tracking
- See reporting status (reported to bureaus, delinquent indicators)
- Update personal information
- Opt-out of rent reporting at any time
- View account summary (balance, past due, payment schedule)
- Track enrollment history

### Admin Portal
- Dashboard with real-time statistics (enrollment, payments, delinquency)
- View and search all residents by name or property
- Comprehensive resident detail view with:
  - Personal information (PII masked)
  - Account status and payment history
  - Days late tracking
  - Delinquency reporting
- Handle data mismatch issues
- Manage payment status corrections
- Enrollment history tracking

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Run the Flask app:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://127.0.0.1:5000
```

3. Choose your role:
   - **Resident**: Access the resident portal (demo user: Jane Doe)
   - **Admin**: Access the admin dashboard

## Key Features Needed (See Roadmap)

Based on industry-standard rent reporting portals, the following MVP features are still needed:

### Critical Gaps 🔴
1. **Reporting Runs/Cycles Management** - Track Metro 2 file generation and submission
2. **Dispute Tracking & Guidance** - Help residents dispute inaccurate reporting
3. **Audit Logging** - Track all sensitive data access and actions
4. **Authentication & RBAC** - Real user accounts with role-based permissions
5. **Configuration Management** - Property-level settings and controls
6. **CSV Exports** - Export dashboard and resident data
7. **Notification Preferences** - Email alerts for residents

See [FEATURE_GAPS_AND_ROADMAP.md](FEATURE_GAPS_AND_ROADMAP.md) for detailed implementation plan.

## Demo Data

The application loads test data from `test_data.json`:
- 3 residents with payment history
- Various enrollment statuses
- Multiple payment statuses (Paid, Late, Unpaid)
- Delinquency tracking examples

## Project Structure

```
Credit Boost Portal/
├── main.py                         # Main Flask application
├── app.py                          # (deprecated - use main.py)
├── test_data.json                  # Test resident data
├── requirements.txt                # Python dependencies
├── FEATURE_GAPS_AND_ROADMAP.md     # Implementation roadmap
├── templates/
│   ├── base.html                   # Base template with Bootstrap
│   ├── landing.html                # Role selection page
│   ├── resident/
│   │   ├── dashboard.html          # Resident dashboard
│   │   ├── enroll.html             # Enrollment flow
│   │   ├── enroll_success.html     # Enrollment confirmation
│   │   ├── rent_reporting.html     # Payment history view
│   │   ├── profile.html            # Update personal info
│   │   └── opt_out.html            # Opt-out confirmation
│   └── admin/
│       ├── dashboard.html          # Admin dashboard
│       ├── rent_reporting.html     # Resident list
│       ├── resident_detail.html    # Detailed resident view
│       ├── data_mismatch.html      # Handle data mismatches
│       └── payment_issue.html      # Manage payment issues
└── README.md                       # This file
```

## Technology Stack

- **Backend**: Python 3 + Flask
- **Templates**: Jinja2
- **Frontend**: Bootstrap 5.3 (CDN)
- **Icons**: Bootstrap Icons
- **Data Storage**: In-memory (Python lists/dicts)

## Important Notes

- ⚠️ **This is a demo/MVP application** - Not production-ready
- ⚠️ **No real authentication** - Currently uses simple role selection
- ⚠️ **In-memory data storage** - Data loaded from JSON, resets on restart
- ⚠️ **No database** - For MVP only, will need PostgreSQL for production
- ⚠️ **No audit logging** - Security feature needed for production
- ✅ **PII Protection** - SSN is properly masked in UI
- ✅ **Data Separation** - Test data in separate JSON file for easy management

## Next Steps

1. Review [FEATURE_GAPS_AND_ROADMAP.md](FEATURE_GAPS_AND_ROADMAP.md)
2. Implement Quick Wins (dispute guidance, "what is reported" explainer)
3. Build Reporting Runs tracking system
4. Implement authentication and RBAC
5. Add audit logging for security
6. Migrate to PostgreSQL database
