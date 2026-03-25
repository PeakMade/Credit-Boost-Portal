"""
List all names in Program Participants to help find similar names to Colby Carter
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

def main():
    print("Listing all names in Program Participants list...")
    print("="*80)
    
    access_token = get_access_token()
    site_id = get_site_id(access_token)
    
    # Load Program Participants
    list_id = 'bbe01515-0941-4e67-9381-f662fcfb6aa0'
    list_items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    items_response = requests.get(list_items_url, headers=headers)
    items_response.raise_for_status()
    items = items_response.json().get("value", [])
    
    print(f"\nFound {len(items)} participants\n")
    print(f"{'#':<4} {'Name':<40} {'ParticipantID':<20} {'Enrolled':<10}")
    print("-" * 80)
    
    # Look for names containing 'col', 'car', or similar
    similar_names = []
    
    for idx, item in enumerate(items, 1):
        fields = item.get("fields", {})
        first_name = fields.get('FirstName', '')
        middle_name = fields.get('MiddleName', '')
        last_name = fields.get('LastName', '')
        full_name = f"{first_name} {middle_name} {last_name}".strip().replace('  ', ' ')
        
        participant_id = fields.get('ParticipantID', '')
        enrolled = 'Yes' if fields.get('IsProgramEnrolled') else 'No'
        
        # Check for similar names
        name_lower = full_name.lower()
        if 'col' in name_lower or 'car' in name_lower:
            similar_names.append((full_name, participant_id, enrolled))
            print(f"{idx:<4} {full_name:<40} {participant_id:<20} {enrolled:<10} *SIMILAR*")
        else:
            print(f"{idx:<4} {full_name:<40} {participant_id:<20} {enrolled:<10}")
    
    if similar_names:
        print("\n" + "="*80)
        print(f"FOUND {len(similar_names)} names containing 'col' or 'car':")
        print("="*80)
        for name, pid, enrolled in similar_names:
            print(f"  • {name} (ID: {pid}, Enrolled: {enrolled})")
    else:
        print("\n" + "="*80)
        print("No names found containing 'col' or 'car'")
        print("Double-check the exact spelling in your SharePoint list")
        print("="*80)

if __name__ == "__main__":
    main()
