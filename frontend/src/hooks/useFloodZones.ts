import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '../api/client';
import { fetchFloodZones } from '../api/floodApi';
import { DATA_EXPIRE_MS, POLL_INTERVAL_MS, STALE_AFTER_MS } from '../config';
import type { FloodZonesResponse, SourceSelection } from '../types';
import { floodVersion } from '../utils/status';
import { useNow } from './useNow';

/**
 * Poll /api/flood-zones. Dùng setTimeout nối tiếp (đợi request xong mới hẹn lần sau)
 * nên không bao giờ có hai request chồng nhau. Gỡ component => hủy timer + request.
 */
export function useFloodZones(selection: SourceSelection, refreshKey = 0) {
  const [data, setData] = useState<FloodZonesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastOkAt, setLastOkAt] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const now = useNow(1000);

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    const ctrl = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    setLastOkAt(null);

    const tick = async () => {
      try {
        const d = await fetchFloodZones(selection, ctrl.signal);
        if (stopped) return;
        setData(d); // lỗi thì KHÔNG xóa data cũ, chỉ gắn nhãn
        setError(null);
        setLastOkAt(Date.now());
      } catch (e) {
        if (stopped || (e instanceof ApiError && e.kind === 'aborted')) return;
        setError(e instanceof Error ? e.message : 'Lỗi không xác định');
      } finally {
        if (!stopped) {
          setLoading(false);
          timer = window.setTimeout(tick, POLL_INTERVAL_MS);
        }
      }
    };

    tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [selection.source, selection.include_real, refreshKey]);

  const version = useMemo(() => (data ? floodVersion(data) : null), [data]);
  const noRecentPoll = error !== null || (lastOkAt !== null && now - lastOkAt > STALE_AFTER_MS);
  const dataAge = data ? now - Date.parse(data.generated_at) : 0;
  const expired = data !== null && Number.isFinite(dataAge) && dataAge > DATA_EXPIRE_MS;

  return { data, version, error, loading, lastOkAt, noRecentPoll, expired };
}
