import { LEVEL_INFO } from '../utils/status';

export default function Legend() {
  return (
    <section className="panel" aria-label="Chú giải">
      <h2>Chú giải</h2>
      <p className="sub">Màu = mức ngập</p>
      <ul className="legend">
        {(Object.keys(LEVEL_INFO) as (keyof typeof LEVEL_INFO)[]).map((k) => (
          <li key={k}>
            <span className="dot" style={{ background: LEVEL_INFO[k].color }} />
            {LEVEL_INFO[k].label}
          </li>
        ))}
      </ul>
      <p className="sub">Viền = chất lượng dữ liệu</p>
      <ul className="legend">
        <li><span className="dot solid" style={{ background: '#2f9e6e' }} />Viền liền: dữ liệu mới</li>
        <li><span className="dot dashed" style={{ background: '#e3b505' }} />Viền đứt, mờ: dữ liệu cũ</li>
        <li><span className="dot dashed" style={{ background: '#8a949e' }} />Xám: mất dữ liệu, không rõ mức ngập</li>
        <li><span className="zone" />Vùng cấm đi qua</li>
      </ul>
    </section>
  );
}
