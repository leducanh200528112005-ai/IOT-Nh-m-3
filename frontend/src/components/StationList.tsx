import type { Station } from '../types';
import { formatTime } from '../utils/format';
import { LEVEL_INFO, QUALITY_LABEL, displayLevel } from '../utils/status';

interface Props {
  stations: Station[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function StationList({ stations, selectedId, onSelect }: Props) {
  return (
    <section className="panel" aria-label="Danh sách trạm">
      <h2>Trạm đo ({stations.length})</h2>
      {stations.length === 0 && <p className="sub">Chưa có dữ liệu trạm.</p>}
      <ul className="stations">
        {stations.map((s) => {
          const lv = displayLevel(s);
          const missing = s.data_quality === 'missing';
          return (
            <li key={s.id}>
              <button className={s.id === selectedId ? 'station selected' : 'station'} onClick={() => onSelect(s.id)}>
                <span className="dot" style={{ background: LEVEL_INFO[lv].color }} />
                <span className="st-main">
                   <strong>{s.name} · {s.source === 'demo' ? 'Mô phỏng' : 'Thực tế'}</strong>
                  <span>
                    {LEVEL_INFO[lv].label} · {missing || s.water_depth_cm == null ? 'Chưa có độ sâu' : `${s.water_depth_cm} cm`}
                  </span>
                  <span className={s.data_quality === 'fresh' ? 'q ok' : 'q bad'}>
                     {s.source === 'demo' ? 'Giá trị cấu hình — không tự quá hạn' : `${QUALITY_LABEL[s.data_quality]} · ${formatTime(s.measured_at ?? s.received_at)}`}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
