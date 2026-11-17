import assert from 'node:assert/strict';
import test from 'node:test';
import { depthState, formatDepth, parseForecastBundle, trend } from '../src/utils/forecast.ts';

function bundle() {
  return { schema_version: 1, mode: 'historical_replay', model_id: 'raw_delta_d3_weight20', source: 'FloodNet NYU/CUNY',
    validation: { windows: 92215, balanced_mae_cm: .4949, near_prediction_p90_error_cm: 1.2 },
    scenarios: [{ id: 'case', title: 'Historical', station: { id: 'nyc', name: 'NYC', latitude: 40.6, longitude: -74 },
      frames: [{ decision_at: '2023-04-23T00:00:00.000Z', current_depth_cm: 7, predicted_depth_cm: 9, baseline_depth_cm: 7 }] }] };
}
test('9cm is near threshold, 10cm exceeds; missing never becomes safe', () => {
  assert.match(depthState(9).label, /Gần ngưỡng/);
  assert.match(depthState(10).label, /vượt ngưỡng/);
  assert.match(depthState(null).label, /không dự báo/);
});
test('replay schema accepts current/prediction/baseline and drops unrelated future labels', () => {
  const result = parseForecastBundle(bundle());
  assert.equal(result.scenarios[0].frames[0].predicted_depth_cm, 9);
  assert.equal(trend(7, 9), 'Tăng dự kiến 2.0 cm');
});
test('reject live payload and invalid coordinates', () => {
  assert.throws(() => parseForecastBundle({ ...bundle(), mode: 'live' }));
  const data = bundle();
  data.scenarios[0].station.latitude = 100;
  assert.throws(() => parseForecastBundle(data));
});
test('reject duplicate/out-of-order time and partial missing values', () => {
  const data = bundle();
  data.scenarios[0].frames.push({ ...data.scenarios[0].frames[0] });
  assert.throws(() => parseForecastBundle(data));
  const frame = bundle();
  frame.scenarios[0].frames[0].baseline_depth_cm = 8;
  assert.throws(() => parseForecastBundle(frame));
});
test('reject nonfinite depth, invalid version and empty input', () => {
  const data = bundle();
  data.scenarios[0].frames[0].predicted_depth_cm = Infinity;
  assert.throws(() => parseForecastBundle(data));
  assert.throws(() => parseForecastBundle({ ...bundle(), schema_version: 2 }));
  assert.throws(() => parseForecastBundle(null));
});
test('rounding never implies a below-threshold number has crossed the boundary', () => {
  assert.equal(formatDepth(9.99), '<10,0 cm');
  assert.equal(formatDepth(10), '10,0 cm');
  assert.equal(formatDepth(null), '—');
});
