"""
Quick test script to verify CredHub data loading
"""
import sys
sys.path.insert(0, '.')

from utils.sharepoint_data_loader import load_residents_from_credhub_lists

print("Testing CredHub data loader...")
print("="*80)

residents = load_residents_from_credhub_lists()

if residents:
    print(f"\n✓ Successfully loaded {len(residents)} residents from CredHub!")
    print("\nFirst 3 residents:")
    print("-"*80)
    
    for i, resident in enumerate(residents[:3], 1):
        print(f"\nResident {i}:")
        print(f"  ID: {resident.get('id')}")
        print(f"  Name: {resident.get('name')}")
        print(f"  Property: {resident.get('property')}")
        print(f"  Unit: {resident.get('unit')}")
        print(f"  Enrolled: {resident.get('enrolled')}")
        print(f"  Account Status: {resident.get('account_status')}")
        print(f"  Total Balance: ${resident.get('total_balance', 0):,.2f}")
        print(f"  Amount Past Due: ${resident.get('amount_past_due', 0):,.2f}")
        print(f"  Monthly Rent: ${resident.get('scheduled_monthly_payment', 0):,.2f}")
        print(f"  Lease Relationship: {resident.get('lease_relationship')}")
        print(f"  Program Status: {resident.get('program_status')}")
        
        # Show payment history
        payments = resident.get('payments', [])
        print(f"\n  Payment/Reporting History ({len(payments)} records):")
        if payments:
            for payment in payments[:3]:  # Show first 3 payments
                print(f"    - {payment.get('month')}: " +
                      f"${payment.get('amount', 0):,.2f} - " +
                      f"Status: {payment.get('status')} " +
                      f"({payment.get('days_late', 0)} days late) - " +
                      f"Reported: {'Yes' if payment.get('reported') else 'No'}")
            if len(payments) > 3:
                print(f"    ... and {len(payments) - 3} more")
        else:
            print(f"    No payment history available")
        
    print("\n" + "="*80)
    print(f"Total residents loaded: {len(residents)}")
    
    # Summary stats
    enrolled = sum(1 for r in residents if r.get('enrolled'))
    delinquent = sum(1 for r in residents if 'Delinquent' in r.get('account_status', ''))
    total_past_due = sum(r.get('amount_past_due', 0) for r in residents)
    total_payments = sum(len(r.get('payments', [])) for r in residents)
    reported_payments = sum(1 for r in residents for p in r.get('payments', []) if p.get('reported'))
    
    print(f"\nSummary:")
    print(f"  Enrolled: {enrolled}")
    print(f"  Delinquent: {delinquent}")
    print(f"  Total Past Due: ${total_past_due:,.2f}")
    print(f"  Total Payment Records: {total_payments}")
    print(f"  Reported Payments: {reported_payments}")
    
else:
    print("\n✗ Failed to load CredHub data")
    print("Check your Azure credentials and SharePoint list access")
