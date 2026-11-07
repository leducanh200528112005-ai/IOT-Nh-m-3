import type { DataQuality, FloodLevel, FloodZonesResponse, Station } from '../types';

export const LEVEL_INFO: Record<FloodLevel, { label: string; color: string }> = {
  none: { label: 'Không ngập', color: '#2f9e6e' },
  low: { label: 'Ngập nhẹ', color: '#e3b505' },
  medium: { label: 'Ngập vừa', color: '#ee7d1a' },
  high: { label: 'Ngập sâu', color: '#c8312b' },
  unknown: { label: 'Không rõ', color: '#8a949e' },
};

export const QUALITY_LABEL: Record<DataQuality, string> = {
  ok: 'Dữ liệu mới',
  stale: 'Dữ liệu cũ',
  missing: 'Mất dữ liệu',
};

/** Trạm mất dữ liệu luôn hiển thị "không rõ" (xám), không bao giờ rơi về màu xanh. */
export function displayLevel(s: Station): FloodLevel {
  return s.dataQuality === 'missing' || !(s.level in LEVEL_INFO) ? 'unknown' : s.level;
}

/** Mã phiên bản dữ liệu vùng ngập, dùng để biết tuyến đang hiển thị có còn khớp không. */
export function floodVersion(d: FloodZonesResponse): string {
  if (d.version) return d.version;
  const s = d.stations.map((x) => `${x.id}:${x.level}:${x.dataQuality}:${x.depthCm}`).join('|');
  const z = JSON.stringify(d.restrictedZones);
  let h = 0;
  for (const ch of s + z) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return String(h);
}
