import { API_BASE_URL } from '../config';

export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'parse' | 'aborted';

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  code?: string;
  constructor(kind: ApiErrorKind, message: string, status?: number, code?: string) {
    super(message);
    this.kind = kind;
    this.status = status;
    this.code = code;
  }
}

interface Options {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

/** fetch có timeout + hủy request, quy mọi lỗi về ApiError. */
export async function apiFetch<T>(path: string, opts: Options = {}): Promise<T> {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, opts.timeoutMs ?? 10000);
  const onAbort = () => ctrl.abort();
  opts.signal?.addEventListener('abort', onAbort);
  if (opts.signal?.aborted) ctrl.abort();

  try {
    const res = await fetch(API_BASE_URL + path, {
      method: opts.method ?? 'GET',
      headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const message = typeof body?.error?.message === 'string' ? body.error.message : `Máy chủ trả lỗi ${res.status}`;
      const code = typeof body?.error?.code === 'string' ? body.error.code : undefined;
      throw new ApiError('http', message, res.status, code);
    }
    try {
      if (res.status === 204) return undefined as T;
      return (await res.json()) as T;
    } catch {
      throw new ApiError('parse', 'Dữ liệu trả về không đúng định dạng');
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (timedOut) throw new ApiError('timeout', 'Máy chủ phản hồi quá lâu');
    if (opts.signal?.aborted) throw new ApiError('aborted', 'Đã hủy yêu cầu');
    throw new ApiError('network', 'Không kết nối được máy chủ');
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', onAbort);
  }
}
