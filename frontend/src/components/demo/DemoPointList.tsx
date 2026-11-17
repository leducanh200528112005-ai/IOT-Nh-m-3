import type { DemoPoint, FloodLevel, Station } from '../../types';
import { DEMO_PRESETS, type DemoPreset } from './useDemoPoints';

/** Phân loại mức ngập đồng bộ ngưỡng từng điểm từ backend (tránh hardcode 15/30). */
function pointLevel(
  point: DemoPoint,
  liveStation?: Station,
): Exclude<FloodLevel, 'unknown'> {
  if (liveStation && liveStation.hazard_state !== 'unknown') {
    return liveStation.hazard_state;
  }
  if (point.water_depth_cm >= point.danger_threshold_cm) return 'danger';
  const rate = point.rise_rate_cm_min ?? 0;
  if (rate >= 0.5 || (rate > 0 && point.water_depth_cm + rate * 15 >= point.danger_threshold_cm)) {
    return 'predicted_danger';
  }
  if (point.water_depth_cm >= point.warning_threshold_cm) return 'warning';
  return 'normal';
}

function presetLevel(preset: DemoPreset): Exclude<FloodLevel, 'unknown'> {
  if (preset.depth >= 30) return 'danger';
  if (preset.rate >= 0.5) return 'predicted_danger';
  if (preset.depth >= 15) return 'warning';
  return 'normal';
}

interface Props {
  points: DemoPoint[];
  liveStations: Station[];
  selectedId: string | null;
  loading: boolean;
  busy: boolean;
  onSelect: (id: string) => void;
  onQuickSet: (id: string, preset: DemoPreset) => void;
  onDelete: (id: string, name: string) => void;
  onOpenChart: (id: string) => void;
}

export default function DemoPointList({
  points,
  liveStations,
  selectedId,
  loading,
  busy,
  onSelect,
  onQuickSet,
  onDelete,
  onOpenChart,
}: Props) {
  const liveById = new Map(liveStations.map((s) => [s.id, s]));

  return (
    <section className="panel">
      <h2>Các điểm ngập đã tạo ({points.length})</h2>
      <p className="sub">
        Bấm điểm để sửa. Kéo marker <b>💧</b> trên bản đồ để đổi vị trí. Bấm <b>🟢🟡⚡🔴</b> để đổi nhanh mức ngập.
      </p>

      {loading ? (
        <div className="stations">
          <div className="skeleton" style={{ height: 52 }} />
          <div className="skeleton" style={{ height: 52 }} />
          <div className="skeleton" style={{ height: 52 }} />
        </div>
      ) : points.length === 0 ? (
        <div className="empty-points-card">
          <p>Chưa có điểm ngập nào trong kịch bản.</p>
          <p className="sub">
            Bấm <b>"📍 Click bản đồ lấy tọa độ"</b> và click vị trí bất kỳ trên bản đồ để thêm điểm ngập mới!
          </p>
        </div>
      ) : (
        <ul className="stations">
          {points.map((point) => {
            const level = pointLevel(point, liveById.get(point.id));
            return (
              <li key={point.id}>
                <div className="point-row">
                  <button
                    disabled={busy}
                    className={`station${selectedId === point.id ? ' selected' : ''}`}
                    onClick={() => onSelect(point.id)}
                    title="Bấm để chỉnh sửa chi tiết"
                  >
                    <span className="st-main">
                      <strong>{point.name}</strong>
                      <span>
                        Nước: <b>{point.water_depth_cm} cm</b>
                        {point.rise_rate_cm_min ? ` (+${(point.rise_rate_cm_min * 10).toFixed(0)}cm/10p)` : ''}
                        {!point.is_active ? ' · (Tắt)' : ''}
                      </span>
                    </span>
                  </button>

                  <div className="item-actions">
                    <span className="quick-toggle">
                      {DEMO_PRESETS.map((p) => {
                        const active = level === presetLevel(p);
                        return (
                          <button
                            key={p.label}
                            type="button"
                            disabled={busy}
                            className={`quick-dot${active ? ' active' : ''}`}
                            style={{ color: p.color, borderColor: active ? p.color : undefined }}
                            title={p.label}
                            onClick={(e) => {
                              e.stopPropagation();
                              onQuickSet(point.id, p);
                            }}
                          >
                            {p.icon}
                          </button>
                        );
                      })}
                    </span>
                    <button
                      className="icon-btn"
                      type="button"
                      disabled={busy}
                      title="Xem biểu đồ mực nước & AI"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenChart(point.id);
                      }}
                    >
                      📊
                    </button>
                    <button
                      className="icon-btn"
                      type="button"
                      disabled={busy}
                      title="Xóa điểm này"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(point.id, point.name);
                      }}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
