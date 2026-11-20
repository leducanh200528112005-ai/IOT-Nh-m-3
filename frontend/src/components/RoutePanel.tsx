import { useState } from 'react';
import type { FeatureCollection } from 'geojson';
import type { RouteState } from '../hooks/useSafeRoute';
import { useI18n } from '../i18n';
import type { LatLng, RouteHistoryItem, RouteOption, SourceSelection, VehicleType } from '../types';
import { formatCoord, formatDistance, formatDuration, formatTime } from '../utils/format';
import AddressSearch from './AddressSearch';
import type { PickMode } from './MapView';

interface Props {
  origin: LatLng | null;
  destination: LatLng | null;
  vehicle: VehicleType;
  selection: SourceSelection;
  zones: FeatureCollection | null;
  onVehicleChange: (v: VehicleType) => void;
  onSetOrigin: (pos: LatLng, label?: string) => void;
  onSetDestination: (pos: LatLng, label?: string) => void;
  pickMode: PickMode;
  onPickMode: (m: PickMode) => void;
  onSwap: () => void;
  onCompute: () => void;
  onClear: () => void;
  onSelectHistory: (item: RouteHistoryItem) => void;
  onClearHistory: () => void;
  history: RouteHistoryItem[];
  state: RouteState;
  routes?: RouteOption[];
  selectedRouteIndex?: number;
  onSelectRoute?: (index: number) => void;
  online: boolean;
  outdatedReason: string | null;
}

