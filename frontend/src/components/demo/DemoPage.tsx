import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useFloodZones } from '../../hooks/useFloodZones';
import { useI18n } from '../../i18n';
import type { DemoPointInput, LatLng } from '../../types';
import FloodHistoryModal from '../FloodHistoryModal';
import MapView from '../MapView';
import DemoForm, { blankDraft, pointToDraft, type DemoDraft } from './DemoForm';
import DemoPointList from './DemoPointList';
import { MAX_DEMO_POINTS, useDemoPoints } from './useDemoPoints';

export default function DemoPage() {
  const { t } = useI18n();
  const demo = useDemoPoints();
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<DemoDraft>(() => blankDraft(1));
  const [picking, setPicking] = useState(false);
  const [chartId, setChartId] = useState<string | null>(null);
  const flood = useFloodZones({ source: 'demo', include_real: false }, demo.revision);

  const choose = (id: string) => {
    const point = demo.points.find((p) => p.id === id);
    if (!point || demo.busy) return;
    setSelected(id);
    setDraft(pointToDraft(point));
    demo.setNotice(null);
    setPicking(false);
  };

  const reset = () => {
    setSelected(null);
    setDraft(blankDraft(demo.points.length + 1));
    setPicking(true);
    demo.setNotice('📍 Đã bật chế độ chọn vị trí: hãy click chuột vào vị trí bất kỳ trên bản đồ để đặt điểm!');
    demo.setError(null);
  };

  const applyCoordinate = (position: LatLng, label?: string) => {
    const latStr = position.lat.toFixed(6);
    const lngStr = position.lng.toFixed(6);
    setDraft((d) => ({
      ...d,
      latitude: latStr,
      longitude: lngStr,
      name: label || (selected ? d.name : d.name.startsWith('Điểm ngập #') || !d.name ? `Điểm ngập #${demo.points.length + 1}` : d.name),
    }));
    setPicking(false);
    demo.setNotice(`Đã chọn tọa độ [${latStr}, ${lngStr}]. Bấm "Lưu" bên dưới để hoàn tất.`);
  };

  const handleSave = async (body: DemoPointInput) => {
    const saved = await demo.savePoint(selected, body);
    if (saved) {
      setSelected(saved.id);
      setDraft(pointToDraft(saved));
    }
  };

  const handleDelete = async (id: string, name: string) => {
    const removed = await demo.deleteOne(id, name);
    if (removed && selected === id) reset();
  };

  const handleClearAll = async () => {
    const cleared = await demo.clearAll();
    if (cleared) reset();
  };

  const handleMove = async (id: string, position: LatLng) => {
    const moved = await demo.movePoint(id, position);
    if (moved && selected === id) setDraft(pointToDraft(moved));
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>{t('navDemo')}</h1>
          <Link to="/">{t('navBack')}</Link>
        </header>

        <div className="point-limit-badge">
          <span>Số điểm ngập: <strong>{demo.points.length} / {MAX_DEMO_POINTS}</strong></span>
          {demo.points.length >= MAX_DEMO_POINTS && (
            <span className="badge-max">Đã đạt tối đa {MAX_DEMO_POINTS} điểm</span>
          )}
        </div>

        <div className="demo-top-actions">
          <button
            className={`btn pick ${picking ? 'active' : ''}`}
            type="button"
            disabled={demo.busy || (!selected && demo.points.length >= MAX_DEMO_POINTS)}
            onClick={() => setPicking(!picking)}
            title="Bấm vào nút này rồi click chuột lên bản đồ để chọn tọa độ"
          >
            {picking ? '❌ Hủy chọn' : '📍 Click bản đồ lấy tọa độ'}
          </button>
          <button className="btn" type="button" disabled={demo.busy} onClick={reset} title="Làm mới form để tạo điểm">
            ➕ Thêm mới
          </button>
          {demo.points.length > 0 && (
            <button className="btn btn-danger" type="button" disabled={demo.busy} onClick={handleClearAll} title="Xóa toàn bộ điểm ngập">
              🗑️ Xóa tất cả ({demo.points.length})
            </button>
          )}
        </div>

        {(demo.error || flood.error) && <div className="banner banner-err" role="alert">{demo.error || flood.error}</div>}
        {demo.notice && <div className="banner banner-info" role="status">{demo.notice}</div>}

        <DemoForm
          selectedId={selected}
          pointsCount={demo.points.length}
          draft={draft}
          busy={demo.busy}
          onDraftChange={setDraft}
          onSubmit={handleSave}
          onValidationError={demo.setError}
          onReset={reset}
          onDeleteSelected={() => selected && handleDelete(selected, draft.name)}
          onAddressPicked={(pos, label) => applyCoordinate(pos, label.split(',')[0])}
        />

        <DemoPointList
          points={demo.points}
          liveStations={flood.data?.stations ?? []}
          selectedId={selected}
          loading={demo.loadingList}
          busy={demo.busy}
          onSelect={choose}
          onQuickSet={demo.quickSet}
          onDelete={handleDelete}
          onOpenChart={setChartId}
        />
      </aside>

      <main className="map-wrap">
        <MapView
          stations={flood.data?.stations ?? []}
          zones={flood.data?.flood_zones ?? null}
          zonesKey={flood.version ?? 'none'}
          origin={null}
          destination={null}
          routePath={null}
          routeOutdated={false}
          pickMode={picking && !demo.busy ? 'demo' : null}
          selectedId={selected}
          onPick={(p) => applyCoordinate(p)}
          onSelectStation={choose}
          onMoveDemo={demo.busy ? undefined : handleMove}
        />
        {picking && (
          <div className="pick-hint" role="status">
            📍 Bấm vào vị trí bất kỳ trên bản đồ để lấy tọa độ, sau đó điền tên và bấm Lưu điểm!
          </div>
        )}
      </main>

      {chartId && <FloodHistoryModal pointId={chartId} source="demo" onClose={() => setChartId(null)} />}
    </div>
  );
}
