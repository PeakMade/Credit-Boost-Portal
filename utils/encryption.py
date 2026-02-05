"""
SSN Encryption utilities using Fernet symmetric encryption
"""
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()


def get_cipher():
    """Get Fernet cipher instance"""
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY not found in environment variables")
    return Fernet(key.encode())


def encrypt_ssn(ssn):
    """
    Encrypt an SSN (format: XXX-XX-XXXX)
    Returns encrypted bytes as a string
    """
    cipher = get_cipher()
    encrypted_bytes = cipher.encrypt(ssn.encode())
    return encrypted_bytes.decode()


def decrypt_ssn(encrypted_ssn):
    """
    Decrypt an encrypted SSN
    Returns original SSN string
    """
    cipher = get_cipher()
    decrypted_bytes = cipher.decrypt(encrypted_ssn.encode())
    return decrypted_bytes.decode()


def mask_ssn(ssn):
    """
    Mask SSN to show only last 4 digits
    Input: XXX-XX-XXXX or encrypted string
    Output: ***-**-XXXX
    """
    if not ssn:
        return "***-**-****"
    
    # If it looks encrypted (long string), decrypt first
    if len(ssn) > 15:
        try:
            ssn = decrypt_ssn(ssn)
        except Exception:
            return "***-**-****"
    
    # Mask the SSN
    if len(ssn) >= 11:  # Format: XXX-XX-XXXX
        return f"***-**-{ssn[-4:]}"
    elif len(ssn) >= 4:
        return f"***-**-{ssn[-4:]}"
    else:
        return "***-**-****"


def get_last4_ssn(ssn):
    """
    Get last 4 digits of SSN
    Input: XXX-XX-XXXX or encrypted string
    Output: XXXX
    """
    if not ssn:
        return "****"
    
    # If it looks encrypted, decrypt first
    if len(ssn) > 15:
        try:
            ssn = decrypt_ssn(ssn)
        except Exception:
            return "****"
    
    # Extract last 4 digits
    if len(ssn) >= 11:  # Format: XXX-XX-XXXX
        return ssn[-4:]
    elif len(ssn) >= 4:
        return ssn[-4:]
    else:
        return "****"
