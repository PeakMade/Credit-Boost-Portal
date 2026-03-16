"""
Script to inspect Financial Snapshots and Job Runs schemas in detail
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
    
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]
    
    app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
    result = app.acquire_token_for_client(scopes=scope)
    return result.get("access_token")

def get_site_id(access_token):
    """Get SharePoint site ID"""
    site_hostname = "peakcampus.sharepoint.com"
    site_path = "/sites/BaseCampApps"
    site_url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    site_response = requests.get(site_url, headers=headers)
    site_response.raise_for_status()
    return site_response.json()["id"]

def inspect_list(access_token, site_id, list_id, list_name):
    """Inspect a SharePoint list in detail"""
    print(f"\n{'='*100}")
    print(f"LIST: {list_name}")
    print(f"{'='*100}\n")
    
    # Get columns
    columns_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    columns_response = requests.get(columns_url, headers=headers)
    columns_response.raise_for_status()
    columns = columns_response.json().get("value", [])
    
    print(f"COLUMNS ({len(columns)} total):")
    print("-" * 100)
    print(f"{'Column Name':<45} {'Type':<20} {'Required':<10}")
    print("-" * 100)
    
    for col in columns:
        name = col.get('name', '')
        display_name = col.get('displayName', '')
        required = col.get('required', False)
        
        # Determine type
        if col.get('text'): col_type = 'Text'
        elif col.get('number'): col_type = 'Number'
        elif col.get('dateTime'): col_type = 'DateTime'
        elif col.get('choice'): col_type = 'Choice'
        elif col.get('boolean'): col_type = 'Boolean'
        elif col.get('currency'): col_type = 'Currency'
        elif col.get('calculated'): col_type = 'Calculated'
        else: col_type = 'Other'
        
        col_display = f"{display_name} ({name})" if name != display_name and display_name else name or display_name
        print(f"{col_display:<45} {col_type:<20} {str(required):<10}")
    
    # Get sample items (with pagination)
    items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields&$top=500"
    all_items = []
    page_count = 0
    
    while items_url and page_count < 10:  # Limit to 10 pages for inspection
        page_count += 1
        items_response = requests.get(items_url, headers=headers)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        all_items.extend(items_data.get("value", []))
        items_url = items_data.get("@odata.nextLink")
    
    print(f"\n{'='*100}")
    print(f"SAMPLE DATA ({len(all_items)} items loaded across {page_count} page(s)):")
    print(f"{'='*100}\n")
    
    if all_items:
        # Show first 3 items
        for idx, item in enumerate(all_items[:3], 1):
            print(f"--- ITEM {idx} ---")
            fields = item.get('fields', {})
            
            # Filter out metadata fields
            filtered_fields = {k: v for k, v in fields.items() 
                             if not k.startswith('_') and k not in ['@odata.etag', 'Edit', 'LinkTitle', 
                                                                      'LinkTitleNoMenu', 'DocIcon', 'FolderChildCount',
                                                                      'ItemChildCount', 'id', 'Attachments', 
                                                                      'ContentType', 'Created', 'Modified',
                                                                      'AuthorLookupId', 'EditorLookupId',
                                                                      'AppAuthorLookupId', 'AppEditorLookupId']}
            
            for key, value in sorted(filtered_fields.items()):
                if value is not None and value != '':
                    value_str = str(value)[:80]  # Truncate long values
                    print(f"  {key:<40} = {value_str}")
            print()
    else:
        print("No items in this list\n")

def main():
    print("INSPECTING FINANCIAL SNAPSHOTS AND JOB RUNS")
    print("="*100)
    
    access_token = get_access_token()
    site_id = get_site_id(access_token)
    
    # Inspect Financial Snapshots
    inspect_list(access_token, site_id, 
                'bcf0d7cb-00db-4755-8898-a24dcf83702f', 
                'Monthly Financial Snapshots')
    
    # Inspect Job Runs
    inspect_list(access_token, site_id,
                '097d06bb-0bc6-4fb3-9188-d7afa3773b26',
                'CredHub Job Runs')
    
    print("\n" + "="*100)
    print("INSPECTION COMPLETE")
    print("="*100)

if __name__ == "__main__":
    main()
