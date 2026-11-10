import { useEffect, useState, type FormEvent } from 'react';
import { createStation, deleteStation, listStations, updateStation } from '../api/stationsApi';
import { useFloodZones } from '../hooks/useFloodZones';
import type { LatLng, StationConfig } from '../types';
import { QUALITY_LABEL } from '../utils/status';
import MapView from './MapView';

const fields = [
  ['latitude', 'Vĩ độ', -89.999999, 89.999999],
  ['longitude', 'Kinh độ', -180, 180],
  ['warning_threshold_cm', 'Ngưỡng vàng (cm)', 0, 10000],
  ['danger_threshold_cm', 'Ngưỡng đỏ (cm)', 0.001, 10000],
  ['exclusion_radius_m', 'Bán kính vùng cấm (m)', 0.001, 1000],
] as const;
type NumericField = typeof fields[number][0];
type Draft = { id: string; name: string; is_active: boolean } & Record<NumericField, string>;

const blank = (): Draft => ({ id: '', name: 'Trạm mới', latitude: '10.7701', longitude: '106.7001',
  warning_threshold_cm: '10', danger_threshold_cm: '20', exclusion_radius_m: '40', is_active: true });
function toDraft(station: StationConfig): Draft {
  const draft = blank();
  draft.id = station.id;
  draft.name = station.name;
  draft.is_active = station.is_active;
  for (const [key] of fields) draft[key] = String(station[key]);
  return draft;
}

const DEVICE_ID = /^[A-Za-z0-9_-]+$/;

export default function StationsPage() {
  const [stations, setStations] = useState<StationConfig[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const flood = useFloodZones({ source: 'real', include_real: false }, revision);

  useEffect(() => {
    const ctrl = new AbortController();
    listStations(ctrl.signal).then(setStations).catch((e) => {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Không tải được danh sách trạm.');
    });
    return () => ctrl.abort();
  }, []);

  const choose = (id: string) => {
    const station = stations.find((s) => s.id === id);
    if (!station || busy) return;
    setSelected(id); setDraft(toDraft(station)); setNotice(null); setPicking(false); setError(null);
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
    if (!selected && !DEVICE_ID.test(draft.id)) {
      setError('Mã trạm chỉ gồm chữ, số, gạch dưới và gạch ngang — phải khớp device_id trong firmware.'); return;
    }
    setBusy(true); setError(null); setNotice(null);
    try {
      const station = selected
        ? await updateStation(selected, { name: draft.name, is_active: draft.is_active, ...numeric })
        : await createStation({ id: draft.id, name: draft.name, is_active: draft.is_active, ...numeric });
      setSelected(station.id); setDraft(toDraft(station));
      setStations(await listStations()); setRevision((v) => v + 1);
      setNotice(selected
        ? 'Đã lưu thay đổi. Trạm sẽ dùng cấu hình mới ở lần đọc dữ liệu kế tiếp.'
        : 'Đã tạo trạm. Nạp cùng device_id vào firmware rồi khởi động lại ESP32.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không lưu được trạm.'); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!selected || !window.confirm('Xóa trạm này? Chỉ xóa được khi trạm chưa có số đo nào.')) return;
    setBusy(true); setError(null);
    try {
      await deleteStation(selected);
      reset(); setStations(await listStations()); setRevision((v) => v + 1); setNotice('Đã xóa trạm.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không xóa được trạm.'); }
    finally { setBusy(false); }
  };

  const move = async (id: string, position: LatLng) => {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const station = await updateStation(id, { latitude: position.lat, longitude: position.lng });
      setSelected(id); setDraft(toDraft(station)); setStations(await listStations());
      setNotice('Đã lưu vị trí mới từ thao tác kéo marker.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Không đổi được vị trí.'); }
    finally { setRevision((v) => v + 1); setBusy(false); }
  };

  const live = new Map((flood.data?.stations ?? []).map((s) => [s.id, s]));

  return <div className="app">
    <aside className="sidebar">
      <header><h1>Cấu hình trạm thật</h1><a href="/">← Bản đồ và tìm đường</a></header>
      <div className="banner banner-info">Mã trạm phải trùng <code>device_id</code> mà ESP32 gửi trong topic <code>flood/&lt;mã&gt;/telemetry</code>. Không đổi được mã sau khi tạo.</div>
      {(error || flood.error) && <div className="banner banner-err" role="alert">{error || flood.error}</div>}
      {notice && <div className="banner banner-info" role="status">{notice}</div>}
      <form className="panel demo-form" onSubmit={save}>
        <h2>{selected ? 'Chỉnh sửa trạm' : 'Tạo trạm mới'}</h2>
        <fieldset disabled={busy}>
          <label>Mã trạm (device_id)
            <input required maxLength={64} pattern="[A-Za-z0-9_\-]+" placeholder="station-02"
              value={draft.id} readOnly={!!selected}
              onChange={(e) => setDraft({ ...draft, id: e.target.value })} />
          </label>
          {selected && <p className="sub">Mã trạm không sửa được vì đang gắn với lịch sử số đo và firmware.</p>}
          <label>Tên trạm<input required maxLength={150} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
          <button className="btn" type="button" onClick={() => setPicking(!picking)}>{picking ? 'Hủy chọn vị trí' : 'Chọn vị trí trên bản đồ'}</button>
          {fields.map(([key, label, min, max]) => <label key={key}>{label}
            <input type="number" required step="any" min={min} max={max} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
          </label>)}
          <label><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Trạm đang hoạt động</label>
          <div className="actions">
            <button className="btn primary" type="submit">{busy ? 'Đang lưu…' : 'Lưu trạm'}</button>
            <button className="btn" type="button" onClick={reset}>Tạo mới</button>
            {selected && <button className="btn" type="button" onClick={remove}>Xóa trạm</button>}
          </div>
        </fieldset>
      </form>
      <section className="panel"><h2>Các trạm ({stations.length})</h2>
        <p className="sub">Bấm trạm để sửa. Kéo marker T để lưu vị trí mới. Trạm tắt không hiện trên bản đồ.</p>
        <ul className="stations">{stations.map((station) => {
          const state = live.get(station.id);
          return <li key={station.id}>
            <button disabled={busy} className={`station${selected === station.id ? ' selected' : ''}`} onClick={() => choose(station.id)}>
              <span className="st-main">
                <strong>{station.name}</strong>
                <span className="coord">{station.id}</span>
                <span className={`q ${state?.data_quality === 'fresh' ? 'ok' : 'bad'}`}>
                  {station.is_active ? (state ? QUALITY_LABEL[state.data_quality] : 'Đang tải…') : 'Đã tắt'}
                  {state?.water_depth_cm != null ? ` · ${state.water_depth_cm} cm` : ''}
                </span>
              </span>
            </button>
          </li>;
        })}</ul>
      </section>
    </aside>
    <main className="map-wrap">
      <MapView stations={flood.data?.stations ?? []} zones={flood.data?.flood_zones ?? null}
        zonesKey={flood.version ?? 'none'} origin={null} destination={null} routePath={null} routeOutdated={false}
        pickMode={picking && !busy ? 'demo' : null} selectedId={selected} onPick={pick} onSelectStation={choose}
        onMoveStation={busy ? undefined : move} />
      {picking && <div className="pick-hint" role="status">Bấm bản đồ để điền tọa độ, rồi bấm Lưu trạm.</div>}
    </main>
  </div>;
}
