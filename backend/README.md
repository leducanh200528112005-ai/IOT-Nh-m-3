# Backend FastAPI

## Phạm vi hiện tại

- Hai bảng `stations`, `measurements` và migration Alembic.
- Nhận MQTT QoS 1, kiểm tra payload/topic, chống trùng ở database.
- API trạng thái, kiểm tra sẵn sàng và vùng cấm GeoJSON.
- Chưa tích hợp ORS/tìm đường; không có endpoint giả trả tuyến chưa kiểm tra.
- Chưa có đăng nhập/phân quyền HTTP; chỉ dùng môi trường phát triển/LAN tin cậy.

## 1. Cài đặt

Cần Python **3.12** và hạ tầng đang chạy. Không dùng Python 3.15 cho môi trường này.

```powershell
cd D:\CODE\IOT\infra
docker compose up -d --wait
cd ..\backend
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py
```

Setup chỉ tạo `.env` nếu chưa có, lấy thông tin đăng nhập từ `infra/.env`; không tự đồng bộ nếu sau đó thay đổi mật khẩu. Không commit file bí mật. Tọa độ trạm seed chỉ là minh họa, cần cập nhật trước thử nghiệm thực tế. Seed chạy lại không ghi đè trạm đã tồn tại.

## 2. Chạy

```powershell
cd D:\CODE\IOT\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

- Swagger: <http://localhost:8000/docs>
- Liveness: `GET /api/health`
- Readiness DB/schema/MQTT: `GET /api/ready`
- Trạng thái và vùng cấm: `GET /api/flood-zones`

Chạy **một worker** vì MQTT subscriber nằm trong ứng dụng. Khi phát triển có thể thêm `--reload`, nhưng chỉ chạy một instance dùng client ID này. Nếu cần frontend truy cập qua LAN, cấu hình host/CORS thích hợp và firewall, không công khai API ra Internet.

## 3. Gửi số đo mô phỏng

Trong terminal khác, tại `backend`:

```powershell
.\.venv\Scripts\python.exe scripts\simulate.py --depth 23
.\.venv\Scripts\python.exe scripts\simulate.py --depth 15
.\.venv\Scripts\python.exe scripts\simulate.py --invalid
```

Script dùng tài khoản station-01 từ `infra/.env`, chỉ để phát triển local. Các lệnh này tạo lịch sử số đo thật cho trạm thử nghiệm, không tự xóa sau chạy.

Backend đọc topic `flood/+/telemetry`. Status online/offline chưa được lưu; độ mới số đo là nguồn xác định dữ liệu còn dùng được. MQTT chỉ báo kết nối trong readiness, chưa xác nhận SUBACK.

Payload:

```json
{
  "device_id": "station-01",
  "boot_id": "unique-per-reboot",
  "seq": 1,
  "measured_at": "2026-11-07T08:30:00Z",
  "water_depth_cm": 23,
  "sensor_ok": true
}
```

- Timestamp phải có timezone; thời gian tương lai quá 30 giây bị từ chối.
- Chưa đồng bộ giờ: `measured_at = null`. Bản tin vẫn lưu nhưng không được coi là dữ liệu mới đủ tin cậy.
- Lỗi phép đo: `sensor_ok = false`, `water_depth_cm = null`.
- Trạm chưa đăng ký hoặc inactive bị từ chối.
- Chống trùng: `(station_id, boot_id, seq)`.

## 4. Quy tắc trạng thái

- `< 10 cm`: normal; `10–20 cm`: warning; `> 20 cm`: danger, theo cấu hình từng trạm.
- Mặc định quá 15 giây: stale. Lỗi cảm biến: invalid. Chưa có dữ liệu: missing.
- Khi chất lượng không fresh, hazard_state là unknown, không phải normal.
- Số đo có timestamp được sắp theo thời điểm đo để tránh bản tin cũ đến muộn ghi đè trạng thái mới.
- Khi mất dữ liệu và số đo hợp lệ cuối là nguy hiểm, giữ vùng cấm, gắn `retained_due_to_uncertainty`.
- `routing_data_sufficient = false` nếu thiếu trạm hoạt động hoặc có bất kỳ trạm hoạt động nào không fresh.
- Vùng cấm là giả định thử nghiệm; không bảo đảm phạm vi ngập thực. Buffer theo mét dùng phép chiếu cục bộ trước khi đổi sang GeoJSON `[longitude, latitude]`.
- Chưa có hàng đợi lưu bền/gửi bù. MQTT ACK không đảm bảo DB đã ghi thành công; lỗi DB được ghi log. Nếu cần độ tin cậy cao hơn phải bổ sung cơ chế này.

## 5. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Integration test cần PostgreSQL đã migrate, tạo trạm test có mã ngẫu nhiên rồi dọn dữ liệu của chính trạm đó:

```powershell
$env:RUN_DATABASE_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_DATABASE_TESTS
```

Kiểm tra xuyên suốt MQTT thật → DB → HTTP (cần seed `station-01` và broker local, không chạy đồng thời backend có client ID trùng):

```powershell
$env:RUN_MQTT_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_mqtt_integration.py -q
Remove-Item Env:RUN_MQTT_TESTS
```

Smoke test này tạo số đo tạm thời trên trạm demo rồi xóa đúng bản ghi của nó; không chạy trên môi trường thật đang vận hành.

Chỉ chạy integration test trên môi trường phát triển. Đổi schema bằng Alembic, không dùng `create_all` khi ứng dụng khởi động.
