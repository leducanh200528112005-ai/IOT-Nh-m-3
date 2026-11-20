const env = import.meta.env;

export const API_BASE_URL: string = (env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
export const POLL_INTERVAL_MS: number = Math.min(Math.max(Number(env.VITE_POLL_INTERVAL_MS) || 3000, 2000), 5000);
/** Quá ngưỡng này không poll thành công => coi là không còn cập nhật */
export const STALE_AFTER_MS = POLL_INTERVAL_MS * 4;
/** Thời gian tối thiểu giữ tuyến đã tính luôn hợp lệ (1 phút 30 giây = 90.000 ms) */
export const ROUTE_STALE_GRACE_PERIOD_MS = 90 * 1000;
/** Dấu thời gian dữ liệu từ backend quá cũ => coi là quá hạn */
export const DATA_EXPIRE_MS = 2 * 60 * 1000;
export const TILE_URL: string = env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const TILE_ATTRIBUTION: string =
  env.VITE_TILE_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
export const MAP_CENTER: [number, number] = [20.972, 105.770]; // [lat, lng] - Hà Đông, Hà Nội
export const MAP_ZOOM = 14;
