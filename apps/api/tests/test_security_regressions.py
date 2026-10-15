import base64
import hashlib
import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql

from app.api.routes import (
    IndexBody,
    access_token,
    attempt_insert_statement,
    authorization_url,
    connection_has_scopes,
    google_error_reason,
    google_request,
    has_indexing_ownership,
    missing_required_scopes,
    normalize_granted_scopes,
    oauth_error_location,
    property_contains_url,
    property_entries,
    require_connection_scopes,
    token_expiry_seconds,
)
from app.core.config import Settings
from app.core.crypto import TokenCipher
from app.db.models import IndexingAttempt
from app.main import app, unhandled_exception


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def test_production_configuration_requires_secure_origins_cookies_and_encryption_key():
    common = {
        "environment": "production",
        "session_secret": "a-unique-production-session-secret-0123456789",
        "google_client_id": "client-id",
        "google_client_secret": "client-secret",
        "frontend_origin": "https://app.example.test",
        "google_redirect_uri": "https://api.example.test/api/v1/auth/google/callback",
        "encryption_key_id": "key-v2",
        "encryption_keys": f"key-v2:{b64(b'k' * 32)}",
    }
    with pytest.raises(ValueError, match="SECURE_COOKIES"):
        Settings(**common, secure_cookies=False)
    with pytest.raises(ValueError, match="FRONTEND_ORIGIN"):
        Settings(**{**common, "frontend_origin": "https://app.example.test/untrusted-path"}, secure_cookies=True)
    settings = Settings(**common, secure_cookies=True)
    assert TokenCipher(settings).encrypt("credential").startswith("key-v2.")


def test_missing_nonlocal_encryption_key_fails_closed():
    cipher = TokenCipher(Settings(encryption_key_id="key-v2"))
    with pytest.raises(ValueError, match="Active encryption key"):
        cipher.encrypt("credential")


def test_oauth_authorization_url_uses_offline_access_and_pkce_without_verifier_leak():
    cfg = Settings(google_client_id="client", google_redirect_uri="https://api.test/callback")
    verifier = "pkce-verifier-value-that-is-never-put-in-the-url"
    url = authorization_url(cfg, "random-state", verifier)
    query = parse_qs(urlparse(url).query)
    assert query["access_type"] == ["offline"]
    assert query["include_granted_scopes"] == ["true"]
    assert "https://www.googleapis.com/auth/webmasters.readonly" in query["scope"][0].split()
    assert "https://www.googleapis.com/auth/indexing" not in query["scope"][0].split()
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [b64(hashlib.sha256(verifier.encode()).digest())]
    assert query["state"] == ["random-state"]
    assert verifier not in url


def test_oauth_authorization_url_requests_indexing_only_for_incremental_authorization():
    cfg = Settings(google_client_id="client")
    url = authorization_url(cfg, "state", "verifier", include_indexing=True)
    query = parse_qs(urlparse(url).query)
    assert "https://www.googleapis.com/auth/indexing" in query["scope"][0].split()


def test_oauth_scope_validation_accepts_google_email_alias_and_optional_indexing():
    google_grant = {
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    }
    assert normalize_granted_scopes(google_grant) == {
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    }
    assert missing_required_scopes(google_grant) == set()
    connection = SimpleNamespace(scopes=sorted(google_grant))
    assert connection_has_scopes(connection, {"https://www.googleapis.com/auth/webmasters.readonly"})
    assert not connection_has_scopes(connection, {"https://www.googleapis.com/auth/indexing"})

    email_alias_grant = {"https://www.googleapis.com/auth/webmasters.readonly", "email", "openid"}
    assert missing_required_scopes(email_alias_grant) == set()


def test_oauth_scope_validation_does_not_treat_missing_scope_as_granted():
    granted = {"openid", "email"}
    assert missing_required_scopes(granted) == {"https://www.googleapis.com/auth/webmasters.readonly"}
    connection = SimpleNamespace(scopes=None)
    assert not connection_has_scopes(connection, {"https://www.googleapis.com/auth/webmasters.readonly"})


def test_operation_scope_guard_denies_indexing_without_indexing_permission():
    connection = SimpleNamespace(scopes=["openid", "email", "https://www.googleapis.com/auth/webmasters.readonly"])
    with pytest.raises(HTTPException) as exc:
        require_connection_scopes(connection, {"https://www.googleapis.com/auth/indexing"}, "permission required")
    assert exc.value.status_code == 403


def test_token_expiry_rejects_malformed_or_nonpositive_values():
    assert token_expiry_seconds(3600) == 3600
    for value in (None, "3600", 0, -1, True, math.nan, math.inf):
        with pytest.raises(HTTPException):
            token_expiry_seconds(value)


def test_search_console_property_response_must_be_well_formed():
    assert property_entries({"siteEntry": [{"siteUrl": "https://example.com/"}]}) == [{"siteUrl": "https://example.com/"}]
    with pytest.raises(HTTPException, match="malformed property data"):
        property_entries({"siteEntry": "not-a-list"})


def test_oauth_denial_redirect_is_allowlisted_and_does_not_reflect_arbitrary_text():
    assert oauth_error_location("https://app.example.test", "access_denied") == "https://app.example.test?oauth_error=access_denied"
    assert oauth_error_location("https://app.example.test", "attacker-controlled") == "https://app.example.test?oauth_error=authorization_failed"


