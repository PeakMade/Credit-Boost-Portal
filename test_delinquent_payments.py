"""
Test script to specifically show delinquent residents with payment history
"""
import sys
sys.path.insert(0, '.')

from utils.sharepoint_data_loader import load_residents_from_credhub_lists

print("Testing CredHub Payment History - Focusing on Delinquent Residents")
print("="*100)

residents = load_residents_from_credhub_lists()

if residents:
    # Find delinquent residents
    delinquent_residents = [r for r in residents if 'Delinquent' in r.get('account_status', '')]
    
    print(f"\n✓ Found {len(delinquent_residents)} delinquent residents out of {len(residents)} total")
    print("\nDelinquent Resident Payment History:")
    print("="*100)
    
    for i, resident in enumerate(delinquent_residents[:5], 1):  # Show first 5 delinquent
        print(f"\n{'='*100}")
        print(f"Delinquent Resident #{i}: {resident.get('name')}")
        print(f"{'='*100}")
        print(f"  Property: {resident.get('property')} | Unit: {resident.get('unit')}")
        print(f"  Account Status: {resident.get('account_status')}")
        print(f"  Total Balance: ${resident.get('total_balance', 0):,.2f}")
        print(f"  Amount Past Due: ${resident.get('amount_past_due', 0):,.2f}")
        print(f"  Monthly Rent: ${resident.get('scheduled_monthly_payment', 0):,.2f}")
        print(f"  Enrolled & Reporting: {resident.get('enrolled')}")
        
        # Show detailed payment history
        payments = resident.get('payments', [])
        print(f"\n  Payment/Reporting History ({len(payments)} records):")
        print(f"  {'-'*90}")
        print(f"  {'Month':<12} {'Amount':<12} {'Status':<10} {'Days Late':<12} {'Reported':<10} {'Balance':<12}")
        print(f"  {'-'*90}")
        
        for payment in payments:
            month = payment.get('month', '')
            amount = payment.get('amount', 0)
            status = payment.get('status', '')
            days_late = payment.get('days_late', 0)
            reported = 'Yes' if payment.get('reported') else 'No'
            balance = payment.get('total_balance', 0)
            
            print(f"  {month:<12} ${amount:<11,.2f} {status:<10} {days_late:<12} {reported:<10} ${balance:,.2f}")
    
    # Also show a current resident for comparison
    current_residents = [r for r in residents if r.get('account_status') == 'Current' and len(r.get('payments', [])) > 0]
    if current_residents:
        print(f"\n{'='*100}")
        print(f"Current (Non-Delinquent) Resident for Comparison: {current_residents[0].get('name')}")
        print(f"{'='*100}")
        print(f"  Property: {current_residents[0].get('property')} | Unit: {current_residents[0].get('unit')}")
        print(f"  Account Status: {current_residents[0].get('account_status')}")
        print(f"  Total Balance: ${current_residents[0].get('total_balance', 0):,.2f}")
        print(f"  Enrolled & Reporting: {current_residents[0].get('enrolled')}")
        
        payments = current_residents[0].get('payments', [])[:3]
        print(f"\n  Recent Payment History:")
        print(f"  {'-'*90}")
        print(f"  {'Month':<12} {'Amount':<12} {'Status':<10} {'Days Late':<12} {'Reported':<10} {'Balance':<12}")
        print(f"  {'-'*90}")
        
        for payment in payments:
            month = payment.get('month', '')
            amount = payment.get('amount', 0)
            status = payment.get('status', '')
            days_late = payment.get('days_late', 0)
            reported = 'Yes' if payment.get('reported') else 'No'
            balance = payment.get('total_balance', 0)
            
            print(f"  {month:<12} ${amount:<11,.2f} {status:<10} {days_late:<12} {reported:<10} ${balance:,.2f}")
    
    print("\n" + "="*100)
    print("\nSUMMARY:")
    print("="*100)
    total_payments = sum(len(r.get('payments', [])) for r in residents)
    reported_payments = sum(1 for r in residents for p in r.get('payments', []) if p.get('reported'))
    late_payments = sum(1 for r in residents for p in r.get('payments', []) if p.get('status') == 'Late')
    
    print(f"Total Residents: {len(residents)}")
    print(f"Delinquent Residents: {len(delinquent_residents)}")
    print(f"Total Payment Records: {total_payments}")
    print(f"Reported Payments: {reported_payments}")
    print(f"Late Payments: {late_payments}")
    print(f"On-Time Payments: {total_payments - late_payments}")
    
else:
    print("\n✗ Failed to load CredHub data")