export default function RoutePanel(p: Props) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const [showSteps, setShowSteps] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const loading = p.state.status === 'loading';
  const canCompute = !!p.origin && !!p.destination && !loading && p.online;
  const r = p.state.result;
  const selectedIdx = p.selectedRouteIndex ?? 0;
  const activeRoute = (p.routes && p.routes[selectedIdx]) || r;
  const activeDistance = activeRoute?.distance_m ?? r?.distance_m;
  const activeDuration = activeRoute?.duration_s ?? r?.duration_s;
  const activeSteps = activeRoute?.steps ?? r?.steps;
  const activeRouteGeom = activeRoute?.route ?? r?.route;

  const shareRoute = async () => {
    if (!p.origin || !p.destination) return;
    const params = new URLSearchParams({
      from: `${p.origin.lat.toFixed(6)},${p.origin.lng.toFixed(6)}`,
      to: `${p.destination.lat.toFixed(6)},${p.destination.lng.toFixed(6)}`,
      v: p.vehicle,
      src: p.selection.source,
      real: p.selection.include_real ? '1' : '0',
    });
    const url = `${window.location.origin}/?${params.toString()}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      window.prompt('Sao chép đường dẫn chia sẻ:', url);
    }
  };

  const exportGeoJson = () => {
    if (!r || !activeRouteGeom) return;
    const features = [
      {
        ...activeRouteGeom,
        properties: {
          ...activeRouteGeom.properties,
          kind: 'safe_route',
          vehicle: p.vehicle,
          engine: r.engine ?? 'valhalla',
          distance_m: activeDistance,
          duration_s: activeDuration,
          calculated_at: r.calculated_at,
        },
      },
      ...(p.zones?.features ?? []),
    ];
    const collection: FeatureCollection = { type: 'FeatureCollection', features };
    const blob = new Blob([JSON.stringify(collection, null, 2)], { type: 'application/geo+json' });
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = `safe-route-${p.vehicle}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.geojson`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  };

  const vehicles: { id: VehicleType; label: string }[] = [
    { id: 'car', label: t('car') },
    { id: 'motorcycle', label: t('motorcycle') },
    { id: 'pedestrian', label: t('pedestrian') },
  ];

  return (
    <section className="panel" aria-label={t('routeTitle')}>
      <h2>{t('routeTitle')}</h2>

      <div className="vehicle-selector" role="group" aria-label="Chọn phương tiện">
        {vehicles.map((v) => (
          <button
            key={v.id}
            type="button"
            className={`vehicle-btn${p.vehicle === v.id ? ' active' : ''}`}
            onClick={() => p.onVehicleChange(v.id)}
            disabled={loading}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div className="addr-group">
        <AddressSearch placeholder="🔍 Tìm điểm đi…" onSelect={p.onSetOrigin} />
        <div className="pick-row">
          <button
            type="button"
            className={p.pickMode === 'origin' ? 'btn pick active' : 'btn pick'}
            onClick={() => p.onPickMode(p.pickMode === 'origin' ? null : 'origin')}
          >
            {p.pickMode === 'origin' ? t('pickingHint') : t('pickOrigin')}
          </button>
          <span className="coord">{p.origin ? formatCoord(p.origin) : t('notChosen')}</span>
        </div>
      </div>

      <div className="addr-group">
        <AddressSearch placeholder="🔍 Tìm điểm đến…" onSelect={p.onSetDestination} />
        <div className="pick-row">
          <button
            type="button"
            className={p.pickMode === 'destination' ? 'btn pick active' : 'btn pick'}
            onClick={() => p.onPickMode(p.pickMode === 'destination' ? null : 'destination')}
          >
            {p.pickMode === 'destination' ? t('pickingHint') : t('pickDest')}
          </button>
          <span className="coord">{p.destination ? formatCoord(p.destination) : t('notChosen')}</span>
        </div>
      </div>

      <div className="actions">
        <button type="button" className="btn primary" disabled={!canCompute} onClick={p.onCompute}>
          {loading ? t('findingRoute') : p.state.status === 'ok' ? t('recompute') : t('findRoute')}
        </button>
        <button type="button" className="btn" onClick={p.onSwap} disabled={!p.origin || !p.destination || loading}>{t('swap')}</button>
        <button type="button" className="btn" onClick={p.onClear} disabled={!p.origin && !p.destination && p.state.status === 'idle'}>{t('clear')}</button>
      </div>

      {!p.online && <p className="msg err">{t('offlineMsg')}</p>}

      {loading && (
        <div className="msg info" role="status">
          <div>{t('sendingMsg')}</div>
          <div className="skeleton" style={{ height: 14, marginTop: 8 }} />
          <div className="skeleton" style={{ height: 14, width: '72%', marginTop: 6 }} />
        </div>
      )}

      {p.state.status === 'error' && (
        <p className="msg err" role="alert">
          Không tìm được đường: {p.state.error}. Bạn có thể bấm “Tìm đường” để thử lại.
        </p>
      )}

      {p.state.status === 'no_route' && (
        <p className="msg warn" role="alert">
          {p.state.message || 'Không có tuyến phù hợp giữa hai điểm này với tình hình ngập hiện tại.'} Hãy thử đổi điểm đi/đến hoặc phương tiện khác.
        </p>
      )}

      {p.state.status === 'ok' && r && (
        <div className="result">
          {p.outdatedReason && (
            <p className="msg warn" role="alert">
              Tuyến này có thể đã lỗi thời: {p.outdatedReason} Hãy bấm “Tính lại tuyến”.
            </p>
          )}

          {p.routes && p.routes.length > 1 && (
            <div className="route-cards-list" role="radiogroup" aria-label="Tùy chọn tuyến đường">
              <div className="route-cards-title">
                {p.routes.length} phương án di chuyển (Bấm để chọn):
              </div>
              <div className="route-cards-grid">
                {p.routes.map((rt, idx) => {
                  const isSelected = idx === selectedIdx;
                  const diffDist = rt.distance_m - p.routes![0].distance_m;
                  const diffDur = rt.duration_s - p.routes![0].duration_s;
                  return (
                    <button
                      key={rt.id}
                      type="button"
                      className={`route-card-item ${isSelected ? 'active' : ''}`}
                      onClick={() => p.onSelectRoute?.(idx)}
                      role="radio"
                      aria-checked={isSelected}
                    >
                      <div className="route-card-top">
                        <span className={`route-card-badge ${idx === 0 ? 'badge-primary' : 'badge-alt'}`}>
                          {idx === 0 ? 'Tuyến 1 (Tối ưu)' : `Tuyến ${idx + 1}`}
                        </span>
                        <strong className="route-card-time">{formatDuration(rt.duration_s)}</strong>
                      </div>
                      <div className="route-card-bottom">
                        <span className="route-card-dist">{formatDistance(rt.distance_m)}</span>
                        {idx > 0 && (
                          <span className="route-card-diff">
                            {diffDur === 0 ? 'Cùng thời gian' : diffDur > 0 ? `+${formatDuration(diffDur)}` : formatDuration(diffDur)}
                            {diffDist !== 0 ? ` (${diffDist > 0 ? '+' : ''}${formatDistance(diffDist)})` : ''}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <dl>
            <div><dt>{t('distance')}</dt><dd>{formatDistance(activeDistance)}</dd></div>
            <div><dt>{t('duration')}</dt><dd>{formatDuration(activeDuration)}</dd></div>
          </dl>
          <p className="sub">
            {t('calculatedAt')} {formatTime(r.calculated_at)}
            {r.engine ? ` · ${r.engine.toUpperCase()}` : ''}
          </p>

          <div className="actions" style={{ marginTop: 8 }}>
            <button type="button" className="btn btn-sm" onClick={shareRoute}>
              {copied ? t('copiedLink') : t('shareLink')}
            </button>
            <button type="button" className="btn btn-sm" onClick={exportGeoJson}>
              {t('exportGeoJson')}
            </button>
          </div>

          {activeSteps && activeSteps.length > 0 && (
            <div className="collapsible-block">
              <button type="button" className="collapse-toggle" onClick={() => setShowSteps(!showSteps)}>
                <span>{t('stepsTitle')} ({activeSteps.length})</span>
                <span>{showSteps ? '▲' : '▼'}</span>
              </button>
              {showSteps && (
                <ol className="turn-steps">
                  {activeSteps.map((st, idx) => (
                    <li key={`${idx}-${st.type}`}>
                      <span className="step-instr">{st.instruction}</span>
                      <span className="step-meta">{formatDistance(st.distance_m)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}

          {r.warnings.map((warning, idx) => (
            <p className="msg warn" key={`${idx}-${warning}`}>{warning}</p>
          ))}
        </div>
      )}

      {p.history.length > 0 && (
        <div className="collapsible-block">
          <button type="button" className="collapse-toggle" onClick={() => setShowHistory(!showHistory)}>
            <span>{t('historyTitle')} ({p.history.length})</span>
            <span>{showHistory ? '▲' : '▼'}</span>
          </button>
          {showHistory && (
            <div className="history-list">
              {p.history.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="history-item"
                  disabled={loading}
                  onClick={() => p.onSelectHistory(item)}
                >
                  <strong>
                    {item.vehicle === 'motorcycle' ? '🛵' : item.vehicle === 'pedestrian' ? '🚶' : '🚗'}{' '}
                    {item.originLabel || formatCoord(item.origin)} → {item.destinationLabel || formatCoord(item.destination)}
                  </strong>
                  <span>{formatDistance(item.distance_m)} · {formatDuration(item.duration_s)}</span>
                </button>
              ))}
              <button type="button" className="btn btn-sm btn-outline" onClick={p.onClearHistory} style={{ width: '100%', marginTop: 4 }}>
                {t('clearHistory')}
              </button>
            </div>
          )}
        </div>
      )}

      <p className="disclaimer">
        Tuyến được đề xuất dựa trên dữ liệu cảm biến tại thời điểm tính, không phải bảo đảm về an toàn. Luôn quan sát thực tế và tuân thủ biển báo.
      </p>
    </section>
  );
}
