import type { Feature, FeatureCollection, LineString } from 'geojson';

/** Mức ngập do BACKEND tính. Frontend chỉ hiển thị, không tự tính lại. */
export type FloodLevel = 'normal' | 'warning' | 'danger' | 'predicted_danger' | 'unknown';
/** Chất lượng dữ liệu, tách biệt với mức ngập. */
export type DataQuality = 'fresh' | 'stale' | 'invalid' | 'missing';

export type VehicleType = 'car' | 'motorcycle' | 'pedestrian';
export type Lang = 'vi' | 'en';

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
  rise_rate_cm_min?: number;
  hazard_state: FloodLevel;
  data_quality: DataQuality;
  ai_prediction?: {
    depth_current: number;
    rate_cm_per_min: number;
    predicted_15m: number;
    predicted_30m: number;
    danger_probability: number;
    is_predicted_danger: boolean;
    warning_message: string | null;
  };
  measured_at: string | null;
  received_at: string | null;
  updated_at?: string | null;
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
  vehicle?: VehicleType;
  lang?: Lang;
}

export interface RouteStep {
  instruction: string;
  distance_m: number;
  duration_s: number;
  type: string;
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
  engine?: string;
  snap_distances_m: { start: number; end: number };
  warnings: string[];
  steps?: RouteStep[];
}

export interface RouteHistoryItem {
  id: string;
  origin: LatLng;
  destination: LatLng;
  originLabel?: string;
  destinationLabel?: string;
  vehicle: VehicleType;
  distance_m: number;
  duration_s: number;
  savedAt: string;
}

export interface GeocodeResult {
  label: string;
  latitude: number;
  longitude: number;
  city: string;
  district: string;
}

export interface HistoryPoint {
  label: string;
  depth_cm: number;
  is_forecast: boolean;
}

export interface FloodHistoryResponse {
  id: string;
  name: string;
  source: 'real' | 'demo';
  warning_threshold_cm: number;
  danger_threshold_cm: number;
  ai_prediction: Station['ai_prediction'] | null;
  points: HistoryPoint[];
}

export interface RoutingServiceState {
  status: string;
  latency_ms?: number;
}

export interface RoutingStatusResponse {
  valhalla: RoutingServiceState;
  osrm: RoutingServiceState;
  ors: RoutingServiceState;
  checked_at: string;
  cached?: boolean;
}

export interface AdminOverviewResponse {
  checked_at: string;
  database: string;
  mqtt: string;
  routing: RoutingStatusResponse;
  flags: {
    demo_enabled: boolean;
    stations_enabled: boolean;
    admin_auth_required: boolean;
    rate_limit_route_per_min: number;
  };
  stations: {
    total: number;
    active: number;
    quality: Record<DataQuality, number>;
    danger_or_predicted: number;
  };
  demo_points: {
    total: number;
    active: number;
    max: number;
    danger: number;
    predicted_danger: number;
  };
}

export interface DemoPointInput {
  name: string;
  latitude: number;
  longitude: number;
  water_depth_cm: number;
  rise_rate_cm_min?: number;
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
