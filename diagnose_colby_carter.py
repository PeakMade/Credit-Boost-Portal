"""
Search for specific participant by ID: Colby Carter (P-15089824)
"""
import sys
sys.path.insert(0, '.')

import os
import msal
import requests
from dotenv import load_dotenv

load_dotenv()

def get_access_token():
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]
    
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
    result = app.acquire_token_for_client(scopes=scope)
    
    return result.get("access_token")

def get_site_id(access_token):
    site_hostname = "peakcampus.sharepoint.com"
    site_path = "/sites/BaseCampApps"
    site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    site_response = requests.get(site_url, headers=headers)
    site_response.raise_for_status()
    return site_response.json()["id"]

def search_list(access_token, site_id, list_id, list_name, search_id):
    """Search for a specific ParticipantID"""
    list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    items_response = requests.get(list_items_url, headers=headers)
    items_response.raise_for_status()
    items = items_response.json().get("value", [])
    
    found = []
    for item in items:
        fields = item.get("fields", {})
        
        # Check for participant ID or resident ID
        participant_id = fields.get('ParticipantID', '')
        participant_id_ref = fields.get('ParticipantId', '')  # Note: lowercase 'd'
        
        if search_id in [participant_id, participant_id_ref]:
            found.append(fields)
    
    return found

def main():
    print("Searching for Colby Carter (P-15089824)...")
    print("="*100)
    
    access_token = get_access_token()
    site_id = get_site_id(access_token)
    
    participant_id = "P-15089824"
    
    # 1. Check Program Participants
    print(f"\n1. Checking Program Participants for {participant_id}...")
    print("-" * 100)
    participants = search_list(access_token, site_id, 'bbe01515-0941-4e67-9381-f662fcfb6aa0', 
                               'Program Participants', participant_id)
    
    if participants:
        print(f"✓ FOUND in Program Participants!")
        p = participants[0]
        print(f"\n  Key Fields:")
        print(f"    ParticipantID: {p.get('ParticipantID')}")
        print(f"    ResidentID: {p.get('ResidentID')}")
        print(f"    Name: {p.get('FirstName')} {p.get('MiddleName', '')} {p.get('LastName')}")
        print(f"    PropertyID: {p.get('PropertyID')}")
        print(f"    IsProgramEnrolled: {p.get('IsProgramEnrolled')}")
        print(f"    ProgramStatus: {p.get('ProgramStatus')}")
        print(f"    EnrollmentDate: {p.get('EnrollmentDate')}")
    else:
        print(f"✗ NOT found in Program Participants")
        return
    
    # 2. Check Lease Residents (junction table)
    print(f"\n2. Checking Lease Residents for {participant_id}...")
    print("-" * 100)
    lease_residents = search_list(access_token, site_id, '73931c62-e631-4a27-9cbc-8dc5371f8bbc',
                                   'Lease Residents', participant_id)
    
    if lease_residents:
        print(f"✓ FOUND {len(lease_residents)} Lease Resident record(s)!")
        for idx, lr in enumerate(lease_residents, 1):
            print(f"\n  Record {idx}:")
            print(f"    LeaseResidentId: {lr.get('LeaseResidentId')}")
            print(f"    ParticipantId: {lr.get('ParticipantId')}")
            print(f"    LeaseId: {lr.get('LeaseId')}")
            print(f"    LeaseRelationship: {lr.get('LeaseRelationship')}")
            print(f"    ResidentStatus: {lr.get('ResidentStatus')}")
            print(f"    ReportToCreditBureaus: {lr.get('ReportToCreditBureaus')}")
            print(f"    IsAddressSameAsPrimary: {lr.get('IsAddressSameAsPrimary')}")
            
            # Check if lease exists
            lease_id = lr.get('LeaseId')
            if lease_id:
                print(f"\n  3. Checking for Lease {lease_id}...")
                print("-" * 100)
                
                list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/af09428a-7859-456d-a4be-f8f32c66fb27/items?expand=fields"
                headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
                
                items_response = requests.get(list_items_url, headers=headers)
                items_response.raise_for_status()
                leases = items_response.json().get("value", [])
                
                lease_found = None
                for lease_item in leases:
                    lease_fields = lease_item.get("fields", {})
                    if lease_fields.get('LeaseId') == lease_id:
                        lease_found = lease_fields
                        break
                
                if lease_found:
                    print(f"  ✓ Lease FOUND!")
                    print(f"    LeaseId: {lease_found.get('LeaseId')}")
                    print(f"    AccountNumber: {lease_found.get('AccountNumber')}")
                    print(f"    Address: {lease_found.get('AddressLine1')}")
                    print(f"    LeaseStatus: {lease_found.get('LeaseStatus')}")
                else:
                    print(f"  ✗ Lease NOT FOUND - THIS IS THE PROBLEM!")
                    print(f"    The Lease Resident record references LeaseId '{lease_id}' but no such lease exists")
            else:
                print(f"\n  ✗ No LeaseId in Lease Resident record - THIS IS THE PROBLEM!")
    else:
        print(f"✗ NOT found in Lease Residents - THIS IS WHY THEY DON'T APPEAR!")
        print(f"\n  DIAGNOSIS:")
        print(f"  • Colby Carter exists in Program Participants")
        print(f"  • But has NO record in Lease Residents (junction table)")
        print(f"  • The portal requires BOTH a Participant record AND a Lease Residents record")
        print(f"  • Without the Lease Residents link, we don't know which lease/address to display")
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    
    if participants and lease_residents:
        print("\n✓ All required records found - should appear in portal")
        print("  If still not showing, there may be a different issue")
    elif participants and not lease_residents:
        print("\n⚠️ ISSUE IDENTIFIED:")
        print(f"  • Colby Carter (P-15089824) exists in Program Participants")
        print(f"  • But is MISSING from Lease Residents junction table")
        print(f"  • Portal requires both records to display a resident")
        print(f"\n  SOLUTION:")
        print(f"  Add a Lease Residents record linking Colby Carter to a lease")

if __name__ == "__main__":
    main()
