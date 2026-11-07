import { useEffect } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import type { LatLngTuple } from 'leaflet';
import type { FeatureCollection } from 'geojson';
import { MAP_CENTER, MAP_ZOOM, TILE_ATTRIBUTION, TILE_URL } from '../config';
import type { LatLng, Station } from '../types';
import { formatTime } from '../utils/format';
import { LEVEL_INFO, QUALITY_LABEL, displayLevel } from '../utils/status';

export type PickMode = 'origin' | 'destination' | null;

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

export default function MapView(p: Props) {
  return (
    <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className={`map${p.pickMode ? ' picking' : ''}`}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={19} />
      <ClickPicker enabled={p.pickMode !== null} onPick={p.onPick} />
      <FitRoute path={p.routePath} />

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
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lng]}
            radius={selected ? 12 : 9}
            eventHandlers={{ click: () => p.onSelectStation(s.id) }}
            pathOptions={{
              fillColor: LEVEL_INFO[lv].color,
              fillOpacity: s.dataQuality === 'ok' ? 0.95 : 0.55,
              color: selected ? '#12263a' : '#ffffff',
              weight: selected ? 3 : 2,
              // Dữ liệu cũ/mất: viền đứt nét để phân biệt với mức ngập
              dashArray: s.dataQuality === 'ok' ? undefined : '3 3',
            }}
          >
            <Tooltip>
              <strong>{s.name}</strong>
              <br />
              {LEVEL_INFO[lv].label}
              {s.depthCm != null && s.dataQuality !== 'missing' ? `, ${s.depthCm} cm` : ''}
              <br />
              {QUALITY_LABEL[s.dataQuality]} · {formatTime(s.updatedAt)}
            </Tooltip>
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
