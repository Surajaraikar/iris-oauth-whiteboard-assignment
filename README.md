# Iris Search Console

A FastAPI and React take-home implementation of a Google Search Console OAuth integration. It demonstrates server-side authorization, encrypted credential storage, refresh/reconnect behavior, property discovery, URL Inspection, and restricted Indexing API notifications.

> **Google limitations:** URL Inspection reports the indexed version and does not request indexing. Google's Indexing API is only for eligible JobPosting and BroadcastEvent pages embedded in VideoObject. Acceptance means Google received a notification; it does not mean the URL was indexed.

## Run locally

1. Copy `.env.example` to `.env`. Configure a Google OAuth web client, exact redirect URI `http://localhost:8000/api/v1/auth/google/callback`, consent screen, Search Console API, and the requested `webmasters.readonly`, `indexing`, `openid`, and `email` scopes. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`, `ENCRYPTION_KEY_ID`, and a 32-byte base64url key under `ENCRYPTION_KEYS`.
2. Run `docker compose up --build`.
3. Visit `http://localhost:5173` and connect Google. API docs are at `http://localhost:8000/docs`; readiness is `/ready`.

In local development only, the API has a fixed reviewer identity (`local-reviewer@example.test`) when no session cookie exists. There is deliberately no production passwordless user bootstrap. Production deployment must add the organization's real authentication provider and session creation flow before exposing user endpoints.

## Assignment answer

The app starts a server-side authorization-code flow with a random state and PKCE S256 challenge. The callback consumes a short-lived state transaction once, exchanges the code using the configured exact redirect URI and verifier, checks granted scopes, then verifies the Google subject and verified email with OIDC UserInfo. It requests offline access. Access and refresh tokens are encrypted with AES-256-GCM, a random nonce, and key ID as authenticated associated data. Refresh-token omission on a later code exchange preserves the stored value. Rotating keys means deploying old and new key IDs together, switching the current key, re-encrypting stored records, then retiring the old key after verification.

Before expiry, a connection is refreshed under a row lock. A replacement refresh token is saved when returned. `invalid_grant` marks the connection as requiring reauthorization; transient token service failures remain retryable. Password changes do not invalidate every OAuth token: Google specifically lists grants containing Gmail scopes among password-change revocation cases. This integration does not request Gmail scope, so it treats observed `invalid_grant` as the signal rather than predicting revocation.

Properties are discovered from the authenticated user's Search Console `sites.list`; inspection is allowed only for a returned property and a URL contained by that property. Indexing notifications use the separate Indexing API. The requester must have `siteOwner` permission on the selected property, choose an eligible page category, use HTTPS, have Google API access and approval, and confirm removals. This service does not fetch user URLs to verify schema, which avoids SSRF; eligibility remains an operator assertion and Google may reject a request. Notification history records accepted/failed attempts with idempotency keys and sanitized errors and remains after disconnect. Disconnect removes local credentials even if Google revocation fails and reports whether remote revocation was confirmed. The OAuth-based Indexing API authorization used here is not live-verified; Google's setup documentation also describes a service-account-based path.

## Status

This is a take-home reference implementation and is **not production-ready**. It still needs a real application identity/session issuer, shared distributed rate limiting, live Google validation, and a production deployment review. GitHub Actions run [38690369706](https://github.com/Surajaraikar/iris-oauth-whiteboard-assignment/actions/runs/38690369706) passed backend/frontend checks, online PostgreSQL migrations, and the API Docker image build. Local Docker Compose was also built and started on 2026-10-15; database readiness and the frontend-to-backend proxy passed smoke checks. Google OAuth credentials are absent, so login is intentionally unavailable and no live Google OAuth or API call was performed. The public source repository is [github.com/Surajaraikar/iris-oauth-whiteboard-assignment](https://github.com/Surajaraikar/iris-oauth-whiteboard-assignment). Automated tests and actual validation results are listed in `docs/TESTING.md`.

See [architecture](docs/ARCHITECTURE.md), [OAuth flow](docs/OAUTH_FLOW.md), [Google API limitations](docs/GOOGLE_API_LIMITATIONS.md), [security](docs/SECURITY.md), and [demo](docs/DEMO.md).
