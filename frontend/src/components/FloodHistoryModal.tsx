import { useEffect, useState } from 'react';
import { fetchFloodHistory } from '../api/routeApi';
import type { FloodHistoryResponse } from '../types';

interface Props {
  pointId: string;
  source: 'real' | 'demo';
  onClose: () => void;
}

export default function FloodHistoryModal({ pointId, source, onClose }: Props) {
  const [data, setData] = useState<FloodHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    fetchFloodHistory(pointId, source, ctrl.signal)
      .then((res) => {
        if (!ctrl.signal.aborted) setData(res);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Không tải được dữ liệu biểu đồ');
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [pointId, source]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const width = 460;
  const height = 220;
  const pad = { top: 20, right: 20, bottom: 34, left: 38 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const pts = data?.points ?? [];
  const maxY = Math.max(
    40,
    (data?.danger_threshold_cm ?? 30) * 1.2,
    ...pts.map((p) => p.depth_cm + 5),
  );
  const xFor = (i: number) =>
    pts.length <= 1 ? pad.left + plotW / 2 : pad.left + (i / (pts.length - 1)) * plotW;
  const yFor = (val: number) => pad.top + plotH - (Math.max(0, val) / maxY) * plotH;

  const realPts = pts.map((p, i) => ({ ...p, x: xFor(i), y: yFor(p.depth_cm) })).filter((p) => !p.is_forecast);
  const allPts = pts.map((p, i) => ({ ...p, x: xFor(i), y: yFor(p.depth_cm) }));
  const forecastPts = allPts.filter((p, idx) => p.is_forecast || idx === realPts.length - 1);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h2>📊 Biểu đồ mực nước {data ? `— ${data.name}` : ''}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Đóng">✕</button>
        </header>

        {loading && <div className="skeleton" style={{ height: 220 }} />}
        {error && <p className="msg err">{error}</p>}

        {!loading && !error && data && (
          <>
            {pts.length === 0 ? (
              <p className="sub">Chưa có dữ liệu lịch sử số đo cho trạm này.</p>
            ) : (
              <svg viewBox={`0 0 ${width} ${height}`} className="history-chart" role="img" aria-label="Biểu đồ mực nước">
                {/* Ngưỡng nguy hiểm đỏ */}
                <line
                  x1={pad.left}
                  y1={yFor(data.danger_threshold_cm)}
                  x2={width - pad.right}
                  y2={yFor(data.danger_threshold_cm)}
                  stroke="#c8312b"
                  strokeDasharray="5 4"
                  strokeWidth="1.5"
                />
                <text x={width - pad.right} y={yFor(data.danger_threshold_cm) - 4} textAnchor="end" fontSize="10" fill="#c8312b">
                  Nguy hiểm ({data.danger_threshold_cm}cm)
                </text>

                {/* Ngưỡng cảnh báo vàng */}
                <line
                  x1={pad.left}
                  y1={yFor(data.warning_threshold_cm)}
                  x2={width - pad.right}
                  y2={yFor(data.warning_threshold_cm)}
                  stroke="#d99b00"
                  strokeDasharray="3 3"
                  strokeWidth="1.2"
                />

                {/* Đường dữ liệu thực/hiện tại */}
                {realPts.length >= 2 && (
                  <polyline
                    fill="none"
                    stroke="#0b6b8a"
                    strokeWidth="2.8"
                    points={realPts.map((p) => `${p.x},${p.y}`).join(' ')}
                  />
                )}

                {/* Đoạn AI dự báo */}
                {forecastPts.length >= 2 && (
                  <polyline
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth="2.5"
                    strokeDasharray="6 4"
                    points={forecastPts.map((p) => `${p.x},${p.y}`).join(' ')}
                  />
                )}

                {/* Trục đáy */}
                <line x1={pad.left} y1={pad.top + plotH} x2={width - pad.right} y2={pad.top + plotH} stroke="#9aa8b5" strokeWidth="1" />

                {allPts.map((p, i) => (
                  <g key={`${p.label}-${i}`}>
                    <circle cx={p.x} cy={p.y} r="4" fill={p.is_forecast ? '#a855f7' : '#0b6b8a'} stroke="#fff" strokeWidth="1.5" />
                    <text x={p.x} y={p.y - 8} textAnchor="middle" fontSize="10" fontWeight="600" fill="currentColor">
                      {p.depth_cm}cm
                    </text>
                    <text x={p.x} y={height - 10} textAnchor="middle" fontSize="9.5" fill="var(--muted)">
                      {p.label}
                    </text>
                  </g>
                ))}
              </svg>
            )}

            {data.ai_prediction && (
              <div className="msg info">
                <strong>🤖 AI Dự báo:</strong> tốc độ {data.ai_prediction.rate_cm_per_min > 0 ? '+' : ''}
                {(data.ai_prediction.rate_cm_per_min * 10).toFixed(1)} cm/10p · Sau 15p:{' '}
                <b>{data.ai_prediction.predicted_15m} cm</b> · Sau 30p: <b>{data.ai_prediction.predicted_30m} cm</b> · Xác suất ngập đỏ:{' '}
                <b>{data.ai_prediction.danger_probability}%</b>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
