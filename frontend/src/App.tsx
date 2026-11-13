import { useMemo, useState } from 'react';
import Legend from './components/Legend';
import MapView, { type PickMode } from './components/MapView';
import RoutePanel from './components/RoutePanel';
import StationList from './components/StationList';
import StatusBanner from './components/StatusBanner';
import DemoPage from './components/DemoPage';
import StationsPage from './components/StationsPage';
import ForecastPage from './components/ForecastPage';
import { useFloodZones } from './hooks/useFloodZones';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { useSafeRoute } from './hooks/useSafeRoute';
import type { LatLng, SourceSelection } from './types';
import { lineToLatLngs } from './utils/geo';

export default function App() {
  const [selection, setSelection] = useState<SourceSelection>({ source: 'real', include_real: false });
  if (window.location.pathname === '/demo') return <DemoPage />;
  if (window.location.pathname === '/stations') return <StationsPage />;
  if (window.location.pathname === '/forecast') return <ForecastPage />;
  return <Dashboard key={`${selection.source}:${selection.include_real}`} selection={selection} onSelection={setSelection} />;
}

function Dashboard({ selection, onSelection }: { selection: SourceSelection; onSelection: (value: SourceSelection) => void }) {
  const flood = useFloodZones(selection);
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
    else if (!online || flood.noRecentPoll || flood.expired || !flood.data?.routing_data_sufficient) outdatedReason = 'dữ liệu vùng ngập hiện không còn đủ mới và hợp lệ.';
  }

  const handlePick = (p: LatLng) => {
    if (pickMode === 'origin') setOrigin(p);
    if (pickMode === 'destination') setDestination(p);
    setPickMode(null);
  };

  const compute = () => {
    if (origin && destination) route.request(origin, destination, flood.version, selection);
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
          <a href="/demo">Quản lý điểm demo →</a>
        </header>
        <nav className="panel sub-nav">
          <a href="/stations">Cấu hình trạm thật →</a>
          <br /><a href="/forecast">Dự báo độ sâu thử nghiệm →</a>
        </nav>
        <section className="panel">
          <label>Nguồn dữ liệu <select value={selection.source} onChange={(e) => onSelection({ source: e.target.value as 'real' | 'demo', include_real: false })}>
            <option value="real">Thực tế</option><option value="demo">Demo</option>
          </select></label>
          {selection.source === 'demo' && <>
            <p className="msg warn">DỮ LIỆU MÔ PHỎNG{selection.include_real ? ' KẾT HỢP TRẠM THỰC TẾ' : ''}</p>
            <label><input type="checkbox" checked={selection.include_real} onChange={(e) => onSelection({ source: 'demo', include_real: e.target.checked })} /> Bao gồm trạm thực tế</label>
          </>}
        </section>
        <StatusBanner
          online={online}
          loading={flood.loading}
          hasData={!!flood.data}
          error={flood.error}
          noRecentPoll={flood.noRecentPoll}
          expired={flood.expired}
          dataUpdatedAt={flood.data?.generated_at}
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
          zones={flood.data?.flood_zones ?? null}
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
