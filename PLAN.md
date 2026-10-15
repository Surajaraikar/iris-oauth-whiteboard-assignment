# Implementation Plan — iris OAuth Whiteboard

## Repository assessment
- Workspace is empty: no existing source files, repository metadata, local `AGENTS.md`, or assignment PDF was found in the workspace.
- The supplied instructions contain the technical scope but refer to `Questions for the Backend & Integration Engineer (iris).pdf`, which was not included as an accessible file. The implementation will address every question explicitly listed in the supplied prompt.
- No Google OAuth credentials, verified Search Console property, or Indexing API approval are present. The public repository was created and pushed during the prior implementation turn.

## Architecture decisions
- Modular monorepo: `apps/api` (FastAPI, SQLAlchemy async, PostgreSQL) and `apps/web` (React/Vite/TypeScript).
- Cookie-backed authenticated demo user identity with server-side session and CSRF protections; no caller-supplied user ID. A local development identity bootstrap will be explicit and disabled in production.
- OAuth is authorization-code with PKCE, one-time server-side state/transaction, OIDC identity verification, minimal Search Console scope, and offline access.
- Refresh and access token secrets are AES-GCM encrypted with versioned keys. PostgreSQL row locking serializes refreshes across workers.
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
- Regression tests cover key handling, production settings, PKCE parameter construction, refresh-token rotation path, property permission and URL boundaries, retry policy, and idempotent insert SQL. They do not exercise full OAuth replay/expiry or PostgreSQL refresh concurrency against a live database.
- Local demo identity is development-only. A production identity provider/session issuer and shared multi-instance rate limiter are not included.
- Eligible page type is an operator declaration; URLs are not fetched or schema-verified. This avoids SSRF, but Google remains authoritative and may reject an asserted category.
- Live Google calls remain unavailable because no credentials, verified property, or Indexing API approval are configured. Docker Compose/PostgreSQL were started and validated locally on 2026-10-15; both migrations applied successfully.
- GitHub repository is public at https://github.com/Surajaraikar/iris-oauth-whiteboard-assignment.

## Validation strategy
- Deterministic backend tests cover focused security regressions and mocked Google transport retry behavior. Full database-backed OAuth/replay/idempotency cases need PostgreSQL integration coverage.
- Frontend component tests and production build where package tooling is available.
- Validate Alembic online migrations, Docker Compose startup, service health, and frontend-to-backend proxy locally; keep external Google behavior explicitly unverified without credentials.
- Never describe mocked API results as a live Google integration test.

## External prerequisites / risks
- Google Cloud OAuth client (web application), consent screen and approved scopes, exact redirect URI, and enabled Search Console API.
- Search Console account with a verified property and appropriate permission.
- Indexing API project enablement plus Google quota/approval and an eligible JobPosting or BroadcastEvent-in-VideoObject page.
- Production secrets: database URL, session signing key, encryption key ring/current key ID, Google client credentials, and stable HTTPS origins.
- The public GitHub repository exists. No Google credentials or application secrets are committed.

### 2026-10-15 Google OAuth setup follow-up

- [x] Created the Google Auth Platform configuration in `iris-oauth-wb-20261015-6d435b`; External audience with Testing status is active.
- [x] Added the signed-in account as a test user and saved Search Console read-only, Indexing API, OpenID, and email scopes.
- [ ] Web OAuth client creation is blocked: Google Cloud Console's OAuth client page and legacy credentials page stayed on an indefinite loading spinner after project context was restored.
- [x] Diagnostic follow-up: authenticated gcloud confirms the project is ACTIVE and both APIs are enabled. One direct Clients-page load and one refresh still showed only a progress bar; captured browser console diagnostics had repeated `No ID or name found in config.` warnings and no JavaScript errors. The available browser API did not expose Network panel response details.
- [x] Checked the documented gcloud alternative: `gcloud iam oauth-clients create` calls the IAM OAuth client API and supports only IAM/federated-client scopes, not the Search Console or Indexing scopes needed here; it was not used.
- [ ] No Google OAuth credentials are in local `.env`; OAuth start returns a JSON 503 configuration error. Callback, encrypted token persistence, Search Console, Inspection, Indexing, refresh, reconnect, disconnect, and revocation remain unverified live.
- [x] Local Compose status checked: `api`, `db`, and `web` are running; `/ready` reports `database: ok`.
- [x] Follow-up validation: 21 backend tests, Ruff, mypy, 5 frontend tests, frontend production build, and `git diff --check` passed. Three Alembic import-order lint violations were corrected.
- This is partial setup only; it does not establish production readiness or live integration success.

## 2026-10-15 production-readiness audit

