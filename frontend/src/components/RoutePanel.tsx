import type { RouteState } from '../hooks/useSafeRoute';
import type { LatLng } from '../types';
import { formatCoord, formatDistance, formatDuration, formatTime } from '../utils/format';
import type { PickMode } from './MapView';

interface Props {
  origin: LatLng | null;
  destination: LatLng | null;
  pickMode: PickMode;
  onPickMode: (m: PickMode) => void;
  onSwap: () => void;
  onCompute: () => void;
  onClear: () => void;
  state: RouteState;
  online: boolean;
  outdatedReason: string | null;
}

export default function RoutePanel(p: Props) {
  const loading = p.state.status === 'loading';
  const canCompute = !!p.origin && !!p.destination && !loading && p.online;
  const r = p.state.result;

  return (
    <section className="panel" aria-label="Tìm đường">
      <h2>Tìm đường tránh ngập</h2>

      <div className="pick-row">
        <button className={p.pickMode === 'origin' ? 'btn pick active' : 'btn pick'} onClick={() => p.onPickMode(p.pickMode === 'origin' ? null : 'origin')}>
          {p.pickMode === 'origin' ? 'Bấm lên bản đồ…' : 'Chọn điểm đi'}
        </button>
        <span className="coord">{p.origin ? formatCoord(p.origin) : 'Chưa chọn'}</span>
      </div>
      <div className="pick-row">
        <button className={p.pickMode === 'destination' ? 'btn pick active' : 'btn pick'} onClick={() => p.onPickMode(p.pickMode === 'destination' ? null : 'destination')}>
          {p.pickMode === 'destination' ? 'Bấm lên bản đồ…' : 'Chọn điểm đến'}
        </button>
        <span className="coord">{p.destination ? formatCoord(p.destination) : 'Chưa chọn'}</span>
      </div>

      <div className="actions">
        <button className="btn primary" disabled={!canCompute} onClick={p.onCompute}>
          {loading ? 'Đang tìm tuyến…' : p.state.status === 'ok' ? 'Tính lại tuyến' : 'Tìm đường'}
        </button>
        <button className="btn" onClick={p.onSwap} disabled={!p.origin || !p.destination || loading}>Đổi chiều</button>
        <button className="btn" onClick={p.onClear} disabled={!p.origin && !p.destination && p.state.status === 'idle'}>Xóa</button>
      </div>
      {!p.online && <p className="msg err">Mất kết nối mạng, chưa thể tìm đường.</p>}

      {loading && <p className="msg info" role="status">Đang gửi yêu cầu tới máy chủ…</p>}

      {p.state.status === 'error' && (
        <p className="msg err" role="alert">
          Không tìm được đường: {p.state.error}. Bạn có thể bấm “Tìm đường” để thử lại.
        </p>
      )}

      {p.state.status === 'no_route' && (
        <p className="msg warn" role="alert">
          {p.state.message || 'Không có tuyến phù hợp giữa hai điểm này với tình hình ngập hiện tại.'} Hãy thử đổi điểm đi/đến hoặc chờ dữ liệu cập nhật.
        </p>
      )}

      {p.state.status === 'ok' && r && (
        <div className="result">
          {p.outdatedReason && (
            <p className="msg warn" role="alert">
              Tuyến này có thể đã lỗi thời: {p.outdatedReason} Hãy bấm “Tính lại tuyến”.
            </p>
          )}
          <dl>
            <div><dt>Khoảng cách</dt><dd>{formatDistance(r.distance_m)}</dd></div>
            <div><dt>Thời gian</dt><dd>{formatDuration(r.duration_s)}</dd></div>
          </dl>
          <p className="sub">Tính lúc {formatTime(r.calculated_at)}</p>
          {r.warnings.map((warning) => <p className="msg warn" key={warning}>{warning}</p>)}
        </div>
      )}

      <p className="disclaimer">
        Tuyến được đề xuất dựa trên dữ liệu cảm biến tại thời điểm tính, không phải bảo đảm về an toàn. Luôn quan sát thực tế và tuân thủ biển báo.
      </p>
    </section>
  );
}
