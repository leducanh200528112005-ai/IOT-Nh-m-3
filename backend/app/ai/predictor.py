"""
Module tải mô hình và thực hiện dự báo nguy cơ ngập lụt bằng AI.
"""
from functools import lru_cache
from pathlib import Path
from typing import TypedDict
import joblib
import numpy as np

MODEL_DIR = Path(__file__).resolve().parent


class PredictionResult(TypedDict):
    depth_current: float
    rate_cm_per_min: float
    predicted_15m: float
    predicted_30m: float
    danger_probability: float
    is_predicted_danger: bool
    warning_message: str | None


@lru_cache(maxsize=1)
def load_models():
    m15 = joblib.load(MODEL_DIR / "model_15m.joblib")
    m30 = joblib.load(MODEL_DIR / "model_30m.joblib")
    clf = joblib.load(MODEL_DIR / "classifier_danger.joblib")
    return m15, m30, clf


def predict_flood_risk(
    depth_current: float,
    depth_lag_5m: float | None = None,
    depth_lag_10m: float | None = None,
    danger_threshold_cm: float = 30.0,
) -> PredictionResult:
    """
    Dự báo mực nước sau 15 và 30 phút, đánh giá nguy cơ ngập lụt đỏ.
    Nếu không có lag_5m hoặc lag_10m, có thể suy ra từ tốc độ hoặc giả định không đổi.
    """
    if depth_lag_5m is None:
        depth_lag_5m = depth_current
    if depth_lag_10m is None:
        depth_lag_10m = depth_lag_5m

    rate_5m = (depth_current - depth_lag_5m) / 5.0
    rate_10m = (depth_current - depth_lag_10m) / 10.0
    accel = rate_5m - rate_10m
    ratio_to_danger = depth_current / max(1.0, danger_threshold_cm)

    features = np.array([[depth_current, depth_lag_5m, depth_lag_10m, rate_5m, rate_10m, accel, ratio_to_danger]], dtype=np.float32)

    m15, m30, clf = load_models()
    pred_15 = float(m15.predict(features)[0])
    pred_30 = float(m30.predict(features)[0])
    danger_prob = float(clf.predict_proba(features)[0, 1])

    # Điều kiện kích hoạt cảnh báo nguy cơ ngập đỏ sớm:
    # 1. Dự báo 15 hoặc 30 phút vượt ngưỡng đỏ (>= 30cm)
    # 2. Hoặc xác suất ngập đỏ >= 50% khi tốc độ dâng nhanh
    is_predicted_danger = False
    warning_msg = None

    if depth_current < danger_threshold_cm:
        if pred_15 >= danger_threshold_cm or pred_30 >= danger_threshold_cm or danger_prob >= 0.5:
            is_predicted_danger = True
            warning_msg = (
                f"🤖 AI CẢNH BÁO SỚM: Mực nước đang dâng (+{rate_10m * 10:.1f} cm/10p). "
                f"Dự báo đạt {pred_15:.1f} cm sau 15p (vượt ngưỡng {danger_threshold_cm:.0f}cm). "
                f"Tuyến đường đã tự động né vị trí này!"
            )

    return {
        "depth_current": round(depth_current, 1),
        "rate_cm_per_min": round(rate_10m, 2),
        "predicted_15m": round(max(0.0, pred_15), 1),
        "predicted_30m": round(max(0.0, pred_30), 1),
        "danger_probability": round(danger_prob * 100, 1),
        "is_predicted_danger": is_predicted_danger,
        "warning_message": warning_msg,
    }


if __name__ == "__main__":
    # Test 1: Nước 5cm lên 12cm trong 10 phút (dâng nhanh)
    res = predict_flood_risk(depth_current=12.0, depth_lag_5m=8.0, depth_lag_10m=5.0, danger_threshold_cm=30.0)
    print("Test 1 (Dâng nhanh):", res)

    # Test 2: Nước ổn định 5cm
    res2 = predict_flood_risk(depth_current=5.0, depth_lag_5m=5.0, depth_lag_10m=5.0, danger_threshold_cm=30.0)
    print("Test 2 (Ổn định):", res2)
