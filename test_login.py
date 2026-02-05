from utils.data_loader import load_residents_from_excel

residents = load_residents_from_excel('Resident PII Test.xlsx')

print(f"Total residents loaded: {len(residents)}")
print("\nChecking first 5 residents:")
print("=" * 80)

for i in range(min(5, len(residents))):
    r = residents[i]
    print(f"\nResident {i+1}:")
    print(f"  ID: {r.get('id')}")
    print(f"  Name: {r.get('name')}")
    print(f"  Email: {r.get('email')}")
    print(f"  Property: {r.get('property')}")
    print(f"  Unit: {r.get('unit')}")

# Test login logic
test_email = "alexander.kelly@test.com"
print(f"\n\nTesting login with: {test_email}")
print("=" * 80)

resident_found = None
for resident in residents:
    if resident.get('email', '').lower() == test_email.lower():
        resident_found = resident
        break

if resident_found:
    print(f"✅ FOUND: {resident_found['name']} (ID: {resident_found['id']})")
    print(f"   Email: {resident_found['email']}")
else:
    print("❌ NOT FOUND")
