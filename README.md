# Hệ thống IoT cảnh báo ngập

## 1. Cấu trúc dự án

```text
IOT/
├── infra/       # Docker Compose, PostgreSQL, Mosquitto
├── backend/     # FastAPI, MQTT subscriber, migration và kiểm thử
└── frontend/    # Dự kiến: React + TypeScript + Vite
```

Hạ tầng và backend đã được khởi tạo. Frontend chưa triển khai. Backend hiện có API trạng thái/vùng ngập; phần gọi ORS sẽ được bổ sung sau.

### Chạy backend

Cần Python 3.12. Khởi chạy hạ tầng ở các bước dưới trước, rồi:

```powershell
cd D:\CODE\IOT\backend
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Mở <http://localhost:8000/docs> để thử API. Máy hiện tại đã cài môi trường, migrate và seed; những lần sau chỉ cần chạy lệnh Uvicorn sau khi mở hạ tầng. Chi tiết: [backend/README.md](backend/README.md).

## 2. Yêu cầu

- Cài và mở Docker Desktop, dùng Linux containers với WSL 2 trên Windows.
- Có Internet để tải image lần đầu.
- Cổng `5432` và `1883` chưa bị ứng dụng khác chiếm.
- **Nếu không muốn dùng docker thì tải trực tiếp posgres và mosquitto broker về máy theo phiên bản được sử dụng trong file compose.yaml**

Kiểm tra trong PowerShell:

```powershell
docker --version
docker compose version
```

## 3. Chạy lần đầu trên máy mới

Mở PowerShell và chạy:

```powershell
cd D:\CODE\IOT\infra
powershell -ExecutionPolicy Bypass -File .\setup.ps1
docker compose up -d --wait
docker compose ps
```

Script `setup.ps1` tạo mật khẩu ngẫu nhiên trong `.env` và tài khoản MQTT trong `mosquitto/config/passwords` nếu các file này chưa tồn tại. Chạy lại không ghi đè mật khẩu đã có.

Kết quả mong đợi:

- `postgres`: đang chạy và có trạng thái `healthy`.
- `mosquitto`: đang chạy (`Up`).

**Máy hiện tại đã được thiết lập**, có thể bỏ qua bước chạy `setup.ps1`.

## 4. Chạy lại và xem log

Mở Docker Desktop trước, sau đó:

```powershell
cd D:\CODE\IOT\infra
docker compose up -d --wait
docker compose ps
```

Xem log gần nhất:

```powershell
docker compose logs --tail=100 postgres mosquitto
```

Theo dõi log trực tiếp:

```powershell
docker compose logs -f
```

Nhấn `Ctrl+C` để thoát theo dõi log; container vẫn tiếp tục chạy.

Nếu muốn giữ PowerShell tại thư mục gốc dự án, có thể dùng:

```powershell
cd D:\CODE\IOT
docker compose --env-file .\infra\.env -f .\infra\compose.yaml up -d --wait
docker compose --env-file .\infra\.env -f .\infra\compose.yaml ps
```

## 5. Kết nối các dịch vụ

### PostgreSQL — DBeaver hoặc backend trên laptop

| Thông số | Giá trị |
|---|---|
| Image | `postgres:17` |
| Host | `localhost` |
| Port | `5432` |
| Database | `flood_monitor` |
| Username | `flood_admin` |
| Password | Giá trị `POSTGRES_PASSWORD` trong `infra/.env` |

PostgreSQL chỉ mở cổng trên laptop, không mở ra LAN. Kiểm tra kết nối từ thư mục `infra`:

```powershell
docker compose exec postgres psql -U flood_admin -d flood_monitor -c "SELECT current_database(), current_user;"
```

### Mosquitto — ESP32 và backend

| Client | Host | Port | Username | Password trong `infra/.env` |
|---|---|---|---|---|
| Backend chạy trực tiếp trên laptop | `localhost` | `1883` | `backend` | `MQTT_BACKEND_PASSWORD` |
| ESP32 cùng mạng Wi-Fi | IP LAN của laptop | `1883` | `station-01` | `MQTT_STATION_PASSWORD` |

- Image: `eclipse-mosquitto:2.0.22`.
- ESP32 gửi QoS 1 tới `flood/station-01/telemetry` và `flood/station-01/status`.
- Backend subscribe QoS 1 tới `flood/+/telemetry` và `flood/+/status`.
- ESP32 **không dùng `localhost`**. Chạy `ipconfig` để tìm IPv4 của Wi-Fi laptop.
- Nếu ESP32 không kết nối được, kiểm tra cùng mạng Wi-Fi, client isolation và quyền TCP `1883` trên Windows Firewall (profile Private, phạm vi Local subnet).
- MQTT chưa có TLS, chỉ dùng trong LAN tin cậy; không mở cổng ra Internet.

Nếu backend sau này cũng chạy trong cùng Docker Compose, dùng host `postgres` và `mosquitto` thay cho `localhost`.

## 6. Dừng và khởi động lại

Chạy các lệnh sau tại `D:\CODE\IOT\infra`.

Dừng container, giữ dữ liệu:

```powershell
docker compose stop
```

Khởi chạy lại:

```powershell
docker compose up -d --wait
```

Xóa container và network nhưng giữ named volume:

```powershell
docker compose down
```

**Không thêm `-v` vào lệnh `down` nếu cần giữ dữ liệu:** tùy chọn này xóa volume, bao gồm database. Volume không thay thế bản sao lưu.

## 7. Lưu ý và xử lý lỗi

- Không đưa `infra/.env` và `infra/mosquitto/config/passwords` lên Git hoặc chia sẻ công khai.
- Nếu Docker báo không kết nối được engine, mở Docker Desktop và chờ khởi động xong.
- Nếu cổng bị chiếm, kiểm tra dịch vụ PostgreSQL/Mosquitto khác đang chạy. Có thể đổi cổng bên trái trong `ports` của Compose rồi cập nhật thông tin kết nối client.
- Sửa `POSTGRES_PASSWORD` trong `.env` không đổi mật khẩu database đã khởi tạo; cần đổi bằng SQL.
- Sửa mật khẩu MQTT trong `.env` không tự cập nhật file hash của broker.
- Không tự đổi major PostgreSQL với volume cũ; cần backup và migration phù hợp.

Xem thêm cấu hình và cách thử MQTT trong [infra/README.md](infra/README.md).
