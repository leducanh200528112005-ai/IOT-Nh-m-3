import type { FloodZonesResponse, SourceSelection } from '../types';
import { apiFetch } from './client';

export function fetchFloodZones(selection: SourceSelection, signal?: AbortSignal): Promise<FloodZonesResponse> {
  const query = new URLSearchParams({ source: selection.source, include_real: String(selection.include_real) });
  return apiFetch<FloodZonesResponse>(`/api/flood-zones?${query}`, { signal });
}
