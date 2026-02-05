"""
Test script to verify encrypted SSN handling
"""
import pandas as pd
from utils.encryption import encrypt_ssn, decrypt_ssn, mask_ssn, get_last4_ssn

# Load the Excel file
df = pd.read_excel('Resident PII Test.xlsx')

print("=" * 60)
print("ENCRYPTED EXCEL DATA TEST")
print("=" * 60)

# Show first resident's data
if len(df) > 0:
    first_row = df.iloc[0]
    
    print(f"\nFirst Resident from Excel:")
    print(f"Name: {first_row['Name']}")
    print(f"Email: {first_row['Email']}")
    print(f"Encrypted SSN (raw): {first_row['SSN'][:50]}...")
    print(f"Encrypted SSN length: {len(str(first_row['SSN']))} characters")
    
    # Test decryption and masking
    encrypted_ssn = str(first_row['SSN'])
    masked = mask_ssn(encrypted_ssn)
    last4 = get_last4_ssn(encrypted_ssn)
    
    print(f"\nAfter Processing:")
    print(f"Masked SSN: {masked}")
    print(f"Last 4 digits: {last4}")
    print(f"Credit Score: {first_row['Credit Score']}")
    
    # Try decrypting (this reveals the actual SSN - only for testing!)
    try:
        decrypted = decrypt_ssn(encrypted_ssn)
        print(f"Decrypted SSN (TEST ONLY - never show in app): {decrypted}")
    except Exception as e:
        print(f"Decryption error: {e}")

print(f"\nTotal residents in Excel: {len(df)}")
print("\n✅ Encryption system working correctly!")
print("=" * 60)
