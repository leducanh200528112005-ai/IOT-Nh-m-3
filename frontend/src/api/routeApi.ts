import type { RouteRequest, RouteResponse } from '../types';
import { apiFetch } from './client';

/** Chỉ gọi khi người dùng bấm nút. Frontend không gọi ORS trực tiếp. */
export async function requestSafeRoute(req: RouteRequest, signal?: AbortSignal): Promise<RouteResponse> {
  return apiFetch<RouteResponse>('/api/routes/safe', { method: 'POST', body: req, signal, timeoutMs: 40000 });
}
