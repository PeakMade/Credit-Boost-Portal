"""
Script to search for Colby Carter in ALL SharePoint lists (both Credit Boost and CredHub)
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


def search_in_list(access_token, site_id, list_id, list_name):
    """Search for Colby Carter in a SharePoint list"""
    list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
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
            
            # Search for Colby Carter
            if ('colby' in first_name.lower() and 'carter' in last_name.lower()) or 'colby carter' in title.lower():
                found_items.append(fields)
        
        if found_items:
            print(f"\n✓ FOUND {len(found_items)} match(es) in {list_name}!")
            print(f"{'='*100}")
            for idx, fields in enumerate(found_items, 1):
                print(f"\nMatch #{idx}:")
                # Show key fields first
                key_fields = ['FirstName', 'MiddleName', 'LastName', 'Title', 'ResidentID', 'ParticipantID', 
                             'LeaseId', 'PropertyID', 'IsProgramEnrolled', 'ProgramStatus', 
                             'ReportToCreditBureaus', 'LeaseRelationship']
                
                for key in key_fields:
                    if key in fields and fields[key]:
                        print(f"  {key}: {fields[key]}")
                
                print(f"\n  All Fields:")
                for key, value in sorted(fields.items()):
                    if value and key not in ['@odata.etag', 'Edit', 'LinkTitle', 'LinkTitleNoMenu', 
                                              'DocIcon', 'FolderChildCount', 'ItemChildCount', 
                                              '_ComplianceFlags', '_ComplianceTag', '_ComplianceTagUserId',
                                              '_ComplianceTagWrittenTime', '_UIVersionString']:
                        print(f"    {key}: {value}")
            return True
        else:
            print(f"  ✗ Not found in {list_name}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error searching {list_name}: {e}")
        return False


def main():
    print("Searching for 'Colby Carter' in ALL SharePoint Lists...")
    print("="*100)
    
    access_token = get_access_token()
    if not access_token:
        return
    
    print("✓ Authenticated")
    
    site_id = get_site_id(access_token)
    print(f"✓ Site ID: {site_id}")
    
    print("\n" + "="*100)
    print("CHECKING CREDIT BOOST LISTS (Original)")
    print("="*100)
    
    # Original Credit Boost lists
    original_lists = [
        ('7569dfb7-5d2f-452d-a384-0af63b38b559', 'Credit Boost - Tenants'),
        ('f836ae36-efe3-47e5-8f11-d191422ca5d4', 'Credit Boost - Accounts'),
        ('15cdc70e-ba08-4f9b-9ba2-79d66e8c6552', 'Credit Boost - Statements'),
    ]
    
    found_in_original = False
    for list_id, list_name in original_lists:
        print(f"\nSearching: {list_name}...")
        if search_in_list(access_token, site_id, list_id, list_name):
            found_in_original = True
    
    print("\n" + "="*100)
    print("CHECKING CREDHUB LISTS (New)")
    print("="*100)
    
    # CredHub lists
    credhub_lists = [
        ('bbe01515-0941-4e67-9381-f662fcfb6aa0', 'CredHub - Program Participants'),
        ('af09428a-7859-456d-a4be-f8f32c66fb27', 'CredHub - Leases'),
        ('73931c62-e631-4a27-9cbc-8dc5371f8bbc', 'CredHub - Lease Residents'),
    ]
    
    found_in_credhub = False
    for list_id, list_name in credhub_lists:
        print(f"\nSearching: {list_name}...")
        if search_in_list(access_token, site_id, list_id, list_name):
            found_in_credhub = True
    
    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    
    if found_in_original:
        print("\n✓ Colby Carter found in ORIGINAL Credit Boost lists")
        print("  → This person will appear when using 'Real Data (SharePoint List)' data source")
        print("  → They will NOT appear in 'CredHub Data (Reporting System)' source")
    
    if found_in_credhub:
        print("\n✓ Colby Carter found in CREDHUB lists")
        print("  → This person will appear when using 'CredHub Data (Reporting System)' data source")
        print("  → They will also appear in 'Real Data (SharePoint List)' if they exist there too")
    
    if not found_in_original and not found_in_credhub:
        print("\n✗ Colby Carter not found in ANY lists")
        print("  → Check the spelling or look manually in SharePoint")
        print("  → This person may be in a different SharePoint site or list")


if __name__ == "__main__":
    main()
