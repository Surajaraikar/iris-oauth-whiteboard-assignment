# Security notes

- OAuth code, access token, refresh token and client secret are never intentionally logged or returned to the browser.
- Tokens use AES-256-GCM with random nonces and versioned key IDs. Production startup fails without the active key. Keep old keys available until records are re-encrypted; manage key material in a secret manager.
- To rotate, configure both old and new key IDs, set the new ID active, run `cd apps/api && python -m app.services.key_rotation`, verify the result, then remove the old key after backups/records are confirmed.
- OAuth state is random, hashed at rest, expires after ten minutes and is consumed once. PKCE uses S256.
- User identity is dependency-injected from a signed session or development-only local reviewer. Endpoints filter connections and history by the authenticated user; there is no user_id request parameter.
- CSRF is checked on state-changing disconnect and indexing notification requests. Cookies must be HttpOnly, Secure, and SameSite=Lax when implementing the production session issuer. The local reviewer mode is only for development and must not be exposed publicly.
- CORS allows only the configured frontend origin. URLs are validated locally and never fetched, avoiding SSRF. HTTPS is required for notifications.
- Request payloads are bounded and typed. Google HTTP calls use timeouts. Errors returned to callers are sanitized.
- Remaining production work: integrate a real identity provider/session lifecycle, set cookies from that provider, add shared Redis rate limiting, configure reverse-proxy TLS/security headers, and provide operational metrics/alerting.
