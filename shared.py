import os
import json
from pathlib import Path
import base64
from aqt.utils import showInfo

# Initialize questions cycle
questions_cycle = {
    "questions": [],
    "index": 0
}

# Global variable for user access key
user_access_key = None

class CredentialManager:
    def __init__(self):
        self.anki_dir = os.path.dirname(os.path.abspath(__file__))
        self.creds_file = os.path.join(self.anki_dir, '.creds')
        self.encryption_available = False
        self._init_encryption()

    def _init_encryption(self):
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            # Use a constant salt (not ideal but acceptable for this use case)
            salt = b'AnkiExamSalt'
            # Use the machine's stable MAC address as a unique key
            from .utils import get_stable_mac_address
            device_id = get_stable_mac_address().encode()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(device_id))
            self.fernet = Fernet(key)
            self.encryption_available = True
        except ImportError:
            print("Cryptography package not available. Using basic encoding.")
            self.encryption_available = False

    def _basic_encode(self, data: str) -> bytes:
        """Basic encoding when cryptography is not available"""
        return base64.b64encode(data.encode())

    def _basic_decode(self, data: bytes) -> str:
        """Basic decoding when cryptography is not available"""
        return base64.b64decode(data).decode()

    def save_credentials(self, username, password, access_key=None):
        """Save credentials to file"""
        try:
            data = {
                'username': username,
                'password': password,
                'access_key': access_key
            }
            if self.encryption_available:
                encrypted = self.fernet.encrypt(json.dumps(data).encode())
            else:
                encrypted = self._basic_encode(json.dumps(data))
            
            with open(self.creds_file, 'wb') as f:
                f.write(encrypted)
            
            # Update global access key
            global user_access_key
            user_access_key = access_key
            return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False

    def load_credentials(self):
        """Load credentials from file"""
        try:
            if not os.path.exists(self.creds_file):
                return None
            
            with open(self.creds_file, 'rb') as f:
                encrypted = f.read()
            
            if self.encryption_available:
                decrypted = self.fernet.decrypt(encrypted)
                data = json.loads(decrypted.decode())
            else:
                decrypted = self._basic_decode(encrypted)
                data = json.loads(decrypted)
            
            # Update global access key
            global user_access_key
            user_access_key = data.get('access_key')
            return data
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None

    def clear_credentials(self):
        """Remove saved credentials"""
        try:
            if os.path.exists(self.creds_file):
                os.remove(self.creds_file)
            # Clear global access key
            global user_access_key
            user_access_key = None
            return True
        except Exception as e:
            print(f"Error clearing credentials: {e}")
            return False

# Create a singleton instance
credential_manager = CredentialManager()

def require_access_key(func):
    """Decorator to require a valid access key for function execution"""
    def wrapper(*args, **kwargs):
        if not user_access_key:
            showInfo("Please log in first to use this feature.")
            return None  # Return None instead of raising error
        return func(*args, **kwargs)
    return wrapper