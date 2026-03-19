"""
Test script to verify first_name, last_name, and current_balance fields
"""
from utils.sharepoint_data_loader import load_residents_from_credhub_lists

print("Loading CredHub residents...")
residents = load_residents_from_credhub_lists()

if residents:
    print(f"\n✓ Loaded {len(residents)} residents\n")
    
    # Check first 3 residents
    for i, resident in enumerate(residents[:3], 1):
        print(f"--- RESIDENT {i} ---")
        print(f"  ID: {resident.get('id')}")
        print(f"  Full Name: {resident.get('name')}")
        print(f"  First Name: {resident.get('first_name')}")
        print(f"  Last Name: {resident.get('last_name')}")
        print(f"  Current Balance: ${resident.get('current_balance', 0)}")
        print(f"  Total Balance: ${resident.get('total_balance', 0)}")
        print(f"  Account Status: {resident.get('account_status')}")
        print()
    
    # Verify all residents have the required fields
    missing_first_name = [r for r in residents if not r.get('first_name')]
    missing_last_name = [r for r in residents if not r.get('last_name')]
    missing_current_balance = [r for r in residents if r.get('current_balance') is None]
    
    print(f"Field Validation:")
    print(f"  Residents missing first_name: {len(missing_first_name)}")
    print(f"  Residents missing last_name: {len(missing_last_name)}")
    print(f"  Residents missing current_balance: {len(missing_current_balance)}")
    
    if not missing_first_name and not missing_last_name and not missing_current_balance:
        print("\n✓ All fields are properly populated!")
    else:
        print("\n⚠ Some fields are missing")
        if missing_first_name:
            print(f"  First resident missing first_name: {missing_first_name[0]}")
        if missing_current_balance:
            print(f"  First resident missing current_balance: {missing_current_balance[0]}")
else:
    print("⚠ No residents loaded")
