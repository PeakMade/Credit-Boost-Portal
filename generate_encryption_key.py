"""
Generate encryption key for SSN encryption
Run this ONCE to create the ENCRYPTION_KEY in .env file
"""
from cryptography.fernet import Fernet
import os

# Generate a new Fernet key
key = Fernet.generate_key()

# Read existing .env file
env_file = '.env'
env_content = ''

if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        env_content = f.read()

# Check if ENCRYPTION_KEY already exists
if 'ENCRYPTION_KEY=' in env_content:
    print("⚠️  ENCRYPTION_KEY already exists in .env file")
    response = input("Do you want to overwrite it? (yes/no): ")
    if response.lower() != 'yes':
        print("Keeping existing key.")
        exit(0)
    
    # Remove old key
    lines = env_content.split('\n')
    lines = [line for line in lines if not line.startswith('ENCRYPTION_KEY=')]
    env_content = '\n'.join(lines)

# Add new key
if env_content and not env_content.endswith('\n'):
    env_content += '\n'

env_content += f"ENCRYPTION_KEY={key.decode()}\n"

# Write back to .env
with open(env_file, 'w') as f:
    f.write(env_content)

print("✅ Encryption key generated and saved to .env file")
print("⚠️  IMPORTANT: Never commit .env file to version control!")
print("⚠️  IMPORTANT: Keep this key secure - if lost, encrypted SSNs cannot be decrypted!")
