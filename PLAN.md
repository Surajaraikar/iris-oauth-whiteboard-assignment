# Implementation Plan — iris OAuth Whiteboard

## Repository assessment
- Workspace is empty: no existing source files, repository metadata, local `AGENTS.md`, or assignment PDF was found in the workspace.
- The supplied instructions contain the technical scope but refer to `Questions for the Backend & Integration Engineer (iris).pdf`, which was not included as an accessible file. The implementation will address every question explicitly listed in the supplied prompt.
- No Google OAuth credentials, verified Search Console property, Indexing API approval, or public GitHub repository credentials are present in the supplied materials. Live Google calls and publishing therefore remain external prerequisites.

## Architecture decisions
- Modular monorepo: `apps/api` (FastAPI, SQLAlchemy async, PostgreSQL) and `apps/web` (React/Vite/TypeScript).
- Cookie-backed authenticated demo user identity with server-side session and CSRF protections; no caller-supplied user ID. A local development identity bootstrap will be explicit and disabled in production.
- OAuth is authorization-code with PKCE, one-time server-side state/transaction, OIDC identity verification, minimal Search Console scope, and offline access.
- Refresh and access token secrets are AES-GCM encrypted with versioned keys. PostgreSQL advisory/row locking serializes refreshes across workers.
- Google APIs are called through bounded HTTPX adapters. Indexing notification support is explicitly conditional on eligible page category and account permissions. Local structural validation avoids fetching user-provided URLs, preventing SSRF.
- Rate limiting is process-local for this single-instance assignment; deployment guidance will require a shared limiter for multi-instance operation. This and session-store strategy will be documented.
- Frontend focuses on functional OAuth, property discovery, inspection, eligible notifications, history, and disconnect, with responsive styling and accessible states.

## Phases and progress

- [x] Phase 0 — Inspect workspace, establish constraints, and record this plan before implementation.
- [x] Phase 1 — Backend foundation: settings, database models/migrations, session/CSRF/rate limiting, health/readiness, structured redacted request logging.
- [x] Phase 2 — OAuth lifecycle: state/PKCE transaction, callback and identity/scopes validation, encrypted token persistence, row-lock refresh, revocation/disconnect.
- [x] Phase 3 — Google integrations: Search Console properties and URL Inspection, property/URL checks, eligible-category Indexing API notifications, idempotency/history/error mapping.
- [x] Phase 4 — Frontend dashboard with property, inspection, notification, history and settings views.
- [x] Phase 5 — Tests, Docker/CI, and setup/security/architecture/API limitations/demo/assignment documentation.
- [x] Phase 6 — Run available checks; exact results and external prerequisites documented.

### Delivery limitations
- Automated backend coverage is a focused baseline (crypto/key rotation and request schema policy); the full requested OAuth, refresh race, database ownership, Google error, replay/expiry, and duplicate-submission matrix remains untested.
- Local demo identity is development-only. A production identity provider/session issuer and shared multi-instance rate limiter are not included.
- Eligible page type is an operator declaration; URLs are not fetched or schema-verified. This avoids SSRF, but Google remains authoritative and may reject an asserted category.
- Real Google calls, online PostgreSQL migration, container startup, and public GitHub publication were unavailable or not performed.

## Validation strategy
- Deterministic backend tests with mocked Google endpoints and ASGI client; cover authorization state and replay, token handling and refresh, ownership, eligibility, idempotency, disconnect, and Google error classes.
- Frontend component tests and production build where package tooling is available.
- Validate Alembic migration generation/application and Docker Compose configuration where dependencies are available.
- Never describe mocked API results as a live Google integration test.

## External prerequisites / risks
- Google Cloud OAuth client (web application), consent screen and approved scopes, exact redirect URI, and enabled Search Console API.
- Search Console account with a verified property and appropriate permission.
- Indexing API project enablement plus Google quota/approval and an eligible JobPosting or BroadcastEvent-in-VideoObject page.
- Production secrets: database URL, session signing key, encryption key ring/current key ID, Google client credentials, and stable HTTPS origins.
- Public GitHub publication requires a GitHub account/repository and authorization not available in this workspace. No credentials will be committed.
- The referenced assignment PDF is absent; if its questions differ from the supplied prompt, the written response may need a final alignment pass.
