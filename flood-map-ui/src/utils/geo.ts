import type { LatLngTuple } from 'leaflet';
import type { Feature, LineString } from 'geojson';

/** GeoJSON dùng [lng, lat]; Leaflet dùng [lat, lng]. Mọi chuyển đổi đi qua hàm này. */
export function lineToLatLngs(feature: Feature<LineString>): LatLngTuple[] {
  const coords = feature.geometry.coordinates;
  if (import.meta.env.DEV && coords.length > 0 && Math.abs(coords[0][0]) < Math.abs(coords[0][1]) && coords[0][1] > 90) {
    console.warn('Tọa độ tuyến có vẻ bị đảo thứ tự lng/lat. Hợp đồng với nhóm 2 là [lng, lat].');
  }
  return coords.map(([lng, lat]) => [lat, lng] as LatLngTuple);
}
