# Backend FastAPI

## Phạm vi hiện tại

- Hai bảng `stations`, `measurements` và migration Alembic.
- Nhận MQTT QoS 1, kiểm tra payload/topic, chống trùng ở database.
- API trạng thái, kiểm tra sẵn sàng và vùng cấm GeoJSON.
- Tích hợp ORS với `driving-car`, tối đa hai lần gọi cho mỗi yêu cầu; không trả tuyến chưa kiểm tra.
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
- Tìm đường: `POST /api/routes/safe`

Chạy **một worker** vì MQTT subscriber nằm trong ứng dụng. Khi phát triển có thể thêm `--reload`, nhưng chỉ chạy một instance dùng client ID này. Nếu cần frontend truy cập qua LAN, cấu hình host/CORS thích hợp và firewall, không công khai API ra Internet.

## 3. Gửi số đo mô phỏng

Trong terminal khác, tại `backend`:

```powershell
.\.venv\Scripts\python.exe scripts\simulate.py --depth 23
.\.venv\Scripts\python.exe scripts\simulate.py --device-id station-02 --depth 15
.\.venv\Scripts\python.exe scripts\simulate.py --invalid
```

Script dùng tài khoản `station` dùng chung từ `infra/.env`, chỉ để phát triển local. `--device-id` chọn trạm (mặc định `station-01`); trạm phải có trong bảng `stations`. Các lệnh này tạo lịch sử số đo thật cho trạm thử nghiệm, không tự xóa sau chạy.

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

## 6. OpenRouteService

Thêm vào `backend/.env` (không đưa khóa thật lên Git):

```dotenv
ORS_API_KEY=your_key_here
ORS_BASE_URL=https://api.heigit.org/openrouteservice
ORS_ALTERNATIVE_ROUTES_ENABLED=true
ORS_ALTERNATIVE_TARGET_COUNT=3
ORS_ALTERNATIVE_WEIGHT_FACTOR=1.4
ORS_ALTERNATIVE_SHARE_FACTOR=0.6
ROUTE_WARNING_PROXIMITY_LIMIT_M=50
ROUTE_WARNING_PROXIMITY_ETA_TOLERANCE_S=60
ORS_TIMEOUT_SECONDS=15
ORS_MAX_SNAP_M=50
```

Khởi động lại backend sau khi sửa cấu hình. Nếu `.env` còn trỏ đến `api.openrouteservice.org`, đổi sang URL mới ở trên. ORS có thể trả ít tuyến hơn `TARGET_COUNT` (1–3); tắt `ENABLED` để chỉ trả một tuyến. `WEIGHT_FACTOR` giới hạn chi phí đi vòng theo ORS; `SHARE_FACTOR` giới hạn phần trùng với tuyến tối ưu của ORS. Hai giá trị này không phải điểm rủi ro ngập. Valhalla/OSRM cũng trả không quá số tuyến đã cấu hình, nhưng hai hệ số ORS không điều khiển cách các dịch vụ đó sinh ứng viên.

### Request

```http
POST /api/routes/safe
Content-Type: application/json
```

```json
{
  "start": {"longitude": 106.7001, "latitude": 10.7701},
  "end": {"longitude": 106.7201, "latitude": 10.7901}
}
```

Tọa độ trên chỉ minh họa. Chọn hai điểm trên đường, ngoài vùng cấm. API yêu cầu mọi trạm hoạt động đều có số đo fresh; không có trạm, thiếu đồng bộ giờ, dữ liệu lỗi/quá hạn thì từ chối. Với timeout ORS 15 giây, số đo có thể quá hạn trong lúc chờ, nên cần ESP32 hoặc nguồn mô phỏng tiếp tục gửi dữ liệu khi thử.

### Response thành công

