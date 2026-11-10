import type { Feature, FeatureCollection, LineString } from 'geojson';

/** Mức ngập do BACKEND tính. Frontend chỉ hiển thị, không tự tính lại. */
export type FloodLevel = 'normal' | 'warning' | 'danger' | 'unknown';
/** Chất lượng dữ liệu, tách biệt với mức ngập. */
export type DataQuality = 'fresh' | 'stale' | 'invalid' | 'missing';

export interface LatLng {
  lat: number;
  lng: number;
}

export interface Station {
  source?: 'real' | 'demo';
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  water_depth_cm: number | null;
  hazard_state: FloodLevel;
  data_quality: DataQuality;
  measured_at: string | null;
  received_at: string | null;
}

export interface FloodZonesResponse {
  source: 'real' | 'demo';
  include_real: boolean;
  generated_at: string;
  stations: Station[];
  /** GeoJSON: tọa độ theo thứ tự [lng, lat] */
  flood_zones: FeatureCollection;
  routing_data_sufficient: boolean;
}

export interface SourceSelection {
  source: 'real' | 'demo';
  include_real: boolean;
}

export interface RouteRequest extends SourceSelection {
  start: { latitude: number; longitude: number };
  end: { latitude: number; longitude: number };
}

export interface RouteResponse {
  source: 'real' | 'demo';
  include_real: boolean;
  /** GeoJSON LineString: tọa độ theo thứ tự [lng, lat] */
  route: Feature<LineString>;
  distance_m: number;
  duration_s: number;
  calculated_at: string;
  data_generated_at: string;
  profile: string;
  snap_distances_m: { start: number; end: number };
  warnings: string[];
}

export interface DemoPointInput {
  name: string;
  latitude: number;
  longitude: number;
  water_depth_cm: number;
  warning_threshold_cm: number;
  danger_threshold_cm: number;
  exclusion_radius_m: number;
  is_active: boolean;
}

export interface DemoPoint extends DemoPointInput {
  id: string;
  created_at: string;
  updated_at: string;
}

/** Trạm thật. `id` là device_id trong payload MQTT, không đổi được sau khi tạo. */
export interface StationInput {
  name: string;
  latitude: number;
  longitude: number;
  warning_threshold_cm: number;
  danger_threshold_cm: number;
  exclusion_radius_m: number;
  is_active: boolean;
}

export interface StationCreateInput extends StationInput {
  id: string;
}

export interface StationConfig extends StationInput {
  id: string;
  created_at: string;
  updated_at: string;
}
