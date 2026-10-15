export async function api(path: string, init?: RequestInit): Promise<any> {
  const response = await fetch(path, { credentials: 'include', ...init });
  const body = await response.text();
  let data: any = null;

  if (body) {
    try {
      data = JSON.parse(body);
    } catch {
      // Proxies and gateways sometimes return empty or non-JSON error pages.
      // Keep the UI error readable instead of surfacing a JSON parser exception.
      data = null;
    }
  }

  if (!response.ok) {
    const detail = data?.detail ?? data?.message;
    const message = typeof detail === 'string' ? detail : `Request failed (${response.status})`;
    throw new Error(message);
  }

  return data;
}
