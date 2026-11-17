import type { FormEvent } from 'react';
import type { DemoPoint, DemoPointInput, LatLng } from '../../types';
import AddressSearch from '../AddressSearch';
import { DEMO_PRESETS, MAX_DEMO_POINTS, type DemoPreset } from './useDemoPoints';

export const DEMO_FIELDS = [
  ['latitude', 'Vĩ độ', -89.999999, 89.999999],
  ['longitude', 'Kinh độ', -180, 180],
  ['water_depth_cm', 'Độ ngập nước hiện tại (cm)', 0, 10000],
  ['rise_rate_cm_min', 'Tốc độ dâng (cm/phút)', 0, 100],
  ['warning_threshold_cm', 'Ngưỡng cảnh báo vàng (cm)', 0, 10000],
  ['danger_threshold_cm', 'Ngưỡng nguy hiểm đỏ (cm)', 0.001, 10000],
  ['exclusion_radius_m', 'Bán kính vùng ngập lụt (m)', 0.001, 1000],
] as const;

export type NumericField = (typeof DEMO_FIELDS)[number][0];
export type DemoDraft = { name: string; is_active: boolean } & Record<NumericField, string>;

export function blankDraft(seq = 1): DemoDraft {
  const angle = ((seq - 1) * 137.5 * Math.PI) / 180;
  const dist = 0.005 * Math.sqrt(seq);
  const lat = (20.9826 + dist * Math.cos(angle)).toFixed(6);
  const lng = (105.7704 + dist * Math.sin(angle)).toFixed(6);
  return {
    name: `Điểm ngập #${seq}`,
    latitude: lat,
    longitude: lng,
    water_depth_cm: '0',
    rise_rate_cm_min: '0',
    warning_threshold_cm: '15',
    danger_threshold_cm: '30',
    exclusion_radius_m: '40',
    is_active: true,
  };
}

export function pointToDraft(point: DemoPoint): DemoDraft {
  const draft = blankDraft();
  draft.name = point.name;
  draft.is_active = point.is_active;
  for (const [key] of DEMO_FIELDS) draft[key] = String(point[key as keyof DemoPoint] ?? '0');
  return draft;
}

interface Props {
  selectedId: string | null;
  pointsCount: number;
  draft: DemoDraft;
  busy: boolean;
  onDraftChange: (next: DemoDraft) => void;
  onSubmit: (body: DemoPointInput) => void;
  onValidationError: (msg: string) => void;
  onReset: () => void;
  onDeleteSelected: () => void;
  onAddressPicked: (pos: LatLng, label: string) => void;
}

export default function DemoForm({
  selectedId,
  pointsCount,
  draft,
  busy,
  onDraftChange,
  onSubmit,
  onValidationError,
  onReset,
  onDeleteSelected,
  onAddressPicked,
}: Props) {
  const handlePreset = (preset: DemoPreset) => {
    onDraftChange({
      ...draft,
      water_depth_cm: String(preset.depth),
      rise_rate_cm_min: String(preset.rate),
    });
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId && pointsCount >= MAX_DEMO_POINTS) {
      onValidationError(`Đã đạt giới hạn tối đa ${MAX_DEMO_POINTS} điểm demo. Vui lòng xóa bớt điểm cũ trước khi thêm mới.`);
      return;
    }
    const numeric = Object.fromEntries(DEMO_FIELDS.map(([key]) => [key, Number(draft[key])])) as Record<NumericField, number>;
    if (Object.values(numeric).some((v) => !Number.isFinite(v)) || numeric.danger_threshold_cm <= numeric.warning_threshold_cm) {
      onValidationError('Vui lòng nhập số hợp lệ. Ngưỡng đỏ (nguy hiểm) phải lớn hơn ngưỡng vàng (cảnh báo).');
      return;
    }
    onSubmit({ name: draft.name, is_active: draft.is_active, ...numeric });
  };

  return (
    <form className="panel demo-form" onSubmit={handleSubmit}>
      <h2>{selectedId ? '✏️ Chỉnh sửa điểm ngập' : '➕ Thêm điểm ngập mới'}</h2>
      <fieldset disabled={busy}>
        <label>
          Tìm địa chỉ đặt điểm (tùy chọn)
          <AddressSearch placeholder="🔍 Tìm phố, ngã tư để điền tọa độ…" onSelect={onAddressPicked} />
        </label>

        <label>
          Tên vị trí ngập
          <input
            required
            maxLength={150}
            placeholder="VD: Ngã tư Vạn Phúc, Cổng trường..."
            value={draft.name}
            onChange={(e) => onDraftChange({ ...draft, name: e.target.value })}
          />
        </label>

        <label>
          Mức độ ngập nhanh:
          <div className="preset-buttons">
            {DEMO_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`preset-btn${
                  Number(draft.water_depth_cm) === p.depth && Number(draft.rise_rate_cm_min) === p.rate ? ' active' : ''
                }`}
                style={{ color: p.color }}
                onClick={() => handlePreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </label>

        {DEMO_FIELDS.map(([key, label, min, max]) => (
          <label key={key}>
            {label}
            {key === 'rise_rate_cm_min' && (
              <span style={{ display: 'block', fontSize: '11px', color: '#7c3aed', marginTop: '2px', fontWeight: 500 }}>
                💡 Gợi ý: nhập 0.5 - 0.8 (tương đương dâng +5cm đến +8cm trong 10p) để AI báo ngập đỏ
              </span>
            )}
            <input
              type="number"
              required
              step="any"
              min={min}
              max={max}
              value={draft[key]}
              onChange={(e) => onDraftChange({ ...draft, [key]: e.target.value })}
            />
          </label>
        ))}

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', margin: '8px 0' }}>
          <input
            type="checkbox"
            checked={draft.is_active}
            onChange={(e) => onDraftChange({ ...draft, is_active: e.target.checked })}
          />
          Kích hoạt điểm này (tham gia né đường khi tìm đường)
        </label>

        <div className="actions">
          <button className="btn primary" type="submit" disabled={!selectedId && pointsCount >= MAX_DEMO_POINTS}>
            {busy ? 'Đang lưu…' : selectedId ? '💾 Lưu thay đổi' : '➕ Thêm điểm này'}
          </button>
          <button className="btn" type="button" onClick={onReset}>
            Làm mới form
          </button>
          {selectedId && (
            <button className="btn btn-danger" type="button" onClick={onDeleteSelected}>
              Xóa điểm này
            </button>
          )}
        </div>
      </fieldset>
    </form>
  );
}
