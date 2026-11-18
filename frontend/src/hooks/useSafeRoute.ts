import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { requestSafeRoute } from '../api/routeApi';
import type { Lang, LatLng, RouteHistoryItem, RouteResponse, SourceSelection, VehicleType } from '../types';

export interface RouteState {
  status: 'idle' | 'loading' | 'ok' | 'no_route' | 'error';
  result?: RouteResponse;
  error?: string;
  message?: string;
  /** Phiên bản dữ liệu ngập tại lúc người dùng bấm tính */
  floodVersion?: string | null;
}

const ROUTE_CACHE_KEY = 'flood_last_route_cache_v1';
const HISTORY_STORAGE_KEY = 'flood_route_history_v1';
const MAX_HISTORY = 10;

interface CachedRouteEntry {
  state: RouteState;
  origin: LatLng;
  destination: LatLng;
  vehicle: VehicleType;
  selection: SourceSelection;
}

export function loadCachedRoute(selection: SourceSelection): CachedRouteEntry | null {
  try {
    const raw = sessionStorage.getItem(ROUTE_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedRouteEntry;
    if (
      parsed?.state?.status === 'ok' &&
      parsed.selection?.source === selection.source &&
      Boolean(parsed.selection?.include_real) === Boolean(selection.include_real)
    ) {
      return parsed;
    }
  } catch {
    // Ignore corrupted storage entries.
  }
  return null;
}

function readHistory(): RouteHistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function useSafeRoute(initialState?: RouteState) {
  const [state, setState] = useState<RouteState>(initialState ?? { status: 'idle' });
  const [history, setHistory] = useState<RouteHistoryItem[]>(readHistory);
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => () => ctrlRef.current?.abort(), []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    localStorage.removeItem(HISTORY_STORAGE_KEY);
  }, []);

  const request = useCallback(
    async (
      origin: LatLng,
      destination: LatLng,
      floodVersion: string | null,
      selection: SourceSelection,
      vehicle: VehicleType = 'motorcycle',
      lang: Lang = 'vi',
      labels?: { originLabel?: string; destinationLabel?: string },
    ) => {
      ctrlRef.current?.abort();
      const ctrl = new AbortController();
      ctrlRef.current = ctrl;
      setState({ status: 'loading', floodVersion });
      try {
        const result = await requestSafeRoute(
          {
            ...selection,
            vehicle,
            lang,
            start: { latitude: origin.lat, longitude: origin.lng },
            end: { latitude: destination.lat, longitude: destination.lng },
          },
          ctrl.signal,
        );
        if (ctrl.signal.aborted) return;
        const nextState: RouteState = { status: 'ok', result, floodVersion };
        setState(nextState);
        try {
          const cache: CachedRouteEntry = { state: nextState, origin, destination, vehicle, selection };
          sessionStorage.setItem(ROUTE_CACHE_KEY, JSON.stringify(cache));
        } catch {
          // Ignore storage quota issues.
        }
        setHistory((prev) => {
          const id = `${origin.lat.toFixed(4)},${origin.lng.toFixed(4)}->${destination.lat.toFixed(4)},${destination.lng.toFixed(4)}:${vehicle}`;
          const item: RouteHistoryItem = {
            id,
            origin,
            destination,
            originLabel: labels?.originLabel,
            destinationLabel: labels?.destinationLabel,
            vehicle,
            distance_m: result.distance_m,
            duration_s: result.duration_s,
            savedAt: result.calculated_at,
          };
          const deduped = [item, ...prev.filter((x) => x.id !== id)].slice(0, MAX_HISTORY);
          try {
            localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(deduped));
          } catch {
            // Ignore storage quota issues.
          }
          return deduped;
        });
      } catch (e) {
        if (ctrl.signal.aborted || (e instanceof ApiError && e.kind === 'aborted')) return;
        if (e instanceof ApiError && e.code === 'NO_SUITABLE_ROUTE') {
          setState({ status: 'no_route', message: e.message, floodVersion });
        } else {
          setState({ status: 'error', error: e instanceof Error ? e.message : 'Lỗi không xác định', floodVersion });
        }
      }
    },
    [],
  );

  const clear = useCallback(() => {
    ctrlRef.current?.abort();
    setState({ status: 'idle' });
    sessionStorage.removeItem(ROUTE_CACHE_KEY);
  }, []);

  return { state, history, request, clear, clearHistory };
}
