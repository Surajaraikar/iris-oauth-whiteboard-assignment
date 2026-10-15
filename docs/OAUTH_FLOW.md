# OAuth and token lifecycle

1. The authenticated user starts `/api/v1/auth/google/start`. The server creates random state and PKCE verifier, stores a hash of state and expiry, and returns Google's authorization URL.
2. Google redirects to the registered callback. The API hashes and compares state, locks and consumes the transaction, then exchanges code + verifier with the configured redirect URI.
3. The API validates required returned scopes and verifies Google `sub` and verified email through OIDC UserInfo. It stores encrypted access/refresh tokens, expiry, and granted scopes.
4. Google API calls refresh close-to-expiry access tokens. The connection row is locked and refreshed tokens are committed together. `invalid_grant` moves the connection to `reauthorization_required`.
5. Disconnect attempts the Google revocation endpoint and always removes local credentials; the response distinguishes confirmed remote revocation from local deletion only.

The configured OAuth client redirect URI must exactly match the callback URI. A new refresh token is not guaranteed on every consent; existing refresh credentials are retained. Refresh-token invalidation can result from revocation, inactivity, token limits, testing-mode expiry, session controls, or some Gmail-scope password changes.
