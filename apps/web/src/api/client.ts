/**
 * Base HTTP API client with unified error normalization.
 * Every request in the app goes through this module (no raw fetch in components).
 */

const API_BASE = '/api';

export class ApiError extends Error {
  public status: number;
  public details?: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }

  /** The backend could not be reached at all (status 0). */
  get isConnectionError(): boolean {
    return this.status === 0;
  }

  /** The daily character limit was reached (HTTP 429). */
  get isQuotaError(): boolean {
    return this.status === 429;
  }
}

function url(endpoint: string): string {
  return `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(input, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(0, 'Không kết nối được máy chủ.');
  }
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    let details: unknown = null;
    try {
      const data = await res.json();
      message = data.error || message;
      details = data.details ?? null;
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(res.status, message, details);
  }
  return res;
}

async function parseJson<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type Params = Record<string, string | number | boolean | undefined | null>;

function withParams(endpoint: string, params?: Params): string {
  const query = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) query.append(key, String(value));
  });
  const qs = query.toString();
  return qs ? `${url(endpoint)}?${qs}` : url(endpoint);
}

export async function apiGet<T>(endpoint: string, params?: Params, signal?: AbortSignal): Promise<T> {
  return parseJson<T>(await request(withParams(endpoint, params), { headers: { Accept: 'application/json' }, signal }));
}

/** Download a binary body (audio) as a Blob together with its content type. */
export async function apiGetBlob(endpoint: string, params?: Params, signal?: AbortSignal): Promise<Blob> {
  return (await request(withParams(endpoint, params), { signal })).blob();
}

function jsonInit(method: string, body?: unknown, keepalive = false): RequestInit {
  return {
    method,
    keepalive,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

export async function apiPost<T>(endpoint: string, body?: unknown, options?: { keepalive?: boolean }): Promise<T> {
  return parseJson<T>(await request(url(endpoint), jsonInit('POST', body, options?.keepalive)));
}

export async function apiPut<T>(endpoint: string, body: unknown): Promise<T> {
  return parseJson<T>(await request(url(endpoint), jsonInit('PUT', body)));
}

export async function apiPatch<T>(endpoint: string, body: unknown): Promise<T> {
  return parseJson<T>(await request(url(endpoint), jsonInit('PATCH', body)));
}

export async function apiDelete(endpoint: string): Promise<void> {
  await request(url(endpoint), { method: 'DELETE' });
}

export async function apiUpload<T>(endpoint: string, formData: FormData): Promise<T> {
  return parseJson<T>(await request(url(endpoint), { method: 'POST', headers: { Accept: 'application/json' }, body: formData }));
}

/** Absolute-path URL for a file endpoint (used for `<a download>`). */
export function fileUrl(endpoint: string): string {
  return url(endpoint);
}
