import asyncio
import base64
import hashlib
import json
import logging
import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import csrf_check, current_user
from app.core.config import get_settings
from app.core.crypto import TokenCipher
from app.db.models import GoogleConnection, IndexingAttempt, OAuthTransaction, User
from app.db.session import get_db

router = APIRouter(prefix="/api/v1")
log = logging.getLogger("iris.api")
SCOPES = {"https://www.googleapis.com/auth/webmasters.readonly", "https://www.googleapis.com/auth/indexing", "openid", "email"}
GOOGLE = "https://oauth2.googleapis.com"

def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def cipher() -> TokenCipher:
    return TokenCipher(get_settings())

@router.get("/auth/google/start")
async def google_start(request: Request, response: Response, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    cfg = get_settings()
    if not cfg.google_client_id or not cfg.google_client_secret:
        raise HTTPException(503, "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    state = b64(secrets.token_bytes(32)); verifier = b64(secrets.token_bytes(48))
    challenge = b64(hashlib.sha256(verifier.encode()).digest())
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    db.add(OAuthTransaction(state_hash=state_hash, user_id=user.id, verifier=verifier, expires_at=datetime.now(UTC)+timedelta(minutes=10)))
    await db.commit()
    query = urlencode({"client_id": cfg.google_client_id, "redirect_uri": cfg.google_redirect_uri, "response_type": "code", "scope": " ".join(sorted(SCOPES)), "access_type": "offline", "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + query}

@router.get("/auth/google/callback")
async def google_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    cfg = get_settings(); state_hash = hashlib.sha256(state.encode()).hexdigest()
    tx = await db.scalar(select(OAuthTransaction).where(OAuthTransaction.state_hash == state_hash).with_for_update())
    if tx is None or tx.expires_at <= datetime.now(UTC):
        raise HTTPException(400, "OAuth state is invalid, expired, or already used")
    verifier, user_id = tx.verifier, tx.user_id
    await db.delete(tx); await db.commit()  # consume before external request; callback cannot replay
    async with httpx.AsyncClient(timeout=8.0) as client:
        token_response = await client.post(f"{GOOGLE}/token", data={"code": code, "client_id": cfg.google_client_id, "client_secret": cfg.google_client_secret, "redirect_uri": cfg.google_redirect_uri, "grant_type": "authorization_code", "code_verifier": verifier})
        if token_response.status_code != 200:
            raise HTTPException(400, "Google authorization code exchange failed")
        token = token_response.json()
        returned_scopes = set(token.get("scope", "").split())
        if not SCOPES.issubset(returned_scopes):
            raise HTTPException(403, "Google did not grant all required scopes")
        info_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": "Bearer " + token["access_token"]})
        if info_response.status_code != 200:
            raise HTTPException(400, "Could not verify Google account identity")
        info = info_response.json()
    if not info.get("sub") or not info.get("email") or info.get("email_verified") is not True:
        raise HTTPException(400, "Google account identity is incomplete or unverified")
    conn = await db.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user_id, GoogleConnection.google_sub == info["sub"]).with_for_update())
    refresh_token = token.get("refresh_token")
    if conn and not refresh_token:
        refresh_token = cipher().decrypt(conn.refresh_token_enc)
    if not refresh_token:
        raise HTTPException(400, "Google did not issue a refresh token; reconnect with offline access")
    expiry = datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))
    fields = {"email": info["email"], "access_token_enc": cipher().encrypt(token["access_token"]), "refresh_token_enc": cipher().encrypt(refresh_token), "expires_at": expiry, "scopes": sorted(returned_scopes), "status": "connected"}
    if conn:
        for k, v in fields.items(): setattr(conn, k, v)
    else:
        conn = GoogleConnection(user_id=user_id, google_sub=info["sub"], **fields); db.add(conn)
    await db.commit()
    from app.api.deps import signer
    response = RedirectResponse(get_settings().frontend_origin, status_code=303)
    response.set_cookie("iris_session", signer.dumps(str(user_id)), httponly=True, secure=cfg.secure_cookies, samesite="lax", max_age=43200, path="/")
    response.set_cookie("iris_csrf", secrets.token_urlsafe(32), httponly=False, secure=cfg.secure_cookies, samesite="lax", max_age=43200, path="/")
    return response

