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

## Earlier local run snapshot - superseded by Live OAuth verification below (2026-10-15)

- `.env` exists and is ignored by Git. Google client ID, fresh client secret, session secret, encryption key configuration, and exact redirect URI were present; values were not emitted or logged.
- Google Auth Platform client details showed the exact redirect URI `http://localhost:8000/api/v1/auth/google/callback`.
- Docker Compose services were force-recreated to load the local credentials. API, web, and PostgreSQL are running; PostgreSQL is healthy.
- `GET /ready`: HTTP 200, database `ok`.
- `GET /api/v1/connections`: HTTP 200, JSON list.
- `GET /api/v1/auth/google/start`: HTTP 200. The response contained a Google authorization endpoint, state, PKCE challenge, exact redirect URI, and the configured Search Console read-only, Indexing API, OpenID, and email scopes. State and the full URL were not printed.
- Backend Pytest: 21 passed. Ruff: passed. Mypy: passed (10 source files). Frontend Vitest: 5 passed. Frontend production build: passed.
- Live OAuth is **pending user sign-in/consent**. No callback, code exchange, database token write, encrypted-token readback, Search Console property discovery, URL Inspection, Indexing notification, or refresh/revocation behavior has been tested live. Do not interpret the HTTP 200 start response as successful Google integration.
- Previously exposed client secrets remain to be disabled/deleted after successful validation of the fresh local secret. No secret was committed.

## OAuth scope mismatch regression run - pre-consent snapshot (2026-10-15)

- Read-only Google Auth Platform Data Access inspection showed `userinfo.email`, `openid`, `webmasters.readonly`, and `indexing` are configured.
- The reported callback took the branch where the token response has a string `scope` value but did not contain every literal required scope. The old callback did not record the returned scope list, so the exact list for that attempt is unavailable. The configured email scope and requested literal `email` differed in representation; Google documents equivalent API scope forms and recommends comparing grants per feature.
- Regression changes normalize the `email` alias to `userinfo.email`, keep Search Console plus OIDC identity as connection requirements, and treat Indexing as a separately requested optional permission. Properties and URL Inspection require Search Console scope; Indexing notifications require both Search Console and Indexing scopes. Missing scope data is still rejected and never treated as granted.
- Backend tests: 25 passed. Ruff: passed. Mypy: passed (10 files). Frontend tests: 5 passed. Frontend TypeScript/Vite production build: passed. `git diff --check`: passed.
- Safe diagnostics now report only the provider's scope names, missing required scope names, and whether the optional Indexing permission was granted. No access token, refresh token, authorization code, state, client secret, or callback query is logged.
- Docker Compose was rebuilt with this code. PostgreSQL is healthy and `/ready` reports database `ok`; `/api/v1/connections` returned HTTP 200. The base OAuth start URL requested Search Console and identity scopes without Indexing; the explicit incremental URL added Indexing. Both returned HTTP 200 with `include_granted_scopes=true`, state, PKCE, and the configured redirect. Pending: the user must repeat Google authorization personally, after which callback/token encryption/connection and only accessible Google properties or eligible Indexing URLs can be checked. No live OAuth or Google API success is claimed.

## Live OAuth verification - 2026-10-15

- User completed the Google sign-in and consent screen. Safe request logs showed callback HTTP 303; the callback created one persisted connection with status `connected`.
- Safe callback diagnostic confirmed a string `scope` field, all required permissions present, and the exact returned scope identifiers: `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/webmasters.readonly`, and `https://www.googleapis.com/auth/indexing`. No tokens, code, state, or client credentials were emitted.
- This successful response confirms the code defect: Google returned canonical `userinfo.email` whereas the previous implementation compared literal `email`; the updated validator normalizes the email alias.
- Database inspection verified access/refresh token columns contain encrypted envelope formats and both decrypt with the configured key. Values were not emitted. Connection listing returned HTTP 200 and status `connected`.
- Live Search Console property discovery returned HTTP 200 with an empty property list. No URL Inspection or Indexing API write was sent because no accessible property/eligible URL was available.
- Real refresh was tested through the app: the local access expiry was moved into the past, the properties endpoint triggered Google token refresh and returned HTTP 200, the access token changed, a future expiry persisted, and the connection remained connected with decryptable token envelopes. No token values or hashes were printed.
- Disconnect/revocation and reconnect were not attempted to preserve the live grant. No real property permission, URL Inspection result, Indexing API acceptance/quota, or indexing outcome is verified.
- Final local regression results: Pytest 25 passed; Ruff passed; mypy passed (10 source files); Vitest 5 passed; production build passed; Compose services running with healthy PostgreSQL; `/ready` returned HTTP 200.
- No `.env` or credential file is tracked. Commit and push are authorized after local validation; GitHub Actions status for the resulting commit is reported separately.
