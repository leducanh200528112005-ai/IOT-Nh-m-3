"""ORS boundary and conservative route validation. No unchecked fallback routes."""
import math
from datetime import datetime, timezone

import httpx
from pyproj import CRS, Geod, Transformer
from shapely import transform
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union

from app.schemas import RouteRequest


class RoutingError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def zones_from(data: dict, margin_m: float = 0):
    zones = []
    for feature in data["flood_zones"]["features"]:
        geometry = shape(feature["geometry"])
        if margin_m:
            center = geometry.centroid
            local = CRS.from_proj4(
                f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m"
            )
            forward = Transformer.from_crs("EPSG:4326", local, always_xy=True)
            backward = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
            geometry = transform(transform(geometry, forward.transform, interleaved=False).buffer(margin_m), backward.transform, interleaved=False)
        zones.append(geometry)
    return unary_union(zones)


def require_data(data, request, zones):
    if not data["routing_data_sufficient"]:
        raise RoutingError("INSUFFICIENT_DATA", "Dữ liệu trạm thiếu, lỗi hoặc quá hạn; chưa đủ cơ sở đề xuất.", 409)
    if any(zones.intersects(Point(point.coordinates())) for point in (request.start, request.end)):
        raise RoutingError("POINT_IN_FLOOD_ZONE", "Điểm đi hoặc điểm đến nằm trong/chạm vùng cấm.")


def parse_route(response: httpx.Response):
    if response.status_code == 429:
        raise RoutingError("ROUTING_RATE_LIMITED", "ORS đang giới hạn lượt gọi. Vui lòng thử lại sau.", 429)
    if response.status_code in (401, 403):
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS từ chối xác thực hoặc quyền truy cập của server.", 503)
    try:
        payload = response.json()
    except ValueError:
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS trả dữ liệu không hợp lệ.", 502) from None
    if response.is_error:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict) and error.get("code") in (2009, 2010):
            raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến hoặc điểm đường phù hợp.")
        raise RoutingError("ROUTING_UNAVAILABLE", "Dịch vụ định tuyến không xử lý được yêu cầu.", 502)
    try:
        feature = payload["features"][0]
        geometry = feature["geometry"]
        if geometry["type"] != "LineString":
            raise ValueError()
        coordinates = geometry["coordinates"]
        if len(coordinates) < 2:
            raise ValueError()
        for coordinate in coordinates:
            if len(coordinate) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in coordinate):
                raise ValueError()
            if not (-180 <= coordinate[0] <= 180 and -90 < coordinate[1] < 90):
                raise ValueError()
        line = LineString(coordinates)
        if not line.is_valid or line.length == 0:
            raise ValueError()
        summary = feature["properties"]["summary"]
        distance, duration = summary["distance"], summary["duration"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (distance, duration)):
            raise ValueError()
        if distance == 0:
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS trả tuyến không hợp lệ.", 502) from None
    # Return only allowlisted fields, never upstream metadata or request headers.
    return line, distance, duration


def find_route(request: RouteRequest, settings, get_snapshot, client) -> dict:
    key = settings.ors_api_key.get_secret_value().strip()
    if not key:
        raise RoutingError("ROUTING_UNAVAILABLE", "Server chưa cấu hình ORS_API_KEY.", 503)
    data = get_snapshot()
    geod = Geod(ellps="WGS84")
    for attempt in range(2):
        zones = zones_from(data, margin_m=20 if attempt else 0)
        require_data(data, request, zones)
        body = {
            "coordinates": [request.start.coordinates(), request.end.coordinates()],
            "instructions": False, "geometry_simplify": False,
            "radiuses": [settings.ors_max_snap_m, settings.ors_max_snap_m],
        }
        if not zones.is_empty:
            body["options"] = {"avoid_polygons": mapping(zones)}
        try:
            response = client.post(
                settings.ors_base_url.rstrip("/") + "/v2/directions/driving-car/geojson",
                headers={"Authorization": key}, json=body,
                timeout=settings.ors_timeout_seconds,
            )
        except httpx.RequestError:
            raise RoutingError("ROUTING_UNAVAILABLE", "Không kết nối được ORS hoặc yêu cầu quá thời gian.", 503) from None
        line, distance, duration = parse_route(response)
        coordinates = list(line.coords)
        offsets = [abs(geod.inv(*point.coordinates(), *snapped)[2]) for point, snapped in (
            (request.start, coordinates[0]), (request.end, coordinates[-1]),
        )]
        if any(offset > settings.ors_max_snap_m for offset in offsets):
            raise RoutingError("NO_SUITABLE_ROUTE", "Điểm trên đường cách điểm đã chọn quá xa.")
        # Check the short snapped connectors too, but do not represent them as drivable roads.
        checked_line = LineString([request.start.coordinates(), *coordinates, request.end.coordinates()])
        current = get_snapshot()
        current_zones = zones_from(current)
        require_data(current, request, current_zones)
        if not checked_line.intersects(zones) and not checked_line.intersects(current_zones):
            return {
                "route": {"type": "Feature", "geometry": mapping(line), "properties": {}},
                "distance_m": distance, "duration_s": duration,
                "calculated_at": datetime.now(timezone.utc), "data_generated_at": current["generated_at"],
                "profile": "driving-car", "snap_distances_m": {"start": offsets[0], "end": offsets[1]},
                "source": request.source, "include_real": request.include_real,
                "warnings": [
                    *(["DỮ LIỆU MÔ PHỎNG" + (" kết hợp trạm thực tế." if request.include_real else ".")] if request.source == "demo" else []),
                    "Tuyến ít rủi ro hơn theo dữ liệu hiện có, không bảo đảm an toàn thực tế.",
                    "Vùng cấm là mô phỏng quanh điểm đo, không phải toàn bộ phạm vi ngập.",
                    "Khoảng cách/thời gian chỉ tính phần tuyến trên đường; đoạn nối từ điểm chọn chưa được xác minh có thể đi được.",
                ],
            }
        data = current
    raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm sau hai lần kiểm tra.")
