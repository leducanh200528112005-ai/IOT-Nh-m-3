"""
Sinh tập dữ liệu huấn luyện chuỗi thời gian mực nước ngập đô thị.
Sử dụng thuần NumPy (không cần pandas).
Mô phỏng các đợt mưa bão thực tế tại Hà Nội:
- Mưa rào cường độ lớn (dâng nhanh 1-3 cm/phút)
- Mưa phùn/mưa vừa (dâng chậm 0.2-0.5 cm/phút)
- Tạnh mưa/nước rút (rút 0.3-0.8 cm/phút)
- Giai đoạn khô ráo bình thường (0-2 cm)
- Nhiễu cảm biến siêu âm (+/- 0.4 cm)
"""
import numpy as np

FEATURE_NAMES = [
    "depth_current",
    "depth_lag_5m",
    "depth_lag_10m",
    "rate_5m",
    "rate_10m",
    "accel",
    "ratio_to_danger",
]


def generate_synthetic_flood_data(n_events: int = 400, random_state: int = 42):
    np.random.seed(random_state)
    X_list = []
    y_15m_list = []
    y_30m_list = []
    y_danger_list = []

    for _ in range(n_events):
        duration = np.random.randint(60, 180)
        base_level = np.random.uniform(0.0, 3.0)
        rain_peak_min = np.random.randint(20, duration - 30)
        max_surge = np.random.uniform(15.0, 55.0)

        depths = []
        for t in range(duration):
            if t <= rain_peak_min:
                progress = t / rain_peak_min
                depth = base_level + max_surge * (progress ** 2.2)
            else:
                drain_progress = (t - rain_peak_min) / (duration - rain_peak_min)
                depth = base_level + max_surge * np.exp(-2.5 * drain_progress)
            
            noise = np.random.normal(0, 0.35)
            depth = max(0.0, depth + noise)
            depths.append(depth)

        for t in range(10, duration - 30):
            current = depths[t]
            lag_5 = depths[t - 5]
            lag_10 = depths[t - 10]
            
            rate_5m = (current - lag_5) / 5.0
            rate_10m = (current - lag_10) / 10.0
            accel = rate_5m - rate_10m
            ratio_to_danger = current / 30.0
            
            target_15m = depths[t + 15]
            target_30m = depths[t + 30]
            danger = 1.0 if (target_15m >= 30.0 or target_30m >= 30.0) else 0.0
            
            X_list.append([current, lag_5, lag_10, rate_5m, rate_10m, accel, ratio_to_danger])
            y_15m_list.append(target_15m)
            y_30m_list.append(target_30m)
            y_danger_list.append(danger)

    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_15m_list, dtype=np.float32),
        np.array(y_30m_list, dtype=np.float32),
        np.array(y_danger_list, dtype=np.float32),
    )


if __name__ == "__main__":
    X, y15, y30, yd = generate_synthetic_flood_data(n_events=50)
    print(f"Generated {X.shape[0]} samples with {X.shape[1]} features.")
    print(f"Mean current depth: {X[:, 0].mean():.2f} cm")
    print(f"Mean 15m depth: {y15.mean():.2f} cm")
    print(f"Danger ratio: {yd.mean() * 100:.1f}%")
