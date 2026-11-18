import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import type { Station } from '../types';
import { formatTime } from '../utils/format';
import { LEVEL_INFO, QUALITY_LABEL, displayLevel } from '../utils/status';

interface Props {
  stations: Station[];
  loading?: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onOpenChart?: (station: Station) => void;
}

export default function StationList({ stations, loading, selectedId, onSelect, onOpenChart }: Props) {
  const { t } = useI18n();

  return (
    <section className="panel" aria-label={t('stationsTitle')}>
      <h2>{t('stationsTitle')} ({stations.length})</h2>
      {loading && stations.length === 0 ? (
        <div className="stations">
          <div className="skeleton" style={{ height: 56 }} />
          <div className="skeleton" style={{ height: 56 }} />
          <div className="skeleton" style={{ height: 56 }} />
        </div>
      ) : (
        <>
          {stations.length === 0 && (
            <p className="sub">
              {t('emptyStations')}{' '}
              <Link to="/demo" style={{ color: 'var(--accent)', fontWeight: 600 }}>
                {t('addDemoNow')}
              </Link>
            </p>
          )}
          <ul className="stations">
            {stations.map((s) => {
              const lv = displayLevel(s);
              const missing = s.data_quality === 'missing';
              const depthText = missing || s.water_depth_cm == null ? 'Chưa có độ sâu' : `${s.water_depth_cm} cm`;
              return (
                <li key={s.id} className="point-row">
                  <button
                    type="button"
                    aria-label={`${s.name}, ${LEVEL_INFO[lv].label}, ${depthText}`}
                    className={s.id === selectedId ? 'station selected' : 'station'}
                    onClick={() => onSelect(s.id)}
                  >
                    <span className="dot" style={{ background: LEVEL_INFO[lv].color }} />
                    <span className="st-main">
                      <strong>{s.name} · {s.source === 'demo' ? 'Kịch bản mô phỏng' : 'Trạm thực địa'}</strong>
                      <span>{LEVEL_INFO[lv].label} · {depthText}</span>
                      <span className={s.data_quality === 'fresh' ? 'q ok' : 'q bad'}>
                        {s.source === 'demo'
                          ? 'Dữ liệu kịch bản cố định'
                          : `${QUALITY_LABEL[s.data_quality]} · ${formatTime(s.measured_at ?? s.received_at)}`}
                      </span>
                    </span>
                  </button>
                  {onOpenChart && (
                    <button
                      type="button"
                      className="icon-btn"
                      title="Xem biểu đồ mực nước"
                      aria-label={`Biểu đồ mực nước ${s.name}`}
                      onClick={() => onOpenChart(s)}
                    >
                      📊
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
