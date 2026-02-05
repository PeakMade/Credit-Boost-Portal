"""
Generate test resident data with encrypted SSNs
Uses Faker for realistic fake names and SSNs
"""
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
import random
from utils.encryption import encrypt_ssn

# Initialize Faker
fake = Faker()

def generate_test_residents(num_residents=1000):
    """Generate test resident data with encrypted SSNs"""
    
    residents = []
    
    for i in range(num_residents):
        # Generate fake personal info
        first_name = fake.first_name()
        last_name = fake.last_name()
        name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}@test.com"
        
        # Generate fake SSN and encrypt it
        ssn = fake.ssn()
        encrypted_ssn = encrypt_ssn(ssn)
        
        # Generate other fields
        phone = fake.phone_number()
        unit = f"{random.randint(1, 20)}{random.choice(['A', 'B', 'C', 'D', ''])}"
        dob = fake.date_of_birth(minimum_age=21, maximum_age=65).strftime('%Y-%m-%d')
        address = fake.street_address()
        
        # Random credit score
        credit_score = random.choice([
            random.randint(300, 579),  # Poor
            random.randint(580, 669),  # Fair
            random.randint(670, 739),  # Good
            random.randint(740, 799),  # Very Good
            random.randint(800, 850),  # Exceptional
        ])
        
        # Generate lease dates
        lease_start = datetime.now() - timedelta(days=random.randint(30, 365))
        lease_end = lease_start + timedelta(days=365)
        
        # Monthly rent
        monthly_rent = random.choice([1200, 1350, 1500, 1650, 1800, 2000])
        
        resident = {
            'Name': name,
            'Email': email,
            'Phone': phone,
            'Unit': unit,
            'Property': '48 West',
            'DOB': dob,
            'Address': address,
            'SSN': encrypted_ssn,  # Encrypted SSN
            'Credit Score': credit_score,
            'Lease Start': lease_start.strftime('%Y-%m-%d'),
            'Lease End': lease_end.strftime('%Y-%m-%d'),
            'Monthly Rent': monthly_rent
        }
        
        residents.append(resident)
    
    return residents


if __name__ == '__main__':
    print("Generating test resident data...")
    
    # Generate 1000 test residents
    residents = generate_test_residents(1000)
    
    # Create DataFrame
    df = pd.DataFrame(residents)
    
    # Save to Excel
    output_file = 'Resident PII Test.xlsx'
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"✅ Created {output_file} with {len(residents)} residents")
    print(f"✅ All SSNs are encrypted")
    print("\nSample resident emails (password: 'resident'):")
    for i in range(min(5, len(residents))):
        print(f"  - {residents[i]['Email']}")
    
    print("\nAdmin login:")
    print("  - pbatson@peakmade.com (password: 'admin')")