- `routes[]`: danh sách xếp hạng, mỗi phần tử có `id`, `rank`, `route` (GeoJSON LineString theo `[longitude, latitude]`), khoảng cách, thời gian và `assessment`.
- `assessment`: độ dài trong hợp các vùng `warning`, số vùng giao, thông tin trạm liên quan và `nearest_warning_zone_distance_m` (xem bên dưới). Chỉ vùng `danger`/`predicted_danger` (và vùng nguy hiểm được giữ lại) dùng để tránh cứng; vùng `warning` không gửi vào `avoid_polygons`.
- `recommended_route_id`, `requested_route_count`, `returned_route_count`, `ranking_policy`, `ranking_parameters`: tuyến đề xuất, số tuyến mục tiêu/số thực trả, quy tắc và tham số xếp hạng.
- `route` và các trường một tuyến cũ phản ánh tuyến đề xuất để giữ tương thích.
- `distance_m`, `duration_s`: khoảng cách và thời gian phần tuyến trên đường.
- `calculated_at`, `data_generated_at`: thời điểm tính và snapshot kiểm tra cuối.
- `profile`, `engine`: profile và dịch vụ định tuyến thực tế.
- `snap_distances_m`: khoảng cách từ hai điểm chọn tới điểm đường ORS dùng.
- `warnings`: các giới hạn cần hiển thị cho người dùng.

Backend kiểm tra tuyến và đoạn nối tới hai điểm chọn không giao/chạm vùng cấm. Đoạn nối chỉ được kiểm tra hình học, không được xác nhận là đường đi được và không cộng vào distance/duration. Backend không chuyển tiếp metadata ORS hoặc khóa API.

Trước khi trả kết quả, backend đọc lại trạng thái trạm và kiểm tra từng ứng viên. Nếu dữ liệu quá hạn thì từ chối; nếu mọi tuyến ORS hợp lệ về snap đều giao vùng cấm, thử thêm tối đa một lần với biên 20 m quanh vùng cấm hiện tại. Không trả tuyến chưa qua kiểm tra.

### Xếp hạng theo khoảng cách đến vùng cảnh báo

1. Ưu tiên tuyến có ít mét nằm **trong** vùng cảnh báo hơn (so đến 0,1 m; phần vùng chồng nhau không cộng trùng).
2. Trong các tuyến cùng mức phơi nhiễm, nhóm các tuyến có thời gian chênh không quá `ROUTE_WARNING_PROXIMITY_ETA_TOLERANCE_S` (mặc định 60 giây) so với tuyến nhanh nhất còn lại. Xếp nhóm nhanh hơn trước. Trong từng nhóm, ưu tiên tuyến có khoảng cách gần nhất tới vùng cảnh báo **lớn hơn**.
3. Khi xếp hạng, mọi khoảng cách từ `ROUTE_WARNING_PROXIMITY_LIMIT_M` trở lên được xem là ngang nhau (mặc định 50 m; đặt 0 để tắt tiêu chí khoảng cách). Nếu vẫn ngang nhau, ưu tiên thời gian ngắn hơn rồi quãng đường ngắn hơn.

Ví dụ: hai tuyến không cắt vùng cảnh báo, chỗ gần nhất của A cách mép 5 m và của B cách 30 m. Nếu B chỉ chậm hơn 20 giây, B được ưu tiên theo cấu hình mặc định. Nếu B chậm hơn 90 giây, A đứng trước. Khoảng cách là khoảng cách ngắn nhất từ phần tuyến trên đường đến đa giác `warning`, không phải tới tâm trạm hay trung bình toàn tuyến. API trả số đo đến 0,1 m (0 nếu chạm/cắt vùng, `null` nếu không có vùng cảnh báo đã biết); giới hạn 50 m chỉ dùng để xếp hạng, không cắt số hiển thị.

Vùng cảnh báo là vùng đệm cấu hình, không phải ranh giới ngập thực tế. Phép đo hai chiều chưa phân biệt cầu vượt, hầm và đường song song; chưa tự miễn đánh giá cho các đoạn này. Chỉ cân nhắc ngoại lệ theo đoạn đường sau khi xác minh được tuyến đi trên hay dưới, và không dùng ngoại lệ để bỏ vùng cấm. Không suy ra tuyến xa vùng cảnh báo hơn là an toàn hoặc phần ngoài vùng giám sát là khô.

