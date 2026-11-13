/** Local historical replay only. No API, routing or live hazard-state integration. */
export interface ForecastFrame {
  decision_at: string;
  current_depth_cm: number | null;
  predicted_depth_cm: number | null;
  baseline_depth_cm: number | null;
}
export interface ForecastScenario {
  id: string;
  title: string;
  station: { id: string; name: string; latitude: number; longitude: number };
  frames: ForecastFrame[];
}
export interface ForecastBundle {
  schema_version: 1;
  mode: 'historical_replay';
  model_id: 'raw_delta_d3_weight20';
  source: string;
  validation: { windows: number; balanced_mae_cm: number; near_prediction_p90_error_cm: number | null };
  scenarios: ForecastScenario[];
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Đối tượng JSON không hợp lệ.');
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 300) throw new Error('Chuỗi dữ liệu không hợp lệ.');
  return value;
}
function finite(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error('Giá trị số ngoài phạm vi.');
  return value;
}
function depth(value: unknown): number | null { return value === null ? null : finite(value, 0, 10000); }

export function parseForecastBundle(value: unknown): ForecastBundle {
  const root = record(value);
  if (root.schema_version !== 1 || root.mode !== 'historical_replay' || root.model_id !== 'raw_delta_d3_weight20') {
    throw new Error('Chỉ hỗ trợ file phát lại v1 của model raw ba mã; không phải dữ liệu trực tiếp.');
  }
  if (!Array.isArray(root.scenarios) || root.scenarios.length < 1 || root.scenarios.length > 10) throw new Error('Cần 1–10 kịch bản.');
  const ids = new Set<string>();
  const scenarios = root.scenarios.map((item): ForecastScenario => {
    const scenario = record(item);
    const id = text(scenario.id);
    if (ids.has(id)) throw new Error('Trùng mã kịch bản.');
    ids.add(id);
    const st = record(scenario.station);
    if (!Array.isArray(scenario.frames) || !scenario.frames.length || scenario.frames.length > 2000) throw new Error('Kịch bản cần 1–2000 mốc.');
    let previous: number | null = null;
    const frames = scenario.frames.map((item): ForecastFrame => {
      const frame = record(item);
      const at = text(frame.decision_at);
      const ms = Date.parse(at);
      if (!Number.isFinite(ms) || new Date(ms).toISOString() !== at || ms % 300000 !== 0 ||
          (previous !== null && ms - previous !== 300000)) throw new Error('Mốc thời gian phải là UTC liên tục bước 5 phút.');
      previous = ms;
      const current = depth(frame.current_depth_cm);
      const prediction = depth(frame.predicted_depth_cm);
      const baseline = depth(frame.baseline_depth_cm);
      if ((current === null) !== (prediction === null) || (current === null) !== (baseline === null)) throw new Error('Mốc thiếu phải để trống cả số đo và dự báo.');
      if (baseline !== current) throw new Error('Baseline persistence phải bằng độ sâu hiện tại.');
      return { decision_at: at, current_depth_cm: current, predicted_depth_cm: prediction, baseline_depth_cm: baseline };
    });
    return { id, title: text(scenario.title), station: { id: text(st.id), name: text(st.name),
      latitude: finite(st.latitude, -90, 90), longitude: finite(st.longitude, -180, 180) }, frames };
  });
  const val = record(root.validation);
  const windows = finite(val.windows, 1, 100000000);
  if (!Number.isInteger(windows)) throw new Error('Số cửa sổ phải là số nguyên.');
  return { schema_version: 1, mode: 'historical_replay', model_id: 'raw_delta_d3_weight20', source: text(root.source),
    validation: { windows, balanced_mae_cm: finite(val.balanced_mae_cm, 0, 10000),
      near_prediction_p90_error_cm: depth(val.near_prediction_p90_error_cm) }, scenarios };
}

export function depthState(depth: number | null) {
  if (depth === null) return { label: 'Thiếu dữ liệu — không dự báo', color: '#667785' };
  if (depth >= 10) return { label: 'Dự báo đạt/vượt ngưỡng nghiên cứu 10 cm', color: '#be3d28' };
  if (depth >= 8) return { label: 'Gần ngưỡng nghiên cứu 10 cm', color: '#ad6b00' };
  return { label: 'Dưới vùng gần ngưỡng — không khẳng định an toàn', color: '#0b6b8a' };
}

export function trend(current: number | null, predicted: number | null): string {
  if (current === null || predicted === null) return 'Không đủ dữ liệu';
  const delta = predicted - current;
  if (Math.abs(delta) < .5) return 'Ít thay đổi dự kiến (<0,5 cm)';
  return `${delta > 0 ? 'Tăng' : 'Giảm'} dự kiến ${Math.abs(delta).toFixed(1)} cm`;
}

/** Do not round a value from below a color boundary into the next category. */
export function formatDepth(value: number | null): string {
  if (value === null) return '—';
  const rounded = Number(value.toFixed(1));
  if (value < 10 && rounded >= 10) return '<10,0 cm';
  if (value < 8 && rounded >= 8) return '<8,0 cm';
  return `${value.toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} cm`;
}

export function utcTime(value: string): string {
  return `${new Date(value).toLocaleString('vi-VN', { timeZone: 'UTC', hour12: false })} UTC`;
}
