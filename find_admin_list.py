"""
Find the correct SharePoint site and list for the admin list
"""
import sys
sys.path.insert(0, '.')

import os
from dotenv import load_dotenv
from utils.sharepoint_verification import get_sharepoint_access_token
import requests

load_dotenv()

print("="*80)
print("🔍 FINDING ADMIN LIST IN SHAREPOINT")
print("="*80)
print()

# Get access token
access_token, _ = get_sharepoint_access_token()
if not access_token:
    print("❌ Failed to get access token")
    sys.exit(1)

print("✅ Got access token")
print()

# Try different site resolution methods
site_url = os.environ.get('SHAREPOINT_SITE_URL', 'https://peakcampus.sharepoint.com/sites/BaseCampApps')
print(f"Site URL from env: {site_url}")
print()

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json"
}

# Method 1: Try the configured site URL
print("METHOD 1: Using configured site URL")
print("-"*80)
from urllib.parse import urlparse
parsed = urlparse(site_url)
site_hostname = parsed.hostname
site_path = parsed.path

graph_url_1 = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
print(f"Trying: {graph_url_1}")

response = requests.get(graph_url_1, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    site_id = data.get('id')
    print(f"✅ Site ID: {site_id}")
    print(f"   Site Name: {data.get('displayName')}")
    print(f"   Web URL: {data.get('webUrl')}")
else:
    print(f"❌ Error: {response.text[:200]}")

print()

# Method 2: Try root site
print("METHOD 2: Using root site")
print("-"*80)
graph_url_2 = f"https://graph.microsoft.com/v1.0/sites/root"
print(f"Trying: {graph_url_2}")

response2 = requests.get(graph_url_2, headers=headers)
print(f"Status: {response2.status_code}")

if response2.status_code == 200:
    data2 = response2.json()
    root_site_id = data2.get('id')
    print(f"✅ Root Site ID: {root_site_id}")
    print(f"   Site Name: {data2.get('displayName')}")
    print(f"   Web URL: {data2.get('webUrl')}")
else:
    print(f"❌ Error: {response2.text[:200]}")

print()

# Method 3: Try with just hostname (no path)
print("METHOD 3: Using hostname only")
print("-"*80)
graph_url_3 = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}"
print(f"Trying: {graph_url_3}")

response3 = requests.get(graph_url_3, headers=headers)
print(f"Status: {response3.status_code}")

if response3.status_code == 200:
    data3 = response3.json()
    hostname_site_id = data3.get('id')
    print(f"✅ Site ID: {hostname_site_id}")
    print(f"   Site Name: {data3.get('displayName')}")
    print(f"   Web URL: {data3.get('webUrl')}")
else:
    print(f"❌ Error: {response3.text[:200]}")

print()

# Now try to find the admin list
print("="*80)
print("🔍 LOOKING FOR ADMIN LIST")
print("="*80)
print()

admin_list_id = os.environ.get('SHAREPOINT_ADMIN_LIST_ID', 'c07805eb-b91c-47df-ac6e-b8dc811862c0')
print(f"Looking for list ID: {admin_list_id}")
print()

# Try each successful site
for method_name, result, site_id_key in [
    ("Method 1 (configured path)", response, 'site_id'),
    ("Method 2 (root)", response2, 'root_site_id'),
    ("Method 3 (hostname)", response3, 'hostname_site_id')
]:
    if result.status_code == 200:
        print(f"{method_name}:")
        print("-"*80)
        site_data = result.json()
        try_site_id = site_data.get('id')
        
        list_url = f"https://graph.microsoft.com/v1.0/sites/{try_site_id}/lists/{admin_list_id}"
        print(f"Trying: {list_url}")
        
        list_response = requests.get(list_url, headers=headers)
        print(f"Status: {list_response.status_code}")
        
        if list_response.status_code == 200:
            list_data = list_response.json()
            print(f"✅ FOUND IT!")
            print(f"   List Name: {list_data.get('displayName')}")
            print(f"   List Description: {list_data.get('description')}")
            print(f"   List Web URL: {list_data.get('webUrl')}")
            print()
            print(f"✅ CORRECT SITE ID TO USE: {try_site_id}")
            print()
            
            # Get list items
            items_url = f"https://graph.microsoft.com/v1.0/sites/{try_site_id}/lists/{admin_list_id}/items?expand=fields"
            items_response = requests.get(items_url, headers=headers)
            if items_response.status_code == 200:
                items_data = items_response.json()
                items = items_data.get('value', [])
                print(f"   Items in list: {len(items)}")
                if len(items) > 0:
                    print(f"   Sample fields: {list(items[0].get('fields', {}).keys())}")
            break
        else:
            print(f"❌ List not found here")
            print(f"   Error: {list_response.text[:200]}")
        print()

print("="*80)
