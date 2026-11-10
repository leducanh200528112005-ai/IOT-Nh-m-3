import { useEffect, useRef } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import { divIcon, type LatLngTuple, type Marker as LeafletMarker } from 'leaflet';
import type { FeatureCollection } from 'geojson';
import { MAP_CENTER, MAP_ZOOM, TILE_ATTRIBUTION, TILE_URL } from '../config';
import type { LatLng, Station } from '../types';
import { formatTime } from '../utils/format';
import { LEVEL_INFO, QUALITY_LABEL, displayLevel } from '../utils/status';

export type PickMode = 'origin' | 'destination' | 'demo' | null;

interface Props {
  stations: Station[];
  zones: FeatureCollection | null;
  zonesKey: string;
  origin: LatLng | null;
  destination: LatLng | null;
  routePath: LatLngTuple[] | null;
  routeOutdated: boolean;
  pickMode: PickMode;
  selectedId: string | null;
  onPick: (p: LatLng) => void;
  onSelectStation: (id: string) => void;
  onMoveDemo?: (id: string, position: LatLng) => void;
  /** Cho phép kéo marker trạm thật (trang cấu hình trạm). */
  onMoveStation?: (id: string, position: LatLng) => void;
}

function ClickPicker({ enabled, onPick }: { enabled: boolean; onPick: (p: LatLng) => void }) {
  useMapEvents({ click: (e) => enabled && onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function FitRoute({ path }: { path: LatLngTuple[] | null }) {
  const map = useMap();
  useEffect(() => {
    if (path && path.length > 1) map.fitBounds(path, { padding: [40, 40] });
  }, [path, map]);
  return null;
}

function FitStations({ stations }: { stations: Station[] }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (fitted.current || stations.length === 0) return;
    map.fitBounds(stations.map((s): LatLngTuple => [s.latitude, s.longitude]), { padding: [40, 40], maxZoom: 15 });
    fitted.current = true;
  }, [stations, map]);
  return null;
}

export default function MapView(p: Props) {
  return (
    <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className={`map${p.pickMode ? ' picking' : ''}`}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={19} />
      <ClickPicker enabled={p.pickMode !== null} onPick={p.onPick} />
      <FitRoute path={p.routePath} />
      <FitStations stations={p.stations} />

      {p.zones && (
        <GeoJSON
          key={p.zonesKey}
          data={p.zones}
          style={{ color: '#8e1b16', weight: 2, dashArray: '6 4', fillColor: '#c8312b', fillOpacity: 0.28 }}
          onEachFeature={(f, layer) => layer.bindTooltip(String(f.properties?.name ?? 'Vùng cấm đi qua'))}
        />
      )}

      {p.routePath && (
        <Polyline
          positions={p.routePath}
          pathOptions={
            p.routeOutdated
              ? { color: '#8a949e', weight: 6, opacity: 0.8, dashArray: '10 8' }
              : { color: '#0b6b8a', weight: 6, opacity: 0.9 }
          }
        />
      )}

      {p.stations.map((s) => {
        const lv = displayLevel(s);
        const selected = s.id === p.selectedId;
        if (s.source === 'demo') {
          return <Marker key={s.id} position={[s.latitude, s.longitude]}
            icon={divIcon({ className: 'demo-map-marker', html: `<span style="background:${LEVEL_INFO[lv].color}">D</span>`, iconSize: [24, 24], iconAnchor: [12, 12] })}
            draggable={!!p.onMoveDemo}
            eventHandlers={{ click: () => p.onSelectStation(s.id), dragend: (event) => {
              const location = (event.target as LeafletMarker).getLatLng();
              p.onMoveDemo?.(s.id, { lat: location.lat, lng: location.lng });
            } }}>
            <Tooltip><strong>{s.name}</strong><br />MÔ PHỎNG · {LEVEL_INFO[lv].label} · {s.water_depth_cm} cm</Tooltip>
          </Marker>;
        }
        const tooltip = <>
          <strong>{s.name}</strong> · Thực tế
          <br />
          {LEVEL_INFO[lv].label}
          {s.water_depth_cm != null && s.data_quality !== 'missing' ? `, ${s.water_depth_cm} cm` : ''}
          <br />
          {QUALITY_LABEL[s.data_quality]} · {formatTime(s.measured_at ?? s.received_at)}
        </>;
        const style = {
          fillColor: LEVEL_INFO[lv].color,
          fillOpacity: s.data_quality === 'fresh' ? 0.95 : 0.55,
          color: selected ? '#12263a' : '#ffffff',
          weight: selected ? 3 : 2,
          // Dữ liệu cũ/mất: viền đứt nét để phân biệt với mức ngập
          dashArray: s.data_quality === 'fresh' ? undefined : '3 3',
        };
        // Leaflet chỉ cho kéo Marker, không kéo được CircleMarker.
        if (p.onMoveStation) {
          return <Marker key={s.id} position={[s.latitude, s.longitude]} draggable
            icon={divIcon({ className: 'demo-map-marker', html: `<span style="background:${LEVEL_INFO[lv].color}">T</span>`, iconSize: [24, 24], iconAnchor: [12, 12] })}
            eventHandlers={{ click: () => p.onSelectStation(s.id), dragend: (event) => {
              const location = (event.target as LeafletMarker).getLatLng();
              p.onMoveStation?.(s.id, { lat: location.lat, lng: location.lng });
            } }}>
            <Tooltip>{tooltip}</Tooltip>
          </Marker>;
        }
        return (
          <CircleMarker
            key={s.id}
            center={[s.latitude, s.longitude]}
            radius={selected ? 12 : 9}
            eventHandlers={{ click: () => p.onSelectStation(s.id) }}
            pathOptions={style}
          >
            <Tooltip>{tooltip}</Tooltip>
          </CircleMarker>
        );
      })}

      {p.origin && (
        <CircleMarker center={[p.origin.lat, p.origin.lng]} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#0b6b8a', fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Điểm đi</Tooltip>
        </CircleMarker>
      )}
      {p.destination && (
        <CircleMarker center={[p.destination.lat, p.destination.lng]} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#12263a', fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Điểm đến</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
