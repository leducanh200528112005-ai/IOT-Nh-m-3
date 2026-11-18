import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '../api/client';
import { fetchFloodZones } from '../api/floodApi';
import { API_BASE_URL, DATA_EXPIRE_MS, POLL_INTERVAL_MS, STALE_AFTER_MS } from '../config';
import type { FloodZonesResponse, SourceSelection } from '../types';
import { floodVersion } from '../utils/status';
import { useNow } from './useNow';

/**
 * Kết hợp SSE stream (push ngay khi thay đổi) và polling dự phòng.
 * Gỡ component => hủy SSE, timer và request.
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
    let sse: EventSource | null = null;
    let sseConnected = false;
    const ctrl = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    setLastOkAt(null);

    if (typeof EventSource !== 'undefined') {
      try {
        const streamUrl = `${API_BASE_URL}/api/flood-zones/stream?source=${selection.source}&include_real=${selection.include_real}`;
        sse = new EventSource(streamUrl);
        sse.onopen = () => {
          if (!stopped) sseConnected = true;
        };
        sse.onmessage = (event) => {
          if (stopped) return;
          try {
            const parsed = JSON.parse(event.data) as FloodZonesResponse;
            setData(parsed);
            setError(null);
            setLastOkAt(Date.now());
            setLoading(false);
          } catch {
            // Ignore malformed SSE tick.
          }
        };
        sse.onerror = () => {
          sseConnected = false;
        };
      } catch {
        sseConnected = false;
      }
    }

    const tick = async () => {
      try {
        const d = await fetchFloodZones(selection, ctrl.signal);
        if (stopped) return;
        setData(d);
        setError(null);
        setLastOkAt(Date.now());
      } catch (e) {
        if (stopped || (e instanceof ApiError && e.kind === 'aborted')) return;
        setError(e instanceof Error ? e.message : 'Lỗi không xác định');
      } finally {
        if (!stopped) {
          setLoading(false);
          // When SSE stream is healthy, keep a slower heartbeat poll so timestamps stay fresh without load.
          timer = window.setTimeout(tick, sseConnected ? POLL_INTERVAL_MS * 2 : POLL_INTERVAL_MS);
        }
      }
    };

    tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ctrl.abort();
      sse?.close();
    };
  }, [selection.source, selection.include_real, refreshKey]);

  const version = useMemo(() => (data ? floodVersion(data) : null), [data]);
  const noRecentPoll = error !== null || (lastOkAt !== null && now - lastOkAt > STALE_AFTER_MS);
  const dataAge = data ? now - Date.parse(data.generated_at) : 0;
  const expired = data !== null && Number.isFinite(dataAge) && dataAge > DATA_EXPIRE_MS;

  return { data, version, error, loading, lastOkAt, noRecentPoll, expired };
}
