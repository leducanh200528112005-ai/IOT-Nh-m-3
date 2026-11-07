import { USE_MOCK } from '../config';
import type { RouteRequest, RouteResponse } from '../types';
import { apiFetch } from './client';

/** Chỉ gọi khi người dùng bấm nút. Frontend không gọi ORS trực tiếp. */
export async function requestSafeRoute(req: RouteRequest, signal?: AbortSignal): Promise<RouteResponse> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 700)); // giả lập độ trễ
    return apiFetch<RouteResponse>('/mock/route-safe.json', { signal });
  }
  return apiFetch<RouteResponse>('/api/routes/safe', { method: 'POST', body: req, signal, timeoutMs: 20000 });
}
