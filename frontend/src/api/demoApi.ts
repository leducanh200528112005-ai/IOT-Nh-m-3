import { apiFetch } from './client';
import type { DemoPoint, DemoPointInput } from '../types';

export const listDemoPoints = (signal?: AbortSignal) => apiFetch<DemoPoint[]>('/api/demo-points', { signal });
export const createDemoPoint = (body: DemoPointInput) => apiFetch<DemoPoint>('/api/demo-points', { method: 'POST', body });
export const updateDemoPoint = (id: string, body: Partial<DemoPointInput>) =>
  apiFetch<DemoPoint>(`/api/demo-points/${encodeURIComponent(id)}`, { method: 'PATCH', body });
export const deleteDemoPoint = (id: string) =>
  apiFetch<void>(`/api/demo-points/${encodeURIComponent(id)}`, { method: 'DELETE' });
