"""
SharePoint document library data loader for resident information
Reads Excel file from SharePoint document library
"""
import os
import io
from datetime import datetime, timedelta
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential
from dotenv import load_dotenv
from utils.encryption import mask_ssn, get_last4_ssn
import pandas as pd
import random

load_dotenv()


def load_residents_from_sharepoint():
    """
    Load resident data from Excel file in SharePoint document library
    Returns list of resident dictionaries compatible with existing app structure
    """
    
    site_url = os.environ.get('SHAREPOINT_SITE_URL', 'https://peakcampus.sharepoint.com/sites/BaseCampApps')
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    
    # SharePoint document library and file path
    library_name = "Credit Boost Portal"
    file_name = "Resident PII Test.xlsx"
    
    if not all([client_id, client_secret]):
        print("Warning: Azure credentials not found in .env file")
        return []
    
    try:
        # Connect to SharePoint with client credentials
        print(f"Connecting to SharePoint document library: {library_name}")
        credentials = ClientCredential(client_id, client_secret)
        ctx = ClientContext(site_url).with_credentials(credentials)
        
        # Get the file from document library
        file_url = f"/sites/BaseCampApps/{library_name}/{file_name}"
        file = ctx.web.get_file_by_server_relative_url(file_url)
        
        # Download file content
        download = file.download()
        ctx.execute_query()
        
        print(f"✓ Downloaded {file_name} from SharePoint")
        
        # Read Excel file from bytes
        excel_data = io.BytesIO(download.content)
        df = pd.read_excel(excel_data)
        
        print(f"✓ Loaded {len(df)} residents from SharePoint Excel file")
        
        # Transform to resident dictionaries (same as Excel loader)
        residents = []
        for idx, row in df.iterrows():
            resident_id = idx + 1
            
            # Extract encrypted SSN and create masked version
            encrypted_ssn = str(row['encrypted_ssn'])
            masked_ssn = mask_ssn(encrypted_ssn)
            last4_ssn = get_last4_ssn(encrypted_ssn)
            
            # Get monthly rent
            monthly_rent = float(row['monthly_rent'])
            
            # Parse name into first/last
            full_name = row['name']
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[-1] if len(name_parts) > 1 else ''
            
            # Create resident record
            resident = {
                'id': resident_id,
                'account_number': row['account_number'],
                'name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'email': row['email'],
                'phone': row.get('phone', ''),
                'unit': str(row['unit']),
                'unit_number': str(row['unit']),
                'property': row['property'],
                'dob': row.get('dob', ''),
                'address': row.get('address', ''),
                'ssn': masked_ssn,
                'last4_ssn': last4_ssn,
                'encrypted_ssn': encrypted_ssn,
                'credit_score': int(row['credit_score']),
                'lease_start_date': row['lease_start'].strftime('%Y-%m-%d') if pd.notna(row['lease_start']) else '',
                'lease_end_date': row['lease_end'].strftime('%Y-%m-%d') if pd.notna(row['lease_end']) else '',
                'monthly_rent': monthly_rent,
                
                # Account status fields
                'enrolled': True,
                'enrollment_status': 'enrolled',
                'tradeline_created': True,
                'rent_reporting_status': 'active',
                'account_status': row.get('status', 'Current'),
                'date_opened': row['lease_start'].strftime('%Y-%m-%d') if pd.notna(row['lease_start']) else '',
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': monthly_rent,
                'date_last_payment': datetime.now().strftime('%Y-%m-%d'),
                'date_first_delinquency': None,
                'days_late': int(row.get('days_late', 0)),
                'highest_credit_amount': monthly_rent,
                'amount_past_due': float(row.get('amount_past_due', 0.0)),
                'current_balance': float(row.get('current_balance', 0.0)),
                'last_reported': 'January 2026',
                
                # Payment history
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
        
        print(f"✓ Successfully loaded {len(residents)} residents from SharePoint")
        return residents
        
    except Exception as e:
        print(f"Error loading from SharePoint: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_sample_payments(resident_id, monthly_rent):
    """Generate sample payment history for a resident"""
    payments = []
    current_date = datetime.now()
    
    # Generate last 6 months of payments
    for i in range(6):
        payment_date = current_date - timedelta(days=30 * i)
        month = payment_date.strftime('%B %Y')
        
        # Occasionally make a payment late (10% chance)
        is_late = random.random() < 0.1 and i > 0
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