### Lỗi

Envelope: `{"error": {"code": "...", "message": "..."}}`.

| HTTP | Code | Ý nghĩa |
|---|---|---|
| 422 | `INVALID_INPUT` | Tọa độ/request sai hoặc hai điểm trùng nhau |
| 409 | `INSUFFICIENT_DATA` | Không đủ dữ liệu mới và hợp lệ |
| 422 | `POINT_IN_FLOOD_ZONE` | Điểm đi/đến nằm trong hoặc chạm vùng cấm |
| 422 | `NO_SUITABLE_ROUTE` | Không có tuyến hợp lệ hoặc điểm snap quá xa |
| 429 | `ROUTING_RATE_LIMITED` | ORS giới hạn lượt gọi |
| 502/503 | `ROUTING_UNAVAILABLE` | Thiếu key, xác thực ORS lỗi, timeout hoặc response không hợp lệ |

Không tự gọi API tìm đường theo polling. Hiện chưa có rate limit riêng cho HTTP API; chỉ dùng môi trường phát triển/LAN tin cậy, cần bổ sung trước khi public để tránh lạm dụng quota ORS. Timeout là giới hạn HTTPX theo từng pha I/O, không phải cam kết tổng thời gian xử lý.

### Kiểm tra kết nối ORS thật

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_ors
.\.venv\Scripts\python.exe -m scripts.smoke_ors --with-avoid
```

Script dùng tọa độ công khai tại Heidelberg và có thể thêm một vùng cấm giả lập để kiểm tra `alternative_routes` cùng `avoid_polygons`. Không ghi DB hay thay đổi trạm. Các test tự động `tests/test_routing.py` dùng mock, không tiêu tốn quota.

## 7. Điểm demo và kết hợp dữ liệu thật

Bảng `demo_points` tách biệt hoàn toàn `stations` và `measurements`. Cập nhật schema trước khi dùng:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Bật chức năng trong `backend/.env`, rồi khởi động lại backend:

```dotenv
DEMO_ENABLED=true
```

Mặc định code là `false`. Khi tắt, API quản lý và yêu cầu lấy nguồn demo trả `403 DEMO_DISABLED`. Hiện API demo chưa có xác thực, chỉ bật ở môi trường local/LAN tin cậy; đây không phải cơ chế phân quyền cho môi trường công khai. Máy phát triển hiện tại đã được bật demo.

### Quản lý điểm

| Endpoint | Chức năng |
|---|---|
| `GET /api/demo-points` | Liệt kê cả điểm bật và tắt |
| `POST /api/demo-points` | Tạo điểm, trả 201 |
| `PATCH /api/demo-points/{id}` | Chỉnh một hoặc nhiều trường |
| `DELETE /api/demo-points/{id}` | Xóa điểm, trả 204 |

Ví dụ tạo:

```json
{
  "name": "Điểm ngập mô phỏng",
  "latitude": 20.9826,
  "longitude": 105.7704,
  "water_depth_cm": 25,
  "warning_threshold_cm": 10,
  "danger_threshold_cm": 20,
  "exclusion_radius_m": 40,
  "is_active": true
}
```

Ngưỡng đỏ phải lớn hơn ngưỡng vàng; độ sâu 0–10000 cm; bán kính lớn hơn 0 và tối đa 1000 m. PATCH không nhận null. Điểm không tồn tại trả `404 DEMO_POINT_NOT_FOUND`.

### Chọn nguồn cho bản đồ và định tuyến

- Thực tế (mặc định): `GET /api/flood-zones`.
- Chỉ demo: `GET /api/flood-zones?source=demo`.
- Demo kết hợp thật: `GET /api/flood-zones?source=demo&include_real=true`.

`POST /api/routes/safe` nhận thêm `source` và `include_real` với cùng ý nghĩa:

```json
{
  "source": "demo",
  "include_real": true,
  "start": {"longitude": 105.765, "latitude": 20.98},
  "end": {"longitude": 105.78, "latitude": 20.99}
}
```

- `source=real` không cho phép `include_real=true` (422).
- Điểm demo bật luôn `fresh`, không cần MQTT, không tự quá hạn và không giả mạo timestamp đo. Mức ngập vẫn do backend tính từ độ sâu/ngưỡng.
- Điểm demo tắt không tham gia snapshot hoặc định tuyến. Nếu không có điểm hoạt động nào, dữ liệu không đủ để định tuyến.
- Khi kết hợp, trạm thật vẫn kiểm tra cảm biến/độ mới như cũ; chỉ một trạm thật không fresh cũng có thể chặn định tuyến. Không bật kết hợp nếu muốn demo độc lập phần cứng.
- Cả hai nguồn cùng áp dụng chặn điểm đi/đến trong vùng cấm, kiểm tra tuyến giao vùng cấm và đọc lại snapshot sau ORS.
- Snapshot trả `source`, `include_real`, nguồn từng station/feature. Response tuyến có cùng nhãn nguồn và cảnh báo mô phỏng. Tuyến được ORS tính thật, không phải tuyến giả.

Giao diện quản lý riêng tại `http://localhost:5173/demo`. Trang bản đồ có lựa chọn nguồn và checkbox **Bao gồm trạm thực tế**; đổi nguồn sẽ hủy yêu cầu đang chạy và xóa tuyến/điểm chọn cũ để không trộn kết quả.

