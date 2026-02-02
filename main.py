from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'demo-secret-key-change-in-production'

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

def save_test_data():
    """Save resident data back to test_data.json"""
    data_file = os.path.join(os.path.dirname(__file__), 'test_data.json')
    try:
        with open(data_file, 'w') as f:
            json.dump({'residents': residents}, f, indent=2)
        print(f"Data saved to {data_file}")
    except Exception as e:
        print(f"Error saving test_data.json: {e}")

# In-memory data structures (loaded from test_data.json)
CURRENT_RESIDENT_ID = 1
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
    resident = get_resident_by_id(CURRENT_RESIDENT_ID)
    return render_template('resident/dashboard.html', resident=resident)


@app.route('/resident/enroll', methods=['GET', 'POST'])
def resident_enroll():
    resident = get_resident_by_id(CURRENT_RESIDENT_ID)
    
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
            
            # Save changes to file
            save_test_data()
            
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
    resident = get_resident_by_id(CURRENT_RESIDENT_ID)
    return render_template('resident/rent_reporting.html', resident=resident)


@app.route('/resident/profile', methods=['GET', 'POST'])
def resident_profile():
    resident = get_resident_by_id(CURRENT_RESIDENT_ID)
    
    if request.method == 'POST':
        resident['name'] = request.form.get('name', resident['name'])
        resident['dob'] = request.form.get('dob', resident['dob'])
        resident['address'] = request.form.get('address', resident['address'])
        resident['last4_ssn'] = request.form.get('last4_ssn', resident['last4_ssn'])
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('resident_dashboard'))
    
    return render_template('resident/profile.html', resident=resident)


