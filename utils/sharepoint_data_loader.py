"""
SharePoint data loader for resident information
Reads data from three SharePoint lists using Microsoft Graph API:
1. Credit Boost - Tenants (7569dfb7-5d2f-452d-a384-0af63b38b559) - Resident personal info
2. Credit Boost - Accounts (f836ae36-efe3-47e5-8f11-d191422ca5d4) - Account enrollment info
3. Credit Boost - Statements (15cdc70e-ba08-4f9b-9ba2-79d66e8c6552) - Payment history
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
    DEPRECATED: This function is no longer used.
    Payment data is now loaded from the Credit Boost - Statements list (15cdc70e-ba08-4f9b-9ba2-79d66e8c6552).
    Use load_statements_from_sharepoint() instead.
    Kept for backward compatibility.
    """
    return {}


def load_tenants_from_sharepoint(access_token, site_id):
    """
    Load tenant data from SharePoint List: Credit Boost - Tenants
    List ID: 7569dfb7-5d2f-452d-a384-0af63b38b559
    Returns dict: mapping ResidentID to tenant info
    """
    list_id = '7569dfb7-5d2f-452d-a384-0af63b38b559'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print(f"Loading items from SharePoint List: Credit Boost - Tenants")
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        print(f"✓ Loaded {len(items)} tenant records from SharePoint List")
        
        tenants_dict = {}
        
        for idx, item in enumerate(items):
            fields = item.get("fields", {})
            
            resident_id = str(fields.get('ResidentID', '')).strip()
            if not resident_id:
                continue
            
            # Parse date helper
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
            
            tenants_dict[resident_id] = {
                'ResidentID': resident_id,
                'FirstName': fields.get('FirstName', ''),
                'MiddleName': fields.get('MiddleName', ''),
                'LastName': fields.get('LastName', ''),
                'GenerationCode': fields.get('GenerationCode', ''),
                'DateofBirth': parse_sp_date(fields.get('DateofBirth', '')),
                'SSNLast4': str(fields.get('SSNLast4', '')),
                'AddressLine1': fields.get('AddressLine1', ''),
                'AddressLine2': fields.get('AddressLine2', ''),
                'City': fields.get('City', ''),
                'StateCode': fields.get('StateCode', ''),
                'ZipCode': fields.get('ZipCode', ''),
                'PrimaryAddress': fields.get('PrimaryAddress', True),
                'Property': fields.get('Property', ''),
                'Unit': fields.get('Unit', ''),
                'BloomConsumerID': fields.get('BloomConsumerID', ''),
                'BloomConsumerStatus': fields.get('BloomConsumerStatus', ''),
                'BloomConsumerCreatedAt': parse_sp_date(fields.get('BloomConsumerCreatedAt', '')),
                'LastSyncAt': parse_sp_date(fields.get('LastSyncAt', ''))
            }
        
        print(f"✓ Organized {len(tenants_dict)} tenants")
        return tenants_dict
        
    except Exception as e:
        print(f"Error loading tenants from SharePoint: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_accounts_from_sharepoint(access_token, site_id):
    """
    Load account data from SharePoint List: Credit Boost - Accounts
    List ID: f836ae36-efe3-47e5-8f11-d191422ca5d4
    Returns dict: mapping ResidentID to account info
    """
    list_id = 'f836ae36-efe3-47e5-8f11-d191422ca5d4'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print(f"Loading items from SharePoint List: Credit Boost - Accounts")
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        print(f"✓ Loaded {len(items)} account records from SharePoint List")
        
        accounts_dict = {}
        
        for idx, item in enumerate(items):
            fields = item.get("fields", {})
            
            resident_id = str(fields.get('ResidentID', '')).strip()
            if not resident_id:
                continue
            
            # Parse date helper
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
            
            accounts_dict[resident_id] = {
                'AccountID': fields.get('AccountID', ''),
                'ResidentID': resident_id,
                'CreditProductID': fields.get('CreditProductID', ''),
                'ExternalAccountIdentifier': fields.get('ExternalAccountIdentifier', ''),
                'AccountType': fields.get('AccountType', 'Individual'),
                'OpenedDate': parse_sp_date(fields.get('OpenedData', '')),  # Note: SharePoint field has typo 'OpenedData'
                'TermsDuration': fields.get('TermsDuration', ''),
                'ConsumerAccountNumber': fields.get('ConsumerAccountNumber', ''),
                'BloomAccountID': fields.get('BloomAccountID', ''),
                'BloomAccountStatus': fields.get('BloomAccountStatus', ''),
                'BloomAccountCreatedAt': parse_sp_date(fields.get('BloomAccountCreatedAt', '')),
                'LastSyncAt': parse_sp_date(fields.get('LastSyncAt', ''))
            }
        
        print(f"✓ Organized {len(accounts_dict)} accounts")
        return accounts_dict
        
    except Exception as e:
        print(f"Error loading accounts from SharePoint: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_statements_from_sharepoint(access_token, site_id):
    """
    Load statement data from SharePoint List: Credit Boost - Statements
    List ID: 15cdc70e-ba08-4f9b-9ba2-79d66e8c6552
    Returns dict: mapping ResidentID to list of statements
    """
    list_id = '15cdc70e-ba08-4f9b-9ba2-79d66e8c6552'
    
    try:
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
        
        statements_by_resident = {}
        
        # Parse date helper
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
        
        for idx, item in enumerate(items):
            fields = item.get("fields", {})
            
            resident_id = str(fields.get('ResidentID', '')).strip()
            if not resident_id:
                continue
            
            # Get payment date
            payment_date = parse_sp_date(fields.get('LastPaymentDate', ''))
            
            # Derive month from payment date
            payment_month = ''
            if payment_date:
                try:
                    date_obj = datetime.strptime(payment_date, '%Y-%m-%d')
                    payment_month = date_obj.strftime('%b %Y')
                except:
                    pass
            
            # Get amounts
            current_balance = float(fields.get('CurrentBalance', 0) or 0)
            scheduled_payment = float(fields.get('ScheduledMonthlyPayment', 0) or 0)
            actual_payment = float(fields.get('ActualMonthlyPayment', 0) or 0)
            amount_past_due = float(fields.get('AmountPastDue', 0) or 0)
            days_delinquent = int(fields.get('DaysDelinquent', 0) or 0)
            
            # Determine payment status
            if days_delinquent > 30:
                status = 'Delinquent'
            elif days_delinquent > 0:
                status = 'Late'
            else:
                status = 'Paid'
            
            # Check if reported (based on FurnishmentStatus)
            furnishment_status = fields.get('FurnishmentStatus', '')
            reported = furnishment_status.upper() in ['SUBMITTED', 'ACCEPTED']
            report_date = parse_sp_date(fields.get('FurnishedAt', '')) if reported else None
            
            statement = {
                'StatementID': fields.get('StatementID', ''),
                'AccountID': fields.get('AccountID', ''),
                'month': payment_month,
                'amount': actual_payment,
                'date_paid': payment_date,
                'payment_date': payment_date,
                'status': status,
                'days_late': days_delinquent,
                'reported': reported,
                'report_date': report_date,
                'scheduled_payment': scheduled_payment,
                'amount_past_due': amount_past_due,
                'current_balance': current_balance,
                'statement_date': parse_sp_date(fields.get('StatementDate', '')),
                'statement_identifier': fields.get('StatementIdentifier', ''),
                'bloom_statement_id': fields.get('BloomStatementID', ''),
                'furnishment_status': furnishment_status
            }
            
            if resident_id not in statements_by_resident:
                statements_by_resident[resident_id] = []
            statements_by_resident[resident_id].append(statement)
        
        # Sort statements by payment date (most recent first)
        for resident_id in statements_by_resident:
            statements_by_resident[resident_id].sort(
                key=lambda s: s['date_paid'] if s['date_paid'] else '0000-00-00',
                reverse=True
            )
        
        print(f"✓ Organized statements for {len(statements_by_resident)} residents")
        return statements_by_resident
        
    except Exception as e:
        print(f"Error loading statements from SharePoint: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_residents_and_payments_from_sharepoint_list(access_token, site_id):
    """
    Load resident and payment data from THREE SharePoint Lists:
    - Credit Boost - Tenants (7569dfb7-5d2f-452d-a384-0af63b38b559)
    - Credit Boost - Accounts (f836ae36-efe3-47e5-8f11-d191422ca5d4)
    - Credit Boost - Statements (15cdc70e-ba08-4f9b-9ba2-79d66e8c6552)
    
    Returns tuple: (residents_dict, statements_dict)
    - residents_dict: mapping Resident_ID to combined tenant + account info
    - statements_dict: mapping Resident_ID to list of payment statements
    """
    
    # Load data from all three lists
    
    try:
        # Load data from all three SharePoint lists
        tenants = load_tenants_from_sharepoint(access_token, site_id)
        accounts = load_accounts_from_sharepoint(access_token, site_id)
        statements = load_statements_from_sharepoint(access_token, site_id)
        
        # Combine tenant and account data
        residents_dict = {}
        
        for resident_id, tenant_data in tenants.items():
            # Start with tenant data
            combined_data = tenant_data.copy()
            
            # Add account data if available
            account_data = accounts.get(resident_id, {})
            combined_data.update({
                'AccountID': account_data.get('AccountID', ''),
                'CreditProductID': account_data.get('CreditProductID', ''),
                'ExternalAccountIdentifier': account_data.get('ExternalAccountIdentifier', ''),
                'AccountType': account_data.get('AccountType', 'Individual'),
                'OpenedDate': account_data.get('OpenedDate', ''),
                'TermsDuration': account_data.get('TermsDuration', ''),
                'ConsumerAccountNumber': account_data.get('ConsumerAccountNumber', ''),
                'BloomAccountID': account_data.get('BloomAccountID', ''),
                'BloomAccountStatus': account_data.get('BloomAccountStatus', ''),
                'BloomAccountCreatedAt': account_data.get('BloomAccountCreatedAt', ''),
            })
            
            residents_dict[resident_id] = combined_data
        
        print(f"✓ Combined {len(residents_dict)} residents with tenant and account data")
        
        # Debug: Show sample data
        if residents_dict:
            sample_resident_id = list(residents_dict.keys())[0]
            print(f"DEBUG - Sample combined resident info for ID {sample_resident_id}:")
            print(f"  Name: {residents_dict[sample_resident_id].get('FirstName')} {residents_dict[sample_resident_id].get('LastName')}")
            print(f"  Property: {residents_dict[sample_resident_id].get('Property')}")
            print(f"  Unit: {residents_dict[sample_resident_id].get('Unit')}")
            print(f"  Account ID: {residents_dict[sample_resident_id].get('AccountID')}")
            print(f"  Bloom Consumer ID: {residents_dict[sample_resident_id].get('BloomConsumerID')}")
            
        if statements:
            sample_resident_id = list(statements.keys())[0]
            sample_payments = statements[sample_resident_id]
            print(f"DEBUG - Sample statement for Resident ID {sample_resident_id}:")
            if sample_payments:
                print(f"  Month: {sample_payments[0].get('month')}")
                print(f"  Amount: {sample_payments[0].get('amount')}")
                print(f"  Date: {sample_payments[0].get('date_paid')}")
                print(f"  Status: {sample_payments[0].get('status')}")
                print(f"  Furnishment Status: {sample_payments[0].get('furnishment_status')}")
        
        return residents_dict, statements
        
    except Exception as e:
        print(f"Error loading from SharePoint List: {e}")
        import traceback
        traceback.print_exc()
        return {}, {}


def load_residents_from_sharepoint_list():
    """
    Load resident data from THREE SharePoint Lists:
    - Credit Boost - Tenants (7569dfb7-5d2f-452d-a384-0af63b38b559)
    - Credit Boost - Accounts (f836ae36-efe3-47e5-8f11-d191422ca5d4)
    - Credit Boost - Statements (15cdc70e-ba08-4f9b-9ba2-79d66e8c6552)
    
    Uses Microsoft Graph API for authentication and data access
    Returns list of resident dictionaries compatible with existing app structure
    """
    
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
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
        
        # Load resident and payment data from three SharePoint lists
        residents_data, statements_by_resident = load_residents_and_payments_from_sharepoint_list(access_token, site_id)
        
        print(f"✓ Loaded data for {len(residents_data)} residents from SharePoint Lists")
        
        # Transform to resident dictionaries
        residents = []
        for idx, (resident_id_key, resident_data) in enumerate(residents_data.items()):
            resident_id = idx + 1
            
            # Get field values from resident data dictionary
            first_name = resident_data.get('FirstName', '')
            last_name = resident_data.get('LastName', '')
            full_name = f"{first_name} {last_name}".strip() or f"Resident {resident_id}"
            
            # SSN - we only have last 4 digits from SharePoint
            ssn_last4 = str(resident_data.get('SSNLast4', ''))
            masked_ssn = f"***-**-{ssn_last4}" if ssn_last4 else "***-**-****"
            encrypted_ssn = f"ENC{resident_id:04d}{ssn_last4}"  # Create a pseudo-encrypted value
            
            # Address fields
            address_line1 = resident_data.get('AddressLine1', '')
            address_line2 = resident_data.get('AddressLine2', '')
            city = resident_data.get('City', '')
            state_code = resident_data.get('StateCode', '')
            zip_code = resident_data.get('ZipCode', '')
            
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
            
            # Get DOB from resident data
            dob_value = resident_data.get('DateofBirth', '')
            
            # Debug: Print DOB value if first resident
            if idx == 0:
                print(f"DEBUG - First resident DOB field value: {dob_value}")
                print(f"DEBUG - First resident all fields: {list(resident_data.keys())}")
            
            dob = parse_sp_date(dob_value)
            
            # Get MoveInDate for enrollment history (not currently in Tenants list, would need to add)
            move_in_date_value = resident_data.get('MoveInDate', '')
            move_in_date = parse_sp_date(move_in_date_value)
            
            # Get account opened date from Accounts list
            account_opened_date = resident_data.get('OpenedDate', '')
            
            # Set enrollment date - use account opened date if available, otherwise move-in date, otherwise default
            if account_opened_date:
                enrollment_date = account_opened_date
                date_opened = account_opened_date
            elif move_in_date:
                enrollment_date = move_in_date
                date_opened = move_in_date
            else:
                # Default to 2025-01-01 to ensure all payment history shows
                enrollment_date = '2025-01-01'
                date_opened = datetime.now().strftime('%Y-%m-%d')
            
            # Get Resident ID from resident data
            sp_resident_id = str(resident_id_key).strip()
            
            # Debug: Print resident ID matching for first few residents
            if idx < 3:
                print(f"DEBUG - Resident {idx}: ID='{sp_resident_id}'")
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
            property_name = resident_data.get('Property', 'Property TBD')
            unit_number = resident_data.get('Unit', 'Unit TBD')
            
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
                'date_opened': date_opened,  # From Accounts.OpenedDate
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': monthly_rent,
                'date_last_payment': date_last_payment,
                'date_first_delinquency': None,
                'days_late': days_late,
                'amount_past_due': amount_past_due,
                'current_balance': current_balance,
                'last_reported': last_reported,
                
                # Payment history - from SharePoint Statements list
                'payments': resident_payments,
                
                # Enrollment history - use move-in date or default to early date
                'enrollment_history': [
                    {
                        'action': 'enrolled',
                        'timestamp': enrollment_date + ' 00:00:00'  # Add time component for consistency
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
            'payment_date': (payment_date + timedelta(days=days_late)).strftime('%Y-%m-%d'),  # Alias for compatibility
            'status': status,
            'days_late': days_late,
            'reported': reported,
            'report_date': payment_date.strftime('%Y-%m-%d') if reported else None
        })
    
    return payments


def generate_credhub_payment_history(all_snapshots, monthly_rent, is_enrolled_and_reporting):
    """
    Generate payment history from CredHub financial snapshots
    
    Args:
        all_snapshots: List of financial snapshot dicts for a lease (sorted by date, most recent first)
        monthly_rent: Monthly rent amount
        is_enrolled_and_reporting: Whether the resident is enrolled and reporting to bureaus
        
    Returns:
        List of payment records compatible with portal structure
    """
    payments = []
    
    if not all_snapshots:
        return payments
    
    for snapshot in all_snapshots:
        as_of_date_str = snapshot.get('AsOfDate', '')
        if not as_of_date_str:
            continue
        
        # Parse the AsOfDate
        try:
            if 'T' in as_of_date_str:
                as_of_date = datetime.fromisoformat(as_of_date_str.replace('Z', '+00:00'))
            else:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d')
        except:
            continue
        
        month = as_of_date.strftime('%b %Y')  # e.g., "Mar 2026"
        
        # Get balance information
        total_balance = float(snapshot.get('TotalLedgerBalance', 0) or 0)
        aged_30_59 = float(snapshot.get('BalanceAged30To59', 0) or 0)
        aged_60_89 = float(snapshot.get('BalanceAged60To89', 0) or 0)
        aged_90_119 = float(snapshot.get('BalanceAged90To119', 0) or 0)
        aged_120_149 = float(snapshot.get('BalanceAged120To149', 0) or 0)
        aged_150_179 = float(snapshot.get('BalanceAged150To179', 0) or 0)
        aged_180_plus = float(snapshot.get('BalanceAged180Plus', 0) or 0)
        
        # Calculate actual days late from OldestOpenChargeDate if available
        oldest_charge_date_str = snapshot.get('OldestOpenChargeDate', '')
        days_late = 0
        
        if total_balance <= 0:
            status = 'Paid'
            days_late = 0
        else:
            status = 'Late'
            # Try to calculate actual days late from OldestOpenChargeDate
            if oldest_charge_date_str:
                try:
                    if 'T' in oldest_charge_date_str:
                        oldest_charge_date = datetime.fromisoformat(oldest_charge_date_str.replace('Z', '+00:00'))
                    else:
                        oldest_charge_date = datetime.strptime(oldest_charge_date_str, '%Y-%m-%d')
                    days_late = (as_of_date - oldest_charge_date).days
                except:
                    # Fall back to aging bucket estimation if date parsing fails
                    pass
            
            # If we couldn't calculate from date, fall back to aging bucket estimation
            if days_late == 0:
                if aged_180_plus > 0:
                    days_late = 195  # 180+ days, use 195 as representative
                elif aged_150_179 > 0:
                    days_late = 165  # Midpoint of 150-179
                elif aged_120_149 > 0:
                    days_late = 135  # Midpoint of 120-149
                elif aged_90_119 > 0:
                    days_late = 105  # Midpoint of 90-119
                elif aged_60_89 > 0:
                    days_late = 75   # Midpoint of 60-89
                elif aged_30_59 > 0:
                    days_late = 45   # Midpoint of 30-59
                else:
                    days_late = 15   # 1-29 days, use 15 as representative
        
        # Get payment information
        last_payment_date = snapshot.get('LastPaymentDate', '')
        last_payment_amount = float(snapshot.get('LastPaymentAmount', 0) or 0)
        
        # Parse payment date
        if last_payment_date:
            try:
                if 'T' in last_payment_date:
                    payment_date_str = last_payment_date.split('T')[0]
                else:
                    payment_date_str = last_payment_date
            except:
                payment_date_str = as_of_date.strftime('%Y-%m-%d')
        else:
            payment_date_str = as_of_date.strftime('%Y-%m-%d')
        
        # Determine if this was reported to credit bureaus
        # Only report if enrolled AND reporting is enabled
        reported = is_enrolled_and_reporting
        
        # Use the actual rent amount if available, otherwise use scheduled monthly rent
        payment_amount = monthly_rent if monthly_rent > 0 else last_payment_amount
        
        payment_record = {
            'month': month,
            'amount': payment_amount,
            'date_paid': payment_date_str,
            'payment_date': payment_date_str,
            'status': status,
            'days_late': days_late,
            'reported': reported,
            'report_date': as_of_date.strftime('%Y-%m-%d') if reported else None,
            # Additional CredHub fields for reference
            'total_balance': total_balance,
            'as_of_date': as_of_date.strftime('%Y-%m-%d')
        }
        
        payments.append(payment_record)
    
    return payments


def load_residents_from_credhub_lists():
    """
    Load resident data from SIX CredHub SharePoint Lists:
    - Program Participants (bbe01515-0941-4e67-9381-f662fcfb6aa0) - Individual participant info
    - Leases (af09428a-7859-456d-a4be-f8f32c66fb27) - Lease/account information
    - Lease Residents (73931c62-e631-4a27-9cbc-8dc5371f8bbc) - Links participants to leases
    - Monthly Financial Snapshots (bcf0d7cb-00db-4755-8898-a24dcf83702f) - Financial data showing delinquency
    - Reporting Cycles (c2545153-1aa1-409b-aad4-a6361966af0a) - Monthly reporting cycles
    - CredHub Job Runs (097d06bb-0bc6-4fb3-9188-d7afa3773b26) - Job tracking
    
    Uses Microsoft Graph API for authentication and data access
    Returns list of resident dictionaries compatible with existing app structure
    """
    
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        print("Warning: Azure credentials not found in .env file")
        return []
    
    try:
        # Authenticate using MSAL (Microsoft Authentication Library)
        print(f"Authenticating with Microsoft Graph API...")
        
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
        
        # Get Site ID
        site_hostname = "peakcampus.sharepoint.com"
        site_path = "/sites/BaseCampApps"
        
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
        
        # Load all lists
        print("\n=== Loading CredHub Lists ===")
        
        # 1. Load Program Participants
        print("Loading Program Participants...")
        participants_dict = load_credhub_participants(access_token, site_id)
        print(f"✓ Loaded {len(participants_dict)} participants")
        
        # 2. Load Leases
        print("Loading Leases...")
        leases_dict = load_credhub_leases(access_token, site_id)
        print(f"✓ Loaded {len(leases_dict)} leases")
        
        # 3. Load Lease Residents (junction table)
        print("Loading Lease Residents...")
        lease_residents = load_credhub_lease_residents(access_token, site_id)
        print(f"✓ Loaded {len(lease_residents)} lease-resident associations")
        
        # 4. Load Monthly Financial Snapshots
        print("Loading Monthly Financial Snapshots...")
        snapshots_dict, all_snapshots_by_lease = load_credhub_financial_snapshots(access_token, site_id)
        print(f"✓ Loaded {len(snapshots_dict)} current financial snapshots")
        print(f"✓ Loaded {sum(len(s) for s in all_snapshots_by_lease.values())} total snapshot records for payment history")
        
        # 5. Load Reporting Cycles (optional for now)
        print("Loading Reporting Cycles...")
        cycles_dict = load_credhub_reporting_cycles(access_token, site_id)
        print(f"✓ Loaded {len(cycles_dict)} reporting cycles")
        
        # 6. Load CredHub Job Runs (optional for now)
        print("Loading CredHub Job Runs...")
        job_runs = load_credhub_job_runs(access_token, site_id)
        print(f"✓ Loaded {len(job_runs)} job runs")
        
        # Now join the data and create resident records
        print("\n=== Assembling Resident Data ===")
        residents = []
        resident_counter = 1
        
        # Iterate through lease residents (junction table)
        for lr in lease_residents:
            participant_id = lr.get('ParticipantId', '')
            lease_id = lr.get('LeaseId', '')
            
            if not participant_id or not lease_id:
                continue
            
            # Get participant info
            participant = participants_dict.get(participant_id, {})
            if not participant:
                continue
            
            # Get lease info
            lease = leases_dict.get(lease_id, {})
            if not lease:
                continue
            
            # Get most recent financial snapshot for this lease
            snapshot = snapshots_dict.get(lease_id, {})
            
            # Parse dates
            def parse_date(date_val):
                if not date_val:
                    return ''
                if isinstance(date_val, str):
                    try:
                        if 'T' in date_val:
                            return date_val.split('T')[0]
                        return date_val
                    except:
                        return date_val
                return ''
            
            # Calculate enrollment status
            is_enrolled = participant.get('IsProgramEnrolled', False)
            program_status = participant.get('ProgramStatus', 'Unknown')
            report_to_bureaus = lr.get('ReportToCreditBureaus', False)
            
            # Calculate delinquency status based on financial snapshot
            total_balance = float(snapshot.get('TotalLedgerBalance', 0) or 0)
            aged_30_59 = float(snapshot.get('BalanceAged30To59', 0) or 0)
            aged_60_89 = float(snapshot.get('BalanceAged60To89', 0) or 0)
            aged_90_119 = float(snapshot.get('BalanceAged90To119', 0) or 0)
            aged_120_149 = float(snapshot.get('BalanceAged120To149', 0) or 0)
            aged_150_179 = float(snapshot.get('BalanceAged150To179', 0) or 0)
            aged_180_plus = float(snapshot.get('BalanceAged180Plus', 0) or 0)
            
            # Determine account status
            if total_balance <= 0:
                account_status = 'Current'
            elif aged_180_plus > 0:
                account_status = 'Delinquent 180+ days'
            elif aged_150_179 > 0:
                account_status = 'Delinquent 150-179 days'
            elif aged_120_149 > 0:
                account_status = 'Delinquent 120-149 days'
            elif aged_90_119 > 0:
                account_status = 'Delinquent 90-119 days'
            elif aged_60_89 > 0:
                account_status = 'Delinquent 60-89 days'
            elif aged_30_59 > 0:
                account_status = 'Delinquent 30-59 days'
            elif total_balance > 0:
                account_status = 'Delinquent 1-29 days'
            else:
                account_status = 'Current'
            
            # Get monthly rent and payment info
            monthly_rent = float(snapshot.get('MonthlyRentAmount', 0) or 0)
            last_payment_date = parse_date(snapshot.get('LastPaymentDate', ''))
            last_payment_amount = float(snapshot.get('LastPaymentAmount', 0) or 0)
            
            # Build resident name
            first_name = participant.get('FirstName', '')
            middle_name = participant.get('MiddleName', '')
            last_name = participant.get('LastName', '')
            full_name = f"{first_name} {middle_name} {last_name}".strip().replace('  ', ' ')
            
            # Build address
            address_line1 = lease.get('AddressLine1', '')
            address_line2 = lease.get('AddressLine2', '')
            city = lease.get('City', '')
            state = lease.get('State', '')
            postal_code = lease.get('PostalCode', '')
            
            address = f"{address_line1}"
            if address_line2:
                address += f", {address_line2}"
            
            # Generate payment history from financial snapshots
            lease_snapshots = all_snapshots_by_lease.get(lease_id, [])
            is_enrolled_and_reporting = is_enrolled and report_to_bureaus
            payment_history = generate_credhub_payment_history(
                lease_snapshots, 
                monthly_rent, 
                is_enrolled_and_reporting
            )
            
            # Create resident record
            resident = {
                'id': resident_counter,
                'name': full_name,
                'email': participant.get('Email', f"{first_name.lower()}.{last_name.lower()}@example.com"),
                'phone': participant.get('PhoneNumber', ''),
                'address': address,
                'city': city,
                'state': state,
                'zip': postal_code,
                'property': participant.get('PropertyID', lease.get('PropertyId', '')),
                'unit': lease.get('UnitNumber', address_line2),
                'dob': parse_date(participant.get('DateOfBirth', '')),
                'last4_ssn': '',  # Not available in CredHub data
                'enrolled': is_enrolled and report_to_bureaus,
                'enrollment_status': 'enrolled' if (is_enrolled and report_to_bureaus) else 'not enrolled',
                'tradeline_created': is_enrolled and report_to_bureaus,
                'account_status': account_status,
                'amount_past_due': total_balance if total_balance > 0 else 0,
                'scheduled_monthly_payment': monthly_rent,
                'lease_start_date': parse_date(lease.get('CurrentLeaseStartDate', '')),
                'lease_end_date': parse_date(lease.get('CurrentLeaseEndDate', '')),
                'move_in_date': parse_date(lease.get('MoveInDate', '')),
                'enrollment_history': [],
                'payments': payment_history,
                # CredHub specific fields
                'participant_id': participant_id,
                'lease_id': lease_id,
                'resident_id': participant.get('ResidentID', ''),
                'lease_relationship': lr.get('LeaseRelationship', ''),
                'resident_status': lr.get('ResidentStatus', ''),
                'program_status': program_status,
                'last_payment_date': last_payment_date,
                'last_payment_amount': last_payment_amount,
                'total_balance': total_balance,
                'aged_30_59': aged_30_59,
                'aged_60_89': aged_60_89,
                'aged_90_plus': aged_90_119 + aged_120_149 + aged_150_179 + aged_180_plus,
            }
            
            # Add enrollment history if enrolled
            if is_enrolled:
                enrollment_date = parse_date(participant.get('EnrollmentDate', ''))
                if enrollment_date:
                    resident['enrollment_history'].append({
                        'action': 'enrolled',
                        'timestamp': enrollment_date
                    })
            
            # Add opt-out history if applicable
            opt_out_date = parse_date(participant.get('OptOutDate', ''))
            if opt_out_date:
                resident['enrollment_history'].append({
                    'action': 'revoked consent',
                    'timestamp': opt_out_date
                })
            
            residents.append(resident)
            resident_counter += 1
        
        print(f"✓ Assembled {len(residents)} resident records")
        return residents
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error loading CredHub data: {e}")
        print(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        return []
    except Exception as e:
        print(f"Error loading CredHub data: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_credhub_participants(access_token, site_id):
    """Load Program Participants from SharePoint with pagination support"""
    list_id = 'bbe01515-0941-4e67-9381-f662fcfb6aa0'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        participants_dict = {}
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                participant_id = fields.get('ParticipantID', '')
                if participant_id:
                    participants_dict[participant_id] = fields
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        return participants_dict
        
    except Exception as e:
        print(f"Error loading Program Participants: {e}")
        return {}


def load_credhub_leases(access_token, site_id):
    """Load Leases from SharePoint with pagination support"""
    list_id = 'af09428a-7859-456d-a4be-f8f32c66fb27'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        leases_dict = {}
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                lease_id = fields.get('LeaseId', '')
                if lease_id:
                    leases_dict[lease_id] = fields
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        return leases_dict
        
    except Exception as e:
        print(f"Error loading Leases: {e}")
        return {}


def load_credhub_lease_residents(access_token, site_id):
    """Load Lease Residents (junction table) from SharePoint with pagination support"""
    list_id = '73931c62-e631-4a27-9cbc-8dc5371f8bbc'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        lease_residents = []
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                lease_residents.append(fields)
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        return lease_residents
        
    except Exception as e:
        print(f"Error loading Lease Residents: {e}")
        return []


def load_credhub_financial_snapshots(access_token, site_id):
    """Load Monthly Financial Snapshots from SharePoint with pagination support
    Returns two dicts:
    1. Most recent snapshot per lease (for current status)
    2. All snapshots grouped by lease (for payment history)
    """
    list_id = 'bcf0d7cb-00db-4755-8898-a24dcf83702f'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        # Get the most recent snapshot for each lease
        snapshots_dict = {}
        # Get ALL snapshots grouped by lease (for payment history)
        all_snapshots_by_lease = {}
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                lease_id = fields.get('LeaseId', '')
                as_of_date = fields.get('AsOfDate', '')
                
                if lease_id:
                    # Track all snapshots for this lease
                    if lease_id not in all_snapshots_by_lease:
                        all_snapshots_by_lease[lease_id] = []
                    all_snapshots_by_lease[lease_id].append(fields)
                    
                    # If we don't have a snapshot for this lease yet, or this one is more recent
                    if lease_id not in snapshots_dict:
                        snapshots_dict[lease_id] = fields
                    else:
                        # Compare dates
                        existing_date = snapshots_dict[lease_id].get('AsOfDate', '')
                        if as_of_date > existing_date:
                            snapshots_dict[lease_id] = fields
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        # Sort all snapshots by date (most recent first)
        for lease_id in all_snapshots_by_lease:
            all_snapshots_by_lease[lease_id].sort(
                key=lambda x: x.get('AsOfDate', ''), 
                reverse=True
            )
        
        return snapshots_dict, all_snapshots_by_lease
        
    except Exception as e:
        print(f"Error loading Financial Snapshots: {e}")
        return {}, {}


def load_credhub_reporting_cycles(access_token, site_id):
    """Load Reporting Cycles from SharePoint with pagination support"""
    list_id = 'c2545153-1aa1-409b-aad4-a6361966af0a'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        cycles_dict = {}
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                cycle_id = fields.get('ReportingCycleId', '')
                if cycle_id:
                    cycles_dict[cycle_id] = fields
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        return cycles_dict
        
    except Exception as e:
        print(f"Error loading Reporting Cycles: {e}")
        return {}


def load_credhub_job_runs(access_token, site_id):
    """Load CredHub Job Runs from SharePoint with pagination support"""
    list_id = '097d06bb-0bc6-4fb3-9188-d7afa3773b26'
    
    try:
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        job_runs = []
        page_count = 0
        
        # Handle pagination
        while list_items_url:
            page_count += 1
            items_response = requests.get(list_items_url, headers=headers)
            items_response.raise_for_status()
            items_data = items_response.json()
            
            items = items_data.get("value", [])
            
            for item in items:
                fields = item.get("fields", {})
                job_runs.append(fields)
            
            # Check for next page
            list_items_url = items_data.get("@odata.nextLink")
        
        if page_count > 1:
            print(f"  (Loaded across {page_count} pages)")
        
        return job_runs
        
    except Exception as e:
        print(f"Error loading CredHub Job Runs: {e}")
        return []