@router.get("/connections")
async def connections(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(GoogleConnection).where(GoogleConnection.user_id == user.id))).all()
    return [{"id": str(r.id), "email": r.email, "status": r.status, "scopes": r.scopes} for r in rows]

async def owned_connection(db: AsyncSession, user: User, connection_id: uuid.UUID | None = None) -> GoogleConnection:
    stmt = select(GoogleConnection).where(GoogleConnection.user_id == user.id)
    if connection_id: stmt = stmt.where(GoogleConnection.id == connection_id)
    conn = await db.scalar(stmt.order_by(GoogleConnection.updated_at.desc()).limit(1))
    if conn is None: raise HTTPException(404, "Google Search Console connection not found")
    if conn.status != "connected": raise HTTPException(409, "Google connection requires reauthorization")
    return conn

async def access_token(db: AsyncSession, conn: GoogleConnection) -> str:
    now = datetime.now(UTC)
    # Lock connection row and re-check expiry so concurrent requests share the refresh.
    await db.refresh(conn, with_for_update=True)
    if conn.expires_at > now + timedelta(minutes=2): return cipher().decrypt(conn.access_token_enc)
    refresh = cipher().decrypt(conn.refresh_token_enc)
    cfg = get_settings()
    async with httpx.AsyncClient(timeout=8.0) as client:
        res = await client.post(f"{GOOGLE}/token", data={"client_id": cfg.google_client_id, "client_secret": cfg.google_client_secret, "refresh_token": refresh, "grant_type": "refresh_token"})
    if res.status_code != 200:
        body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        if body.get("error") == "invalid_grant":
            conn.status = "reauthorization_required"; await db.commit()
            raise HTTPException(401, "Google authorization expired or was revoked. Reconnect the account.")
        if res.status_code in (429, 500, 502, 503, 504): raise HTTPException(503, "Google token service temporarily unavailable")
        raise HTTPException(502, "Google token refresh failed")
    data = res.json(); conn.access_token_enc = cipher().encrypt(data["access_token"])
    conn.expires_at = datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 3600)))
    if data.get("refresh_token"): conn.refresh_token_enc = cipher().encrypt(data["refresh_token"])
    await db.commit()
    return data["access_token"]

async def google_request(method: str, url: str, token: str, *, json_body=None, safe_to_retry: bool = False):
    attempts = 3 if safe_to_retry else 1
    res = None
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.request(method, url, json=json_body, headers={"Authorization": "Bearer " + token})
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt + 1 == attempts:
                raise HTTPException(503, "Google API request timed out or could not connect")
        else:
            if res.status_code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                break
        await asyncio.sleep((0.2 * (2**attempt)) + random.uniform(0, 0.15))
    assert res is not None
    if res.status_code == 401: raise HTTPException(401, "Google rejected the access token; reconnect the account")
    if res.status_code == 403: raise HTTPException(403, "Google denied access. Check property permission and API enablement.")
    if res.status_code == 429: raise HTTPException(429, "Google API quota exceeded; retry later")
    if res.status_code >= 500: raise HTTPException(503, "Google API is temporarily unavailable")
    if res.status_code >= 400: raise HTTPException(502, "Google API rejected the request")
    try: return res.json()
    except json.JSONDecodeError: raise HTTPException(502, "Google API returned malformed JSON")

