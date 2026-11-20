# Flood Map UI (nhóm 3)

React + TypeScript + Vite + Leaflet. Chỉ gọi backend nhóm 2: `GET /api/flood-zones` (poll 3–5 giây) và `POST /api/routes/safe` (khi bấm nút).

## Chạy
```bash
npm install
cp .env.example .env
npm run dev
npm run build
```

## Hợp đồng dữ liệu (xem src/types.ts)
- Mọi GeoJSON dùng thứ tự `[lng, lat]`; chuyển sang `[lat, lng]` duy nhất ở `src/utils/geo.ts`.
- Frontend chỉ gọi API thật, không dùng dữ liệu mock. Backend cần chạy tại `http://localhost:8000` (đổi `VITE_PROXY_TARGET` nếu cần). Khi deploy cần cấu hình reverse proxy `/api` hoặc `VITE_API_BASE_URL` và CORS phía backend.
- Dữ liệu dùng trực tiếp schema backend: `generated_at`, `stations`, `flood_zones`, `routing_data_sufficient`.
- `hazard_state`: `normal / warning / danger / unknown`; `data_quality`: `fresh / stale / invalid / missing`. Frontend không tự tính mức ngập; dữ liệu không fresh hiển thị xám/không rõ.
- Tìm đường gửi `start/end` với `latitude/longitude`; đọc `route`, `distance_m`, `duration_s`, `calculated_at` và hiển thị cảnh báo backend. Lỗi API được đọc từ `error.code/message`.
- Lỗi poll: giữ dữ liệu cũ + banner "không còn được cập nhật". Dữ liệu đổi/quá hạn: tuyến hiện tại chuyển nét đứt xám + cảnh báo, người dùng tự bấm "Tính lại tuyến".

## Cấu trúc
- `src/api/` gọi API (client có timeout, hủy request), `src/hooks/` polling và tìm đường, `src/components/` giao diện.

## Bản đồ nền
Mặc định dùng tile OSM; cần giữ attribution và tuân thủ chính sách tile của OSM (không tải hàng loạt, không dùng cho lưu lượng lớn). Production nên đổi `VITE_TILE_URL` sang nhà cung cấp phù hợp.
# Chế độ demo

- Mở `/demo` để tạo/sửa/xóa/bật/tắt điểm mô phỏng.
- Chọn tọa độ bằng click bản đồ rồi bấm **Lưu điểm**, hoặc nhập trực tiếp tọa độ.
- Kéo marker **D** để lưu vị trí mới. Marker tròn là trạm thật; marker vuông D là demo.
- Mực nước, ngưỡng vàng/đỏ và bán kính đều chỉnh được; ngưỡng đỏ phải lớn hơn ngưỡng vàng.
- Trên trang bản đồ `/`, chọn nguồn **Demo**. Có thể bật **Bao gồm trạm thực tế** để ghép hai nguồn.
- Điểm demo đang bật không tự quá hạn; trạm thật vẫn cần số đo mới/hợp lệ. Không có điểm nào hoạt động thì không đủ dữ liệu định tuyến.
- Backend cần migration mới nhất và `DEMO_ENABLED=true` trong `backend/.env`, sau đó khởi động lại.
- Đổi nguồn sẽ hủy/xóa tuyến cũ. Bản đồ và request định tuyến dùng cùng lựa chọn nguồn.
- API chỉnh sửa demo chưa có đăng nhập, chỉ sử dụng local/LAN tin cậy.

# Cấu hình trạm thật

- Mở `/stations` để tạo/sửa/tắt/xóa trạm thật. Cần `STATIONS_ENABLED=true` trong `backend/.env`.
- **Mã trạm** là `device_id` mà ESP32 gửi trong topic `flood/<mã>/telemetry`. Phải khớp chính xác; không sửa được sau khi tạo.
- Chọn vị trí bằng click bản đồ hoặc kéo marker **T**.
- Danh sách trạm hiển thị trạng thái dữ liệu live (`Dữ liệu mới / cũ / lỗi cảm biến / mất dữ liệu`) và độ ngập hiện tại.
- Trạm đã có số đo không xóa được (lỗi 409); dùng **Trạm đang hoạt động** để tắt thay vì xóa, giữ nguyên lịch sử.
- Sau khi tạo trạm, nạp cùng `device_id` vào firmware ESP32. Mosquitto dùng chung tài khoản `station`, không cần sửa ACL.
- API này chưa có đăng nhập và sửa được trạm thật: chỉ dùng local/LAN tin cậy.
