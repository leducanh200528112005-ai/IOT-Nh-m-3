import { useCallback, useEffect, useState } from 'react';
import {
  batchCreateDemoPoints,
  createDemoPoint,
  deleteAllDemoPoints,
  deleteDemoPoint,
  listDemoPoints,
  updateDemoPoint,
} from '../../api/demoApi';
import { DEFAULT_DEMO_POINTS } from '../../data/defaultDemoPoints';
import type { DemoPoint, DemoPointInput, LatLng } from '../../types';

export const MAX_DEMO_POINTS = 30;

export const DEMO_PRESETS = [
  { label: '🟢 An toàn (0cm)', depth: 0, rate: 0.0, color: '#2f9e6e', icon: '🟢' },
  { label: '🟡 Cảnh báo (15cm)', depth: 15, rate: 0.0, color: '#e3b505', icon: '🟡' },
  { label: '⚡ Dự báo ngập sớm (12cm, dâng +8cm/10p)', depth: 12, rate: 0.8, color: '#a855f7', icon: '⚡' },
  { label: '🔴 Nguy hiểm (35cm)', depth: 35, rate: 0.0, color: '#c8312b', icon: '🔴' },
] as const;

export type DemoPreset = (typeof DEMO_PRESETS)[number];

export function useDemoPoints() {
  const [points, setPoints] = useState<DemoPoint[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [busy, setBusy] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoadingList(true);
    listDemoPoints(ctrl.signal)
      .then((rows) => {
        if (!ctrl.signal.aborted) setPoints(rows);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Không tải được danh sách điểm demo.');
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoadingList(false);
      });
    return () => ctrl.abort();
  }, []);

  const savePoint = useCallback(async (selectedId: string | null, body: DemoPointInput): Promise<DemoPoint | null> => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (selectedId) {
        const updated = await updateDemoPoint(selectedId, body);
        setPoints((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
        setRevision((v) => v + 1);
        setNotice('Đã cập nhật điểm ngập thành công!');
        return updated;
      }
      const created = await createDemoPoint(body);
      setPoints((prev) => [...prev, created]);
      setRevision((v) => v + 1);
      setNotice('Đã thêm điểm ngập mới lên bản đồ!');
      return created;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không lưu được điểm demo.');
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  const quickSet = useCallback(async (id: string, preset: DemoPreset) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateDemoPoint(id, { water_depth_cm: preset.depth, rise_rate_cm_min: preset.rate });
      setPoints((prev) => prev.map((p) => (p.id === id ? updated : p)));
      setRevision((r) => r + 1);
      setNotice(`Đã đổi trạng thái điểm sang: ${preset.label}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không cập nhật được điểm.');
    } finally {
      setBusy(false);
    }
  }, []);

  const movePoint = useCallback(async (id: string, position: LatLng): Promise<DemoPoint | null> => {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateDemoPoint(id, { latitude: position.lat, longitude: position.lng });
      setPoints((prev) => prev.map((p) => (p.id === id ? updated : p)));
      setNotice(`Đã cập nhật vị trí mới [${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}].`);
      return updated;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không đổi được vị trí marker.');
      return null;
    } finally {
      setRevision((v) => v + 1);
      setBusy(false);
    }
  }, []);

  const deleteOne = useCallback(async (id: string, name: string): Promise<boolean> => {
    if (!window.confirm(`Bạn có chắc muốn xóa điểm "${name}"?`)) return false;
    setBusy(true);
    setError(null);
    try {
      await deleteDemoPoint(id);
      setPoints((prev) => prev.filter((p) => p.id !== id));
      setRevision((r) => r + 1);
      setNotice(`Đã xóa điểm "${name}".`);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không xóa được điểm.');
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const clearAll = useCallback(async (): Promise<boolean> => {
    if (points.length === 0) return false;
    if (!window.confirm(`Bạn có chắc muốn XÓA TẤT CẢ ${points.length} điểm ngập lụt hiện có trên bản đồ?`)) return false;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await deleteAllDemoPoints();
      setPoints([]);
      setRevision((r) => r + 1);
      setNotice('Đã xóa toàn bộ điểm ngập. Bản đồ hiện tại hoàn toàn sạch.');
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không xóa được toàn bộ điểm.');
      return false;
    } finally {
      setBusy(false);
    }
  }, [points.length]);

  const seedDefaults = useCallback(async () => {
    if (points.length > 0 && !window.confirm(`Đã có ${points.length} điểm. Vẫn nạp thêm điểm mẫu?`)) return;
    const remaining = Math.max(0, MAX_DEMO_POINTS - points.length);
    if (remaining === 0) {
      setError(`Đã đạt tối đa ${MAX_DEMO_POINTS} điểm demo.`);
      return;
    }
    setSeeding(true);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await batchCreateDemoPoints(DEFAULT_DEMO_POINTS.slice(0, remaining));
      setPoints((prev) => [...prev, ...created]);
      setRevision((r) => r + 1);
      setNotice(`Đã nạp nhanh ${created.length} điểm mẫu (1 batch request)!`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không tạo được điểm mẫu.');
    } finally {
      setSeeding(false);
      setBusy(false);
    }
  }, [points.length]);

  return {
    points,
    loadingList,
    busy,
    seeding,
    error,
    setError,
    notice,
    setNotice,
    revision,
    savePoint,
    quickSet,
    movePoint,
    deleteOne,
    clearAll,
    seedDefaults,
  };
}
