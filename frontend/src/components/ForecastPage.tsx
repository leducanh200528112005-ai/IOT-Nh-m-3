import { useEffect, useRef, useState } from 'react';
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet';
import { TILE_ATTRIBUTION, TILE_URL } from '../config';
import { depthState, formatDepth as cm, parseForecastBundle, trend, utcTime, type ForecastBundle } from '../utils/forecast';

export default function ForecastPage() {
  const [bundle, setBundle] = useState<ForecastBundle | null>(null);
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showBaseline, setShowBaseline] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tileError, setTileError] = useState(false);
  const importVersion = useRef(0);
  const scenario = bundle?.scenarios[scenarioIndex];
  const frame = scenario?.frames[index];
  const state = depthState(frame?.predicted_depth_cm ?? null);

  useEffect(() => {
    if (!playing || !scenario) return;
    if (index >= scenario.frames.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setIndex((i) => i + 1), 750);
    return () => window.clearTimeout(timer);
  }, [playing, scenario, index]);

  const importFile = async (file: File) => {
    const version = ++importVersion.current;
    setPlaying(false); setBundle(null); setIndex(0); setScenarioIndex(0); setError(null); setLoading(true); setTileError(false);
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('File quá lớn (tối đa 10 MB).');
      const data = parseForecastBundle(JSON.parse(await file.text()));
      if (version === importVersion.current) setBundle(data);
    } catch (err) {
      if (version === importVersion.current) setError(err instanceof Error ? err.message : 'Không đọc được file.');
    } finally {
      if (version === importVersion.current) setLoading(false);
    }
  };

  return <div className="app forecast-app">
    <aside className="sidebar forecast-sidebar">
      <header><h1>Dự báo độ sâu</h1><a href="/">← Bản đồ ESP32 / demo hiện tại</a></header>
      <div className="banner banner-warn" role="note">
        <strong>PHÁT LẠI LỊCH SỬ NYC — THỬ NGHIỆM</strong><br />
        Không phải số đo ESP32 hay dự báo đang vận hành. Không dùng để quyết định đi qua vùng ngập.
      </div>
      <section className="panel">
        <h2>Mở dữ liệu cục bộ</h2>
        <label>File forecast-replay-local.json
          <input className="forecast-file" type="file" accept=".json,application/json" onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void importFile(file);
            e.target.value = '';
          }} />
        </label>
        <p className="sub">Chọn file từ công cụ export trong thư mục AI. File được đọc trong trình duyệt, không tải lên backend hoặc lưu vào public.</p>
        {loading && <p role="status">Đang kiểm tra file…</p>}
        {error && <p className="msg err" role="alert">{error}</p>}
        {bundle && <button className="btn" onClick={() => {
          ++importVersion.current; setBundle(null); setPlaying(false); setIndex(0);
        }}>Đóng file</button>}
      </section>
      {bundle && scenario && frame && <>
        <section className="panel">
          <label>Kịch bản <select value={scenarioIndex} onChange={(e) => {
            setPlaying(false); setScenarioIndex(Number(e.target.value)); setIndex(0); setTileError(false);
          }}>{bundle.scenarios.map((s, i) => <option value={i} key={s.id}>{s.title}</option>)}</select></label>
          <p><strong>{scenario.station.name}</strong></p>
          <p className="sub">{scenario.station.id} · Vị trí theo dữ liệu NYC, không đặt lại lên địa bàn ESP32.</p>
          <p className="coord">{utcTime(frame.decision_at)}</p>
          <input className="forecast-slider" type="range" aria-label="Mốc phát lại" min={0} max={scenario.frames.length - 1} value={index}
            onChange={(e) => { setPlaying(false); setIndex(Number(e.target.value)); }} />
          <div className="actions">
            <button className="btn primary" disabled={!playing && index === scenario.frames.length - 1} onClick={() => setPlaying(!playing)}>{playing ? 'Tạm dừng' : 'Phát lại ×400'}</button>
            <button className="btn" onClick={() => { setPlaying(false); setIndex(0); }}>Về đầu</button>
            <button className="btn" disabled={index >= scenario.frames.length - 1} onClick={() => { setPlaying(false); setIndex(index + 1); }}>+5 phút</button>
          </div>
          <p className="sub">Mỗi 0,75 giây phát một bin 5 phút. Mốc thiếu không được nội suy hoặc giữ dự báo cũ.</p>
          <p className="sub">Chỉ phát lại cửa sổ validation hợp lệ. Mốc trống có thể thiếu lịch sử hoặc nhãn để chấm điểm, không nhất thiết trạm mất số đo; không mô phỏng đầy đủ quyết định khả dụng lúc chạy thật.</p>
        </section>
        <section className="panel forecast-card" style={{ borderLeftColor: state.color }} aria-live="polite">
          <h2>Độ sâu dự kiến trong bin tương lai</h2>
          <p className="forecast-number" style={{ color: state.color }}>{cm(frame.predicted_depth_cm)}</p>
          <p><strong>{state.label}</strong></p>
          <p>{trend(frame.current_depth_cm, frame.predicted_depth_cm)}</p>
          <p>Độ sâu hiện tại (trung vị raw): <strong>{cm(frame.current_depth_cm)}</strong></p>
          {frame.current_depth_cm !== null && frame.current_depth_cm >= 10 && <p className="msg warn">Số đo hiện tại đã đạt/vượt 10 cm. Dự báo giảm không phủ nhận mức nước đang quan sát.</p>}
          <p className="sub">Nhãn mục tiêu: số đo cuối bin (t+5, t+10 phút], không phải mức lớn nhất 10 phút tới hoặc chính xác tại t+10.</p>
          <p className="coord">({utcTime(new Date(Date.parse(frame.decision_at) + 300000).toISOString())},<br />
            {utcTime(new Date(Date.parse(frame.decision_at) + 600000).toISOString())}]</p>
          <label><input type="checkbox" checked={showBaseline} onChange={(e) => setShowBaseline(e.target.checked)} /> So sánh baseline giữ nguyên độ sâu</label>
          {showBaseline && <p>Baseline: <strong>{cm(frame.baseline_depth_cm)}</strong></p>}
        </section>
        <section className="panel">
          <h2>Độ tin cậy: chưa hiệu chuẩn</h2>
          <p className="sub">Model raw ba mã · {bundle.model_id}. Không có xác suất hoặc khoảng dự báo đã được xác nhận độc lập.</p>
          <p className="sub">MAE cân bằng trên {bundle.validation.windows.toLocaleString('vi-VN')} cửa sổ validation đã xem: <strong>{bundle.validation.balanced_mae_cm.toFixed(3)} cm</strong>. Không phải giới hạn sai số từng lần.</p>
          {bundle.validation.near_prediction_p90_error_cm !== null && <p className="sub">Khi dự báo 8–12 cm, P90 sai số tuyệt đối hồi cứu: <strong>{bundle.validation.near_prediction_p90_error_cm.toFixed(2)} cm</strong>. Không phải khoảng tin cậy được bảo đảm.</p>}
          <p className="disclaimer">8–&lt;10 cm chỉ là quy ước hiển thị “gần ngưỡng”. Dưới 10 cm không có nghĩa đường an toàn. Điểm đo không đại diện độ sâu cả con đường.</p>
          <p className="disclaimer">Nguồn: {bundle.source}. Dữ liệu phái sinh giữ cục bộ, tuân giấy phép nguồn. Bản đồ nền có thể gọi nhà cung cấp tile, nhưng ứng dụng không gửi file dự báo.</p>
        </section>
      </>}
    </aside>
    <main className="map-wrap">
      {scenario && frame ? <>
        <MapContainer key={scenario.id} center={[scenario.station.latitude, scenario.station.longitude]} zoom={16} className="map">
          <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={19} eventHandlers={{ tileerror: () => setTileError(true) }} />
          <CircleMarker center={[scenario.station.latitude, scenario.station.longitude]} radius={14}
            pathOptions={{ color: '#fff', weight: 3, fillColor: state.color, fillOpacity: .9, dashArray: frame.predicted_depth_cm === null ? '3 3' : undefined }}>
            <Tooltip permanent direction="top"><strong>{scenario.station.name}</strong><br />
              Dự báo: {cm(frame.predicted_depth_cm)}<br />{state.label}<br />
              Hiện tại: {cm(frame.current_depth_cm)}{showBaseline && <> · Baseline: {cm(frame.baseline_depth_cm)}</>}
            </Tooltip>
          </CircleMarker>
        </MapContainer>
        <div className="forecast-map-note">NYC · LỊCH SỬ · {utcTime(frame.decision_at)}<br />Không gửi cảnh báo, không tham gia định tuyến.
          {tileError && <p className="msg warn" role="status">Không tải đủ bản đồ nền. Kiểm tra mạng/nhà cung cấp tile; số liệu phát lại vẫn đọc từ file cục bộ.</p>}
        </div>
      </> : <div className="forecast-empty panel"><h2>Bản đồ dự báo thử nghiệm</h2>
        <p>Mở file phát lại cục bộ để xem độ sâu dự kiến tại đúng vị trí trạm NYC.</p>
        <p>Trang này độc lập với ESP32, dữ liệu demo hiện tại và chức năng tìm đường.</p>
        <p className="sub">Tạo file bằng <code>analysis/export_forecast_replay.py</code> trong thư mục <code>IOT training</code>.</p>
      </div>}
    </main>
  </div>;
}
