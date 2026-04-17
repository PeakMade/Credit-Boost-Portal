"""
Diagnostic script to investigate the session/authentication issue
where admin login is redirecting to Alexander Kelly's resident screen
"""
import sys
sys.path.insert(0, '.')

from utils.data_loader import load_residents_from_excel
from utils.sharepoint_data_loader import load_residents_from_credhub_lists
import os
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("🔍 SESSION/AUTHENTICATION DIAGNOSTIC")
print("="*80)
print()

# Check what resident ID 1 is
print("1️⃣  CHECKING DEFAULT RESIDENT (ID=1)")
print("-"*80)

try:
    residents = load_residents_from_credhub_lists()
    if residents:
        resident_1 = None
        for r in residents:
            if r.get('id') == 1:
                resident_1 = r
                break
        
        if resident_1:
            print(f"✅ Found Resident ID 1:")
            print(f"   Name: {resident_1.get('name')}")
            print(f"   Email: {resident_1.get('email')}")
            print(f"   OID: {resident_1.get('external_oid', 'Not set')}")
            print(f"   Tenant ID: {resident_1.get('external_tenant_id', 'Not set')}")
        else:
            print("❌ Resident ID 1 not found")
    else:
        print("❌ Failed to load residents from CredHub")
except Exception as e:
    print(f"❌ Error loading residents: {e}")

print()
print("2️⃣  CHECKING ADMIN AUTHORIZATION")
print("-"*80)

# Check admin list configuration
admin_list_id = os.environ.get('SHAREPOINT_ADMIN_LIST_ID')
sharepoint_site_url = os.environ.get('SHAREPOINT_SITE_URL')

print(f"Admin List ID from env: {admin_list_id or 'NOT SET'}")
print(f"SharePoint Site URL: {sharepoint_site_url or 'NOT SET'}")
print()

# Try to check admin authorization for the user
test_admin_email = "pbatson@peakmade.com"
print(f"Testing admin authorization for: {test_admin_email}")

try:
    from utils.sharepoint_verification import check_admin_authorization
    is_admin = check_admin_authorization(test_admin_email)
    
    if is_admin:
        print(f"✅ {test_admin_email} is authorized as admin")
    else:
        print(f"❌ {test_admin_email} is NOT authorized as admin")
        print("   Possible reasons:")
        print("   - Email not in SharePoint admin list")
        print("   - Admin record exists but 'Active' field is not set to Yes/True")
        print("   - SharePoint list ID or site URL is incorrect")
except Exception as e:
    print(f"❌ Error checking admin authorization: {e}")
    import traceback
    traceback.print_exc()

print()
print("3️⃣  CHECKING FOR ALEXANDER KELLY IN RESIDENT DATA")
print("-"*80)

try:
    if residents:
        alexander_kelly = None
        for r in residents:
            if 'alexander' in r.get('name', '').lower() and 'kelly' in r.get('name', '').lower():
                alexander_kelly = r
                break
        
        if alexander_kelly:
            print(f"✅ Found Alexander Kelly:")
            print(f"   ID: {alexander_kelly.get('id')}")
            print(f"   Name: {alexander_kelly.get('name')}")
            print(f"   Email: {alexander_kelly.get('email')}")
            print(f"   OID: {alexander_kelly.get('external_oid', 'Not set')}")
            print(f"   Tenant ID: {alexander_kelly.get('external_tenant_id', 'Not set')}")
        else:
            print("❌ Alexander Kelly not found in resident data")
except Exception as e:
    print(f"❌ Error searching for Alexander Kelly: {e}")

print()
print("4️⃣  RECOMMENDATIONS")
print("-"*80)
print("Based on the diagnostic above:")
print()
print("Issue A: If Resident ID 1 is Alexander Kelly:")
print("   → The system defaults to resident ID 1 when no match is found")
print("   → Your Microsoft email isn't matching any resident record")
print("   → Admin check may be failing, so system treats you as 'unmatched resident'")
print()
print("Issue B: If your email is matching Alexander Kelly's record:")
print("   → Check if Alexander Kelly's email in SharePoint matches your Microsoft email")
print("   → Check if Alexander Kelly's OID matches your Microsoft OID")
print()
print("Issue C: Session caching issue:")
print("   → Old session data from previous login may be persisting")
print("   → Solution: Clear browser cookies/session storage and try again")
print()
print("Issue D: Admin authorization failing:")
print("   → Your email might not be in the SharePoint admin list")
print("   → Admin list might not be configured correctly")
print("   → Solution: Add your email to the SharePoint admin list with Active=Yes")
print()
print("="*80)
