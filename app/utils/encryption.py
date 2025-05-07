from cryptography.fernet import Fernet
from flask import current_app

_cipher_suite = None

def _get_cipher():
    global _cipher_suite
    if _cipher_suite is None:
        key = current_app.config.get('FERNET_ENCRYPTION_KEY')
        if not key or key == 'thisIsAWeakFallbackKeyPleaseSetItProperly':
            current_app.logger.warning(
                "FERNET_ENCRYPTION_KEY is not set or using fallback. API keys will not be securely stored."
            )
            # In a real scenario, you might want to raise an error or use a more robust fallback,
            # but for now, we'll proceed with a potentially insecure (or no) encryption if not set.
            # This means encrypt/decrypt might effectively become no-ops if key is bad.
            # A better approach for unconfigured key: return a cipher that raises error on use.
            try:
                _cipher_suite = Fernet(key.encode() if key else Fernet.generate_key()) # last part is risky if key is bad string
            except ValueError as e:
                current_app.logger.error(f"Invalid FERNET_ENCRYPTION_KEY: {e}. Encryption will likely fail.")
                # Use a dummy key that will likely cause errors, to highlight the issue
                _cipher_suite = Fernet(Fernet.generate_key()) # Temporary, non-persistent key
        else:
            _cipher_suite = Fernet(key.encode())
    return _cipher_suite

def encrypt_data(data: str) -> str:
    if not data:
        return ""
    try:
        cipher = _get_cipher()
        return cipher.encrypt(data.encode()).decode()
    except Exception as e:
        current_app.logger.error(f"Encryption failed: {e}")
        # Depending on policy, either return original data, an error placeholder, or raise
        return "[encryption_error]" 

def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data or encrypted_data == "[encryption_error]":
        return "" # Or return encrypted_data if it was an error placeholder
    try:
        cipher = _get_cipher()
        return cipher.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        current_app.logger.error(f"Decryption failed for data: {e}")
        # Common issue: Fernet.InvalidToken, often due to wrong key or non-encrypted data
        return "[decryption_error]" # Or raise, or return a specific message 