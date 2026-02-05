"""
Data loader for resident information from Excel files
Handles SSN decryption and data transformation
"""
import os
import pandas as pd
from datetime import datetime
from utils.encryption import mask_ssn, get_last4_ssn


def load_residents_from_excel(file_path='Resident PII Test.xlsx'):
    """
    Load resident data from Excel file with encrypted SSNs
    Returns list of resident dictionaries compatible with existing app structure
    """
    full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
    
    if not os.path.exists(full_path):
        print(f"Warning: {full_path} not found. Using empty resident list.")
        return []
    
    try:
        # Read Excel file
        df = pd.read_excel(full_path)
        
        # Transform to resident dictionaries
        residents = []
        for idx, row in df.iterrows():
            resident_id = idx + 1
            
            # Extract encrypted SSN and create masked version
            encrypted_ssn = str(row.get('SSN', ''))
            masked_ssn = mask_ssn(encrypted_ssn)
            last4_ssn = get_last4_ssn(encrypted_ssn)
            
            # Get monthly rent for payment generation
            monthly_rent = float(row.get('Monthly Rent', 1500.0))
            
            # Create resident record
            resident = {
                'id': resident_id,
                'account_number': f'ACC2024{resident_id:06d}',
                'name': str(row.get('Name', '')),
                'first_name': str(row.get('Name', '')).split()[0] if row.get('Name', '') else '',
                'last_name': str(row.get('Name', '')).split()[-1] if row.get('Name', '') else '',
                'email': str(row.get('Email', '')),
                'phone': str(row.get('Phone', '')),
                'unit': str(row.get('Unit', '')),
                'unit_number': str(row.get('Unit', '')),
                'property': str(row.get('Property', '48 West')),
                'dob': str(row.get('DOB', '')),
                'address': str(row.get('Address', '')),
                'ssn': masked_ssn,  # Always masked
                'last4_ssn': last4_ssn,
                'encrypted_ssn': encrypted_ssn,  # Store encrypted version for later use
                'credit_score': int(row.get('Credit Score', 650)),
                'lease_start_date': str(row.get('Lease Start', '')),
                'lease_end_date': str(row.get('Lease End', '')),
                'monthly_rent': monthly_rent,
                
                # Account status fields
                'enrolled': True,
                'enrollment_status': 'enrolled',
                'tradeline_created': True,
                'rent_reporting_status': 'active',
                'account_status': 'Current',
                'date_opened': str(row.get('Lease Start', '')),
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': monthly_rent,
                'date_last_payment': datetime.now().strftime('%Y-%m-%d'),
                'date_first_delinquency': None,
                'days_late': 0,
                'highest_credit_amount': monthly_rent,
                'amount_past_due': 0.0,
                'current_balance': 0.0,
                'last_reported': 'January 2026',
                
                # Payment history (generate sample data)
                'payments': generate_sample_payments(resident_id, monthly_rent),
                
                # Enrollment history
                'enrollment_history': [
                    {
                        'action': 'enrolled',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                ],
                
                # Disputes
                'disputes': []
            }
            
            residents.append(resident)
        
        print(f"Loaded {len(residents)} residents from Excel file")
        return residents
        
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_sample_payments(resident_id, monthly_rent):
    """Generate sample payment history for a resident"""
    from datetime import datetime, timedelta
    import random
    
    payments = []
    current_date = datetime.now()
    
    # Generate last 6 months of payments
    for i in range(6):
        payment_date = current_date - timedelta(days=30 * i)
        month = payment_date.strftime('%B %Y')
        
        # Occasionally make a payment late (10% chance)
        is_late = random.random() < 0.1 and i > 0  # Never make current month late
        days_late = random.randint(5, 25) if is_late else 0
        status = 'Late' if is_late and days_late > 0 else 'Paid'
        
        # Late payments might not be reported
        reported = not is_late or days_late < 30
        
        payments.append({
            'month': month,
            'amount': monthly_rent,
            'date_paid': (payment_date + timedelta(days=days_late)).strftime('%Y-%m-%d'),
            'status': status,
            'days_late': days_late,
            'reported': reported,
            'report_date': payment_date.strftime('%Y-%m-%d') if reported else None
        })
    
    return payments
