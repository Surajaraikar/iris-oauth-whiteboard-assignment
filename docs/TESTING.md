# Testing and verification

Automated tests cover security configuration, token encryption/key rotation, OAuth PKCE construction and denial handling, token refresh replacement/locking arguments and `invalid_grant`, ownership boundaries, migration-sensitive foreign-key behavior, idempotent reservation SQL, Google error classification, health, and safe retry behavior. They do not prove real PostgreSQL locking semantics or a live Google authorization/property/API/indexing outcome. Safe reads and URL Inspection have bounded exponential retry with jitter; Indexing API writes are never automatically retried. Run backend checks with `cd apps/api && pip install -e '.[dev]' && pytest`; run frontend checks with `cd apps/web && npm install && npm test && npm run build`.

## Results in the delivery environment

- Python bytecode compile: passed (Python 3.14.2 available; project targets Python 3.12+).
- Pytest: 20 passed.
- Ruff: passed.
- Mypy: passed (10 backend source files).
- FastAPI `/health` ASGI test: passed (HTTP 200).
- Alembic offline SQL generation through both migrations: passed. No PostgreSQL listener or service was available, so an online migration was not exercised.
- Frontend tests: 1 passed.
- Frontend production TypeScript/Vite build: passed.
- npm audit: 0 vulnerabilities.
- Docker Compose configuration: passed. `docker build` was attempted but unavailable because the Docker Desktop Linux engine was not running; containers were not started.
- Live Google OAuth and APIs: not run; credentials, a verified property, and Indexing API approval were not supplied.

The tests are a deterministic regression baseline, not the full database-backed OAuth/refresh race matrix. CI is configured to run migrations against PostgreSQL and build the API image on GitHub-hosted runners; those remote checks have not yet been observed for this audit commit. Google credentials and Indexing API approval are not included in this repository.
