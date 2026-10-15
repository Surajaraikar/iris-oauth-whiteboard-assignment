# Testing and verification

Automated tests cover security configuration, token encryption/key rotation, OAuth PKCE construction and denial handling, token refresh replacement/locking arguments and `invalid_grant`, ownership boundaries, migration-sensitive foreign-key behavior, idempotent reservation SQL, Google error classification, health, and safe retry behavior. They do not prove real PostgreSQL locking semantics or a live Google authorization/property/API/indexing outcome. Safe reads and URL Inspection have bounded exponential retry with jitter; Indexing API writes are never automatically retried. Run backend checks with `cd apps/api && pip install -e '.[dev]' && pytest`; run frontend checks with `cd apps/web && npm install && npm test && npm run build`.

## Results in the delivery environment

- Python bytecode compile: passed (Python 3.14.2 available; project targets Python 3.12+).
- Pytest: 20 passed.
- Ruff: passed.
- Mypy: passed (10 backend source files).
- FastAPI `/health` ASGI test: passed (HTTP 200).
- Alembic offline SQL generation through both migrations: passed. GitHub Actions also applied both migrations online against its PostgreSQL service.
- Frontend tests: 1 passed.
- Frontend production TypeScript/Vite build: passed.
- npm audit: 0 vulnerabilities.
- Docker Compose configuration and hosted Docker image build passed. At the time of the initial audit Docker Desktop was unavailable; it was later started and the full local Compose build passed (see runtime verification below).
- Live Google OAuth and APIs: not run; credentials, a verified property, and Indexing API approval were not supplied.

The tests are a deterministic regression baseline, not the full database-backed OAuth/refresh race matrix. The audit commit's GitHub Actions run passed both online migrations and the API image build, as well as backend and frontend checks. Google credentials and Indexing API approval are not included in this repository.

## Local Docker Compose runtime verification — 2026-10-15

- Docker Desktop was started; `docker compose up -d --build` built and started the API, PostgreSQL 16, and Vite frontend.
- PostgreSQL health check passed; the running database reports Alembic revision `0002_preserve_history`.
- Requests through the browser-facing frontend proxy passed: `/health` 200, `/ready` 200 with database `ok`, and `/api/v1/connections` 200 with an empty list.
- `/api/v1/auth/google/start` returned 503 JSON with `Google OAuth is not configured...`; `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are absent. No Google login or API result was simulated.
- Root cause for the reported frontend 500s: the Vite development server runs inside the `web` container, but its proxy pointed to `localhost:8000` (the web container itself). Compose now sets `VITE_API_PROXY_TARGET=http://api:8000`. The original `ECONNREFUSED` proxy response was empty/non-JSON, and the frontend now handles it without throwing a JSON parse exception.
- Unexpected FastAPI exceptions now return generic JSON containing a correlation ID; exception messages and secrets are not included in the response. Regression tests cover this response and frontend empty/non-JSON bodies.
- After the fix: Pytest 21 passed; Ruff and mypy passed; frontend tests 5 passed; production build passed; npm audit reported 0 vulnerabilities; `git diff --check` passed.

Google OAuth, Search Console, URL Inspection, Indexing API, token refresh/revocation, and live Google error/quota behavior were not tested because no Google credentials or verified property are configured. This local runtime result does not establish production readiness.

## Google Cloud OAuth setup follow-up — 2026-10-15

- Google Auth Platform configuration created in project `iris-oauth-wb-20261015-6d435b`; External audience and Testing status were visible in the Console.
- The signed-in Google account was visible in the Test users list. Data Access displayed the requested Search Console read-only, Indexing API, OpenID, and email scopes, and showed a successful save notification.
- Web OAuth client was not created. Both the Auth Platform Clients page and the legacy Credentials page remained on an indefinite loading spinner in the authenticated Cloud Console.
- Local `.env` still has no Google client ID or secret. No credential values were printed, committed, or uploaded.
- Local checks: Compose services `api`, `db`, and `web` are running; `/ready` returned `{"status":"ready","database":"ok"}`. `/api/v1/auth/google/start` returned HTTP 503 JSON explaining the missing client ID and secret.
- Follow-up validation: Pytest passed (21 tests); Ruff passed after fixing three Alembic import-order violations; mypy passed (10 source files); frontend tests passed (5 tests); `npm run build` passed; `git diff --check` passed.
- Live OAuth authorization/callback/token exchange/encrypted persistence, Google Search Console property discovery, URL Inspection, Indexing API, refresh, reconnect, disconnect, and revocation are blocked or untested until a Web client is created and local credentials are securely configured. No live Google API success is claimed.
- Cloud Console diagnostics: one direct Auth Platform Clients page load and one reload left the page on a progress bar. Captured browser console output contained repeated `No ID or name found in config.` warnings and no JavaScript errors; the available browser diagnostics did not surface Network panel request/response status details. Authenticated gcloud reported the project ACTIVE and both APIs enabled.
- Supported CLI check: official `gcloud iam oauth-clients create` targets the IAM `iam/v1` OAuth client feature; its documented scopes are `cloud-platform`, `openid`, `email`, and `groups`, so it cannot safely replace the standard Google Auth Platform Web client for Search Console/Indexing API access. It was not invoked to create a client.
