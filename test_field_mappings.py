"""
Test script to verify field mappings and data relationships
"""
import os
from dotenv import load_dotenv
import msal
import requests
from datetime import datetime

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

def main():
    print("TESTING FIELD MAPPINGS AND DATA RELATIONSHIPS")
    print("="*100)
    
    access_token = get_access_token()
    site_id = get_site_id(access_token)
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    # Get ONE Financial Snapshot with a balance > 0 (delinquent)
    print("\n1. FINANCIAL SNAPSHOT (Delinquent Example)")
    print("-"*100)
    snapshots_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/bcf0d7cb-00db-4755-8898-a24dcf83702f/items?expand=fields&$top=500"
    response = requests.get(snapshots_url, headers=headers)
    snapshots = response.json().get("value", [])
    
    # Find a delinquent one
    delinquent_snapshot = None
    for item in snapshots:
        fields = item.get('fields', {})
        balance = float(fields.get('TotalLedgerBalance', 0) or 0)
        if balance > 0:
            delinquent_snapshot = fields
            break
    
    if delinquent_snapshot:
        print(f"LeaseId: {delinquent_snapshot.get('LeaseId')}")
        print(f"AsOfDate: {delinquent_snapshot.get('AsOfDate')}")
        print(f"TotalLedgerBalance: ${delinquent_snapshot.get('TotalLedgerBalance', 0)}")
        print(f"MonthlyRentAmount: ${delinquent_snapshot.get('MonthlyRentAmount', 0)}")
        print(f"LastPaymentDate: {delinquent_snapshot.get('LastPaymentDate')}")
        print(f"LastPaymentAmount: ${delinquent_snapshot.get('LastPaymentAmount', 0)}")
        print(f"BalanceAged30To59: {delinquent_snapshot.get('BalanceAged30To59')}")
        print(f"BalanceAged60To89: {delinquent_snapshot.get('BalanceAged60To89')}")
        print(f"BalanceAged90To119: {delinquent_snapshot.get('BalanceAged90To119')}")
        print(f"BalanceAged120To149: {delinquent_snapshot.get('BalanceAged120To149')}")
        print(f"BalanceAged150To179: {delinquent_snapshot.get('BalanceAged150To179')}")
        print(f"BalanceAged180Plus: {delinquent_snapshot.get('BalanceAged180Plus')}")
        print(f"OldestOpenChargeDate: {delinquent_snapshot.get('OldestOpenChargeDate')}")
    
    # Get Reporting Cycles
    print("\n2. REPORTING CYCLES")
    print("-"*100)
    cycles_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/c2545153-1aa1-409b-aad4-a6361966af0a/items?expand=fields"
    response = requests.get(cycles_url, headers=headers)
    cycles = response.json().get("value", [])
    
    print(f"Found {len(cycles)} reporting cycle(s)")
    for item in cycles:
        fields = item.get('fields', {})
        print(f"\nCycle ID: {fields.get('ReportingCycleId')}")
        print(f"  Period: {fields.get('ReportPeriod')}")
        print(f"  Start Date: {fields.get('StartDate')}")
        print(f"  End Date: {fields.get('EndDate')}")
        print(f"  Status: {fields.get('CycleStatus')}")
    
    # Get Job Runs
    print("\n3. CREDHUB JOB RUNS")
    print("-"*100)
    jobs_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/097d06bb-0bc6-4fb3-9188-d7afa3773b26/items?expand=fields"
    response = requests.get(jobs_url, headers=headers)
    jobs = response.json().get("value", [])
    
    print(f"Found {len(jobs)} job run(s)")
    for item in jobs:
        fields = item.get('fields', {})
        print(f"\nJob ID: {fields.get('CredHubJobRunId')}")
        print(f"  Reporting Cycle: {fields.get('ReportingCycleId')}")
        print(f"  Job Type: {fields.get('JobType')}")
        print(f"  Job Status: {fields.get('JobStatus')}")
        print(f"  Submission Status: {fields.get('SubmissionStatus')}")
        print(f"  Submitted At: {fields.get('SubmittedAt')}")
        print(f"  Status Summary: {fields.get('StatusSummary')}")
        print(f"  Metro2 Generated: {fields.get('Metro2Generated')}")
        print(f"  Errors: {fields.get('ErrorCount')}")
        print(f"  Warnings: {fields.get('WarningCount')}")
    
    # Now test the data loader
    print("\n4. TESTING DATA LOADER")
    print("-"*100)
    from utils.sharepoint_data_loader import load_residents_from_credhub_lists
    
    residents = load_residents_from_credhub_lists()
    print(f"\nLoaded {len(residents)} residents")
    
    # Show ALL residents
    for idx, resident in enumerate(residents, 1):
        print(f"\n--- RESIDENT {idx} ---")
        print(f"  Name: {resident.get('name')}")
        print(f"  LeaseID: {resident.get('lease_id')}")
        print(f"  ParticipantID: {resident.get('participant_id')}")
        print(f"  Status: {resident.get('account_status')}")
        print(f"  Enrolled: {resident.get('enrolled')}")
        print(f"  Amount Past Due: ${resident.get('amount_past_due', 0)}")
        print(f"  Last Payment Date: {resident.get('last_payment_date')}")
        print(f"  Last Payment Amount: ${resident.get('last_payment_amount', 0)}")
        print(f"  Scheduled Monthly: ${resident.get('scheduled_monthly_payment', 0)}")
        print(f"  Total Balance: ${resident.get('total_balance', 0)}")
        
        print(f"  Payment History ({len(resident.get('payments', []))} records):")
        for payment in resident.get('payments', [])[:5]:
            print(f"    {payment.get('month')}: {payment.get('status')} - "
                  f"${payment.get('amount')} - "
                  f"{payment.get('days_late')} days late - "
                  f"Balance: ${payment.get('total_balance', 0)}")
    
    print("\n" + "="*100)
    print("TEST COMPLETE")
    print("="*100)

if __name__ == "__main__":
    main()
