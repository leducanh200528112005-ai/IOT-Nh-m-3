import type { DemoPointInput } from '../types';

/**
 * 10 điểm demo mẫu quanh khu vực Hà Đông — Hà Nội.
 * Có điểm An toàn (🟢), Cảnh báo (🟡), AI Dự báo ngập đỏ (🤖), và Nguy hiểm thực tế (🔴).
 * Ngưỡng đỏ chuẩn: >= 30 cm.
 */
export const DEFAULT_DEMO_POINTS: DemoPointInput[] = [
  {
    name: 'Ngã tư Trần Phú - Nguyễn Văn Lộc',
    latitude: 20.9826,
    longitude: 105.7865,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Cầu Trắng Hà Đông (Quang Trung)',
    latitude: 20.9723,
    longitude: 105.7768,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Ngã tư Lê Trọng Tấn - Quang Trung',
    latitude: 20.9592,
    longitude: 105.7621,
    water_depth_cm: 35,           // 🔴 Nguy hiểm thực tế (>=30cm)
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 50,
    is_active: true,
  },
  {
    name: 'Đường Tô Hiệu (gần Metro cũ)',
    latitude: 20.9655,
    longitude: 105.7745,
    water_depth_cm: 15,           // 🟡 Cảnh báo (10-30cm, ổn định)
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Khu đô thị Văn Phú (đường 24m)',
    latitude: 20.9575,
    longitude: 105.7695,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Ngã tư Vạn Phúc - Tố Hữu',
    latitude: 20.9808,
    longitude: 105.7682,
    water_depth_cm: 12,           // 🤖 AI DỰ BÁO ĐỎ: Nước mới 12cm nhưng đang dâng +8cm/10p!
    rise_rate_cm_min: 0.8,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 50,
    is_active: true,
  },
  {
    name: 'Đường Chiến Thắng (đoạn hồ Văn Quán)',
    latitude: 20.9845,
    longitude: 105.7925,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Bến xe Yên Nghĩa (cửa ngõ QL6)',
    latitude: 20.9482,
    longitude: 105.7485,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Khuất Duy Tiến - Nguyễn Trãi (hầm chui)',
    latitude: 20.9925,
    longitude: 105.7995,
    water_depth_cm: 14,           // 🤖 AI DỰ BÁO ĐỎ: Nước 14cm dâng nhanh +7cm/10p
    rise_rate_cm_min: 0.7,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
  {
    name: 'Ngã ba Ba La (Quang Trung - QL21B)',
    latitude: 20.9515,
    longitude: 105.7565,
    water_depth_cm: 0,            // 🟢 An toàn
    rise_rate_cm_min: 0.0,
    warning_threshold_cm: 10,
    danger_threshold_cm: 30,
    exclusion_radius_m: 40,
    is_active: true,
  },
];
