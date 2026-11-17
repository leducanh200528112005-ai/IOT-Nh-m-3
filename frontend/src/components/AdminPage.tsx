import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ADMIN_KEY_STORAGE } from '../api/client';
import { fetchAdminOverview, fetchRoutingStatus } from '../api/routeApi';
import { useI18n } from '../i18n';
import type { AdminOverviewResponse } from '../types';
import { formatTime } from '../utils/format';

export default function AdminPage() {
  const { t } = useI18n();
  const [data, setData] = useState<AdminOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(ADMIN_KEY_STORAGE) ?? '');
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  const load = useCallback(async (forceRoutingRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      if (forceRoutingRefresh) await fetchRoutingStatus(true);
      const overview = await fetchAdminOverview();
      setData(overview);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không tải được dữ liệu hệ thống');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const saveKey = () => {
    const clean = apiKey.trim();
    if (clean) sessionStorage.setItem(ADMIN_KEY_STORAGE, clean);
    else sessionStorage.removeItem(ADMIN_KEY_STORAGE);
    setSavedNotice(clean ? 'Đã lưu X-API-Key vào phiên làm việc hiện tại.' : 'Đã xóa X-API-Key khỏi phiên.');
  };

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div>
          <h1>📊 {t('adminTitle')}</h1>
          <Link to="/">{t('navBack')}</Link>
          {' · '}
          <Link to="/demo">{t('navDemo')}</Link>
          {' · '}
          <Link to="/stations">{t('navStations')}</Link>
        </div>
        <button type="button" className="btn primary" disabled={loading} onClick={() => load(true)}>
          {loading ? 'Đang kiểm tra…' : '🔄 Kiểm tra lại tất cả dịch vụ'}
        </button>
      </header>

      {error && <div className="banner banner-err" role="alert">{error}</div>}

      {loading && !data && (
        <div className="admin-grid">
          <div className="panel skeleton" style={{ height: 150 }} />
          <div className="panel skeleton" style={{ height: 150 }} />
          <div className="panel skeleton" style={{ height: 150 }} />
        </div>
      )}

      {data && (
        <div className="admin-grid">
          <section className="panel">
            <h2>🖥️ Hạ tầng lõi</h2>
            <ul className="admin-kv">
              <li>
                <span>PostgreSQL Database</span>
                <strong className={data.database === 'ok' ? 'tag ok' : 'tag err'}>
                  {data.database === 'ok' ? '● Hoạt động' : '● Lỗi kết nối'}
                </strong>
              </li>
              <li>
                <span>MQTT Broker (IoT)</span>
                <strong className={data.mqtt === 'connected' ? 'tag ok' : data.mqtt === 'disabled' ? 'tag' : 'tag err'}>
                  {data.mqtt}
                </strong>
              </li>
              <li>
                <span>Rate limit tìm đường</span>
                <strong>{data.flags.rate_limit_route_per_min > 0 ? `${data.flags.rate_limit_route_per_min}/phút` : 'Không giới hạn'}</strong>
              </li>
              <li>
                <span>Kiểm tra lúc</span>
                <span>{formatTime(data.checked_at)}</span>
              </li>
            </ul>
          </section>

          <section className="panel">
            <h2>🧭 Dịch vụ định tuyến (Routing Engines)</h2>
            <ul className="admin-kv">
              <li>
                <span>Valhalla (OSM Exclude Polygons)</span>
                <strong className={data.routing.valhalla.status === 'ok' ? 'tag ok' : 'tag err'}>
                  {data.routing.valhalla.status}
                  {data.routing.valhalla.latency_ms != null ? ` (${data.routing.valhalla.latency_ms} ms)` : ''}
                </strong>
              </li>
              <li>
                <span>OSRM Fallback</span>
                <strong className={data.routing.osrm.status === 'ok' ? 'tag ok' : 'tag err'}>
                  {data.routing.osrm.status}
                  {data.routing.osrm.latency_ms != null ? ` (${data.routing.osrm.latency_ms} ms)` : ''}
                </strong>
              </li>
              <li>
                <span>OpenRouteService (ORS API Key)</span>
                <strong className={data.routing.ors.status === 'configured' ? 'tag ok' : 'tag'}>
                  {data.routing.ors.status}
                </strong>
              </li>
            </ul>
          </section>

          <section className="panel">
            <h2>📡 Trạm đo thực tế (IoT MQTT)</h2>
            <ul className="admin-kv">
              <li><span>Tổng trạm / Đang bật</span><strong>{data.stations.total} / {data.stations.active}</strong></li>
              <li><span>Dữ liệu mới (Fresh)</span><strong className="tag ok">{data.stations.quality.fresh}</strong></li>
              <li><span>Dữ liệu cũ (Stale)</span><strong>{data.stations.quality.stale}</strong></li>
              <li><span>Lỗi / Mất dữ liệu</span><strong>{data.stations.quality.invalid + data.stations.quality.missing}</strong></li>
              <li><span>Trạm đang ngập đỏ / AI</span><strong className="tag err">{data.stations.danger_or_predicted}</strong></li>
            </ul>
          </section>

          <section className="panel">
            <h2>🧪 Điểm ngập mô phỏng (Demo)</h2>
            <ul className="admin-kv">
              <li><span>Số lượng / Giới hạn</span><strong>{data.demo_points.total} / {data.demo_points.max}</strong></li>
              <li><span>Đang kích hoạt</span><strong>{data.demo_points.active}</strong></li>
              <li><span>Ngập đỏ (&ge; ngưỡng)</span><strong className="tag err">{data.demo_points.danger}</strong></li>
              <li><span>AI Dự báo ngập đỏ sớm</span><strong>{data.demo_points.predicted_danger}</strong></li>
            </ul>
          </section>

          <section className="panel">
            <h2>🔐 Bảo mật quản trị (Optional)</h2>
            <p className="sub">
              {data.flags.admin_auth_required
                ? 'Server đang bật ADMIN_API_KEY. Hãy nhập mã X-API-Key để Thêm/Sửa/Xóa trạm.'
                : 'Server đang chạy chế độ mở cho phát triển nội bộ (ADMIN_API_KEY trống).'}
            </p>
            <div className="actions">
              <input
                type="password"
                placeholder="Nhập X-API-Key (tùy chọn)…"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                style={{ flex: 1, minWidth: 160, padding: '6px 8px', border: '1px solid var(--line)', borderRadius: 6 }}
              />
              <button type="button" className="btn" onClick={saveKey}>Lưu Key</button>
            </div>
            {savedNotice && <p className="msg info">{savedNotice}</p>}
          </section>
        </div>
      )}
    </div>
  );
}
