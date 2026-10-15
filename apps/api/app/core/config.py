from functools import lru_cache

from pydantic import field_validator
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
        if info.data.get("environment") == "production" and (len(value) < 32 or value == "development-only-change-me"):
            raise ValueError("SESSION_SECRET must be a unique random value of at least 32 characters")
        return value

    @property
    def keyring(self) -> dict[str, bytes]:
        # Format: key-id:base64url-encoded-32-byte-key,key-id:...
        import base64
        result: dict[str, bytes] = {}
        for item in self.encryption_keys.split(","):
            if not item.strip():
                continue
            key_id, encoded = item.split(":", 1)
            key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if len(key) != 32:
                raise ValueError(f"Encryption key {key_id!r} must decode to 32 bytes")
            result[key_id] = key
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
