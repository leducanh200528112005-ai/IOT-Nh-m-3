import { USE_MOCK } from '../config';
import type { FloodZonesResponse } from '../types';
import { apiFetch } from './client';

export function fetchFloodZones(signal?: AbortSignal): Promise<FloodZonesResponse> {
  return USE_MOCK
    ? apiFetch<FloodZonesResponse>('/mock/flood-zones.json', { signal })
    : apiFetch<FloodZonesResponse>('/api/flood-zones', { signal });
}
