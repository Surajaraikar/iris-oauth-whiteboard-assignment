import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import Settings


class TokenCipher:
    def __init__(self, settings: Settings):
        self.keys = settings.keyring
        self.current_id = settings.encryption_key_id
        self.allow_local_key = settings.environment == "development" and self.current_id == "local-v1"
        if settings.environment != "development" and self.current_id not in self.keys:
            raise ValueError("Current encryption key ID is missing from ENCRYPTION_KEYS outside development")

    def encrypt(self, plaintext: str) -> str:
        key = self.keys.get(self.current_id)
        if key is None and self.allow_local_key:
            # Development convenience only; production requires an explicitly configured key.
            key = b"\0" * 32
        if key is None:
            raise ValueError("Active encryption key is unavailable")
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), self.current_id.encode())
        return ".".join((self.current_id, base64.urlsafe_b64encode(nonce).decode(), base64.urlsafe_b64encode(ciphertext).decode()))

    def decrypt(self, envelope: str) -> str:
        key_id, nonce, ciphertext = envelope.split(".", 2)
        key = self.keys.get(key_id)
        if key is None and self.allow_local_key and key_id == "local-v1":
            key = b"\0" * 32
        if key is None:
            raise ValueError("Encryption key unavailable; restore the historical key before decrypting")
        raw = AESGCM(key).decrypt(base64.urlsafe_b64decode(nonce), base64.urlsafe_b64decode(ciphertext), key_id.encode())
        return raw.decode()

    def reencrypt(self, envelope: str) -> str:
        """Rewrap a stored value with the currently configured key during rotation."""
        key_id = envelope.split(".", 1)[0]
        if key_id == self.current_id:
            return envelope
        return self.encrypt(self.decrypt(envelope))
