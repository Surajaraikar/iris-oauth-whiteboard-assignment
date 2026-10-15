"""Re-encrypt stored Google credentials after adding a new active key.

Run from apps/api after configuring both historical and new keys:
    python -m app.services.key_rotation
"""
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.crypto import TokenCipher
from app.db.models import GoogleConnection
from app.db.session import SessionLocal


async def rotate_all() -> int:
    cipher = TokenCipher(get_settings())
    count = 0
    async with SessionLocal() as db:
        rows = (await db.scalars(select(GoogleConnection).with_for_update())).all()
        for connection in rows:
            connection.access_token_enc = cipher.reencrypt(connection.access_token_enc)
            connection.refresh_token_enc = cipher.reencrypt(connection.refresh_token_enc)
            count += 1
        await db.commit()
    return count


if __name__ == "__main__":
    print(f"Re-encrypted credentials for {asyncio.run(rotate_all())} connections")
