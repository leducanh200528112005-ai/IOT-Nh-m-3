import { useMemo, useState } from 'react';
import Legend from './components/Legend';
import MapView, { type PickMode } from './components/MapView';
import RoutePanel from './components/RoutePanel';
import StationList from './components/StationList';
import StatusBanner from './components/StatusBanner';
import { useFloodZones } from './hooks/useFloodZones';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { useSafeRoute } from './hooks/useSafeRoute';
import type { LatLng } from './types';
import { lineToLatLngs } from './utils/geo';

export default function App() {
  const flood = useFloodZones();
  const online = useOnlineStatus();
  const route = useSafeRoute();

  const [origin, setOrigin] = useState<LatLng | null>(null);
  const [destination, setDestination] = useState<LatLng | null>(null);
  const [pickMode, setPickMode] = useState<PickMode>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const routeFeature = route.state.status === 'ok' ? route.state.result?.route : undefined;
  const routePath = useMemo(() => (routeFeature ? lineToLatLngs(routeFeature) : null), [routeFeature]);

  // Cảnh báo tuyến lỗi thời; KHÔNG tự gọi lại backend mỗi lần poll.
  let outdatedReason: string | null = null;
  if (route.state.status === 'ok') {
    if (flood.version !== route.state.floodVersion) outdatedReason = 'dữ liệu vùng ngập đã thay đổi kể từ lúc tính.';
    else if (!online || flood.noRecentPoll || flood.expired) outdatedReason = 'dữ liệu vùng ngập hiện không còn được cập nhật.';
  }

  const handlePick = (p: LatLng) => {
    if (pickMode === 'origin') setOrigin(p);
    if (pickMode === 'destination') setDestination(p);
    setPickMode(null);
  };

  const compute = () => {
    if (origin && destination) route.request(origin, destination, flood.version);
  };

  const clearAll = () => {
    setOrigin(null);
    setDestination(null);
    setPickMode(null);
    route.clear();
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Bản đồ ngập</h1>
        </header>
        <StatusBanner
          online={online}
          loading={flood.loading}
          hasData={!!flood.data}
          error={flood.error}
          noRecentPoll={flood.noRecentPoll}
          expired={flood.expired}
          dataUpdatedAt={flood.data?.updatedAt}
        />
        <RoutePanel
          origin={origin}
          destination={destination}
          pickMode={pickMode}
          onPickMode={setPickMode}
          onSwap={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
          onCompute={compute}
          onClear={clearAll}
          state={route.state}
          online={online}
          outdatedReason={outdatedReason}
        />
        <StationList stations={flood.data?.stations ?? []} selectedId={selectedId} onSelect={setSelectedId} />
        <Legend />
      </aside>
      <main className="map-wrap">
        <MapView
          stations={flood.data?.stations ?? []}
          zones={flood.data?.restrictedZones ?? null}
          zonesKey={flood.version ?? 'none'}
          origin={origin}
          destination={destination}
          routePath={routePath}
          routeOutdated={outdatedReason !== null}
          pickMode={pickMode}
          selectedId={selectedId}
          onPick={handlePick}
          onSelectStation={setSelectedId}
        />
        {pickMode && (
          <div className="pick-hint" role="status">
            Bấm lên bản đồ để chọn {pickMode === 'origin' ? 'điểm đi' : 'điểm đến'}
          </div>
        )}
      </main>
    </div>
  );
}
