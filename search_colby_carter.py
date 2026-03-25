"""
Script to search for Colby Carter in CredHub SharePoint lists
"""
import sys
sys.path.insert(0, '.')

import os
import msal
import requests
from dotenv import load_dotenv

load_dotenv()

def get_access_token():
    """Get Microsoft Graph API access token"""
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        print("Error: Azure credentials not found")
        return None
    
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]
    
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )
    
    result = app.acquire_token_for_client(scopes=scope)
    
    if "access_token" not in result:
        print(f"Error acquiring token: {result.get('error')}")
        return None
    
    return result["access_token"]


def get_site_id(access_token):
    """Get SharePoint site ID"""
    site_hostname = "peakcampus.sharepoint.com"
    site_path = "/sites/BaseCampApps"
    
    site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    site_response = requests.get(site_url, headers=headers)
    site_response.raise_for_status()
    site_data = site_response.json()
    return site_data["id"]


def search_in_list(access_token, site_id, list_id, list_name, search_name):
    """Search for a name in a SharePoint list"""
    list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    items_response = requests.get(list_items_url, headers=headers)
    items_response.raise_for_status()
    items_data = items_response.json()
    
    items = items_data.get("value", [])
    found_items = []
    
    for item in items:
        fields = item.get("fields", {})
        # Check various name fields
        first_name = str(fields.get('FirstName', '')).lower()
        last_name = str(fields.get('LastName', '')).lower()
        title = str(fields.get('Title', '')).lower()
        
        if 'colby' in first_name or 'carter' in last_name or 'colby carter' in title.lower():
            found_items.append(fields)
    
    if found_items:
        print(f"\n✓ Found {len(found_items)} match(es) in {list_name}:")
        for fields in found_items:
            print(f"\n  Record Details:")
            for key, value in sorted(fields.items()):
                if value and key not in ['@odata.etag', 'Edit', 'LinkTitle', 'LinkTitleNoMenu', 'DocIcon']:
                    print(f"    {key}: {value}")
    else:
        print(f"\n✗ No matches found in {list_name}")
    
    return found_items


def main():
    print("Searching for 'Colby Carter' in CredHub SharePoint Lists...")
    print("="*100)
    
    access_token = get_access_token()
    if not access_token:
        return
    
    print("✓ Authenticated")
    
    site_id = get_site_id(access_token)
    print(f"✓ Site ID: {site_id}")
    
    # Search in all CredHub lists
    lists_to_search = [
        ('bbe01515-0941-4e67-9381-f662fcfb6aa0', 'Program Participants'),
        ('af09428a-7859-456d-a4be-f8f32c66fb27', 'Leases'),
        ('73931c62-e631-4a27-9cbc-8dc5371f8bbc', 'Lease Residents'),
    ]
    
    all_results = {}
    
    for list_id, list_name in lists_to_search:
        print(f"\n{'='*100}")
        print(f"Searching in: {list_name}")
        print(f"{'='*100}")
        results = search_in_list(access_token, site_id, list_id, list_name, "colby carter")
        all_results[list_name] = results
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    
    if any(all_results.values()):
        print("\n✓ Colby Carter found in SharePoint!")
        
        # Check why they might not appear in portal
        participant = all_results.get('Program Participants', [])
        lease_resident = all_results.get('Lease Residents', [])
        
        if participant:
            p = participant[0]
            print(f"\nParticipant Info:")
            print(f"  ParticipantID: {p.get('ParticipantID')}")
            print(f"  ResidentID: {p.get('ResidentID')}")
            print(f"  IsProgramEnrolled: {p.get('IsProgramEnrolled')}")
            print(f"  ProgramStatus: {p.get('ProgramStatus')}")
        
        if lease_resident:
            lr = lease_resident[0]
            print(f"\nLease Resident Info:")
            print(f"  LeaseResidentId: {lr.get('LeaseResidentId')}")
            print(f"  ParticipantId: {lr.get('ParticipantId')}")
            print(f"  LeaseId: {lr.get('LeaseId')}")
            print(f"  ReportToCreditBureaus: {lr.get('ReportToCreditBureaus')}")
        
        # Check if they have required associations
        if participant and not lease_resident:
            print(f"\n⚠️ ISSUE: Participant exists but NO Lease Resident association found!")
            print(f"   This person won't appear because they're not linked to a lease.")
        
        if lease_resident and not participant:
            print(f"\n⚠️ ISSUE: Lease Resident exists but NO Participant record found!")
            print(f"   This person won't appear because participant data is missing.")
        
        if participant and lease_resident:
            lease_id = lease_resident[0].get('LeaseId')
            if not lease_id:
                print(f"\n⚠️ ISSUE: Lease Resident has no LeaseId!")
            else:
                print(f"\n✓ All associations look good. Checking lease...")
                print(f"   LeaseId: {lease_id}")
    else:
        print("\n✗ Colby Carter not found in any CredHub lists")
        print("   Check spelling or look in other SharePoint lists")


if __name__ == "__main__":
    main()
