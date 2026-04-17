"""
Diagnostic to identify which app registration is being used for SharePoint access
and verify tenant/credentials configuration
"""
import os
from dotenv import load_dotenv
import msal

load_dotenv()

print("="*80)
print("🔍 APP REGISTRATION DIAGNOSTIC")
print("="*80)
print()

print("1️⃣  ENVIRONMENT VARIABLES CHECK")
print("-"*80)

# Check SharePoint access credentials
azure_client_id = os.environ.get('AZURE_CLIENT_ID')
azure_client_secret = os.environ.get('AZURE_CLIENT_SECRET')
azure_tenant_id = os.environ.get('AZURE_TENANT_ID')

print("SharePoint Access (AZURE_* variables):")
print(f"  AZURE_CLIENT_ID:     {azure_client_id[:20] if azure_client_id else 'NOT SET'}...")
print(f"  AZURE_CLIENT_SECRET: {'SET (' + str(len(azure_client_secret)) + ' chars)' if azure_client_secret else 'NOT SET'}")
print(f"  AZURE_TENANT_ID:     {azure_tenant_id if azure_tenant_id else 'NOT SET'}")
print()

# Check External ID auth credentials (for comparison)
entra_client_id = os.environ.get('ENTRA_CLIENT_ID')
auth_ext_client_id = os.environ.get('AUTH_EXTENSION_API_CLIENT_ID')
auth_ext_tenant_id = os.environ.get('AUTH_EXTENSION_TENANT_ID')

print("External ID Auth (ENTRA_* / AUTH_EXTENSION_* variables):")
print(f"  ENTRA_CLIENT_ID:              {entra_client_id[:20] if entra_client_id else 'NOT SET'}...")
print(f"  AUTH_EXTENSION_API_CLIENT_ID: {auth_ext_client_id[:20] if auth_ext_client_id else 'NOT SET'}...")
print(f"  AUTH_EXTENSION_TENANT_ID:     {auth_ext_tenant_id if auth_ext_tenant_id else 'NOT SET'}")
print()

print("2️⃣  TENANT IDENTIFICATION")
print("-"*80)

if azure_tenant_id:
    if '.onmicrosoft.com' in azure_tenant_id:
        print(f"⚠️  WARNING: AZURE_TENANT_ID looks like an External ID tenant domain")
        print(f"   Value: {azure_tenant_id}")
        print(f"   Expected: A GUID like 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'")
        print(f"   OR your main Azure AD tenant domain like 'peakmade.com'")
    elif '-' in azure_tenant_id and len(azure_tenant_id) == 36:
        print(f"✅ AZURE_TENANT_ID is a GUID: {azure_tenant_id}")
        print(f"   This should be your main Azure AD tenant (workforce tenant)")
    else:
        print(f"✅ AZURE_TENANT_ID is a domain: {azure_tenant_id}")
        print(f"   This should be your main Azure AD tenant domain")

if auth_ext_tenant_id:
    print()
    print(f"External ID tenant: {auth_ext_tenant_id}")
    print(f"   This is separate from your SharePoint tenant")

print()
print("3️⃣  TOKEN ACQUISITION TEST")
print("-"*80)

if not all([azure_client_id, azure_client_secret, azure_tenant_id]):
    print("❌ Cannot test - AZURE_* credentials not fully configured")
else:
    try:
        print(f"Attempting to acquire token for SharePoint access...")
        print(f"  Client ID: {azure_client_id[:20]}...")
        print(f"  Tenant: {azure_tenant_id}")
        print(f"  Authority: https://login.microsoftonline.com/{azure_tenant_id}")
        print(f"  Scope: https://graph.microsoft.com/.default")
        print()
        
        authority = f"https://login.microsoftonline.com/{azure_tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]
        
        app = msal.ConfidentialClientApplication(
            azure_client_id,
            authority=authority,
            client_credential=azure_client_secret
        )
        
        result = app.acquire_token_for_client(scopes=scope)
        
        if "access_token" in result:
            print("✅ Token acquired successfully!")
            print(f"   Token length: {len(result['access_token'])} chars")
            print(f"   Expires in: {result.get('expires_in', 'unknown')} seconds")
            
            # Decode the token to see claims (for diagnostic purposes)
            import jwt
            import json
            
            # Decode without verification (just to inspect)
            decoded = jwt.decode(result['access_token'], options={"verify_signature": False})
            
            print()
            print("   Token Claims:")
            print(f"     Issuer (iss): {decoded.get('iss', 'N/A')}")
            print(f"     Audience (aud): {decoded.get('aud', 'N/A')}")
            print(f"     App ID (appid): {decoded.get('appid', 'N/A')}")
            print(f"     Tenant ID (tid): {decoded.get('tid', 'N/A')}")
            
            if decoded.get('roles'):
                print(f"     Roles:")
                for role in decoded.get('roles', []):
                    print(f"       - {role}")
            
        else:
            print("❌ Token acquisition failed!")
            print(f"   Error: {result.get('error', 'Unknown')}")
            print(f"   Description: {result.get('error_description', 'No description')}")
            
            if 'AADSTS' in str(result.get('error_description', '')):
                print()
                print("   This is an Azure AD authentication error.")
                print("   Common causes:")
                print("     - Client ID doesn't exist in the tenant")
                print("     - Client secret is incorrect or expired")
                print("     - Tenant ID is wrong")
                
    except Exception as e:
        print(f"❌ Exception during token acquisition: {e}")
        import traceback
        traceback.print_exc()

print()
print("4️⃣  DIAGNOSIS")
print("-"*80)

print("To fix the 401 Unauthorized error:")
print()
print("Check which app registration you want to use for SharePoint:")
print("  Option A: The app shown in your screenshot ('PeakMade Real Estate')")
print("  Option B: A different app registration")
print()
print("Then verify in Azure Portal:")
print("  1. Go to App Registrations → [Your App]")
print("  2. Copy the 'Application (client) ID'")
print("  3. Copy the 'Directory (tenant) ID'")
print("  4. Go to Certificates & secrets → Create new client secret")
print("  5. Copy the secret value immediately")
print()
print("Set these in your environment variables (.env or Azure config):")
print(f"  AZURE_CLIENT_ID=<Application (client) ID>")
print(f"  AZURE_CLIENT_SECRET=<Client secret value>")
print(f"  AZURE_TENANT_ID=<Directory (tenant) ID>")
print()
print("⚠️  IMPORTANT: The tenant ID should be your MAIN Azure AD tenant")
print("   (where SharePoint lives), NOT the External ID tenant!")
print()
print("="*80)
