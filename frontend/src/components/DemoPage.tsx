import { useEffect, useState, type FormEvent } from 'react';
import { createDemoPoint, deleteDemoPoint, listDemoPoints, updateDemoPoint } from '../api/demoApi';
import { useFloodZones } from '../hooks/useFloodZones';
import type { DemoPoint, DemoPointInput, LatLng } from '../types';
import MapView from './MapView';

const fields = [
  ['latitude', 'Vĩ độ', -89.999999, 89.999999],
  ['longitude', 'Kinh độ', -180, 180],
  ['water_depth_cm', 'Độ ngập (cm)', 0, 10000],
  ['warning_threshold_cm', 'Ngưỡng vàng (cm)', 0, 10000],
  ['danger_threshold_cm', 'Ngưỡng đỏ (cm)', 0.001, 10000],
  ['exclusion_radius_m', 'Bán kính vùng cấm (m)', 0.001, 1000],
] as const;
type NumericField = typeof fields[number][0];
type Draft = { name: string; is_active: boolean } & Record<NumericField, string>;

const blank = (): Draft => ({ name: 'Điểm demo', latitude: '20.9826', longitude: '105.7704',
  water_depth_cm: '0', warning_threshold_cm: '10', danger_threshold_cm: '20', exclusion_radius_m: '40', is_active: true });
function toDraft(point: DemoPoint): Draft {
  const draft = blank();
  draft.name = point.name;
  draft.is_active = point.is_active;
  for (const [key] of fields) draft[key] = String(point[key]);
  return draft;
}

export default function DemoPage() {
  const [points, setPoints] = useState<DemoPoint[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const flood = useFloodZones({ source: 'demo', include_real: false }, revision);

  useEffect(() => {
    const ctrl = new AbortController();
    listDemoPoints(ctrl.signal).then(setPoints).catch((e) => {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Không tải được điểm demo.');
    });
    return () => ctrl.abort();
  }, []);

  const choose = (id: string) => {
    const point = points.find((p) => p.id === id);
    if (!point || busy) return;
    setSelected(id); setDraft(toDraft(point)); setNotice(null); setPicking(false);
  };
  const reset = () => { setSelected(null); setDraft(blank()); setPicking(false); setNotice(null); setError(null); };
  const pick = (position: LatLng) => {
    setDraft((d) => ({ ...d, latitude: String(position.lat), longitude: String(position.lng) }));
    setPicking(false);
    setNotice('Đã chọn vị trí. Bấm Lưu để áp dụng.');
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const numeric = Object.fromEntries(fields.map(([key]) => [key, Number(draft[key])])) as Record<NumericField, number>;
    if (Object.values(numeric).some((v) => !Number.isFinite(v)) || numeric.danger_threshold_cm <= numeric.warning_threshold_cm) {
      setError('Nhập số hợp lệ; ngưỡng đỏ phải lớn hơn ngưỡng vàng.'); return;
    }
    const body: DemoPointInput = { name: draft.name, is_active: draft.is_active, ...numeric };
    setBusy(true); setError(null); setNotice(null);
    try {
      const point = selected ? await updateDemoPoint(selected, body) : await createDemoPoint(body);
      setSelected(point.id); setDraft(toDraft(point));
      setPoints(await listDemoPoints()); setRevision((v) => v + 1);
      setNotice('Đã lưu điểm demo. Điểm đang bật sẽ tham gia định tuyến ở chế độ Demo.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không lưu được điểm demo.'); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!selected || !window.confirm('Xóa điểm demo đang chọn?')) return;
    setBusy(true); setError(null);
    try {
      await deleteDemoPoint(selected);
      reset(); setPoints(await listDemoPoints()); setRevision((v) => v + 1); setNotice('Đã xóa điểm demo.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không xóa được điểm demo.'); }
    finally { setBusy(false); }
  };

  const move = async (id: string, position: LatLng) => {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const point = await updateDemoPoint(id, { latitude: position.lat, longitude: position.lng });
      setSelected(id); setDraft(toDraft(point)); setPoints(await listDemoPoints());
      setNotice('Đã lưu vị trí mới từ thao tác kéo marker.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không đổi được vị trí.'); }
    finally { setRevision((v) => v + 1); setBusy(false); }
  };

  return <div className="app">
    <aside className="sidebar">
      <header><h1>Quản lý điểm demo</h1><a href="/">← Bản đồ và tìm đường</a></header>
      <div className="banner banner-warn">DỮ LIỆU MÔ PHỎNG — tách biệt dữ liệu cảm biến thật. Điểm đang bật luôn hợp lệ và không tự quá hạn.</div>
      {(error || flood.error) && <div className="banner banner-err" role="alert">{error || flood.error}</div>}
      {notice && <div className="banner banner-info" role="status">{notice}</div>}
      <form className="panel demo-form" onSubmit={save}>
        <h2>{selected ? 'Chỉnh sửa điểm' : 'Tạo điểm mới'}</h2>
        <fieldset disabled={busy}>
          <label>Tên điểm<input required maxLength={150} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
          <button className="btn" type="button" onClick={() => setPicking(!picking)}>{picking ? 'Hủy chọn vị trí' : 'Chọn vị trí trên bản đồ'}</button>
          {fields.map(([key, label, min, max]) => <label key={key}>{label}
            <input type="number" required step="any" min={min} max={max} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
          </label>)}
          <label><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Bật điểm này trong demo</label>
          <div className="actions">
            <button className="btn primary" type="submit">{busy ? 'Đang lưu…' : 'Lưu điểm'}</button>
            <button className="btn" type="button" onClick={reset}>Tạo mới</button>
            {selected && <button className="btn" type="button" onClick={remove}>Xóa điểm</button>}
          </div>
        </fieldset>
      </form>
      <section className="panel"><h2>Các điểm đã tạo ({points.length})</h2>
        <p className="sub">Bấm điểm để sửa. Kéo marker D để lưu vị trí mới. Điểm tắt không xuất hiện trên bản đồ.</p>
        <ul className="stations">{points.map((point) => <li key={point.id}>
          <button disabled={busy} className={`station${selected === point.id ? ' selected' : ''}`} onClick={() => choose(point.id)}>
            {point.name} · {point.water_depth_cm} cm · {point.is_active ? 'Bật' : 'Tắt'}
          </button>
        </li>)}</ul>
      </section>
    </aside>
    <main className="map-wrap">
      <MapView stations={flood.data?.stations ?? []} zones={flood.data?.flood_zones ?? null}
        zonesKey={flood.version ?? 'none'} origin={null} destination={null} routePath={null} routeOutdated={false}
        pickMode={picking && !busy ? 'demo' : null} selectedId={selected} onPick={pick} onSelectStation={choose}
        onMoveDemo={busy ? undefined : move} />
      {picking && <div className="pick-hint" role="status">Bấm bản đồ để điền tọa độ, rồi bấm Lưu điểm.</div>}
    </main>
  </div>;
}
