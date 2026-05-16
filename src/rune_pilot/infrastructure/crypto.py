"""
Güvenli şifreleme/şifre çözme işlemleri.
Yerel makineye özgü bir şifreleme anahtarı (Fernet) kullanarak şifreleri saklar.
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def _get_machine_key() -> bytes:
    """
    Geçerli Windows kullanıcısı ve makine adına göre deterministik bir anahtar üretir.
    Böylece şifrelenmiş veriler sadece bu bilgisayarda ve bu kullanıcı oturumunda çözülebilir.
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
    """Parolayı yerel makineye özel anahtarla şifreler."""
    if not plain_text:
        return ""
    fernet = Fernet(_get_machine_key())
    encrypted = fernet.encrypt(plain_text.encode("utf-8"))
    return encrypted.decode("utf-8")

def decrypt_password(encrypted_text: str) -> str:
    """Parolanın şifresini çözer."""
    if not encrypted_text:
        return ""
    try:
        fernet = Fernet(_get_machine_key())
        decrypted = fernet.decrypt(encrypted_text.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # Şifre çözülemezse (başka makineye taşınmışsa veya bozuksa) boş dönebiliriz.
        return ""
