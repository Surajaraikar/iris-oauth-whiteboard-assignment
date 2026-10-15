# Testing and verification

Automated tests use local crypto and request-schema checks plus a mocked frontend empty-state render. They do not prove a live Google authorization, property permission, API approval, or indexing outcome. Run backend tests with `cd apps/api && pip install -e '.[dev]' && pytest`; run frontend checks with `cd apps/web && npm install && npm test && npm run build`.

## Results in the delivery environment

- Python bytecode compile: passed (Python 3.14.2 available; project targets Python 3.12+).
- Pytest: 5 passed.
- Ruff: passed.
- Alembic offline SQL generation: passed. No PostgreSQL server was available, so an online migration was not exercised.
- Frontend tests: 1 passed.
- Frontend production TypeScript/Vite build: passed.
- Docker Compose configuration: passed. Images/containers were not built or started.
- Live Google OAuth and APIs: not run; credentials, a verified property, and Indexing API approval were not supplied.

The test suite is intentionally a small deterministic baseline and does not yet exercise the full OAuth/database/Google error matrix described in the assignment. Google credentials and Indexing API approval are not included in this repository.
