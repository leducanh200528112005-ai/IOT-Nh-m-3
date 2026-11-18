"""
Huấn luyện mô hình Machine Learning dự báo mực nước và nguy cơ ngập lụt.
Sử dụng Gradient Boosting / Random Forest từ scikit-learn.
Đầu ra mô hình được lưu vào thư mục backend/app/ai/.
"""
from pathlib import Path
import joblib
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.ai.dataset import generate_synthetic_flood_data, FEATURE_NAMES

MODEL_DIR = Path(__file__).resolve().parent


def train_models():
    print("1. Đang sinh tập dữ liệu mô phỏng mưa bão Hà Nội...")
    X, y15, y30, yd = generate_synthetic_flood_data(n_events=600, random_state=42)
    print(f"   Tổng số mẫu: {len(X):,} dòng dữ liệu với {len(FEATURE_NAMES)} đặc trưng.")

    # Phân chia tập train/test (80/20)
    indices = range(len(X))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42)

    X_train, X_test = X[train_idx], X[test_idx]
    y15_train, y15_test = y15[train_idx], y15[test_idx]
    y30_train, y30_test = y30[train_idx], y30[test_idx]
    yd_train, yd_test = yd[train_idx], yd[test_idx]

    print("\n2. Đang huấn luyện Model 1: Dự báo mực nước sau 15 phút (Regression)...")
    model_15m = GradientBoostingRegressor(n_estimators=120, max_depth=4, learning_rate=0.08, random_state=42)
    model_15m.fit(X_train, y15_train)
    pred_15m = model_15m.predict(X_test)
    mae_15 = mean_absolute_error(y15_test, pred_15m)
    r2_15 = r2_score(y15_test, pred_15m)
    print(f"   MAE (15 phút): {mae_15:.2f} cm | R2-Score: {r2_15:.4f}")

    print("\n3. Đang huấn luyện Model 2: Dự báo mực nước sau 30 phút (Regression)...")
    model_30m = GradientBoostingRegressor(n_estimators=120, max_depth=4, learning_rate=0.08, random_state=42)
    model_30m.fit(X_train, y30_train)
    pred_30m = model_30m.predict(X_test)
    mae_30 = mean_absolute_error(y30_test, pred_30m)
    r2_30 = r2_score(y30_test, pred_30m)
    print(f"   MAE (30 phút): {mae_30:.2f} cm | R2-Score: {r2_30:.4f}")

    print("\n4. Đang huấn luyện Model 3: Phân loại nguy cơ ngập đỏ >=30cm (Classification)...")
    classifier_danger = GradientBoostingClassifier(n_estimators=100, max_depth=4, learning_rate=0.08, random_state=42)
    classifier_danger.fit(X_train, yd_train)
    prob_danger = classifier_danger.predict_proba(X_test)[:, 1]
    auc_danger = roc_auc_score(yd_test, prob_danger)
    print(f"   ROC-AUC Score: {auc_danger:.4f}")

    # In độ quan trọng đặc trưng (Feature Importance)
    print("\n5. Tầm quan trọng của các đặc trưng (Feature Importances):")
    for name, imp in zip(FEATURE_NAMES, model_15m.feature_importances_):
        print(f"   - {name:<18}: {imp * 100:.2f}%")

    # Lưu models
    joblib.dump(model_15m, MODEL_DIR / "model_15m.joblib")
    joblib.dump(model_30m, MODEL_DIR / "model_30m.joblib")
    joblib.dump(classifier_danger, MODEL_DIR / "classifier_danger.joblib")
    joblib.dump(FEATURE_NAMES, MODEL_DIR / "feature_names.joblib")

    print("\nĐã lưu các mô hình thành công vào thư mục:", MODEL_DIR)
    return {
        "mae_15m": float(mae_15),
        "r2_15m": float(r2_15),
        "mae_30m": float(mae_30),
        "r2_30m": float(r2_30),
        "auc": float(auc_danger),
    }


if __name__ == "__main__":
    train_models()