## 8. Cấu hình trạm thật

Bảng `stations` đã có từ migration `0001`, không cần migration mới. Bật chức năng trong `backend/.env`, rồi khởi động lại backend:

```dotenv
STATIONS_ENABLED=true
```

Mặc định là `false`. Khi tắt, mọi endpoint `/api/stations` trả `403 STATIONS_DISABLED`. Tách riêng khỏi `DEMO_ENABLED` để có thể bật demo trên máy dev mà không cho ai sửa trạm đang chạy thật.

| Endpoint | Chức năng |
|---|---|
| `GET /api/stations` | Liệt kê cả trạm bật và tắt |
| `POST /api/stations` | Tạo trạm, trả 201 |
| `PATCH /api/stations/{id}` | Chỉnh một hoặc nhiều trường |
| `DELETE /api/stations/{id}` | Xóa trạm, trả 204 |

Ví dụ tạo:

```json
{
  "id": "station-02",
  "name": "Ngã tư Hàng Xanh",
  "latitude": 10.8012,
  "longitude": 106.7108,
  "warning_threshold_cm": 10,
  "danger_threshold_cm": 20,
  "exclusion_radius_m": 40,
  "is_active": true
}
```

- `id` là `device_id` trong topic `flood/<id>/telemetry`; chỉ gồm chữ, số, `_`, `-`. **Không sửa được sau khi tạo** vì gắn với lịch sử số đo và firmware.
- Tạo trùng mã trả `409 STATION_EXISTS`.
- Xóa trạm đã có số đo trả `409 STATION_HAS_MEASUREMENTS`; dùng `is_active=false` để giữ lịch sử.
- Trạm không tồn tại trả `404 STATION_NOT_FOUND`; ngưỡng sai trả `422 INVALID_INPUT`.
- API này chưa có đăng nhập và sửa được trạm thật: chỉ bật ở local/LAN tin cậy.

Giao diện tại `http://localhost:5173/stations`: chọn vị trí trên bản đồ hoặc kéo marker **T**, và xem trạng thái `fresh/stale/invalid/missing` cùng độ ngập hiện tại của từng trạm ngay trong danh sách.

Sau khi tạo trạm trên web, nạp cùng `device_id` vào firmware ESP32. Broker dùng chung tài khoản `station` với ACL `flood/+/telemetry`, nên không cần sửa gì thêm trong Mosquitto.
