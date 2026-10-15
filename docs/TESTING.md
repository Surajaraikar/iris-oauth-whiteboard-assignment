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
