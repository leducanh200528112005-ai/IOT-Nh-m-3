import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { requestSafeRoute } from '../api/routeApi';
import type { LatLng, RouteResponse, SourceSelection } from '../types';

export interface RouteState {
  status: 'idle' | 'loading' | 'ok' | 'no_route' | 'error';
  result?: RouteResponse;
  error?: string;
  message?: string;
  /** Phiên bản dữ liệu ngập tại lúc người dùng bấm tính */
  floodVersion?: string | null;
}

export function useSafeRoute() {
  const [state, setState] = useState<RouteState>({ status: 'idle' });
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => () => ctrlRef.current?.abort(), []);

  const request = useCallback(async (origin: LatLng, destination: LatLng, floodVersion: string | null, selection: SourceSelection) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    setState({ status: 'loading' });
    try {
      const result = await requestSafeRoute({
        ...selection,
        start: { latitude: origin.lat, longitude: origin.lng },
        end: { latitude: destination.lat, longitude: destination.lng },
      }, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setState({ status: 'ok', result, floodVersion });
    } catch (e) {
      if (ctrl.signal.aborted || (e instanceof ApiError && e.kind === 'aborted')) return;
      if (e instanceof ApiError && e.code === 'NO_SUITABLE_ROUTE') {
        setState({ status: 'no_route', message: e.message });
      } else {
        setState({ status: 'error', error: e instanceof Error ? e.message : 'Lỗi không xác định' });
      }
    }
  }, []);

  const clear = useCallback(() => {
    ctrlRef.current?.abort();
    setState({ status: 'idle' });
  }, []);

  return { state, request, clear };
}