@router.get("/search-console/properties")
async def properties(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    conn = await owned_connection(db, user); token = await access_token(db, conn)
    data = await google_request("GET", "https://searchconsole.googleapis.com/webmasters/v3/sites", token, safe_to_retry=True)
    return data.get("siteEntry", [])

class InspectBody(BaseModel):
    site_url: str = Field(min_length=1, max_length=2048)
    inspection_url: HttpUrl

def property_contains_url(site: str, url: str) -> bool:
    parsed_url = urlparse(url)
    host = parsed_url.hostname or ""
    if site.startswith("sc-domain:"):
        domain = site.removeprefix("sc-domain:")
        return host == domain or host.endswith("." + domain)
    return url.startswith(site)

@router.post("/search-console/inspect")
async def inspect(body: InspectBody, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    conn = await owned_connection(db, user); token = await access_token(db, conn)
    props = await google_request("GET", "https://searchconsole.googleapis.com/webmasters/v3/sites", token, safe_to_retry=True)
    if body.site_url not in {p.get("siteUrl") for p in props.get("siteEntry", [])}:
        raise HTTPException(403, "The connected account does not have access to this property")
    site = body.site_url
    if not property_contains_url(site, str(body.inspection_url)):
        raise HTTPException(422, "URL is outside the selected property")
    return await google_request("POST", "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect", token, json_body={"inspectionUrl": str(body.inspection_url), "siteUrl": site}, safe_to_retry=True)

class IndexBody(BaseModel):
    url: HttpUrl
    site_url: str = Field(min_length=1, max_length=2048)
    action: str = Field(pattern="^(URL_UPDATED|URL_DELETED)$")
    page_type: str = Field(pattern="^(JobPosting|BroadcastEventVideoObject)$")
    confirm_delete: bool = False

@router.post("/indexing/notifications")
async def indexing(body: IndexBody, request: Request, x_idempotency_key: str = Header(min_length=8, max_length=128), x_csrf_token: str | None = Header(default=None), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    csrf_check(request, x_csrf_token)
    if body.action == "URL_DELETED" and not body.confirm_delete: raise HTTPException(422, "Explicit deletion confirmation is required")
    parsed = urlparse(str(body.url))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise HTTPException(422, "Use a public HTTPS URL without credentials or a nonstandard port")
    conn = await owned_connection(db, user)
    props = await google_request("GET", "https://searchconsole.googleapis.com/webmasters/v3/sites", await access_token(db, conn), safe_to_retry=True)
    if body.site_url not in {p.get("siteUrl") for p in props.get("siteEntry", [])}:
        raise HTTPException(403, "The connected account does not have access to this property")
    if not property_contains_url(body.site_url, str(body.url)):
        raise HTTPException(422, "URL is outside the selected property")
    old = await db.scalar(select(IndexingAttempt).where(IndexingAttempt.user_id == user.id, IndexingAttempt.idempotency_key == x_idempotency_key))
    if old:
        if old.url != str(body.url) or old.site_url != body.site_url or old.action != body.action or old.page_type != body.page_type: raise HTTPException(409, "Idempotency key was already used for a different request")
        return {"id": str(old.id), "status": old.status, "message": "Indexing notification accepted by Google; indexing is not guaranteed." if old.status == "accepted" else old.safe_error}
    attempt = IndexingAttempt(user_id=user.id, connection_id=conn.id, idempotency_key=x_idempotency_key, url=str(body.url), site_url=body.site_url, action=body.action, page_type=body.page_type, status="pending")
    db.add(attempt); await db.commit(); await db.refresh(attempt)
    token = await access_token(db, conn)
    try:
        data = await google_request("POST", "https://indexing.googleapis.com/v3/urlNotifications:publish", token, json_body={"url": str(body.url), "type": body.action})
        attempt.status = "accepted"; attempt.response = {k: v for k, v in data.items() if k in {"url", "type", "notifyTime"}}
        await db.commit()
        return {"id": str(attempt.id), "status": "accepted", "message": "Indexing notification accepted by Google; indexing is not guaranteed."}
    except HTTPException as exc:
        attempt.status = "failed"; attempt.safe_error = exc.detail[:500]; await db.commit(); raise

@router.get("/indexing/history")
async def history(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(IndexingAttempt).where(IndexingAttempt.user_id == user.id).order_by(IndexingAttempt.created_at.desc()).limit(100))).all()
    return [{"id": str(x.id), "url": x.url, "action": x.action, "page_type": x.page_type, "status": x.status, "safe_error": x.safe_error, "created_at": x.created_at} for x in rows]

@router.delete("/connections/{connection_id}")
async def disconnect(connection_id: uuid.UUID, request: Request, response: Response, x_csrf_token: str | None = Header(default=None), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    csrf_check(request, x_csrf_token)
    conn = await owned_connection(db, user, connection_id); token = cipher().decrypt(conn.refresh_token_enc); revoked = False
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            res = await client.post(f"{GOOGLE}/revoke", data={"token": token})
            revoked = res.status_code == 200
        except httpx.HTTPError: pass
    await db.delete(conn); await db.commit()
    return {"disconnected": True, "remote_revocation_confirmed": revoked, "message": "Local credentials removed." if revoked else "Local credentials removed; Google could not confirm remote revocation. Revoke access in your Google Account if needed."}
