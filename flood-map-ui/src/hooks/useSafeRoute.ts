import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { requestSafeRoute } from '../api/routeApi';
import type { LatLng, RouteResponse } from '../types';

export interface RouteState {
  status: 'idle' | 'loading' | 'ok' | 'no_route' | 'error';
  result?: RouteResponse;
  error?: string;
  /** Phiên bản dữ liệu ngập tại lúc người dùng bấm tính */
  floodVersion?: string | null;
}

export function useSafeRoute() {
  const [state, setState] = useState<RouteState>({ status: 'idle' });
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => () => ctrlRef.current?.abort(), []);

  const request = useCallback(async (origin: LatLng, destination: LatLng, floodVersion: string | null) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    setState({ status: 'loading' });
    try {
      const result = await requestSafeRoute({ origin, destination }, ctrl.signal);
      if (ctrl.signal.aborted) return;
      if (result.status === 'ok' && result.route) setState({ status: 'ok', result, floodVersion });
      else setState({ status: 'no_route', result });
    } catch (e) {
      if (ctrl.signal.aborted || (e instanceof ApiError && e.kind === 'aborted')) return;
      setState({ status: 'error', error: e instanceof Error ? e.message : 'Lỗi không xác định' });
    }
  }, []);

  const clear = useCallback(() => {
    ctrlRef.current?.abort();
    setState({ status: 'idle' });
  }, []);

  return { state, request, clear };
}
