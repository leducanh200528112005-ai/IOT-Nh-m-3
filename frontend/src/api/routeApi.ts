import type {
  AdminOverviewResponse,
  FloodHistoryResponse,
  GeocodeResult,
  RouteRequest,
  RouteResponse,
  RoutingStatusResponse,
} from '../types';
import { apiFetch } from './client';

/** Chỉ gọi khi người dùng bấm nút. Frontend không gọi upstream trực tiếp. */
export async function requestSafeRoute(req: RouteRequest, signal?: AbortSignal): Promise<RouteResponse> {
  return apiFetch<RouteResponse>('/api/routes/safe', { method: 'POST', body: req, signal, timeoutMs: 20000 });
}

export async function geocodeAddress(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const data = await apiFetch<{ results: GeocodeResult[] }>(
    `/api/geocode?q=${encodeURIComponent(query)}&limit=6`,
    { signal, timeoutMs: 8000 },
  );
  return data.results ?? [];
}

export async function fetchFloodHistory(
  pointId: string,
  source: 'real' | 'demo',
  signal?: AbortSignal,
): Promise<FloodHistoryResponse> {
  return apiFetch<FloodHistoryResponse>(
    `/api/flood-zones/${encodeURIComponent(pointId)}/history?source=${source}`,
    { signal, timeoutMs: 8000 },
  );
}

export async function fetchRoutingStatus(refresh = false, signal?: AbortSignal): Promise<RoutingStatusResponse> {
  return apiFetch<RoutingStatusResponse>(`/api/routing-status?refresh=${refresh}`, { signal, timeoutMs: 8000 });
}

export async function fetchAdminOverview(signal?: AbortSignal): Promise<AdminOverviewResponse> {
  return apiFetch<AdminOverviewResponse>('/api/admin/overview', { signal, timeoutMs: 10000 });
}
