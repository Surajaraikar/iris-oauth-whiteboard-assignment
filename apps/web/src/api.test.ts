import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('api response handling', () => {
  it('returns JSON response bodies', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"ok":true}', { status: 200 })));
    await expect(api('/health')).resolves.toEqual({ ok: true });
  });

  it('uses structured API error details', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"detail":"Google OAuth is not configured."}', { status: 503 })));
    await expect(api('/api/v1/auth/google/start')).rejects.toThrow('Google OAuth is not configured.');
  });

  it.each([
    ['empty', ''],
    ['non-JSON', '<html>proxy unavailable</html>'],
  ])('returns a status error for %s error bodies', async (_kind, body) => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 500 })));
    await expect(api('/api/v1/connections')).rejects.toThrow('Request failed (500)');
  });
});