- [x] Corrected indexing-history deletion on disconnect by changing the connection foreign key to `SET NULL` in migration `0002`; downgrade fails safely because prior connection references cannot be reconstructed.
- [x] Required non-development settings to use HTTPS origins, Secure cookies, configured OAuth credentials, a strong session secret, and an active encryption key; non-local key IDs now fail closed.
- [x] Added stable idempotency reservation with PostgreSQL `ON CONFLICT DO NOTHING`, owner-only Indexing API permission checks, OAuth denial handling, malformed response handling, and refresh time calculation after row lock acquisition.
- [x] Expanded regression coverage and added mypy and Docker image build to CI.
- [x] Local results: 20 pytest passed; Ruff and mypy passed; frontend test/build and npm audit passed; offline migrations and Compose config passed.
- [x] GitHub Actions run `38690369706` passed online migrations against PostgreSQL and the Docker image build, along with backend and frontend validation. Local Docker/PostgreSQL were unavailable.
- [ ] No live Google OAuth/API call was performed. Production auth/session issuer, shared limiter, project-specific Indexing API authorization setup, and external approval remain prerequisites.
- [x] Follow-up runtime debugging: corrected the Compose Vite proxy target (`api:8000`); browser-facing health/readiness/connections now return 200 and OAuth start returns a JSON 503 when credentials are absent. Added empty/non-JSON frontend response handling and generic structured FastAPI 500 responses.
- [x] Follow-up local checks: Docker Compose build/start passed, PostgreSQL healthy at migration `0002_preserve_history`, 21 backend tests, Ruff, mypy, 5 frontend tests, production build, and npm audit (0 findings) passed.
- The referenced assignment PDF is absent; if its questions differ from the supplied prompt, the written response may need a final alignment pass.

## 2026-10-15 OAuth credential configuration follow-up

- [x] Fresh OAuth credentials are present in the ignored local `.env`; presence was checked without printing values. The exact callback URI is configured.
- [x] Google Auth Platform client details showed redirect URI `http://localhost:8000/api/v1/auth/google/callback`.
- [x] Recreated Docker Compose after configuring `.env`; `api`, `db`, and `web` are running, PostgreSQL is healthy, and `/ready` reports the database as `ok`.
- [x] `/api/v1/connections` returns HTTP 200. `/api/v1/auth/google/start` returns HTTP 200 and constructs an authorization request with state, PKCE, correct callback and requested scopes.
- [x] Local validation: 21 backend tests, Ruff, mypy (10 source files), 5 frontend tests, and frontend production build passed.
- [x] At this point in the setup, Google sign-in and consent were still pending. The later live OAuth completion section below records the operations subsequently verified.
- Previous client secrets were exposed in chat and must be disabled/deleted after the newly configured secret is verified. No credential values are in source control.
- This latest status supersedes the earlier note that OAuth client creation and local credentials were blocked. This does not establish production readiness.

## 2026-10-15 OAuth scope mismatch fix

- Google Auth Platform Data Access was inspected read-only. It lists the email permission as the canonical `userinfo.email` URL, plus OpenID, Search Console read-only, and Indexing scopes.
- The previous callback's token response included a string `scope` field (the missing-field case has a separate error). The application did not persist or log that list, so the exact returned list cannot be recovered from the consumed transaction.
- Fixed the confirmed literal-scope comparison defect by normalizing the `email` / `userinfo.email` aliases. Base connection success now requires Search Console read and identity permissions; Indexing is optional until its operation is used.
- Added per-operation scope checks for Search Console properties/inspection and Indexing submissions. Missing permissions remain denied. OAuth requests support incremental Indexing authorization and `include_granted_scopes=true`.
- Added regression tests for scope alias normalization, missing-scope denial, optional Indexing scope, and incremental authorization parameters.
- Validation after the fix: 24 backend tests passed; Ruff and mypy passed; 5 frontend tests passed; TypeScript/Vite production build passed. Initial build surfaced and then fixed three handler typing errors from the new optional callback argument; final build passed.
- Docker Compose has now been rebuilt with the scope change. The API is running; PostgreSQL is healthy; `/ready`, `/api/v1/connections`, and both base/incremental OAuth start requests passed smoke checks. The user still needs to repeat Google consent. Callback, encrypted token persistence, connected status, Search Console properties, URL Inspection, Indexing, refresh, and revocation remain unverified live.

## 2026-10-15 live OAuth completion

- [x] User completed Google sign-in and consent; the callback returned HTTP 303 and a connected account was persisted.
- [x] The safe callback scope diagnostic showed a present `scope` field, granted `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/webmasters.readonly`, and `https://www.googleapis.com/auth/indexing`, with no missing required scopes.
- [x] This successful grant confirms the earlier diagnosis: Google returned the configured canonical `userinfo.email` URL while the former code compared the requested `email` literal. The fix normalizes only that alias.
- [x] Stored access and refresh token columns use encrypted envelopes and both decrypted successfully with the configured key. Connection status is `connected`.
- [x] Live Search Console `sites.list` returned HTTP 200 with zero properties for this Google account.
- [x] Real token refresh was exercised through the app by forcing the local expiry timestamp into the past and calling the property endpoint. The request returned HTTP 200; access token changed, future expiry persisted, connection stayed connected, and token envelopes remained decryptable.
- [ ] URL Inspection and Indexing API notification were not run: no accessible property or eligible URL was returned. No reconnect, disconnect, or revocation was performed to avoid disrupting the active grant.
- [x] Regression validation: 25 backend tests, Ruff, mypy (10 source files), 5 frontend tests, production frontend build, Compose rebuild, and `git diff --check` passed.
- No credentials were printed, logged, committed, or pushed. Commit and push were authorized after local verification.
