import base64
import binascii
import re
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://iris:iris@localhost:5432/iris"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    frontend_origin: str = "http://localhost:5173"
    session_secret: str = "development-only-change-me"
    encryption_key_id: str = "local-v1"
    encryption_keys: str = ""
    secure_cookies: bool = False

    @field_validator("session_secret")
    @classmethod
    def secure_secret_in_prod(cls, value: str, info):
        if info.data.get("environment") != "development" and (len(value) < 32 or value == "development-only-change-me"):
            raise ValueError("SESSION_SECRET must be a unique random value of at least 32 characters outside development")
        return value

    @field_validator("encryption_key_id")
    @classmethod
    def valid_key_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise ValueError("ENCRYPTION_KEY_ID may contain only letters, digits, underscore, or hyphen")
        return value

    @property
    def keyring(self) -> dict[str, bytes]:
        # Format: key-id:base64url-encoded-32-byte-key,key-id:...
        result: dict[str, bytes] = {}
        for item in self.encryption_keys.split(","):
            if not item.strip():
                continue
            key_id, encoded = item.split(":", 1)
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key_id) or key_id in result:
                raise ValueError("ENCRYPTION_KEYS contains an invalid or duplicate key ID")
            try:
                key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError(f"Encryption key {key_id!r} is not valid base64url") from exc
            if len(key) != 32:
                raise ValueError(f"Encryption key {key_id!r} must decode to 32 bytes")
            result[key_id] = key
        return result

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment != "development":
            if not self.secure_cookies:
                raise ValueError("SECURE_COOKIES must be true outside development")
            frontend = urlsplit(self.frontend_origin)
            callback = urlsplit(self.google_redirect_uri)
            if frontend.scheme != "https" or not frontend.hostname or frontend.path not in ("", "/") or frontend.query or frontend.fragment or frontend.username or frontend.password:
                raise ValueError("FRONTEND_ORIGIN must use HTTPS outside development")
            if callback.scheme != "https" or not callback.hostname or callback.query or callback.fragment or callback.username or callback.password:
                raise ValueError("GOOGLE_REDIRECT_URI must use HTTPS outside development")
            if not self.google_client_id or not self.google_client_secret:
                raise ValueError("Google OAuth credentials must be configured outside development")
            if self.encryption_key_id not in self.keyring:
                raise ValueError("ENCRYPTION_KEY_ID must be present in ENCRYPTION_KEYS outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