def test_disconnecting_connection_preserves_indexing_history_schema():
    column = IndexingAttempt.__table__.c.connection_id
    fk = next(iter(column.foreign_keys))
    assert column.nullable is True
    assert fk.ondelete == "SET NULL"


def test_idempotency_insert_uses_database_conflict_handling():
    body = IndexBody(url="https://example.com/job/1", site_url="https://example.com/", action="URL_UPDATED", page_type="JobPosting")
    stmt = attempt_insert_statement({"user_id": "u", "idempotency_key": "same-key-123", "url": str(body.url), "site_url": body.site_url, "action": body.action, "page_type": body.page_type, "status": "pending"})
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (user_id, idempotency_key) DO NOTHING" in sql


def test_property_url_matching_respects_domain_and_path_boundaries():
    assert property_contains_url("sc-domain:example.com", "https://shop.example.com/job")
    assert not property_contains_url("sc-domain:example.com", "https://example.com.evil.test/job")
    assert property_contains_url("https://example.com/jobs/", "https://example.com/jobs/1")
    assert not property_contains_url("https://example.com/jobs/", "https://example.com/jobs-evil/1")


def test_indexing_notifications_require_site_owner_permission():
    assert has_indexing_ownership("siteOwner")
    assert not has_indexing_ownership("siteFullUser")
    assert not has_indexing_ownership(None)


def test_google_error_parser_distinguishes_scope_and_quota_errors():
    scope_error = httpx.Response(403, json={"error": {"errors": [{"reason": "insufficientPermissions"}]}})
    quota_error = httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED", "errors": [{"reason": "rateLimitExceeded"}]}})
    assert google_error_reason(scope_error) == "insufficientpermissions"
    assert google_error_reason(quota_error) == "ratelimitexceeded"


@pytest.mark.asyncio
async def test_refresh_locks_row_persists_rotated_refresh_token_and_reuses_fresh_access_token(monkeypatch):
    cipher = TokenCipher(Settings())
    now = datetime.now(UTC)
    connection = SimpleNamespace(
        expires_at=now - timedelta(seconds=5),
        access_token_enc=cipher.encrypt("expired-access"),
        refresh_token_enc=cipher.encrypt("old-refresh"),
        status="connected",
    )
    calls = []
    lock_flags = []

    class FakeSession:
        async def refresh(self, row, with_for_update=False):
            assert row is connection
            lock_flags.append(with_for_update)

        async def commit(self):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_args, **_kwargs):
            calls.append("refresh")
            return httpx.Response(200, json={"access_token": "new-access", "refresh_token": "rotated-refresh", "expires_in": 3600})

    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", FakeClient)
    db = FakeSession()
    assert await access_token(db, connection) == "new-access"
    assert cipher.decrypt(connection.refresh_token_enc) == "rotated-refresh"
    assert await access_token(db, connection) == "new-access"
    assert calls == ["refresh"]
    assert lock_flags == [True, True]


@pytest.mark.asyncio
async def test_invalid_grant_marks_connection_for_reauthorization(monkeypatch):
    cipher = TokenCipher(Settings())
    connection = SimpleNamespace(
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        access_token_enc=cipher.encrypt("expired-access"),
        refresh_token_enc=cipher.encrypt("revoked-refresh"),
        status="connected",
    )

    class FakeSession:
        commits = 0

        async def refresh(self, _row, with_for_update=False):
            assert with_for_update is True

        async def commit(self):
            self.commits += 1

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_args, **_kwargs):
            return httpx.Response(400, json={"error": "invalid_grant"})

    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", FakeClient)
    db = FakeSession()
    with pytest.raises(HTTPException) as exc:
        await access_token(db, connection)
    assert exc.value.status_code == 401
    assert connection.status == "reauthorization_required"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_google_reads_retry_but_writes_do_not(monkeypatch):
    calls = []
    responses = [httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}), httpx.Response(200, json={"ok": True})]

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def request(self, *args, **kwargs):
            calls.append(args[0])
            return responses.pop(0)

    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr("app.api.routes.asyncio.sleep", no_sleep)
    assert await google_request("GET", "https://google.test/read", "token", safe_to_retry=True) == {"ok": True}
    assert calls == ["GET", "GET"]

    calls.clear()
    responses[:] = [httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})]
    with pytest.raises(HTTPException) as exc:
        await google_request("POST", "https://google.test/write", "token")
    assert exc.value.status_code == 503
    assert calls == ["POST"]

    calls.clear()
    responses[:] = [httpx.Response(403, json={"error": {"errors": [{"reason": "rateLimitExceeded"}]}}) for _ in range(3)]
    with pytest.raises(HTTPException) as quota:
        await google_request("GET", "https://google.test/read", "token", safe_to_retry=True)
    assert quota.value.status_code == 429
    assert calls == ["GET", "GET", "GET"]


@pytest.mark.asyncio
async def test_health_endpoint_smoke():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_unhandled_api_exceptions_return_structured_json_without_exception_details():
    test_app = FastAPI()
    test_app.add_exception_handler(Exception, unhandled_exception)

    @test_app.get("/failure")
    async def failure():
        raise RuntimeError("sensitive database connection string")

    async with AsyncClient(transport=ASGITransport(app=test_app, raise_app_exceptions=False), base_url="http://test") as client:
        response = await client.get("/failure")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["correlation_id"]
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]
    assert "sensitive" not in response.text
