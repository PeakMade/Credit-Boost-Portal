from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from utils.data_loader import load_residents_from_excel
from utils.sharepoint_data_loader import load_residents_from_sharepoint_list
from utils.excel_export import (create_resident_list_export, create_reporting_runs_export,
                                create_disputes_export, create_audit_logs_export)

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'demo-secret-key-change-in-production')

# Custom Jinja filter for currency formatting with commas
@app.template_filter('currency')
def currency_filter(value):
    """Format number as currency with dollar sign and commas"""
    try:
        return "${:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return "$0.00"

# Custom Jinja filter for date formatting
@app.template_filter('date_format')
def date_format_filter(value):
    """Format date as MM-DD-YY"""
    if not value:
        return ''
    try:
        # Handle different input formats
        if isinstance(value, str):
            # Try parsing YYYY-MM-DD format
            if len(value) >= 10 and value[4] == '-':
                date_obj = datetime.strptime(value[:10], '%Y-%m-%d')
            # Try parsing other common formats
            else:
                date_obj = datetime.strptime(value, '%Y-%m-%d')
        else:
            date_obj = value
        return date_obj.strftime('%m-%d-%y')
    except (ValueError, TypeError, AttributeError):
        return value

# Custom Jinja filter to filter payments during enrollment
@app.template_filter('enrolled_payments')
def enrolled_payments_filter(payments, enrollment_history):
    """Filter payments to only show those that occurred during enrolled periods"""
    if not payments or not enrollment_history:
        return []
    
    # Find the first enrollment date
    enrollment_date = None
    for event in enrollment_history:
        if event.get('action') == 'enrolled':
            enrollment_date = event.get('timestamp')
            break
    
    if not enrollment_date:
        return []
    
    # Parse enrollment date (could be datetime string or date string)
    try:
        if ' ' in enrollment_date:  # datetime format
            enrollment_dt = datetime.strptime(enrollment_date, '%Y-%m-%d %H:%M:%S')
        else:  # date only format
            enrollment_dt = datetime.strptime(enrollment_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return payments  # If we can't parse, return all payments
    
    # Filter payments to only those on or after enrollment date
    filtered_payments = []
    for payment in payments:
        payment_date_str = payment.get('payment_date')
        if payment_date_str:
            try:
                payment_dt = datetime.strptime(payment_date_str, '%Y-%m-%d')
                if payment_dt >= enrollment_dt:
                    filtered_payments.append(payment)
            except (ValueError, TypeError):
                continue
    
    return filtered_payments

# Load test data from JSON file (fallback)
def load_test_data():
    """Load resident data from test_data.json"""
    data_file = os.path.join(os.path.dirname(__file__), 'test_data.json')
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
            return data.get('residents', [])
    except FileNotFoundError:
        print(f"Warning: {data_file} not found. Using empty resident list.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing test_data.json: {e}")
        return []

# In-memory data structures (loaded from Excel with encrypted SSNs)
CURRENT_RESIDENT_ID = 1

# Try to load from Excel first, fallback to JSON if it fails
try:
    residents = load_residents_from_excel('Resident PII Test.xlsx')
    if not residents:
        print("Excel file empty or not found, falling back to JSON")
        residents = load_test_data()
except Exception as e:
    print(f"Error loading Excel file: {e}, falling back to JSON")
    residents = load_test_data()


def get_resident_by_id(resident_id):
    """Get resident by ID"""
    for resident in residents:
        if resident['id'] == resident_id:
            return resident
    return None


def get_last_reported_month(resident):
    """Get the last reported month for a resident"""
    reported_payments = [p for p in resident['payments'] if p.get('reported', False)]
    if reported_payments:
        return reported_payments[0]['month']
    return "N/A"


# Landing / Role selection
@app.route('/')
@app.route('/login')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    # Hardcoded credentials for demo
    if email == 'pbatson@peakmade.com' and password == 'admin':
        session['role'] = 'admin'
        session['user_email'] = email
        return redirect(url_for('admin_dashboard'))
    elif password == 'resident':
        # Check if email matches any resident in the data
        resident_found = None
        for resident in residents:
            if resident.get('email', '').lower() == email.lower():
                resident_found = resident
                break
        
        if resident_found:
            session['role'] = 'resident'
            session['user_email'] = email
            session['resident_id'] = resident_found['id']
            return redirect(url_for('resident_dashboard'))
        else:
            return render_template('landing.html', error='Email not found')
    else:
        return render_template('landing.html', error='Invalid email or password')


@app.route('/select-role', methods=['POST'])
def select_role():
    role = request.form.get('role')
    if role == 'resident':
        session['role'] = 'resident'
        return redirect(url_for('resident_dashboard'))
    elif role == 'admin':
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Please select a role', 'danger')
        return redirect(url_for('landing'))


# ============= RESIDENT ROUTES =============

@app.route('/resident/dashboard')
def resident_dashboard():
    # Get resident from session or default to first resident
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
    # Calculate current reporting cycle (current month)
    current_date = datetime.now()
    current_cycle = current_date.strftime('%b %Y')
    
    # Calculate next reporting run (last day of current month)
    from calendar import monthrange
    last_day = monthrange(current_date.year, current_date.month)[1]
    next_run_date = current_date.replace(day=last_day).strftime('%b %d, %Y')
    
    return render_template('resident/dashboard.html', 
                          resident=resident,
                          current_cycle=current_cycle,
                          next_run_date=next_run_date)


@app.route('/resident/enroll', methods=['GET', 'POST'])
def resident_enroll():
    # Get resident from session or default to first resident
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        dob = request.form.get('dob', '').strip()
        address = request.form.get('address', '').strip()
        last4_ssn = request.form.get('last4_ssn', '').strip()
        
        # Validate against resident record
        if (name.lower() == resident['name'].lower() and
            dob == resident['dob'] and
            address.lower() == resident['address'].lower() and
            last4_ssn == resident['last4_ssn']):
            
            # Match successful - enroll resident
            resident['enrolled'] = True
            resident['enrollment_status'] = 'enrolled'
            resident['tradeline_created'] = True
            resident['enrollment_history'].append({
                'action': 'enrolled',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            flash('Enrollment successful! Your rent payments will now be reported.', 'success')
            return redirect(url_for('resident_enroll_success'))
        else:
            # Mismatch
            flash('We couldn\'t match your information. Please verify and try again or contact support.', 'danger')
            return render_template('resident/enroll.html', 
                                   resident=resident, 
                                   show_form=True,
                                   form_data={
                                       'name': name,
                                       'dob': dob,
                                       'address': address,
                                       'last4_ssn': last4_ssn
                                   })
    
    return render_template('resident/enroll.html', resident=resident, show_form=False)


@app.route('/resident/enroll/success')
def resident_enroll_success():
    return render_template('resident/enroll_success.html')


@app.route('/resident/rent-reporting')
def resident_rent_reporting():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    return render_template('resident/rent_reporting.html', resident=resident)


@app.route('/resident/settings')
def resident_settings():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    return render_template('resident/settings.html', resident=resident)


@app.route('/resident/profile', methods=['GET', 'POST'])
def resident_profile():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        resident['name'] = request.form.get('name', resident['name'])
        resident['dob'] = request.form.get('dob', resident['dob'])
        resident['address'] = request.form.get('address', resident['address'])
        resident['last4_ssn'] = request.form.get('last4_ssn', resident['last4_ssn'])
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('resident_rent_reporting'))
    
    return render_template('resident/profile.html', resident=resident)


@app.route('/resident/opt-out', methods=['GET', 'POST'])
def resident_opt_out():
    resident_id = session.get('resident_id', CURRENT_RESIDENT_ID)
    resident = get_resident_by_id(resident_id)
    
    if request.method == 'POST':
        resident['enrolled'] = False
        resident['enrollment_status'] = 'not enrolled'
        resident['enrollment_history'].append({
            'action': 'revoked consent',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        flash('You have successfully opted out. Future rent payments will not be reported.', 'info')
        return redirect(url_for('resident_rent_reporting'))
    
    return render_template('resident/opt_out.html', resident=resident)


# ============= ADMIN ROUTES =============

@app.route('/admin/dashboard')
def admin_dashboard():
    # Calculate statistics from resident data
    total_residents = len(residents)
    enrolled_residents = [r for r in residents if r.get('enrolled', False)]
    not_enrolled_residents = [r for r in residents if not r.get('enrolled', False)]
    # Calculate payment statistics
    current_accounts = [r for r in residents if r.get('account_status', '') == 'Current']
    delinquent_accounts = [r for r in residents if 'Delinquent' in r.get('account_status', '')]
    # Calculate total amounts
    total_past_due = sum(r.get('amount_past_due', 0) for r in residents)
    total_monthly_revenue = sum(r.get('scheduled_monthly_payment', 0) for r in residents)
    # Calculate reporting statistics
    total_payments = sum(len(r.get('payments', [])) for r in residents)
    reported_payments = sum(1 for r in residents for p in r.get('payments', []) if p.get('reported', False))
    stats = {
        'total_residents': total_residents,
        'enrolled_count': len(enrolled_residents),
        'not_enrolled_count': len(not_enrolled_residents),
        'current_accounts': len(current_accounts),
        'delinquent_accounts': len(delinquent_accounts),
        'total_past_due': total_past_due,
        'total_monthly_revenue': total_monthly_revenue,
        'total_payments': total_payments,
        'reported_payments': reported_payments
    }
    return render_template('admin/dashboard.html', residents=residents, stats=stats)


@app.route('/admin/rent-reporting')
def admin_rent_reporting():
    search_query = request.args.get('search', '').lower()
    data_source = request.args.get('data_source', 'test')  # 'test' or 'sharepoint'
    
    # Load data based on selected source
    if data_source == 'sharepoint':
        # Load from SharePoint List
        source_residents = load_residents_from_sharepoint_list()
        if not source_residents:
            flash('Failed to load SharePoint data. Falling back to test data.', 'warning')
            source_residents = residents
    else:
        # Use test data
        source_residents = residents
    
    filtered_residents = source_residents
    
    # Filter by search query (searches name, property, and unit)
    if search_query:
        filtered_residents = [
            r for r in filtered_residents 
            if search_query in r['name'].lower() or 
               search_query in r.get('property', '').lower() or 
               search_query in r.get('unit', '').lower()
        ]
    
    # Add last reported month to each resident
    residents_with_info = []
    for r in filtered_residents:
        resident_copy = r.copy()
        resident_copy['last_reported'] = get_last_reported_month(r)
        residents_with_info.append(resident_copy)
    
    # Calculate current reporting cycle (current month)
    current_date = datetime.now()
    current_cycle = current_date.strftime('%b %Y')
    
    # Calculate next reporting run (last day of current month)
    from calendar import monthrange
    last_day = monthrange(current_date.year, current_date.month)[1]
    next_run_date = current_date.replace(day=last_day).strftime('%b %d, %Y')
    
    return render_template('admin/rent_reporting.html', 
                          residents=residents_with_info, 
                          current_cycle=current_cycle,
                          next_run_date=next_run_date,
                          data_source=data_source)


@app.route('/admin/resident/<int:resident_id>')
def admin_resident_detail(resident_id):
    data_source = request.args.get('data_source', 'test')  # 'test' or 'sharepoint'
    
    # Load data based on selected source
    if data_source == 'sharepoint':
        # Load from SharePoint List
        source_residents = load_residents_from_sharepoint_list()
        if not source_residents:
            flash('Failed to load SharePoint data. Falling back to test data.', 'warning')
            source_residents = residents
    else:
        # Use test data
        source_residents = residents
    
    # Find the specific resident
    resident = None
    for r in source_residents:
        if r['id'] == resident_id:
            resident = r
            break
    
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting', data_source=data_source))
    
    return render_template('admin/resident_detail.html', resident=resident, data_source=data_source)


@app.route('/admin/resident/<int:resident_id>/data-mismatch', methods=['GET', 'POST'])
def admin_data_mismatch(resident_id):
    resident = get_resident_by_id(resident_id)
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'fix':
            flash('Data has been corrected successfully.', 'success')
        elif action == 'notify':
            flash('Resident has been notified to update their information.', 'info')
        elif action == 'escalate':
            flash('Issue has been escalated to support team.', 'warning')
        
        return redirect(url_for('admin_resident_detail', resident_id=resident_id))
    
    # Simulate mismatch data
    mismatch_data = {
        'ssn_bureau': '****1111',
        'ssn_system': f"****{resident['last4_ssn']}",
        'name_bureau': resident['name'].upper(),
        'name_system': resident['name'],
        'dob_bureau': resident['dob'],
        'dob_system': resident['dob']
    }
    
    return render_template('admin/data_mismatch.html', 
                          resident=resident, 
                          mismatch_data=mismatch_data)


@app.route('/admin/resident/<int:resident_id>/payment-issue', methods=['GET', 'POST'])
def admin_payment_issue(resident_id):
    resident = get_resident_by_id(resident_id)
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        month = request.form.get('month')
        new_status = request.form.get('new_status')
        
        if action == 'change_status' and month and new_status:
            # Find and update payment
            for payment in resident['payments']:
                if payment['month'] == month:
                    payment['status'] = new_status
                    flash(f'Payment status for {month} updated to {new_status}.', 'success')
                    break
        elif action == 'confirm':
            flash('Payment status confirmed.', 'success')
        
        return redirect(url_for('admin_payment_issue', resident_id=resident_id))
    
    return render_template('admin/payment_issue.html', resident=resident)


@app.route('/admin/reporting-runs')
def admin_reporting_runs():
    runs = [
        {
            'id': 'RUN-2026-001',
            'date': '2026-01-20 14:30:00',
            'type': 'Monthly Full',
            'period': 'January 2026',
            'accounts': 3,
            'status': 'Completed',
            'file': 'metro2_jan2026.dat'
        },
        {
            'id': 'RUN-2025-012',
            'date': '2025-12-20 15:15:00',
            'type': 'Monthly Full',
            'period': 'December 2025',
            'accounts': 3,
            'status': 'Completed',
            'file': 'metro2_dec2025.dat'
        },
        {
            'id': 'RUN-2025-011',
            'date': '2025-11-22 10:45:00',
            'type': 'Correction',
            'period': 'November 2025',
            'accounts': 1,
            'status': 'Completed',
            'file': 'metro2_nov2025_corr.dat'
        },
        {
            'id': 'RUN-2025-010',
            'date': '2025-11-20 14:00:00',
            'type': 'Monthly Full',
            'period': 'November 2025',
            'accounts': 3,
            'status': 'Failed',
            'file': None
        },
        {
            'id': 'RUN-2025-009',
            'date': '2025-10-20 13:30:00',
            'type': 'Monthly Full',
            'period': 'October 2025',
            'accounts': 2,
            'status': 'Completed',
            'file': 'metro2_oct2025.dat'
        }
    ]
    successful_runs = len([r for r in runs if r['status'] == 'Completed'])
    failed_runs = len([r for r in runs if r['status'] == 'Failed'])
    total_accounts = sum(r['accounts'] for r in runs if r['status'] == 'Completed')
    return render_template('admin/reporting_runs.html',
                          runs=runs,
                          successful_runs=successful_runs,
                          failed_runs=failed_runs,
                          total_accounts=total_accounts)

@app.route('/admin/disputes')
def admin_disputes():
    import random
    from datetime import timedelta
    
    # Generate realistic disputes with real residents and dynamic due dates
    current_date = datetime.now()
    disputes = []
    
    # Create 15 sample disputes (only Open and In Progress)
    dispute_types = ['Data Mismatch', 'Payment Error', 'Identity Dispute', 'Incorrect Amount', 'Late Payment Dispute']
    statuses = ['Open', 'Open', 'Open', 'In Progress', 'In Progress']
    
    for i in range(15):
        # Random case ID
        case_id = f"DSP-{random.randint(1000, 9999)}"
        
        # Assign a random resident
        resident = random.choice(residents)
        
        # Random date filed (between 5 and 60 days ago)
        days_ago = random.randint(5, 60)
        date_filed = (current_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        # Random due date (between 1 and 30 days from today)
        days_until_due = random.randint(1, 30)
        due_date = (current_date + timedelta(days=days_until_due)).strftime('%Y-%m-%d')
        
        # Calculate priority based on days remaining (changed labels)
        if days_until_due >= 20:
            priority = 'Low'  # was Medium
        elif days_until_due >= 10:
            priority = 'Medium'  # was High
        else:
            priority = 'High'  # was Critical
        
        # Random status (no resolved)
        status = random.choice(statuses)
        
        disputes.append({
            'id': case_id,
            'date_filed': date_filed,
            'due_date': due_date,
            'days_until_due': days_until_due,
            'resident': f"{resident.get('name')} - Unit {resident.get('unit')}",
            'resident_id': resident.get('id'),
            'type': random.choice(dispute_types),
            'priority': priority,
            'status': status,
            'details': f"Dispute regarding {random.choice(['rent amount', 'payment date', 'account information', 'reporting accuracy'])}"
        })
    
    # Sort by priority (High first, then Medium, Low) and then by due date
    priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
    disputes.sort(key=lambda x: (priority_order.get(x['priority'], 99), x['due_date']))
    
    open_disputes = len([d for d in disputes if d['status'] == 'Open'])
    in_progress_disputes = len([d for d in disputes if d['status'] == 'In Progress'])
    resolved_disputes = 0  # No resolved disputes
    
    return render_template('admin/disputes.html',
                          disputes=disputes,
                          open_disputes=open_disputes,
                          in_progress_disputes=in_progress_disputes,
                          resolved_disputes=resolved_disputes)

@app.route('/admin/audit-logs')
def admin_audit_logs():
    audit_logs = [
        {'id': 1, 'timestamp': '2026-01-10 10:00:00', 'user': 'admin', 'action': 'Viewed resident PII', 'details': 'Jane Doe'},
        {'id': 2, 'timestamp': '2026-01-11 14:30:00', 'user': 'admin', 'action': 'Exported report', 'details': 'Monthly Metro2'},
        {'id': 3, 'timestamp': '2026-01-12 09:15:00', 'user': 'admin', 'action': 'Resolved dispute', 'details': 'D-001'}
    ]
    return render_template('admin/audit_logs.html', audit_logs=audit_logs)

# Excel Export Routes
@app.route('/admin/export/residents', methods=['GET', 'POST'])
def export_residents():
    """Export resident list to Excel"""
    if request.method == 'POST':
        # Get filtered resident IDs from POST data
        import json
        resident_ids_json = request.form.get('resident_ids', '[]')
        resident_ids = json.loads(resident_ids_json)
        
        # Convert to integers
        resident_ids = [int(id) for id in resident_ids]
        
        # Filter residents by IDs
        filtered_residents = [r for r in residents if r.get('id') in resident_ids]
    else:
        # No filter - export all enrolled residents
        filtered_residents = [r for r in residents if r.get('enrollment_status', '').lower() == 'enrolled' or r.get('enrolled') == True]
    
    excel_file = create_resident_list_export(filtered_residents)
    filename = f"residents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/reporting-runs')
def export_reporting_runs():
    """Export reporting runs to Excel"""
    # Get the same data as the reporting runs page
    runs = [
        {'id': 'RUN-2026-001', 'date': '2026-02-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 147, 'success_rate': '99.3%', 'notes': 'Successfully processed'},
        {'id': 'RUN-2026-002', 'date': '2026-01-15', 'type': 'Supplemental', 'status': 'Completed', 'records': 23, 'success_rate': '100%', 'notes': 'New enrollments'},
        {'id': 'RUN-2026-003', 'date': '2026-01-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 145, 'success_rate': '98.6%', 'notes': '2 payment disputes pending'},
        {'id': 'RUN-2025-012', 'date': '2025-12-01', 'type': 'Monthly Metro2', 'status': 'Completed', 'records': 142, 'success_rate': '99.3%', 'notes': 'Year-end reporting'},
    ]
    excel_file = create_reporting_runs_export(runs)
    filename = f"reporting_runs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/disputes')
def export_disputes():
    """Export disputes to Excel"""
    disputes = [
        {'id': 'D-001', 'date': '2026-02-03', 'resident': 'John Smith - Unit 301', 'issue': 'Incorrect rent amount', 'status': 'Open', 'priority': 'High', 'details': 'Resident claims reported amount is $50 higher than actual rent'},
        {'id': 'D-002', 'date': '2026-01-28', 'resident': 'Sarah Johnson - Unit 205', 'issue': 'Late payment dispute', 'status': 'In Progress', 'priority': 'Medium', 'details': 'Payment was made on time but not processed until the 6th'},
        {'id': 'D-003', 'date': '2026-01-15', 'resident': 'Mike Davis - Unit 102', 'issue': 'Payment not reported', 'status': 'Resolved', 'priority': 'High', 'details': 'December payment was not included in monthly report. Added to supplemental file.'},
    ]
    excel_file = create_disputes_export(disputes)
    filename = f"disputes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/export/audit-logs')
def export_audit_logs():
    """Export audit logs to Excel"""
    audit_logs = [
        {'id': 1, 'timestamp': '2026-01-10 10:00:00', 'user': 'admin', 'action': 'Viewed resident PII', 'details': 'Jane Doe'},
        {'id': 2, 'timestamp': '2026-01-11 14:30:00', 'user': 'admin', 'action': 'Exported report', 'details': 'Monthly Metro2'},
        {'id': 3, 'timestamp': '2026-01-12 09:15:00', 'user': 'admin', 'action': 'Resolved dispute', 'details': 'D-001'}
    ]
    excel_file = create_audit_logs_export(audit_logs)
    filename = f"audit_logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(excel_file, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    # Get configuration from environment variables
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
