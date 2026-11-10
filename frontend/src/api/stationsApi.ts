import { apiFetch } from './client';
import type { StationConfig, StationCreateInput, StationInput } from '../types';

export const listStations = (signal?: AbortSignal) => apiFetch<StationConfig[]>('/api/stations', { signal });
export const createStation = (body: StationCreateInput) => apiFetch<StationConfig>('/api/stations', { method: 'POST', body });
export const updateStation = (id: string, body: Partial<StationInput>) =>
  apiFetch<StationConfig>(`/api/stations/${encodeURIComponent(id)}`, { method: 'PATCH', body });
export const deleteStation = (id: string) =>
  apiFetch<void>(`/api/stations/${encodeURIComponent(id)}`, { method: 'DELETE' });