@app.route('/resident/opt-out', methods=['GET', 'POST'])
def resident_opt_out():
    resident = get_resident_by_id(CURRENT_RESIDENT_ID)
    
    if request.method == 'POST':
        resident['enrolled'] = False
        resident['enrollment_status'] = 'not_enrolled'
        resident['enrollment_history'].append({
            'action': 'revoked consent',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Save changes to file
        save_test_data()
        
        flash('You have successfully opted out. Future rent payments will not be reported.', 'info')
        return redirect(url_for('resident_dashboard'))
    
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
    property_query = request.args.get('property', '').lower()
    name_query = request.args.get('name', '').lower()
    
    filtered_residents = residents
    
    # Filter by property (unit)
    if property_query:
        filtered_residents = [
            r for r in filtered_residents 
            if property_query in r['unit'].lower()
        ]
    
    # Filter by name
    if name_query:
        filtered_residents = [
            r for r in filtered_residents 
            if name_query in r['name'].lower()
        ]
    
    # Add last reported month to each resident
    residents_with_info = []
    for r in filtered_residents:
        resident_copy = r.copy()
        resident_copy['last_reported'] = get_last_reported_month(r)
        residents_with_info.append(resident_copy)
    
    return render_template('admin/rent_reporting.html', 
                          residents=residents_with_info, 
                          property_query=property_query,
                          name_query=name_query)


@app.route('/admin/resident/<int:resident_id>')
def admin_resident_detail(resident_id):
    resident = get_resident_by_id(resident_id)
    if not resident:
        flash('Resident not found', 'danger')
        return redirect(url_for('admin_rent_reporting'))
    
    return render_template('admin/resident_detail.html', resident=resident)


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
    """Reporting runs page for Metro 2 file generation"""
    from datetime import datetime, timedelta
    
    # Sample reporting runs data
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
    """Dispute management page"""
    from datetime import datetime, timedelta
    
    # Sample dispute data
    disputes = [
        {
            'case_id': 'DSP-2026-003',
            'date_filed': '2026-01-24',
            'resident_id': 1,
            'resident_name': 'John Smith',
            'type': 'Data Mismatch',
            'priority': 'High',
            'status': 'Open',
            'assigned_to': 'Admin User',
            'due_date': '2026-02-07',
            'is_overdue': False
        },
        {
            'case_id': 'DSP-2026-002',
            'date_filed': '2026-01-20',
            'resident_id': 2,
            'resident_name': 'Sarah Johnson',
            'type': 'Payment Error',
            'priority': 'Critical',
            'status': 'In Progress',
            'assigned_to': 'Compliance Team',
            'due_date': '2026-01-27',
            'is_overdue': False
        },
        {
            'case_id': 'DSP-2026-001',
            'date_filed': '2026-01-15',
            'resident_id': 3,
            'resident_name': 'Michael Chen',
            'type': 'Identity Dispute',
            'priority': 'Medium',
            'status': 'Resolved',
            'assigned_to': 'Support Team',
            'due_date': '2026-01-29',
            'is_overdue': False
        },
        {
            'case_id': 'DSP-2025-045',
            'date_filed': '2025-12-10',
            'resident_id': 1,
            'resident_name': 'John Smith',
            'type': 'Reporting Error',
            'priority': 'Low',
            'status': 'Closed',
            'assigned_to': 'Admin User',
            'due_date': '2025-12-24',
            'is_overdue': False
        }
    ]
    
    open_disputes = len([d for d in disputes if d['status'] == 'Open'])
    in_progress_disputes = len([d for d in disputes if d['status'] == 'In Progress'])
    resolved_disputes = len([d for d in disputes if d['status'] in ['Resolved', 'Closed']])
    
    return render_template('admin/disputes.html', 
                         disputes=disputes,
                         open_disputes=open_disputes,
                         in_progress_disputes=in_progress_disputes,
                         resolved_disputes=resolved_disputes,
                         all_residents=residents)


@app.route('/admin/audit-logs')
def admin_audit_logs():
    """Audit logs page for security and compliance"""
    from datetime import datetime, timedelta
    
    # Sample audit log data
    logs = [
        {
            'id': 'LOG-' + str(i).zfill(6),
            'timestamp': (datetime.now() - timedelta(minutes=i*15)).strftime('%Y-%m-%d %H:%M:%S'),
            'severity': ['Info', 'Info', 'Warning', 'Info', 'Info', 'Critical', 'Info', 'Info'][i % 8],
            'event_type': ['Login', 'Data Access', 'Data Change', 'Report', 'Logout', 'Security', 'Login', 'Data Access'][i % 8],
            'user': ['Admin User', 'Admin User', 'System', 'Admin User', 'Admin User', 'System', 'API Service', 'Admin User'][i % 8],
            'ip_address': ['192.168.1.100', '192.168.1.100', '127.0.0.1', '192.168.1.100', '192.168.1.100', '10.0.0.5', '192.168.1.50', '192.168.1.100'][i % 8],
            'description': [
                'User logged in successfully',
                'Accessed resident profile: John Smith',
                'Updated payment status for resident ID: 2',
                'Generated Metro 2 reporting file for January 2026',
                'User logged out',
                'Failed login attempt detected from unknown IP',
                'API authentication successful',
                'Viewed resident list'
            ][i % 8]
        }
        for i in range(25)
    ]
    
    successful_logins = len([l for l in logs if l['event_type'] == 'Login'])
    data_changes = len([l for l in logs if l['event_type'] == 'Data Change'])
    security_events = len([l for l in logs if l['severity'] == 'Critical' or l['event_type'] == 'Security'])
    
    return render_template('admin/audit_logs.html', 
                         logs=logs,
                         successful_logins=successful_logins,
                         data_changes=data_changes,
                         security_events=security_events)


if __name__ == '__main__':
    import sys
    try:
        print("Starting Flask application...")
        print(f"Python version: {sys.version}")
        print(f"Residents loaded: {len(residents)}")
        print("Attempting to start server on http://127.0.0.1:5000")
        # Use simple server without threading to avoid network drive issues
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"ERROR starting Flask: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
