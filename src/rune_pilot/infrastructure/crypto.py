"""
Secure password encryption/decryption using a machine-specific Fernet key.

Encrypted data can only be decrypted on the same machine and user account.
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def _get_machine_key() -> bytes:
    """
    Derives a deterministic key from the current Windows username and computer name.
    Ensures encrypted credentials can only be decrypted on this machine and user session.
    """
    # Use environment variables that are tied to the local machine and user
    user = os.getenv("USERNAME", "default_user")
    computer = os.getenv("COMPUTERNAME", "default_computer")

    # Combine them to build a unique machine identifier
    machine_id = f"{user}_{computer}".encode("utf-8")

    # Use PBKDF2 to derive a 32-byte secure key from the machine identifier
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"RunePilot_Secure_Salt_v1",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key

def encrypt_password(plain_text: str) -> str:
    """Encrypts a password using the machine-specific key."""
    if not plain_text:
        return ""
    fernet = Fernet(_get_machine_key())
    encrypted = fernet.encrypt(plain_text.encode("utf-8"))
    return encrypted.decode("utf-8")

def decrypt_password(encrypted_text: str) -> str:
    """Decrypts an encrypted password."""
    if not encrypted_text:
        return ""
    try:
        fernet = Fernet(_get_machine_key())
        decrypted = fernet.decrypt(encrypted_text.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # Returns empty string if decryption fails (e.g. moved to another machine or data is corrupt).
        return ""
