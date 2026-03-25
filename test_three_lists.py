"""
Test script to verify SharePoint data loading from three lists
Tests the updated data loader to ensure it works correctly
"""
import os
from dotenv import load_dotenv
from utils.sharepoint_data_loader import load_residents_from_sharepoint_list

load_dotenv()

def test_sharepoint_loading():
    """Test loading data from three SharePoint lists"""
    print("="*80)
    print("TESTING SHAREPOINT DATA LOADING FROM THREE LISTS")
    print("="*80)
    print()
    
    # Set to use SharePoint data (not test data)
    os.environ['USE_TEST_DATA'] = 'false'
    
    try:
        print("Loading residents from SharePoint...")
        residents = load_residents_from_sharepoint_list()
        
        print()
        print("="*80)
        print("LOADING SUMMARY")
        print("="*80)
        print(f"Total residents loaded: {len(residents)}")
        print()
        
        if residents:
            # Show first resident details
            first_resident = residents[0]
            print("="*80)
            print("SAMPLE RESIDENT DATA (First Resident)")
            print("="*80)
            print(f"ID: {first_resident.get('id')}")
            print(f"Account Number: {first_resident.get('account_number')}")
            print(f"Name: {first_resident.get('name')}")
            print(f"First Name: {first_resident.get('first_name')}")
            print(f"Last Name: {first_resident.get('last_name')}")
            print(f"DOB: {first_resident.get('dob')}")
            print(f"SSN Last 4: {first_resident.get('last4_ssn')}")
            print()
            print(f"Property: {first_resident.get('property')}")
            print(f"Unit: {first_resident.get('unit')}")
            print()
            print(f"Address: {first_resident.get('address')}")
            print(f"City: {first_resident.get('city')}")
            print(f"State: {first_resident.get('state')}")
            print(f"Zip: {first_resident.get('zip')}")
            print()
            print(f"Monthly Rent: ${first_resident.get('monthly_rent')}")
            print(f"Account Status: {first_resident.get('account_status')}")
            print(f"Date Opened: {first_resident.get('date_opened')}")
            print(f"Enrollment Status: {first_resident.get('enrollment_status')}")
            print(f"Days Late: {first_resident.get('days_late')}")
            print(f"Amount Past Due: ${first_resident.get('amount_past_due')}")
            print(f"Current Balance: ${first_resident.get('current_balance')}")
            print()
            
            # Show payment history
            payments = first_resident.get('payments', [])
            print(f"Payment History: {len(payments)} statements")
            if payments:
                print()
                print("Recent Payments:")
                print(f"{'Month':<15} {'Amount':<12} {'Date':<15} {'Status':<12} {'Days Late':<10} {'Reported':<10}")
                print("-" * 80)
                for payment in payments[:5]:  # Show first 5 payments
                    print(f"{payment.get('month', 'N/A'):<15} "
                          f"${payment.get('amount', 0):>10.2f} "
                          f"{payment.get('date_paid', 'N/A'):<15} "
                          f"{payment.get('status', 'N/A'):<12} "
                          f"{payment.get('days_late', 0):<10} "
                          f"{str(payment.get('reported', False)):<10}")
            print()
            
            # Summary statistics
            print("="*80)
            print("SUMMARY STATISTICS")
            print("="*80)
            
            total_with_payments = sum(1 for r in residents if r.get('payments'))
            total_delinquent = sum(1 for r in residents if r.get('account_status') == 'Delinquent')
            total_late = sum(1 for r in residents if r.get('account_status') == 'Late')
            total_current = sum(1 for r in residents if r.get('account_status') == 'Current')
            
            print(f"Residents with payment history: {total_with_payments}")
            print(f"Current accounts: {total_current}")
            print(f"Late accounts: {total_late}")
            print(f"Delinquent accounts: {total_delinquent}")
            print()
            
            # Test specific fields from each list
            print("="*80)
            print("FIELD VERIFICATION (From Three Lists)")
            print("="*80)
            
            # Check if we have data from all three lists
            has_tenant_data = any(r.get('first_name') for r in residents)
            has_account_data = any(r.get('date_opened') for r in residents)
            has_statement_data = any(r.get('payments') for r in residents)
            
            print(f"✓ Tenant data (from Tenants list): {'Yes' if has_tenant_data else 'No'}")
            print(f"✓ Account data (from Accounts list): {'Yes' if has_account_data else 'No'}")
            print(f"✓ Statement data (from Statements list): {'Yes' if has_statement_data else 'No'}")
            print()
            
            print("="*80)
            print("TEST PASSED!")
            print("="*80)
        else:
            print("WARNING: No residents loaded from SharePoint")
            
    except Exception as e:
        print()
        print("="*80)
        print("ERROR DURING TESTING")
        print("="*80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("TEST FAILED!")
        print("="*80)


if __name__ == "__main__":
    test_sharepoint_loading()
