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
        
        # Get list items using Microsoft Graph API
        list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        
        print(f"Loading items from SharePoint List: Credit Boost - Tenants")
        items_response = requests.get(list_items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        items = items_data.get("value", [])
        print(f"✓ Loaded {len(items)} residents from SharePoint List")
        
        # Transform to resident dictionaries
        residents = []
        for idx, item in enumerate(items):
            resident_id = idx + 1
            
            # Get field values from SharePoint list
            fields = item.get("fields", {})
            
            # Map SharePoint fields to resident data
            first_name = fields.get('First_x0020_Name', fields.get('FirstName', ''))
            last_name = fields.get('Last_x0020_Name', fields.get('LastName', ''))
            full_name = f"{first_name} {last_name}".strip() or f"Resident {resident_id}"
            
            # SSN - we only have last 4 digits from SharePoint
            ssn_last4 = str(fields.get('SSN_x0020_Last_x0020_4', fields.get('SSNLast4', '')))
            masked_ssn = f"***-**-{ssn_last4}" if ssn_last4 else "***-**-****"
            encrypted_ssn = f"ENC{resident_id:04d}{ssn_last4}"  # Create a pseudo-encrypted value
            
            # Address fields
            address_line1 = fields.get('Address_x0020_Line_x0020_1', fields.get('AddressLine1', ''))
            address_line2 = fields.get('Address_x0020_Line_x0020_2', fields.get('AddressLine2', ''))
            city = fields.get('City', '')
            state_code = fields.get('State_x0020_Code', fields.get('StateCode', ''))
            zip_code = fields.get('Zip_x0020_Code', fields.get('ZipCode', ''))
            
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
            dob_value = (fields.get('Date_x0020_of_x0020_Birth') or 
                        fields.get('DateOfBirth') or 
                        fields.get('DOB') or 
                        fields.get('Date of Birth') or 
                        fields.get('Date_of_Birth') or '')
            
            # Debug: Print DOB value if first resident
            if idx == 0:
                print(f"DEBUG - First resident DOB field value: {dob_value}")
                print(f"DEBUG - First resident all fields: {list(fields.keys())}")
            
            dob = parse_sp_date(dob_value)
            
            # Get Resident ID from SharePoint or use sequential
            sp_resident_id = fields.get('Resident_x0020_ID', fields.get('ResidentID', resident_id))
            
            # Default values for fields not in SharePoint
            default_monthly_rent = 1200.00
            default_property = 'Property TBD'
            default_unit = 'Unit TBD'
            
            # Create resident record
            resident = {
                'id': resident_id,
                'account_number': str(sp_resident_id),
                'name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'email': f"{first_name.lower()}.{last_name.lower()}@example.com" if first_name and last_name else '',
                'phone': '',  # Not in SharePoint list
                'unit': default_unit,
                'unit_number': default_unit,
                'property': default_property,
                'property_name': default_property,
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
                'monthly_rent': default_monthly_rent,
                
                # Account status fields
                'enrolled': True,
                'enrollment_status': 'enrolled',
                'tradeline_created': True,
                'rent_reporting_status': 'Enrolled',
                'account_status': 'Current',
                'date_opened': datetime.now().strftime('%Y-%m-%d'),
                'payment_schedule': 'Monthly',
                'scheduled_monthly_payment': default_monthly_rent,
                'date_last_payment': datetime.now().strftime('%Y-%m-%d'),
                'date_first_delinquency': None,
                'days_late': 0,
                'highest_credit_amount': default_monthly_rent,
                'amount_past_due': 0.0,
                'current_balance': 0.0,
                'last_reported': 'January 2026',
                
                # Payment history
                'payments': generate_sample_payments(resident_id, default_monthly_rent),
                
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

