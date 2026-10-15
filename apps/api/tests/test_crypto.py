import pytest
from cryptography.exceptions import InvalidTag

from app.core.config import Settings
from app.core.crypto import TokenCipher


def test_token_envelope_round_trip_and_authentication():
    import base64
    key = base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")
    settings = Settings(encryption_key_id="k1", encryption_keys=f"k1:{key}")
    cipher = TokenCipher(settings)
    envelope = cipher.encrypt("secret-token")
    assert envelope.startswith("k1.")
    assert cipher.decrypt(envelope) == "secret-token"
    with pytest.raises((InvalidTag, ValueError)):
        cipher.decrypt(envelope[:-2] + "aa")

def test_old_encryption_key_remains_decryptable_during_rotation():
    import base64
    encode = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    old = TokenCipher(Settings(encryption_key_id="old", encryption_keys=f"old:{encode(b'o'*32)}"))
    envelope = old.encrypt("refresh")
    rotated = TokenCipher(Settings(encryption_key_id="new", encryption_keys=f"old:{encode(b'o'*32)},new:{encode(b'n'*32)}"))
    assert rotated.decrypt(envelope) == "refresh"
    rewrapped = rotated.reencrypt(envelope)
    assert rewrapped.startswith("new.")
    assert rotated.decrypt(rewrapped) == "refresh"
    assert rotated.decrypt(rotated.encrypt("access")) == "access"
