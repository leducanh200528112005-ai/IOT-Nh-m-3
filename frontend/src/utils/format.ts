export function formatDistance(m?: number): string {
  if (m == null) return '—';
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

export function formatDuration(s?: number): string {
  if (s == null) return '—';
  const min = Math.round(s / 60);
  if (min < 60) return `${Math.max(min, 1)} phút`;
  return `${Math.floor(min / 60)} giờ ${min % 60} phút`;
}

export function formatTime(iso?: string | null): string {
  if (!iso) return 'Chưa có';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? 'Chưa có' : d.toLocaleString('vi-VN');
}

export function formatCoord(p: { lat: number; lng: number }): string {
  return `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}`;
}
