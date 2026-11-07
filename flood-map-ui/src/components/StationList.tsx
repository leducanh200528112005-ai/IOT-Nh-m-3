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
          const missing = s.dataQuality === 'missing';
          return (
            <li key={s.id}>
              <button className={s.id === selectedId ? 'station selected' : 'station'} onClick={() => onSelect(s.id)}>
                <span className="dot" style={{ background: LEVEL_INFO[lv].color }} />
                <span className="st-main">
                  <strong>{s.name}</strong>
                  <span>
                    {LEVEL_INFO[lv].label} · {missing || s.depthCm == null ? 'Chưa có độ sâu' : `${s.depthCm} cm`}
                  </span>
                  <span className={s.dataQuality === 'ok' ? 'q ok' : 'q bad'}>
                    {QUALITY_LABEL[s.dataQuality]} · {formatTime(s.updatedAt)}
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
