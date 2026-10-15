import uuid

from fastapi import Cookie, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import User
from app.db.session import SessionLocal

signer = URLSafeTimedSerializer(get_settings().session_secret, salt="iris-session-v1")

async def current_user(request: Request, iris_session: str | None = Cookie(default=None)) -> User:
    settings = get_settings()
    if not iris_session:
        # Explicit local-only identity bootstrap, never enabled outside development.
        if settings.environment != "development":
            raise HTTPException(401, "Sign in required")
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "local-reviewer@example.test"))
            if user is None:
                user = User(email="local-reviewer@example.test")
                db.add(user)
                await db.commit()
                await db.refresh(user)
            return user
    try:
        user_id = uuid.UUID(signer.loads(iris_session, max_age=60 * 60 * 12))
    except (BadSignature, ValueError):
        raise HTTPException(401, "Session expired")
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            raise HTTPException(401, "Session expired")
        request.state.user_id = user.id
        return user

def csrf_check(request: Request, token: str | None) -> None:
    expected = request.cookies.get("iris_csrf")
    if not expected or not token or not __import__("hmac").compare_digest(expected, token):
        raise HTTPException(403, "CSRF token missing or invalid")
