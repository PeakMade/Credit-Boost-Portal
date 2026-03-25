"""
Script to inspect SharePoint list schemas for the three Credit Boost lists
"""
import os
import msal
import requests
from dotenv import load_dotenv
import json

load_dotenv()

def get_access_token():
    """Get Microsoft Graph API access token"""
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        print("Error: Azure credentials not found in .env file")
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
        print(f"Error description: {result.get('error_description')}")
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
    
    print(f"Resolving SharePoint site: {site_hostname}{site_path}")
    site_response = requests.get(site_url, headers=headers)
    site_response.raise_for_status()
    site_data = site_response.json()
    site_id = site_data["id"]
    
    print(f"✓ Site ID: {site_id}\n")
    return site_id


def inspect_list_schema(access_token, site_id, list_id, list_name):
    """Inspect the schema of a SharePoint list"""
    print(f"\n{'='*80}")
    print(f"INSPECTING LIST: {list_name}")
    print(f"List ID: {list_id}")
    print(f"{'='*80}\n")
    
    # Get list columns
    columns_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    columns_response = requests.get(columns_url, headers=headers)
    columns_response.raise_for_status()
    columns_data = columns_response.json()
    
    columns = columns_data.get("value", [])
    
    print(f"Found {len(columns)} columns:\n")
    print(f"{'Column Name':<40} {'Type':<20} {'Required':<10}")
    print("-" * 80)
    
    for col in columns:
        name = col.get('name', '')
        display_name = col.get('displayName', '')
        col_type = ''
        required = col.get('required', False)
        
        # Determine column type
        if col.get('text'):
            col_type = 'Text'
            if col['text'].get('allowMultipleLines'):
                col_type = 'Multi-line Text'
        elif col.get('number'):
            col_type = 'Number'
        elif col.get('dateTime'):
            col_type = 'DateTime'
        elif col.get('choice'):
            col_type = f"Choice ({', '.join(col['choice'].get('choices', []))})"
        elif col.get('boolean'):
            col_type = 'Boolean'
        elif col.get('lookup'):
            col_type = 'Lookup'
        elif col.get('currency'):
            col_type = 'Currency'
        elif col.get('personOrGroup'):
            col_type = 'Person/Group'
        else:
            col_type = 'Other'
        
        # Show both internal name and display name if different
        if name != display_name and display_name:
            col_display = f"{display_name} ({name})"
        else:
            col_display = name or display_name
        
        print(f"{col_display:<40} {col_type:<20} {str(required):<10}")
    
    # Get a sample item to see actual field names used
    items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields&$top=1"
    
    items_response = requests.get(items_url, headers=headers)
    items_response.raise_for_status()
    items_data = items_response.json()
    
    items = items_data.get("value", [])
    
    if items:
        print(f"\n{'='*80}")
        print("SAMPLE ITEM FIELDS (First Record):")
        print(f"{'='*80}\n")
        
        fields = items[0].get('fields', {})
        print(f"{'Field Name':<40} {'Sample Value':<40}")
        print("-" * 80)
        
        for field_name, field_value in fields.items():
            # Truncate long values
            value_str = str(field_value)
            if len(value_str) > 40:
                value_str = value_str[:37] + "..."
            print(f"{field_name:<40} {value_str:<40}")
    
    print("\n")


def main():
    """Main function to inspect all three SharePoint lists"""
    
    # SharePoint lists to inspect
    lists_to_check = [
        {
            'name': 'Credit Boost - Tenants',
            'id': '7569dfb7-5d2f-452d-a384-0af63b38b559'
        },
        {
            'name': 'Credit Boost - Accounts',
            'id': 'f836ae36-efe3-47e5-8f11-d191422ca5d4'
        },
        {
            'name': 'Credit Boost - Statements',
            'id': '15cdc70e-ba08-4f9b-9ba2-79d66e8c6552'
        }
    ]
    
    # Get access token
    print("Authenticating with Microsoft Graph API...")
    access_token = get_access_token()
    if not access_token:
        return
    
    print("✓ Successfully authenticated\n")
    
    # Get site ID
    site_id = get_site_id(access_token)
    
    # Inspect each list
    for list_info in lists_to_check:
        try:
            inspect_list_schema(access_token, site_id, list_info['id'], list_info['name'])
        except Exception as e:
            print(f"Error inspecting list {list_info['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("INSPECTION COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
