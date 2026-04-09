"""
Data loader for resident information from Excel files
Handles SSN decryption and data transformation
"""
import os
import pandas as pd
from datetime import datetime, timedelta
from utils.encryption import mask_ssn, get_last4_ssn


def calculate_last_quarter_date():
    """
    Calculate the last quarter end date (Mar 31, Jun 30, Sep 30, Dec 31)
    Credit scores are typically received quarterly
    """
    current_date = datetime.now()
    year = current_date.year
    month = current_date.month
    
    # Determine the last completed quarter
    if month <= 3:
        # Q4 of previous year
        quarter_month = 12
        quarter_year = year - 1
    elif month <= 6:
        # Q1 of current year
        quarter_month = 3
        quarter_year = year
    elif month <= 9:
        # Q2 of current year
        quarter_month = 6
        quarter_year = year
    else:
        # Q3 of current year
        quarter_month = 9
        quarter_year = year
    
    # Get the last day of the quarter month
    if quarter_month in [3, 12]:
        day = 31
    else:
        day = 30
    
    return f"{quarter_year}-{quarter_month:02d}-{day:02d}"


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
                'property_name': str(row.get('Property', '48 West')),  # Alias for template compatibility
                'dob': str(row.get('DOB', '')),
                'address': str(row.get('Address', '')),
                'ssn': masked_ssn,  # Always masked
                'last4_ssn': last4_ssn,
                'encrypted_ssn': encrypted_ssn,  # Store encrypted version for later use
                'credit_score': int(row.get('Credit Score', 650)),
                'credit_score_date': calculate_last_quarter_date(),  # Quarterly credit score update
                'lease_start_date': str(row.get('Lease Start', '')),
                'lease_end_date': str(row.get('Lease End', '')),
                'move_in_date': str(row.get('Lease Start', '')),  # Alias for template compatibility
                'monthly_rent': monthly_rent,
                
                # External identity linking (for Entra External ID)
                'external_oid': str(row.get('External_OID', '')) if pd.notna(row.get('External_OID', '')) else None,
                'external_tenant_id': str(row.get('External_Tenant_ID', '')) if pd.notna(row.get('External_Tenant_ID', '')) else None,
                
                # Account status fields
                'enrolled': True,
                'enrollment_status': 'enrolled',
                'tradeline_created': True,
                'rent_reporting_status': 'Enrolled',  # Match template check
                'account_status': 'Current',
                'date_opened': str(row.get('Lease Start', '')),
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': monthly_rent,
                'date_last_payment': datetime.now().strftime('%Y-%m-%d'),
                'date_first_delinquency': None,
                'days_late': 0,
                'amount_past_due': 0.0,
                'current_balance': 0.0,
                'last_reported': 'Jan 2026',
                
                # Payment history (generate sample data)
                'payments': generate_sample_payments(resident_id, monthly_rent, str(row.get('Name', ''))),
                
                # Enrollment history (enrolled 6 months ago so all payment history shows)
                'enrollment_history': [
                    {
                        'action': 'enrolled',
                        'timestamp': (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')
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


def link_resident_external_oid(resident_id, external_oid, external_tenant_id, file_path='Resident PII Test.xlsx'):
    """
    Link an External ID OID to an existing resident in the Excel file.
    This enables OID-based authentication for future logins.
    
    Args:
        resident_id: The resident's ID (row index + 1)
        external_oid: The Entra External ID object identifier
        external_tenant_id: The Entra tenant ID
        file_path: Path to the Excel file
    
    Returns:
        bool: True if successful, False otherwise
    """
    full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
    
    if not os.path.exists(full_path):
        print(f"Error: {full_path} not found")
        return False
    
    try:
        # Read Excel file
        df = pd.read_excel(full_path)
        
        # Add columns if they don't exist
        if 'External_OID' not in df.columns:
            df['External_OID'] = None
        if 'External_Tenant_ID' not in df.columns:
            df['External_Tenant_ID'] = None
        
        # Update the row (resident_id is 1-based, row index is 0-based)
        row_index = resident_id - 1
        if row_index < 0 or row_index >= len(df):
            print(f"Error: Invalid resident_id {resident_id}")
            return False
        
        df.at[row_index, 'External_OID'] = external_oid
        df.at[row_index, 'External_Tenant_ID'] = external_tenant_id
        
        # Save back to Excel
        df.to_excel(full_path, index=False)
        print(f"🔗 Linked OID {external_oid[:8]}... to resident ID {resident_id}")
        return True
        
    except Exception as e:
        print(f"Error linking OID to resident: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_sample_payments(resident_id, monthly_rent, resident_name=''):
    """Generate sample payment history for a resident"""
    from datetime import datetime, timedelta
    import random
    
    payments = []
    current_date = datetime.now()
    
    # For Alexander Kelly, generate consistent perfect payment history for demo purposes
    if resident_name == 'Alexander Kelly':
        for i in range(6):
            payment_date = current_date - timedelta(days=30 * i)
            month = payment_date.strftime('%b %Y')
            
            payments.append({
                'month': month,
                'amount': monthly_rent,
                'date_paid': payment_date.strftime('%Y-%m-%d'),
                'payment_date': payment_date.strftime('%Y-%m-%d'),
                'status': 'Paid',
                'days_late': 0,
                'reported': True,
                'report_date': payment_date.strftime('%Y-%m-%d')
            })
    else:
        # Generate last 6 months of payments with some randomness for other residents
        for i in range(6):
            payment_date = current_date - timedelta(days=30 * i)
            month = payment_date.strftime('%b %Y')
            
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
                'payment_date': payment_date.strftime('%Y-%m-%d'),  # Track when payment occurred
                'status': status,
                'days_late': days_late,
                'reported': reported,
                'report_date': payment_date.strftime('%Y-%m-%d') if reported else None
            })
    
    return payments
