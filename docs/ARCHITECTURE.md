# Architecture

The repository is a modular monolith. `apps/api` owns identity context, OAuth transactions, encrypted token persistence, Google HTTP adapters, and audit history. `apps/web` is a same-origin-proxied React UI; browser storage never receives OAuth credentials.

```mermaid
flowchart LR
  Browser[React dashboard] -->|same-origin API + session cookie| API[FastAPI routers]
  API --> Auth[OAuth and token services]
  API --> GSC[Search Console adapter]
  API --> IDX[Indexing API adapter]
  Auth -->|AES-GCM envelope| DB[(PostgreSQL)]
  API --> DB
  Auth <-->|code, refresh, revoke| GoogleOAuth[Google OAuth]
  GSC <-->|properties, inspection| GoogleSC[Search Console API]
  IDX <-->|eligible notifications| GoogleIndex[Indexing API]
```

PostgreSQL is the source of truth. OAuth state records expire after ten minutes and are deleted before code exchange. Google calls have explicit timeouts. API errors are mapped to safe client messages. Migrations are managed by Alembic. The current rate limiting is a single-process design and must move to shared infrastructure for multi-replica deployments.
