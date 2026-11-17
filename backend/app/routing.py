"""Flood-aware routing across Valhalla, OSRM, and OpenRouteService with conservative validation."""
from datetime import datetime, timezone
import logging
import math
from typing import Any

import anyio
import httpx
from pyproj import CRS, Geod, Transformer
from shapely import affinity, transform
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union

from app.schemas import RouteRequest

logger = logging.getLogger(__name__)
_GEOD = Geod(ellps="WGS84")

_ORS_PROFILES = {
    "car": "driving-car",
    "motorcycle": "cycling-regular",  # ORS has no motorcycle profile; cycling-regular approximates narrow alleys.
    "pedestrian": "foot-walking",
}

_VALHALLA_COSTINGS = {
    "car": "auto",
    "motorcycle": "motorcycle",
    "pedestrian": "pedestrian",
}


class RoutingError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def _zone_scale(vehicle: str, settings: Any) -> float:
    if vehicle == "motorcycle":
        return getattr(settings, "motorcycle_zone_scale", 0.65)
    if vehicle == "pedestrian":
        return getattr(settings, "pedestrian_zone_scale", 0.5)
    return 1.0


def zones_from(data: dict, margin_m: float = 0, scale: float = 1.0):
    zones = []
    for feature in data.get("flood_zones", {}).get("features", []):
        try:
            geometry = shape(feature["geometry"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping invalid flood zone geometry in snapshot.")
            continue
        if scale != 1.0:
            geometry = affinity.scale(geometry, xfact=scale, yfact=scale, origin="centroid")
        if margin_m:
            center = geometry.centroid
            local = CRS.from_proj4(
                f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m"
            )
            forward = Transformer.from_crs("EPSG:4326", local, always_xy=True)
            backward = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
            geometry = transform(
                transform(geometry, forward.transform, interleaved=False).buffer(margin_m),
                backward.transform,
                interleaved=False,
            )
        zones.append(geometry)
    return unary_union(zones) if zones else unary_union([])


def require_data(data: dict, request: RouteRequest, zones):
    if not data["routing_data_sufficient"]:
        raise RoutingError("INSUFFICIENT_DATA", "Dữ liệu trạm thiếu, lỗi hoặc quá hạn; chưa đủ cơ sở đề xuất.", 409)
    if any(zones.intersects(Point(point.coordinates())) for point in (request.start, request.end)):
        raise RoutingError("POINT_IN_FLOOD_ZONE", "Điểm đi hoặc điểm đến nằm trong/chạm vùng cấm.")


def _validate_coords(coordinates: Any) -> LineString:
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError()
    for coordinate in coordinates:
        if (
            not isinstance(coordinate, (list, tuple))
            or len(coordinate) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in coordinate)
        ):
            raise ValueError()
        if not (-180 <= coordinate[0] <= 180 and -90 < coordinate[1] < 90):
            raise ValueError()
    line = LineString(coordinates)
    if not line.is_valid or line.length == 0:
        raise ValueError()
    return line


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
        line = _validate_coords(geometry["coordinates"])
        summary = feature["properties"]["summary"]
        distance, duration = summary["distance"], summary["duration"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (distance, duration)):
            raise ValueError()
        if distance == 0:
            raise ValueError()
        steps = []
        for seg in feature.get("properties", {}).get("segments", []):
            for st in seg.get("steps", []):
                instr = st.get("instruction")
                if instr:
                    steps.append({
                        "instruction": str(instr),
                        "distance_m": round(float(st.get("distance", 0.0)), 1),
                        "duration_s": round(float(st.get("duration", 0.0)), 1),
                        "type": str(st.get("type", "")),
                    })
    except (KeyError, IndexError, TypeError, ValueError):
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS trả tuyến không hợp lệ.", 502) from None
    # Return only allowlisted fields, never upstream metadata or request headers.
    return line, distance, duration, steps


def decode_polyline6(polyline_str: str) -> list[list[float]]:
    if not isinstance(polyline_str, str) or not polyline_str:
        raise ValueError("Empty polyline6 string")
    index, lat, lng = 0, 0, 0
    coordinates: list[list[float]] = []
    changes = {"latitude": 0, "longitude": 0}
    n = len(polyline_str)
    while index < n:
        for unit in ("latitude", "longitude"):
            shift, result = 0, 0
            while True:
                if index >= n:
                    raise ValueError("Truncated polyline6 string")
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            changes[unit] = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += changes["latitude"]
        lng += changes["longitude"]
        coordinates.append([lng / 1e6, lat / 1e6])
    return coordinates


def _geom_perimeter_m(geom, scale: float = 1.0) -> float:
    return _GEOD.geometry_length(geom.exterior if hasattr(geom, "exterior") else geom) * scale


def _valhalla_exclude_polys(
    features: list[dict], scale: float, max_verts: int = 96, max_perim_m: float = 9500.0
) -> list[list[list[float]]]:
    valid: list[tuple[dict, Any]] = []
    for f in features:
        try:
            geom = shape(f["geometry"])
            if geom.is_empty or not hasattr(geom, "exterior"):
                continue
            valid.append((f, geom))
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping invalid flood zone feature in exclude_polygons.")
    if not valid:
        return []

    n_sides = 6 if len(valid) <= 15 else 4
    if len(valid) * n_sides > max_verts:
        n_sides = 3
    circum = 1.0 / math.cos(math.pi / n_sides)
    raw_perim = sum(_geom_perimeter_m(geom, scale) * circum for _, geom in valid)
    fit = min(1.0, max_perim_m / raw_perim) if raw_perim > 0 else 1.0
    final_scale = scale * fit

    polys = []
    for _, geom in valid[: max_verts // n_sides]:
        g = affinity.scale(geom, xfact=final_scale, yfact=final_scale, origin="centroid")
        coords = list(g.exterior.coords)
        step = max(1, (len(coords) - 1) // n_sides)
        ring = coords[:-1:step][:n_sides]
        if len(ring) >= 3:
            ring.append(ring[0])
            polys.append([[c[0], c[1]] for c in ring])
    return polys


def _build_valhalla_payload(
    start_pt: list[float],
    end_pt: list[float],
    vehicle: str,
    lang: str,
    features: list[dict],
    base_scale: float,
    force_full: bool = False,
) -> dict:
    costing = _VALHALLA_COSTINGS.get(vehicle, "auto")
    polys = _valhalla_exclude_polys(features, base_scale, max_perim_m=9500.0 if not force_full else 9900.0)
    payload: dict[str, Any] = {
        "locations": [{"lon": start_pt[0], "lat": start_pt[1]}, {"lon": end_pt[0], "lat": end_pt[1]}],
        "costing": costing,
        "directions_options": {
            "units": "kilometers",
            "language": "en-US" if lang == "en" else "vi-VN",
        },
        "alternates": 2,
    }
    if vehicle == "motorcycle":
        payload["costing_options"] = {"motorcycle": {"use_trails": 1.0}}
    if polys:
        payload["exclude_polygons"] = polys
    return payload


def _parse_valhalla_trips(resp: httpx.Response) -> list[tuple[LineString, float, float, list[dict]]]:
    if resp.status_code != 200:
        logger.warning("Valhalla returned HTTP %s: %s", resp.status_code, resp.text[:200])
        return []
    payload = resp.json()
    trips = [payload["trip"]] + [a["trip"] for a in payload.get("alternates", [])]
    parsed = []
    for tr in trips:
        leg = tr["legs"][0]
        pts = decode_polyline6(leg["shape"])
        line = _validate_coords(pts)
        dist = float(tr["summary"]["length"]) * 1000.0
        dur = float(tr["summary"]["time"])
        steps = [
            {
                "instruction": str(m.get("instruction", "")),
                "distance_m": round(float(m.get("length", 0.0)) * 1000.0, 1),
                "duration_s": round(float(m.get("time", 0.0)), 1),
                "type": str(m.get("type", "")),
            }
            for m in leg.get("maneuvers", [])
            if m.get("instruction")
        ]
        parsed.append((line, dist, dur, steps))
    return parsed


def _corridor_feature_subset(features: list[dict], corridor_line: LineString, base_scale: float) -> list[dict]:
    valid_feats = []
    for f in features:
        try:
            geom = shape(f["geometry"])
            valid_feats.append((corridor_line.distance(geom), f, geom))
        except (KeyError, TypeError, ValueError):
            continue
    valid_feats.sort(key=lambda item: item[0])
    kept: list[dict] = []
    acc_perim = 0.0
    for _, f, geom in valid_feats:
        p = _geom_perimeter_m(geom, base_scale) * 1.16
        if acc_perim + p <= 9400.0 or not kept:
            kept.append(f)
            acc_perim += p
    return kept


def _format_osrm_step(step: dict, lang: str) -> str:
    maneuver = step.get("maneuver", {})
    mtype = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    name = (step.get("name") or "").strip()
    if lang == "en":
        action = f"{mtype} {modifier}".strip() or "continue"
        return f"{action.capitalize()} onto {name}".strip() if name else action.capitalize()

    dir_map = {
        "left": "Rẽ trái",
        "slight left": "Chếch sang trái",
        "sharp left": "Rẽ ngoặt sang trái",
        "right": "Rẽ phải",
        "slight right": "Chếch sang phải",
        "sharp right": "Rẽ ngoặt sang phải",
        "uturn": "Quay đầu",
        "straight": "Đi thẳng",
    }
    if mtype == "depart":
        base = "Xuất phát"
    elif mtype == "arrive":
        return "Đến nơi"
    else:
        base = dir_map.get(modifier, "Tiếp tục")
    return f"{base} vào {name}" if name else base


def _parse_osrm_response(resp: httpx.Response, vehicle: str, settings: Any, lang: str) -> list[tuple[LineString, float, float, list[dict]]]:
    if resp.status_code != 200:
        logger.warning("OSRM returned HTTP %s", resp.status_code)
        return []
    data = resp.json()
    if data.get("code") != "Ok":
        return []
    routes = []
    for r in data.get("routes", []):
        coords = r["geometry"]["coordinates"]
        line = _validate_coords(coords)
        dist = float(r["distance"])
        raw_dur = float(r["duration"])
        # Public OSRM only exposes driving speed profiles accurately; heuristic scale adjusts duration.
        if vehicle == "motorcycle":
            speed_kmh = getattr(settings, "motorcycle_speed_kmh", 28.0)
            dur = dist / (speed_kmh / 3.6)
        elif vehicle == "pedestrian":
            speed_kmh = getattr(settings, "pedestrian_speed_kmh", 5.0)
            dur = dist / (speed_kmh / 3.6)
        else:
            dur = raw_dur
        dur_ratio = (dur / raw_dur) if raw_dur > 0 else 1.0
        steps = []
        legs = r.get("legs", [])
        for li, leg in enumerate(legs):
            leg_steps = leg.get("steps", [])
            for si, st in enumerate(leg_steps):
                is_last_step = (si == len(leg_steps) - 1)
                is_last_leg = (li == len(legs) - 1)
                if is_last_step and not is_last_leg:
                    continue  # Bỏ qua chỉ dẫn "Đến nơi" ở điểm né ngập trung gian
                steps.append({
                    "instruction": _format_osrm_step(st, lang),
                    "distance_m": round(float(st.get("distance", 0.0)), 1),
                    "duration_s": round(float(st.get("duration", 0.0)) * dur_ratio, 1),
                    "type": str(st.get("maneuver", {}).get("type", "")),
                })
        routes.append((line, dist, dur, steps))
    return routes


def _build_osrm_detour_waypoints(start_pt: list[float], end_pt: list[float], zones) -> list[list[float]]:
    detour_wps: list[list[float]] = []

    # Priority 1: Tangent & diagonal bypass waypoints around intersected flood zones
    direct = LineString([start_pt, end_pt])
    geoms = list(getattr(zones, "geoms", [zones]))
    for g in geoms:
        if not g.is_empty and direct.intersects(g):
            minx, miny, maxx, maxy = g.bounds
            for pad in (0.003, 0.006, 0.010):
                for cand in (
                    [minx - pad, (miny + maxy) / 2],
                    [maxx + pad, (miny + maxy) / 2],
                    [(minx + maxx) / 2, miny - pad],
                    [(minx + maxx) / 2, maxy + pad],
                    [minx - pad, miny - pad],
                    [maxx + pad, miny - pad],
                    [minx - pad, maxy + pad],
                    [maxx + pad, maxy + pad],
                ):
                    if not zones.intersects(Point(cand)) and cand not in detour_wps:
                        detour_wps.append(cand)

    # Priority 2: Perpendicular corridor offset waypoints
    dx = end_pt[0] - start_pt[0]
    dy = end_pt[1] - start_pt[1]
    line_len = math.hypot(dx, dy)
    if line_len > 0:
        nx = -dy / line_len
        ny = dx / line_len
        for scale in (0.004, 0.008, 0.015, 0.030):
            for fraction in (0.3, 0.5, 0.7):
                bx = start_pt[0] + fraction * dx
                by = start_pt[1] + fraction * dy
                for sign in (-1, 1):
                    wp = [bx + sign * nx * scale, by + sign * ny * scale]
                    if not zones.intersects(Point(wp)) and wp not in detour_wps:
                        detour_wps.append(wp)

    return detour_wps[:24]


def _vehicle_label(vehicle: str, lang: str) -> str:
    if lang == "en":
        if vehicle == "motorcycle":
            return "Vehicle: Motorcycle (alley preference & close flood detour)"
        if vehicle == "pedestrian":
            return "Vehicle: Pedestrian (walkways & minimal flood detour)"
        return "Vehicle: Car (main roads & wide flood exclusion)"
    if vehicle == "motorcycle":
        return "Phương tiện: 🛵 Xe máy (ưu tiên ngõ hẻm & né ngập sát)"
    if vehicle == "pedestrian":
        return "Phương tiện: 🚶 Đi bộ (lối đi bộ & né ngập linh hoạt)"
    return "Phương tiện: 🚗 Ô tô (đi đường lớn & né vùng ngập rộng)"


def _collect_ai_warnings(snapshot_data: dict) -> list[str]:
    return [
        f["properties"]["warning_message"]
        for f in snapshot_data.get("flood_zones", {}).get("features", [])
        if f.get("properties", {}).get("is_predicted") and f.get("properties", {}).get("warning_message")
    ]


def _finalize_route_response(
    *,
    request: RouteRequest,
    best_line: LineString,
    best_dist: float,
    best_dur: float,
    steps: list[dict],
    current_snapshot: dict,
    engine: str,
    profile: str,
    extra_warnings: list[str] | None = None,
) -> dict:
    coordinates = list(best_line.coords)
    offsets = [
        abs(_GEOD.inv(*point.coordinates(), *snapped)[2])
        for point, snapped in ((request.start, coordinates[0]), (request.end, coordinates[-1]))
    ]
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    ai_warnings = _collect_ai_warnings(current_snapshot)
    warnings = []
    if extra_warnings:
        warnings.extend(extra_warnings)
    if engine != "ors":
        warnings.append(_vehicle_label(vehicle, lang))
    if request.source == "demo":
        if lang == "en":
            warnings.append("SIMULATED DATA" + (" combined with real stations." if request.include_real else "."))
        else:
            warnings.append("DỮ LIỆU MÔ PHỎNG" + (" kết hợp trạm thực tế." if request.include_real else "."))
    warnings.extend(ai_warnings)
    if lang == "en":
        warnings.extend([
            "Lower-risk route based on available sensor data; real-world safety is not guaranteed.",
            "Exclusion zones model area around sensors, not exact full flood extent.",
        ])
    else:
        warnings.extend([
            "Tuyến ít rủi ro hơn theo dữ liệu hiện có, không bảo đảm an toàn thực tế.",
            "Vùng cấm là mô phỏng quanh điểm đo, không phải toàn bộ phạm vi ngập.",
        ])
    if engine == "valhalla":
        warnings.append("Sử dụng định tuyến Valhalla/OSM tối ưu đa giác tránh ngập." if lang == "vi" else "Routed via Valhalla/OSM exclude_polygons.")
    elif engine == "osrm":
        warnings.append(
            "Đang dùng OSRM dự phòng (Valhalla tạm gián đoạn); đã kiểm tra tuyến tránh vùng ngập."
            if lang == "vi"
            else "Using OSRM fallback (Valhalla temporarily unavailable); route verified against flood zones."
        )
    else:
        warnings.append("Khoảng cách/thời gian chỉ tính phần tuyến trên đường; đoạn nối từ điểm chọn chưa được xác minh có thể đi được.")

    return {
        "route": {"type": "Feature", "geometry": mapping(best_line), "properties": {}},
        "distance_m": best_dist,
        "duration_s": best_dur,
        "calculated_at": datetime.now(timezone.utc),
        "data_generated_at": current_snapshot["generated_at"],
        "profile": profile,
        "engine": engine,
        "snap_distances_m": {"start": offsets[0], "end": offsets[1]},
        "source": request.source,
        "include_real": request.include_real,
        "warnings": warnings,
        "steps": steps,
    }


def _select_non_intersecting(
    trips: list[tuple[LineString, float, float, list[dict]]],
    start_pt: list[float],
    end_pt: list[float],
    zones,
) -> list[tuple[float, float, LineString, list[dict]]]:
    candidates = []
    for line, dist, dur, steps in trips:
        checked = LineString([start_pt, *line.coords, end_pt])
        if zones.is_empty or not checked.intersects(zones):
            candidates.append((dist, dur, line, steps))
    return candidates


def query_osrm(points: list[list[float]], client: httpx.Client, settings: Any, vehicle: str = "car", lang: str = "vi"):
    base = getattr(settings, "osrm_base_url", "https://router.project-osrm.org").rstrip("/")
    timeout = getattr(settings, "osrm_timeout_seconds", 3.0)
    coords_str = ";".join(f"{p[0]:.6f},{p[1]:.6f}" for p in points)
    url = f"{base}/route/v1/driving/{coords_str}?overview=full&geometries=geojson&alternatives=true&steps=true"
    try:
        resp = client.get(url, timeout=timeout)
        return _parse_osrm_response(resp, vehicle, settings, lang)
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("OSRM query failed: %s", exc)
        return []


async def async_query_osrm(points: list[list[float]], client: httpx.AsyncClient, settings: Any, vehicle: str = "car", lang: str = "vi"):
    base = getattr(settings, "osrm_base_url", "https://router.project-osrm.org").rstrip("/")
    timeout = getattr(settings, "osrm_timeout_seconds", 3.0)
    coords_str = ";".join(f"{p[0]:.6f},{p[1]:.6f}" for p in points)
    url = f"{base}/route/v1/driving/{coords_str}?overview=full&geometries=geojson&alternatives=true&steps=true"
    try:
        resp = await client.get(url, timeout=timeout)
        return _parse_osrm_response(resp, vehicle, settings, lang)
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Async OSRM query failed: %s", exc)
        return []


def _verify_against_fresh_snapshot(request: RouteRequest, best_line: LineString, settings: Any, current: dict):
    vehicle = getattr(request, "vehicle", "car")
    current_zones = zones_from(current, scale=_zone_scale(vehicle, settings))
    require_data(current, request, current_zones)
    checked = LineString([request.start.coordinates(), *best_line.coords, request.end.coordinates()])
    if not current_zones.is_empty and checked.intersects(current_zones):
        raise RoutingError("NO_SUITABLE_ROUTE", "Tình hình ngập vừa cập nhật và giao với tuyến đã tìm. Vui lòng thử lại.")
    return current


def find_route_osrm(request: RouteRequest, settings, get_snapshot, client: httpx.Client) -> dict:
    data = get_snapshot()
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    zones = zones_from(data, scale=_zone_scale(vehicle, settings))
    require_data(data, request, zones)

    start_pt = request.start.coordinates()
    end_pt = request.end.coordinates()
    logger.info("OSRM fallback routing %s: %s -> %s", vehicle, start_pt, end_pt)

    direct = query_osrm([start_pt, end_pt], client, settings, vehicle=vehicle, lang=lang)
    candidates = _select_non_intersecting(direct, start_pt, end_pt, zones)
    if not candidates and not zones.is_empty:
        for wp in _build_osrm_detour_waypoints(start_pt, end_pt, zones):
            detour = query_osrm([start_pt, wp, end_pt], client, settings, vehicle=vehicle, lang=lang)
            candidates = _select_non_intersecting(detour, start_pt, end_pt, zones)
            if candidates:
                break

    if not candidates:
        raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm phù hợp với tình hình ngập hiện tại.")

    candidates.sort(key=lambda x: x[0])
    best_dist, best_dur, best_line, steps = candidates[0]
    current = _verify_against_fresh_snapshot(request, best_line, settings, get_snapshot())
    return _finalize_route_response(
        request=request, best_line=best_line, best_dist=best_dist, best_dur=best_dur, steps=steps,
        current_snapshot=current, engine="osrm", profile="driving-car" if vehicle == "car" else vehicle,
    )


async def async_find_route_osrm(request: RouteRequest, settings, get_snapshot, client: httpx.AsyncClient) -> dict:
    data = await anyio.to_thread.run_sync(get_snapshot)
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    zones = zones_from(data, scale=_zone_scale(vehicle, settings))
    require_data(data, request, zones)

    start_pt = request.start.coordinates()
    end_pt = request.end.coordinates()
    logger.info("Async OSRM fallback routing %s: %s -> %s", vehicle, start_pt, end_pt)

    direct = await async_query_osrm([start_pt, end_pt], client, settings, vehicle=vehicle, lang=lang)
    candidates = _select_non_intersecting(direct, start_pt, end_pt, zones)
    if not candidates and not zones.is_empty:
        for wp in _build_osrm_detour_waypoints(start_pt, end_pt, zones):
            detour = await async_query_osrm([start_pt, wp, end_pt], client, settings, vehicle=vehicle, lang=lang)
            candidates = _select_non_intersecting(detour, start_pt, end_pt, zones)
            if candidates:
                break

    if not candidates:
        raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm phù hợp với tình hình ngập hiện tại.")

    candidates.sort(key=lambda x: x[0])
    best_dist, best_dur, best_line, steps = candidates[0]
    current = _verify_against_fresh_snapshot(request, best_line, settings, await anyio.to_thread.run_sync(get_snapshot))
    return _finalize_route_response(
        request=request, best_line=best_line, best_dist=best_dist, best_dur=best_dur, steps=steps,
        current_snapshot=current, engine="osrm", profile="driving-car" if vehicle == "car" else vehicle,
    )


def find_route_valhalla(request: RouteRequest, settings, get_snapshot, client: httpx.Client) -> dict:
    data = get_snapshot()
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    base_scale = _zone_scale(vehicle, settings)
    features = data.get("flood_zones", {}).get("features", [])
    zones = zones_from(data, scale=base_scale)
    require_data(data, request, zones)

    start_pt = request.start.coordinates()
    end_pt = request.end.coordinates()
    valhalla_url = getattr(settings, "valhalla_url", "https://valhalla1.openstreetmap.de/route")
    timeout = getattr(settings, "valhalla_timeout_seconds", 8.0)
    logger.info("Valhalla routing %s: %s -> %s (%d flood zones)", vehicle, start_pt, end_pt, len(features))

    def query(subset: list[dict], force_full: bool = False):
        payload = _build_valhalla_payload(start_pt, end_pt, vehicle, lang, subset, base_scale, force_full)
        resp = client.post(valhalla_url, json=payload, timeout=timeout)
        return _parse_valhalla_trips(resp)

    try:
        trips = query(features)
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Valhalla request/parse failed (%s), falling back to OSRM.", exc)
        return find_route_osrm(request, settings, get_snapshot, client)

    candidates = _select_non_intersecting(trips, start_pt, end_pt, zones)
    if not candidates and features:
        corridor = trips[0][0] if trips else LineString([start_pt, end_pt])
        kept = _corridor_feature_subset(features, corridor, base_scale)
        try:
            trips2 = query(kept, force_full=True)
            candidates = _select_non_intersecting(trips2, start_pt, end_pt, zones)
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("Valhalla corridor retry failed: %s", exc)

    if not candidates:
        logger.info("Valhalla found no valid detour, falling back to OSRM.")
        return find_route_osrm(request, settings, get_snapshot, client)

    candidates.sort(key=lambda x: x[0])
    best_dist, best_dur, best_line, steps = candidates[0]
    current = _verify_against_fresh_snapshot(request, best_line, settings, get_snapshot())
    return _finalize_route_response(
        request=request, best_line=best_line, best_dist=best_dist, best_dur=best_dur, steps=steps,
        current_snapshot=current, engine="valhalla", profile="driving-car" if vehicle == "car" else vehicle,
    )


async def async_find_route_valhalla(request: RouteRequest, settings, get_snapshot, client: httpx.AsyncClient) -> dict:
    data = await anyio.to_thread.run_sync(get_snapshot)
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    base_scale = _zone_scale(vehicle, settings)
    features = data.get("flood_zones", {}).get("features", [])
    zones = zones_from(data, scale=base_scale)
    require_data(data, request, zones)

    start_pt = request.start.coordinates()
    end_pt = request.end.coordinates()
    valhalla_url = getattr(settings, "valhalla_url", "https://valhalla1.openstreetmap.de/route")
    timeout = getattr(settings, "valhalla_timeout_seconds", 8.0)
    logger.info("Async Valhalla routing %s: %s -> %s (%d flood zones)", vehicle, start_pt, end_pt, len(features))

    async def query(subset: list[dict], force_full: bool = False):
        payload = _build_valhalla_payload(start_pt, end_pt, vehicle, lang, subset, base_scale, force_full)
        resp = await client.post(valhalla_url, json=payload, timeout=timeout)
        return _parse_valhalla_trips(resp)

    try:
        trips = await query(features)
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Async Valhalla request/parse failed (%s), falling back to OSRM.", exc)
        return await async_find_route_osrm(request, settings, get_snapshot, client)

    candidates = _select_non_intersecting(trips, start_pt, end_pt, zones)
    if not candidates and features:
        corridor = trips[0][0] if trips else LineString([start_pt, end_pt])
        kept = _corridor_feature_subset(features, corridor, base_scale)
        try:
            trips2 = await query(kept, force_full=True)
            candidates = _select_non_intersecting(trips2, start_pt, end_pt, zones)
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("Async Valhalla corridor retry failed: %s", exc)

    if not candidates:
        logger.info("Async Valhalla found no valid detour, falling back to OSRM.")
        return await async_find_route_osrm(request, settings, get_snapshot, client)

    candidates.sort(key=lambda x: x[0])
    best_dist, best_dur, best_line, steps = candidates[0]
    current = _verify_against_fresh_snapshot(request, best_line, settings, await anyio.to_thread.run_sync(get_snapshot))
    return _finalize_route_response(
        request=request, best_line=best_line, best_dist=best_dist, best_dur=best_dur, steps=steps,
        current_snapshot=current, engine="valhalla", profile="driving-car" if vehicle == "car" else vehicle,
    )


def _ors_body_and_url(request: RouteRequest, settings: Any, zones) -> tuple[str, dict]:
    vehicle = getattr(request, "vehicle", "car")
    profile = _ORS_PROFILES.get(vehicle, "driving-car")
    url = settings.ors_base_url.rstrip("/") + f"/v2/directions/{profile}/geojson"
    body: dict[str, Any] = {
        "coordinates": [request.start.coordinates(), request.end.coordinates()],
        "instructions": False,
        "geometry_simplify": False,
        "radiuses": [settings.ors_max_snap_m, settings.ors_max_snap_m],
    }
    if not zones.is_empty:
        body["options"] = {"avoid_polygons": mapping(zones)}
    return url, body


def _validate_ors_result(request: RouteRequest, settings: Any, line: LineString, zones, current: dict, current_zones):
    coordinates = list(line.coords)
    offsets = [
        abs(_GEOD.inv(*point.coordinates(), *snapped)[2])
        for point, snapped in ((request.start, coordinates[0]), (request.end, coordinates[-1]))
    ]
    if any(offset > settings.ors_max_snap_m for offset in offsets):
        raise RoutingError("NO_SUITABLE_ROUTE", "Điểm trên đường cách điểm đã chọn quá xa.")
    # Check the short snapped connectors too, but do not represent them as drivable roads.
    checked_line = LineString([request.start.coordinates(), *coordinates, request.end.coordinates()])
    require_data(current, request, current_zones)
    return not checked_line.intersects(zones) and not checked_line.intersects(current_zones)


def find_route(request: RouteRequest, settings, get_snapshot, client: httpx.Client) -> dict:
    key = settings.ors_api_key.get_secret_value().strip()
    if not key:
        return find_route_valhalla(request, settings, get_snapshot, client)

    vehicle = getattr(request, "vehicle", "car")
    scale = _zone_scale(vehicle, settings)
    ors_profile = _ORS_PROFILES.get(vehicle, "driving-car")
    data = get_snapshot()
    for attempt in range(2):
        zones = zones_from(data, margin_m=20 if attempt else 0, scale=scale)
        require_data(data, request, zones)
        url, body = _ors_body_and_url(request, settings, zones)
        try:
            response = client.post(
                url,
                headers={"Authorization": key},
                json=body,
                timeout=settings.ors_timeout_seconds,
            )
        except httpx.RequestError as exc:
            logger.warning("ORS request error (%s)", exc)
            if getattr(settings, "ors_fallback_to_valhalla", False):
                return find_route_valhalla(request, settings, get_snapshot, client)
            raise RoutingError("ROUTING_UNAVAILABLE", "Không kết nối được dịch vụ định tuyến.") from None

        try:
            line, distance, duration, steps = parse_route(response)
        except RoutingError as exc:
            if exc.code == "ROUTING_UNAVAILABLE" and getattr(settings, "ors_fallback_to_valhalla", False):
                return find_route_valhalla(request, settings, get_snapshot, client)
            raise

        current = get_snapshot()
        current_zones = zones_from(current, scale=scale)
        if _validate_ors_result(request, settings, line, zones, current, current_zones):
            return _finalize_route_response(
                request=request, best_line=line, best_dist=distance, best_dur=duration, steps=steps,
                current_snapshot=current, engine="ors", profile=ors_profile,
            )
        data = current
    raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm sau hai lần kiểm tra.")


async def async_find_route(request: RouteRequest, settings, get_snapshot, client: httpx.AsyncClient) -> dict:
    key = settings.ors_api_key.get_secret_value().strip()
    if not key:
        return await async_find_route_valhalla(request, settings, get_snapshot, client)

    vehicle = getattr(request, "vehicle", "car")
    scale = _zone_scale(vehicle, settings)
    ors_profile = _ORS_PROFILES.get(vehicle, "driving-car")
    data = await anyio.to_thread.run_sync(get_snapshot)
    for attempt in range(2):
        zones = zones_from(data, margin_m=20 if attempt else 0, scale=scale)
        require_data(data, request, zones)
        url, body = _ors_body_and_url(request, settings, zones)
        try:
            response = await client.post(
                url,
                headers={"Authorization": key},
                json=body,
                timeout=settings.ors_timeout_seconds,
            )
        except httpx.RequestError as exc:
            logger.warning("Async ORS request error (%s)", exc)
            if getattr(settings, "ors_fallback_to_valhalla", False):
                return await async_find_route_valhalla(request, settings, get_snapshot, client)
            raise RoutingError("ROUTING_UNAVAILABLE", "Không kết nối được dịch vụ định tuyến.") from None

        try:
            line, distance, duration, steps = parse_route(response)
        except RoutingError as exc:
            if exc.code == "ROUTING_UNAVAILABLE" and getattr(settings, "ors_fallback_to_valhalla", False):
                return await async_find_route_valhalla(request, settings, get_snapshot, client)
            raise

        current = await anyio.to_thread.run_sync(get_snapshot)
        current_zones = zones_from(current, scale=scale)
        if _validate_ors_result(request, settings, line, zones, current, current_zones):
            return _finalize_route_response(
                request=request, best_line=line, best_dist=distance, best_dur=duration, steps=steps,
                current_snapshot=current, engine="ors", profile=ors_profile,
            )
        data = current
    raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm sau hai lần kiểm tra.")
