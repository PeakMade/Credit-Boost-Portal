"""
Quick script to show sample resident emails for testing login
"""
import pandas as pd

df = pd.read_excel('Resident PII Test.xlsx')

print("=" * 60)
print("SAMPLE RESIDENT EMAILS FOR LOGIN TESTING")
print("=" * 60)
print("\nPassword for all residents: 'resident'")
print("\nFirst 10 resident emails:")
print("-" * 60)

for i in range(min(10, len(df))):
    row = df.iloc[i]
    print(f"{i+1}. {row['Email']:<40} | {row['Name']}")

print("\n" + "=" * 60)
print(f"Total residents: {len(df)}")
print("=" * 60)
