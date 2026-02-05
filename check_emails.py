import pandas as pd

df = pd.read_excel('Resident PII Test.xlsx')
print("Sample emails from Excel file:")
print("=" * 60)
for i in range(min(10, len(df))):
    print(f"{i+1}. {df.iloc[i]['Email']}")
print("\nAll emails work with password: 'resident'")
print("Admin login: pbatson@peakmade.com / admin")
