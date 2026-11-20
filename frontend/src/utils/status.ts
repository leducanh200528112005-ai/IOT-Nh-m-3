import type { DataQuality, FloodLevel, FloodZonesResponse, Station } from '../types';

export const LEVEL_INFO: Record<FloodLevel, { label: string; color: string }> = {
  normal: { label: 'Bình thường', color: '#2f9e6e' },
  warning: { label: 'Cảnh báo', color: '#e3b505' },
  danger: { label: 'Nguy hiểm', color: '#c8312b' },
  predicted_danger: { label: 'Dự báo nguy cơ ngập sớm (AI)', color: '#a855f7' },
  unknown: { label: 'Không rõ', color: '#8a949e' },
};

export const QUALITY_LABEL: Record<DataQuality, string> = {
  fresh: 'Dữ liệu mới',
  invalid: 'Lỗi cảm biến',
  stale: 'Dữ liệu cũ',
  missing: 'Mất dữ liệu',
};

/** Trạm mất dữ liệu luôn hiển thị "không rõ" (xám), không bao giờ rơi về màu xanh. */
export function displayLevel(s: Station): FloodLevel {
  return s.data_quality !== 'fresh' || !(s.hazard_state in LEVEL_INFO) ? 'unknown' : s.hazard_state;
}

/** Mã phiên bản dữ liệu vùng ngập, dùng để biết tuyến đang hiển thị có còn khớp không.
 * Chỉ theo dõi trạng thái cảnh báo và vùng cấm địa lý thực sự, bỏ qua dao động mực nước nhỏ để tránh làm tuyến bị lỗi thời giả. */
export function floodVersion(d: FloodZonesResponse): string {
  const s = `${d.source}:${d.include_real}|` +
    d.stations.map((x) => `${x.source ?? ''}:${x.id}:${x.hazard_state}:${x.data_quality}`).join('|');
  const zones = (d.flood_zones?.features ?? []).map((f) => {
    const props = f.properties as Record<string, unknown> | undefined;
    return `${props?.station_id ?? ''}:${props?.radius_m ?? ''}:${props?.is_predicted ? '1' : '0'}`;
  }).sort().join(';');
  let h = 0;
  for (const ch of s + '|' + zones) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return String(h);
}
