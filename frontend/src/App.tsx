import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useSearchParams } from 'react-router-dom';
import AdminPage from './components/AdminPage';
import FloodHistoryModal from './components/FloodHistoryModal';
import Legend from './components/Legend';
import MapView, { type PickMode } from './components/MapView';
import RoutePanel from './components/RoutePanel';
import StationList from './components/StationList';
import StationsPage from './components/StationsPage';
import StatusBanner from './components/StatusBanner';
import DemoPage from './components/demo/DemoPage';
import ForecastPage from './components/ForecastPage';
import { useFloodZones } from './hooks/useFloodZones';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { loadCachedRoute, useSafeRoute } from './hooks/useSafeRoute';
import { useTheme } from './hooks/useTheme';
import { useI18n } from './i18n';
import type { LatLng, RouteHistoryItem, SourceSelection, Station, VehicleType } from './types';
import { lineToLatLngs } from './utils/geo';

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; message: string }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, message: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="admin-page">
          <div className="banner banner-err">
            <h2>Đã xảy ra lỗi giao diện</h2>
            <p>{this.state.message}</p>
            <button type="button" className="btn primary" onClick={() => window.location.reload()}>Tải lại trang</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function parseCoordParam(raw: string | null): LatLng | null {
  if (!raw) return null;
  const parts = raw.split(',').map(Number);
  if (parts.length !== 2 || parts.some((n) => !Number.isFinite(n))) return null;
  const [lat, lng] = parts;
  if (lat <= -90 || lat >= 90 || lng < -180 || lng > 180) return null;
  return { lat, lng };
}

