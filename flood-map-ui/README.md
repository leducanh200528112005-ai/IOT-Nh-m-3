# Flood Map UI (nhóm 3)

React + TypeScript + Vite + Leaflet. Chỉ gọi backend nhóm 2: `GET /api/flood-zones` (poll 3–5 giây) và `POST /api/routes/safe` (khi bấm nút).

## Chạy
```bash
npm install
cp .env.example .env     # VITE_USE_MOCK=true để chạy không cần backend
npm run dev
npm run build
```

## Hợp đồng dữ liệu (xem src/types.ts)
- Mọi GeoJSON dùng thứ tự `[lng, lat]`; chuyển sang `[lat, lng]` duy nhất ở `src/utils/geo.ts`.
- `level` (mức ngập) và `dataQuality` (chất lượng dữ liệu) là hai trường riêng. Frontend không tự tính mức ngập.
- `dataQuality = "missing"` luôn hiển thị xám/không rõ.
- Lỗi poll: giữ dữ liệu cũ + banner "không còn được cập nhật". Dữ liệu đổi/quá hạn: tuyến hiện tại chuyển nét đứt xám + cảnh báo, người dùng tự bấm "Tính lại tuyến".

## Cấu trúc
- `src/api/` gọi API (client có timeout, hủy request), `src/hooks/` polling và tìm đường, `src/components/` giao diện.
- Mock: `public/mock/*.json`. Để thử trường hợp không có tuyến, đổi đường dẫn trong `src/api/routeApi.ts` sang `route-no-route.json`.

## Bản đồ nền
Mặc định dùng tile OSM; cần giữ attribution và tuân thủ chính sách tile của OSM (không tải hàng loạt, không dùng cho lưu lượng lớn). Production nên đổi `VITE_TILE_URL` sang nhà cung cấp phù hợp.
