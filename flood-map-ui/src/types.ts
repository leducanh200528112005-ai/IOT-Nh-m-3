import type { Feature, FeatureCollection, LineString } from 'geojson';

/** Mức ngập do BACKEND tính. Frontend chỉ hiển thị, không tự tính lại. */
export type FloodLevel = 'none' | 'low' | 'medium' | 'high' | 'unknown';
/** Chất lượng dữ liệu, tách biệt với mức ngập. */
export type DataQuality = 'ok' | 'stale' | 'missing';

export interface LatLng {
  lat: number;
  lng: number;
}

export interface Station {
  id: string;
  name: string;
  lat: number;
  lng: number;
  depthCm: number | null;
  level: FloodLevel;
  dataQuality: DataQuality;
  updatedAt: string | null; // ISO 8601
}

export interface FloodZonesResponse {
  /** Mã phiên bản dữ liệu (nếu backend có). Không có thì frontend tự băm nội dung. */
  version?: string;
  updatedAt: string;
  stations: Station[];
  /** GeoJSON: tọa độ theo thứ tự [lng, lat] */
  restrictedZones: FeatureCollection;
}

export interface RouteRequest {
  origin: LatLng;
  destination: LatLng;
}

export interface RouteResponse {
  status: 'ok' | 'no_route';
  message?: string;
  /** GeoJSON LineString: tọa độ theo thứ tự [lng, lat] */
  route?: Feature<LineString>;
  distanceM?: number;
  durationS?: number;
  computedAt?: string;
  floodVersion?: string;
}