function parseVehicleParam(raw: string | null): VehicleType {
  if (raw === 'car' || raw === 'motorcycle' || raw === 'pedestrian') return raw;
  return 'motorcycle';
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardShell />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/stations" element={<StationsPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

function DashboardShell() {
  const [searchParams] = useSearchParams();
  const initialSource = searchParams.get('src') === 'real' ? 'real' : 'demo';
  const initialReal = initialSource === 'demo' && searchParams.get('real') === '1';

  const [selection, setSelection] = useState<SourceSelection>({
    source: initialSource,
    include_real: initialReal,
  });

  return (
    <Dashboard
      key={`${selection.source}:${selection.include_real}`}
      selection={selection}
      onSelection={setSelection}
    />
  );
}

function Dashboard({
  selection,
  onSelection,
}: {
  selection: SourceSelection;
  onSelection: (value: SourceSelection) => void;
}) {
  const { lang, toggleLang, t } = useI18n();
  const { theme, cycleTheme } = useTheme();
  const [searchParams] = useSearchParams();

  const sharedOrigin = parseCoordParam(searchParams.get('from'));
  const sharedDest = parseCoordParam(searchParams.get('to'));
  const hasSharedRoute = Boolean(sharedOrigin && sharedDest);
  const cached = !hasSharedRoute ? loadCachedRoute(selection) : null;

  const flood = useFloodZones(selection);
  const online = useOnlineStatus();
  const route = useSafeRoute(cached?.state);

  const [origin, setOrigin] = useState<LatLng | null>(sharedOrigin ?? cached?.origin ?? null);
  const [destination, setDestination] = useState<LatLng | null>(sharedDest ?? cached?.destination ?? null);
  const [originLabel, setOriginLabel] = useState<string | undefined>(undefined);
  const [destinationLabel, setDestinationLabel] = useState<string | undefined>(undefined);
  const [vehicle, setVehicle] = useState<VehicleType>(
    hasSharedRoute ? parseVehicleParam(searchParams.get('v')) : cached?.vehicle ?? 'motorcycle',
  );
  const [pickMode, setPickMode] = useState<PickMode>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chartTarget, setChartTarget] = useState<{ id: string; source: 'real' | 'demo' } | null>(null);

  // Realtime toast alert whenever a sensor newly enters danger or predicted_danger.
  const prevDangerIds = useRef<Set<string> | null>(null);
  const [alertToast, setAlertToast] = useState<string | null>(null);
  const sharedAutoRan = useRef(false);

  useEffect(() => {
    const stations = flood.data?.stations;
    if (!stations) return;
    const currentDanger = stations.filter((s) => s.hazard_state === 'danger' || s.hazard_state === 'predicted_danger');
    const currentSet = new Set(currentDanger.map((s) => s.id));
    if (prevDangerIds.current !== null) {
      const newlyTriggered = currentDanger.filter((s) => !prevDangerIds.current!.has(s.id));
      if (newlyTriggered.length > 0) {
        const names = newlyTriggered.map((s) => s.name).slice(0, 2).join(', ');
        setAlertToast(`${names}${newlyTriggered.length > 2 ? ` (+${newlyTriggered.length - 2})` : ''}`);
      }
    }
    prevDangerIds.current = currentSet;
  }, [flood.data?.stations]);

  useEffect(() => {
    if (hasSharedRoute && !sharedAutoRan.current && flood.version && origin && destination) {
      sharedAutoRan.current = true;
      route.request(origin, destination, flood.version, selection, vehicle, lang);
    }
  }, [hasSharedRoute, flood.version, origin, destination, selection, vehicle, lang, route]);

  const routeFeature = route.state.status === 'ok' ? route.state.result?.route : undefined;
  const routePath = useMemo(() => (routeFeature ? lineToLatLngs(routeFeature) : null), [routeFeature]);

  // Cảnh báo tuyến lỗi thời; KHÔNG tự gọi lại backend mỗi lần poll.
  let outdatedReason: string | null = null;
  if (route.state.status === 'ok') {
    if (flood.version !== route.state.floodVersion) outdatedReason = 'dữ liệu vùng ngập đã thay đổi kể từ lúc tính.';
    else if (!online || flood.noRecentPoll || flood.expired || !flood.data?.routing_data_sufficient) {
      outdatedReason = 'dữ liệu vùng ngập hiện không còn đủ mới và hợp lệ.';
    }
  }

  const handlePick = (p: LatLng) => {
    if (pickMode === 'origin') {
      setOrigin(p);
      setOriginLabel(undefined);
    }
    if (pickMode === 'destination') {
      setDestination(p);
      setDestinationLabel(undefined);
    }
    setPickMode(null);
  };

  const compute = (v: VehicleType = vehicle, nextOrigin = origin, nextDest = destination) => {
    if (nextOrigin && nextDest) {
      route.request(nextOrigin, nextDest, flood.version, selection, v, lang, { originLabel, destinationLabel });
    }
  };

  const clearAll = () => {
    setOrigin(null);
    setDestination(null);
    setOriginLabel(undefined);
    setDestinationLabel(undefined);
    setPickMode(null);
    route.clear();
  };

  const handleHistorySelect = (item: RouteHistoryItem) => {
    setOrigin(item.origin);
    setDestination(item.destination);
    setOriginLabel(item.originLabel);
    setDestinationLabel(item.destinationLabel);
    setVehicle(item.vehicle);
    route.request(item.origin, item.destination, flood.version, selection, item.vehicle, lang, {
      originLabel: item.originLabel,
      destinationLabel: item.destinationLabel,
    });
  };

  const themeIcon = theme === 'dark' ? '🌙' : theme === 'light' ? '☀️' : '🌓';
  const themeLabel = theme === 'dark' ? t('themeDark') : theme === 'light' ? t('themeLight') : t('themeAuto');

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <div className="header-top">
            <h1>{t('appTitle')}</h1>
            <div className="header-tools">
              <button type="button" className="tool-pill" onClick={toggleLang} title="Chuyển ngôn ngữ VI / EN">
                🌐 {lang.toUpperCase()}
              </button>
              <button type="button" className="tool-pill" onClick={cycleTheme} title={themeLabel} aria-label={themeLabel}>
                {themeIcon}
              </button>
            </div>
          </div>
          <nav className="nav-links">
            <Link to="/demo" style={{ fontWeight: 600 }}>{t('navDemo')} →</Link>
            <Link to="/stations">{t('navStations')}</Link>
            <Link to="/forecast">Dự báo NYC (Thử nghiệm)</Link>
            <Link to="/admin">{t('navAdmin')}</Link>
          </nav>
        </header>
        <section className="panel">
          <label>
            {t('dataSource')}{' '}
            <select
              value={selection.source}
              onChange={(e) => onSelection({ source: e.target.value as 'real' | 'demo', include_real: false })}
            >
              <option value="real">{t('sourceReal')}</option>
              <option value="demo">{t('sourceDemo')}</option>
            </select>
          </label>
          {selection.source === 'demo' && (
            <>
              <p className="msg warn">{selection.include_real ? t('simulatedWithReal') : t('simulatedBanner')}</p>
              <label>
                <input
                  type="checkbox"
                  checked={selection.include_real}
                  onChange={(e) => onSelection({ source: 'demo', include_real: e.target.checked })}
                />{' '}
                {t('includeReal')}
              </label>
            </>
          )}
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
          vehicle={vehicle}
          selection={selection}
          zones={flood.data?.flood_zones ?? null}
          onVehicleChange={(v) => {
            setVehicle(v);
            if (origin && destination) compute(v);
          }}
          onSetOrigin={(pos, label) => {
            setOrigin(pos);
            setOriginLabel(label);
          }}
          onSetDestination={(pos, label) => {
            setDestination(pos);
            setDestinationLabel(label);
          }}
          pickMode={pickMode}
          onPickMode={setPickMode}
          onSwap={() => {
            const nextOrig = destination;
            const nextDest = origin;
            const nextOLabel = destinationLabel;
            const nextDLabel = originLabel;
            setOrigin(nextOrig);
            setDestination(nextDest);
            setOriginLabel(nextOLabel);
            setDestinationLabel(nextDLabel);
            if (nextOrig && nextDest && route.state.status !== 'idle') {
              route.request(nextOrig, nextDest, flood.version, selection, vehicle, lang, {
                originLabel: nextOLabel,
                destinationLabel: nextDLabel,
              });
            }
          }}
          onCompute={() => compute()}
          onClear={clearAll}
          onSelectHistory={handleHistorySelect}
          onClearHistory={route.clearHistory}
          history={route.history}
          state={route.state}
          online={online}
          outdatedReason={outdatedReason}
        />

        <StationList
          stations={flood.data?.stations ?? []}
          loading={flood.loading}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onOpenChart={(s: Station) => setChartTarget({ id: s.id, source: s.source === 'demo' ? 'demo' : 'real' })}
        />

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
        {alertToast && (
          <div className="alert-toast" role="alert">
            <div>
              <strong>{t('alertToastTitle')}</strong>
              <div>{alertToast}</div>
            </div>
            <button type="button" className="icon-btn" onClick={() => setAlertToast(null)} aria-label={t('dismiss')}>✕</button>
          </div>
        )}
      </main>

      {chartTarget && (
        <FloodHistoryModal
          pointId={chartTarget.id}
          source={chartTarget.source}
          onClose={() => setChartTarget(null)}
        />
      )}
    </div>
  );
}
