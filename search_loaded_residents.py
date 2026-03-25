"""
Load ALL participants and search for Colby Carter
"""
import sys
sys.path.insert(0, '.')

from utils.sharepoint_data_loader import load_residents_from_credhub_lists
import json

print("Loading ALL residents from CredHub and searching for Colby Carter...")
print("="*100)

residents = load_residents_from_credhub_lists()

print(f"\n✓ Loaded {len(residents)} total residents")
print("\nSearching for 'Colby Carter'...")

# Search for Colby Carter
matches = []
for resident in residents:
    name = resident.get('name', '').lower()
    if 'colby' in name and 'carter' in name:
        matches.append(resident)

if matches:
    print(f"\n✓ FOUND {len(matches)} match(es) in portal data!")
    for match in matches:
        print(f"\n  Resident:")
        print(f"    ID: {match.get('id')}")
        print(f"    Name: {match.get('name')}")
        print(f"    ParticipantID: {match.get('participant_id')}")
        print(f"    ResidentID: {match.get('resident_id')}")
        print(f"    LeaseID: {match.get('lease_id')}")
        print(f"    Property: {match.get('property')}")
        print(f"    Unit: {match.get('unit')}")
        print(f"    Enrolled: {match.get('enrolled')}")
        print(f"    Account Status: {match.get('account_status')}")
else:
    print(f"\n✗ Colby Carter NOT found in the {len(residents)} loaded residents")
    print("\nThis means either:")
    print("  1. The participant is missing from Lease Residents (junction table)")
    print("  2. The participant is missing a valid lease association")
    print("  3. The participant or lease data is incomplete")
    
    # Show a sample of what we DID load
    print(f"\nShowing first 5 residents as examples:")
    for i, r in enumerate(residents[:5], 1):
        print(f"  {i}. {r.get('name')} (Participant: {r.get('participant_id')}, Lease: {r.get('lease_id')})")

# Also search all participant_ids
print(f"\n\nSearching for ParticipantID 'P-15089824'...")
pid_matches = [r for r in residents if r.get('participant_id') == 'P-15089824']

if pid_matches:
    print(f"✓ Found participant by ID!")
    for match in pid_matches:
        print(f"  Name: {match.get('name')}")
else:
    print(f"✗ ParticipantID 'P-15089824' not found in loaded data")
    print(f"\nLet me check what ParticipantIDs we DO have...")
    all_pids = [r.get('participant_id') for r in residents if r.get('participant_id')]
    print(f"Total ParticipantIDs loaded: {len(set(all_pids))}")
    print(f"Sample PIDs: {list(set(all_pids))[:10]}")
