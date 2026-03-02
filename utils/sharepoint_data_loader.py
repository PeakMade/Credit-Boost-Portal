"""
SharePoint document library data loader for resident information
Reads Excel file from SharePoint document library or SharePoint List
Uses Microsoft Graph API for authentication and data access
"""
import os
import io
from datetime import datetime, timedelta
import msal
import requests
from dotenv import load_dotenv
from utils.encryption import mask_ssn, get_last4_ssn
import pandas as pd
import random

load_dotenv()


def load_statements_from_sharepoint_list(access_token, site_id):
    """
    Load payment statements from SharePoint List: Credit Boost - Statements
    List ID: 15cdc70e-ba08-4f9b-9ba2-79d66e8c6552
    Returns dictionary mapping Resident_ID to list of payment statements
    """
    
    list_id = '15cdc70e-ba08-4f9b-9ba2-79d66e8c6552'
    
    try:
        # Get list items using Microsoft Graph API
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print(f"Loading items from SharePoint List: Credit Boost - Statements")
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        print(f"✓ Loaded {len(items)} statement records from SharePoint List")
        
        # Debug: Show first item's fields
        if items:
            print(f"DEBUG - First statement item fields: {list(items[0].get('fields', {}).keys())}")
            print(f"DEBUG - First statement item field values: {items[0].get('fields', {})}")
        
        # Parse dates helper function
        def parse_sp_date(date_val):
            if not date_val:
                return ''
            if isinstance(date_val, datetime):
                return date_val.strftime('%Y-%m-%d')
            if isinstance(date_val, str):
                try:
                    parsed = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                    return parsed.strftime('%Y-%m-%d')
                except:
                    try:
                        if 'T' in date_val:
                            return date_val.split('T')[0]
                        return date_val
                    except:
                        return date_val
            return ''
        
        # Group statements by Resident_ID
        statements_by_resident = {}
        
        for idx, item in enumerate(items):
            fields = item.get("fields", {})
            
            # Get Resident ID - try different field variations and normalize to string
            resident_id_raw = fields.get('ResidentID', fields.get('Resident_x0020_ID', fields.get('ID', '')))
            resident_id = str(resident_id_raw).strip() if resident_id_raw else ''
            
            if not resident_id or resident_id == '0':
                if idx < 3:
                    print(f"DEBUG - Statement {idx}: No valid Resident ID found, skipping. Fields: {list(fields.keys())}")
                continue
            
            if idx < 3:
                print(f"DEBUG - Statement {idx}: Resident ID = '{resident_id}' (type: {type(resident_id_raw)})")
            
            # Debug: Show all available fields for first statement
            if idx == 0:
                print(f"DEBUG - First statement all field names and values:")
                for field_name, field_value in fields.items():
                    print(f"  {field_name}: {field_value}")
            
            # Parse payment data using actual SharePoint field names
            # Payment Date
            payment_date = parse_sp_date(
                fields.get('LastPaymentDate') or 
                fields.get('Payment_x0020_Date') or 
                fields.get('PaymentDate') or
                ''
            )
            
            # Amount Paid
            amount_paid = (
                fields.get('ActualMonthlyPayment') or 
                fields.get('Amount_x0020_Paid') or 
                fields.get('AmountPaid') or
                0
            )
            
            # Payment Status - derive from days delinquent if not explicitly set
            days_delinquent = fields.get('DaysDelinquent', 0)
            payment_status = (
                fields.get('Payment_x0020_Status') or 
                fields.get('PaymentStatus') or 
                fields.get('Status') or
                ('Late' if days_delinquent > 0 else 'Paid')
            )
            
            # Days Late
            days_late = int(days_delinquent) if days_delinquent else 0
            
            # Reported
            reported = fields.get('Reported', True)
            
            # Scheduled Monthly Payment (for this statement)
            scheduled_payment = fields.get('ScheduledMonthlyPayment', 0)
            
            # Amount Past Due (from SharePoint)
            amount_past_due = fields.get('AmountPastDue', 0)
            
            # Current Balance (from SharePoint)
            current_balance = fields.get('CurrentBalance', 0)
            
            if idx < 3:
                print(f"DEBUG - Statement {idx}: Date={payment_date}, Amount={amount_paid}, Status={payment_status}, Days Late={days_late}, Scheduled={scheduled_payment}, Past Due={amount_past_due}")
            
            # Always derive month from payment_date for consistency
            payment_month = ''
            if payment_date:
                try:
                    date_obj = datetime.strptime(payment_date, '%Y-%m-%d')
                    payment_month = date_obj.strftime('%b %Y')  # Abbreviated month (Jan, Feb, etc.)
                except Exception as e:
                    print(f"Warning: Could not parse payment date '{payment_date}': {e}")
            
            # Create payment record
            payment = {
                'month': payment_month,
                'amount': float(amount_paid) if amount_paid else 0.0,
                'date_paid': payment_date,
                'status': payment_status,
                'days_late': int(days_late) if days_late else 0,
                'reported': bool(reported),
                'report_date': payment_date if reported else None,
                'scheduled_payment': float(scheduled_payment) if scheduled_payment else 0.0,
                'amount_past_due': float(amount_past_due) if amount_past_due else 0.0,
                'current_balance': float(current_balance) if current_balance else 0.0
            }
            
            # Add to resident's statements (use string key for consistency)
            resident_id_key = str(resident_id)
            if resident_id_key not in statements_by_resident:
                statements_by_resident[resident_id_key] = []
            statements_by_resident[resident_id_key].append(payment)
        
        # Sort each resident's payments by date (most recent first)
        for resident_id in statements_by_resident:
            statements_by_resident[resident_id].sort(
                key=lambda p: p['date_paid'] if p['date_paid'] else '0000-00-00',
                reverse=True
            )
        
        print(f"✓ Organized statements for {len(statements_by_resident)} residents")
        
        # Debug: Show sample payment data
        if statements_by_resident:
            sample_resident_id = list(statements_by_resident.keys())[0]
            sample_payments = statements_by_resident[sample_resident_id]
            print(f"DEBUG - Sample payment for Resident ID {sample_resident_id}:")
            if sample_payments:
                print(f"  Month: {sample_payments[0].get('month')}")
                print(f"  Amount: {sample_payments[0].get('amount')}")
                print(f"  Date: {sample_payments[0].get('date_paid')}")
                print(f"  Status: {sample_payments[0].get('status')}")
        
        return statements_by_resident
        
    except Exception as e:
        print(f"Error loading statements from SharePoint List: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_residents_from_sharepoint_list():
    """
    Load resident data from SharePoint List: Credit Boost - Tenants
    List ID: 7569dfb7-5d2f-452d-a384-0af63b38b559
    Uses Microsoft Graph API for authentication and data access
    Returns list of resident dictionaries compatible with existing app structure
    """
    
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    list_id = '7569dfb7-5d2f-452d-a384-0af63b38b559'
    
    if not all([client_id, client_secret, tenant_id]):
        print("Warning: Azure credentials not found in .env file")
        return []
    
    try:
        # Authenticate using MSAL (Microsoft Authentication Library)
        print(f"Authenticating with Microsoft Graph API...")
        print(f"Tenant ID: {tenant_id}")
        
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]
        
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )
        
        # Acquire token
        result = app.acquire_token_for_client(scopes=scope)
        
        if "access_token" not in result:
            print(f"Error acquiring token: {result.get('error')}")
            print(f"Error description: {result.get('error_description')}")
            return []
        
        access_token = result["access_token"]
        print(f"✓ Successfully authenticated with Microsoft Graph API")
        
        # Get Site ID first - need to resolve the site URL to site ID
        site_hostname = "peakcampus.sharepoint.com"
        site_path = "/sites/BaseCampApps"
        
        # Get site information
        site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print(f"Resolving SharePoint site: {site_hostname}{site_path}")
        site_response = requests.get(site_url, headers=headers)
        site_response.raise_for_status()
        site_data = site_response.json()
        site_id = site_data["id"]
        
        print(f"✓ Site ID: {site_id}")
        
        # Load payment statements from second SharePoint list
        statements_by_resident = load_statements_from_sharepoint_list(access_token, site_id)
        
        # Get list items using Microsoft Graph API
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        print(f"Loading items from SharePoint List: Credit Boost - Tenants")
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        print(f"✓ Loaded {len(items)} residents from SharePoint List")
        
        # Debug: Show first item's fields
        if items:
            print(f"DEBUG - First tenant item fields: {list(items[0].get('fields', {}).keys())}")
        
        # Transform to resident dictionaries
        residents = []
        for idx, item in enumerate(items):
            resident_id = idx + 1
            
            # Get field values from SharePoint list
            fields = item.get("fields", {})
            
            # Map SharePoint fields to resident data
            first_name = fields.get('FirstName', fields.get('First_x0020_Name', ''))
            last_name = fields.get('LastName', fields.get('Last_x0020_Name', ''))
            full_name = f"{first_name} {last_name}".strip() or f"Resident {resident_id}"
            
            # SSN - we only have last 4 digits from SharePoint
            ssn_last4 = str(fields.get('SSNLast4', fields.get('SSN_x0020_Last_x0020_4', '')))
            masked_ssn = f"***-**-{ssn_last4}" if ssn_last4 else "***-**-****"
            encrypted_ssn = f"ENC{resident_id:04d}{ssn_last4}"  # Create a pseudo-encrypted value
            
            # Address fields
            address_line1 = fields.get('AddressLine1', fields.get('Address_x0020_Line_x0020_1', ''))
            address_line2 = fields.get('AddressLine2', fields.get('Address_x0020_Line_x0020_2', ''))
            city = fields.get('City', '')
            state_code = fields.get('StateCode', fields.get('State_x0020_Code', ''))
            zip_code = fields.get('ZipCode', fields.get('Zip_x0020_Code', ''))
            
            # Construct full address
            address_parts = [p for p in [address_line1, address_line2] if p]
            full_address = ', '.join(address_parts)
            if city or state_code or zip_code:
                city_state_zip = f"{city}, {state_code} {zip_code}".strip()
                full_address = f"{full_address}, {city_state_zip}" if full_address else city_state_zip
            
            # Parse dates - SharePoint dates might come as datetime objects or strings
            def parse_sp_date(date_val):
                if not date_val:
                    return ''
                if isinstance(date_val, datetime):
                    return date_val.strftime('%Y-%m-%d')
                if isinstance(date_val, str):
                    try:
                        # Try parsing ISO format with timezone
                        parsed = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                        return parsed.strftime('%Y-%m-%d')
                    except:
                        try:
                            # Try parsing just the date part (YYYY-MM-DD)
                            if 'T' in date_val:
                                return date_val.split('T')[0]
                            return date_val
                        except:
                            return date_val
                return ''
            
            # Try multiple field name variations for DOB
            dob_value = (fields.get('DateofBirth') or 
                        fields.get('Date_x0020_of_x0020_Birth') or 
                        fields.get('DateOfBirth') or 
                        fields.get('DOB') or '')
            
            # Debug: Print DOB value if first resident
            if idx == 0:
                print(f"DEBUG - First resident DOB field value: {dob_value}")
                print(f"DEBUG - First resident all fields: {list(fields.keys())}")
            
            dob = parse_sp_date(dob_value)
            
            # Get Resident ID from SharePoint - try different field variations and normalize to string
            sp_resident_id_raw = fields.get('ResidentID', fields.get('Resident_x0020_ID', fields.get('ID', resident_id)))
            sp_resident_id = str(sp_resident_id_raw).strip() if sp_resident_id_raw else str(resident_id)
            
            # Debug: Print resident ID matching for first few residents
            if idx < 3:
                print(f"DEBUG - Resident {idx}: ID='{sp_resident_id}' (raw: {sp_resident_id_raw}, type: {type(sp_resident_id_raw)})")
                print(f"DEBUG - Available Resident IDs in statements: {list(statements_by_resident.keys())[:10]}")
            
            # Get payment statements for this resident
            resident_payments = statements_by_resident.get(sp_resident_id, [])
            
            # Get scheduled payment from latest payment record if available
            # ScheduledMonthlyPayment is in the Statements list, not Tenants list
            monthly_rent = 1200.00  # default
            if resident_payments and resident_payments[0].get('scheduled_payment'):
                monthly_rent = resident_payments[0]['scheduled_payment']
            
            if idx < 3:
                print(f"DEBUG - Resident {idx}: Scheduled Payment={monthly_rent}")
                print(f"DEBUG - Found {len(resident_payments)} payments for Resident ID {sp_resident_id}")
                if resident_payments:
                    print(f"DEBUG - Latest payment: {resident_payments[0]}")
            
            # Calculate payment-related fields from real data
            if resident_payments:
                latest_payment = resident_payments[0]
                date_last_payment = latest_payment.get('date_paid', datetime.now().strftime('%Y-%m-%d'))
                
                # Get values from SharePoint statement
                days_late = latest_payment.get('days_late', 0)
                account_status = 'Delinquent' if days_late > 30 else 'Late' if days_late > 0 else 'Current'
                amount_past_due = latest_payment.get('amount_past_due', 0.0)
                current_balance = latest_payment.get('current_balance', 0.0)
                
                # Last reported month
                last_reported = latest_payment.get('month', 'Jan 2026')
            else:
                # No payment data, use defaults
                date_last_payment = datetime.now().strftime('%Y-%m-%d')
                days_late = 0
                account_status = 'Current'
                amount_past_due = 0.0
                current_balance = 0.0
                last_reported = 'Jan 2026'
                # Generate sample payments if no real data
                resident_payments = generate_sample_payments(resident_id, monthly_rent)
            
            # Property and Unit from SharePoint 
            property_name = fields.get('Property', fields.get('Property_x0020_Name', 'Property TBD'))
            unit_number = fields.get('Unit', fields.get('Unit_x0020_Number', 'Unit TBD'))
            
            # Create resident record
            resident = {
                'id': resident_id,
                'account_number': str(sp_resident_id),
                'name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'email': f"{first_name.lower()}.{last_name.lower()}@example.com" if first_name and last_name else '',
                'phone': '',  # Not in SharePoint list
                'unit': unit_number,
                'unit_number': unit_number,
                'property': property_name,
                'property_name': property_name,
                'dob': dob,
                'move_in_date': '',  # Not in SharePoint list
                'address': full_address,
                'city': city,
                'state': state_code,
                'zip': zip_code,
                'ssn': masked_ssn,
                'last4_ssn': ssn_last4,
                'encrypted_ssn': encrypted_ssn,
                'credit_score': 650,  # Default score
                'lease_start_date': '',
                'lease_end_date': '',
                'monthly_rent': monthly_rent,
                
                # Account status fields
                'enrolled': True,
                'enrollment_status': 'enrolled',
                'tradeline_created': True,
                'rent_reporting_status': 'Enrolled',
                'account_status': account_status,
                'date_opened': datetime.now().strftime('%Y-%m-%d'),
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': monthly_rent,
                'date_last_payment': date_last_payment,
                'date_first_delinquency': None,
                'days_late': days_late,
                'highest_credit_amount': monthly_rent,
                'amount_past_due': amount_past_due,
                'current_balance': current_balance,
                'last_reported': last_reported,
                
                # Payment history - from SharePoint Statements list
                'payments': resident_payments,
                
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
        
        print(f"✓ Successfully loaded {len(residents)} residents from SharePoint List")
        return residents
        
    except Exception as e:
        print(f"Error loading from SharePoint List: {e}")
        import traceback
        traceback.print_exc()
        return []


# DEPRECATED: This function uses old SharePoint REST API (office365-python-client)
# Use load_residents_from_sharepoint_list() instead which uses Microsoft Graph API
"""
def load_residents_from_sharepoint():
    #Load resident data from Excel file in SharePoint document library
    #Returns list of resident dictionaries compatible with existing app structure
    
    # This function is deprecated and commented out because it relies on
    # office365-python-client library which requires SharePoint app principal registration
    # Use Microsoft Graph API approach instead (load_residents_from_sharepoint_list)
    pass
"""


def generate_sample_payments(resident_id, monthly_rent):
    """Generate sample payment history for a resident"""
    payments = []
    current_date = datetime.now()
    
    # Generate last 6 months of payments
    for i in range(6):
        payment_date = current_date - timedelta(days=30 * i)
        month = payment_date.strftime('%b %Y')  # Abbreviated month (Jan, Feb, etc.)
        
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

