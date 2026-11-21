"""Flood-aware routing across Valhalla, OSRM, and OpenRouteService with conservative validation."""
from datetime import datetime, timezone
from itertools import groupby
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
_Trip = tuple[LineString, float, float, list[dict]]

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


def parse_ors_routes(response: httpx.Response) -> list[_Trip]:
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
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS trả dữ liệu không hợp lệ.", 502)
    if not features:
        raise RoutingError("NO_SUITABLE_ROUTE", "ORS không trả về tuyến phù hợp.")
    trips = []
    for feature in features:
        try:
            trips.append(_parse_ors_feature(feature))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not trips:
        raise RoutingError("ROUTING_UNAVAILABLE", "ORS trả tuyến không hợp lệ.", 502)
    return trips


def _parse_ors_feature(feature: dict) -> _Trip:
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
    for segment in feature["properties"].get("segments", []):
        if not isinstance(segment, dict):
            raise ValueError()
        for step in segment.get("steps", []):
            if not isinstance(step, dict):
                raise ValueError()
            if step.get("instruction"):
                step_distance, step_duration = float(step.get("distance", 0)), float(step.get("duration", 0))
                if not all(math.isfinite(value) and value >= 0 for value in (step_distance, step_duration)):
                    raise ValueError()
                steps.append({
                    "instruction": str(step["instruction"]), "distance_m": round(step_distance, 1),
                    "duration_s": round(step_duration, 1), "type": str(step.get("type", "")),
                })
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


def _prune_osrm_backtracks(
    coords: list[list[float]],
    steps: list[dict],
    dur_ratio: float,
) -> tuple[LineString, float, float, list[dict]]:
    cleaned = [list(c) for c in coords]
    removed_junctions = []
    changed = True
    while changed:
        changed = False
        for i in range(len(cleaned) - 2):
            for j in range(len(cleaned) - 1, i + 2, -1):
                d = math.hypot(cleaned[i][0] - cleaned[j][0], cleaned[i][1] - cleaned[j][1])
                if d < 0.00015:  # ~15 meters
                    loop_len = j - i
                    half = loop_len // 2
                    is_bt = True
                    for k in range(1, half + 1):
                        diff = math.hypot(cleaned[i + k][0] - cleaned[j - k][0], cleaned[i + k][1] - cleaned[j - k][1])
                        if diff > 0.00025:  # ~25 meters
                            is_bt = False
                            break
                    if is_bt and loop_len > 1:
                        junc = cleaned[i]
                        removed_junctions.append((junc, cleaned[i:j + 1]))
                        cleaned = cleaned[:i + 1] + cleaned[j:]
                        changed = True
                        break
            if changed:
                break

    if not removed_junctions:
        line = _validate_coords(cleaned)
        dist = sum(_GEOD.inv(cleaned[i][0], cleaned[i][1], cleaned[i + 1][0], cleaned[i + 1][1])[2] for i in range(len(cleaned) - 1)) if len(cleaned) > 1 else 0.0
        dur = sum(s.get("duration_s", 0.0) for s in steps)
        return line, dist, dur, steps

    # Clean steps that occurred inside the spur
    cleaned_steps = []
    for st in steps:
        loc = st.get("location", [0, 0])
        name = st.get("name", "")
        mtype = st.get("type", "")
        drop = False
        for junc, spur_coords in removed_junctions:
            if any(math.hypot(loc[0] - sc[0], loc[1] - sc[1]) < 0.0003 for sc in spur_coords[1:-1]):
                drop = True
                break
            if mtype in ("uturn", "depart") and math.hypot(loc[0] - junc[0], loc[1] - junc[1]) < 0.001:
                drop = True
                break
            if ("Ngõ" in name or "Ngách" in name) and math.hypot(loc[0] - junc[0], loc[1] - junc[1]) < 0.0003:
                drop = True
                break
        if not drop:
            cleaned_steps.append(st)

    merged_steps = []
    for st in cleaned_steps:
        if merged_steps and merged_steps[-1].get("instruction") == st.get("instruction") and st.get("name"):
            merged_steps[-1]["distance_m"] = round(merged_steps[-1]["distance_m"] + st["distance_m"], 1)
            merged_steps[-1]["duration_s"] = round(merged_steps[-1]["duration_s"] + st["duration_s"], 1)
        else:
            merged_steps.append(st)

    line = _validate_coords(cleaned)
    dist = sum(_GEOD.inv(cleaned[i][0], cleaned[i][1], cleaned[i + 1][0], cleaned[i + 1][1])[2] for i in range(len(cleaned) - 1)) if len(cleaned) > 1 else 0.0
    dur = sum(s.get("duration_s", 0.0) for s in merged_steps)
    return line, dist, dur, merged_steps


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
                    "name": str(st.get("name", "")),
                    "location": st.get("maneuver", {}).get("location", [0, 0]),
                })
        line, clean_dist, clean_dur, clean_steps = _prune_osrm_backtracks(coords, steps, dur_ratio)
        routes.append((line, clean_dist, clean_dur, clean_steps))
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
    trips: list[_Trip],
    settings: Any,
    current_snapshot: dict,
    engine: str,
    profile: str,
) -> dict:
    limit = _route_limit(settings)
    routes = _rank_routes(trips, request, current_snapshot, limit, settings)
    best = routes[0]
    vehicle = getattr(request, "vehicle", "car")
    lang = getattr(request, "lang", "vi")
    ai_warnings = _collect_ai_warnings(current_snapshot)
    warnings = []
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
            "Routes checked against known exclusion zones; real-world safety is not guaranteed.",
            "Exclusion zones model area around sensors, not exact full flood extent.",
        ])
    else:
        warnings.extend([
            "Các tuyến đã được kiểm tra với vùng cấm đã biết, không bảo đảm an toàn thực tế.",
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
        "route": best["route"],
        "distance_m": best["distance_m"],
        "duration_s": best["duration_s"],
        "routes": routes,
        "recommended_route_id": best["id"],
        "requested_route_count": limit,
        "returned_route_count": len(routes),
        "ranking_policy": "warning_exposure_m_then_near_eta_warning_clearance_then_duration_s_then_distance_m",
        "ranking_parameters": {
            "warning_proximity_limit_m": settings.route_warning_proximity_limit_m,
            "warning_proximity_eta_tolerance_s": settings.route_warning_proximity_eta_tolerance_s,
        },
        "calculated_at": datetime.now(timezone.utc),
        "data_generated_at": current_snapshot["generated_at"],
        "profile": profile,
        "engine": engine,
        "snap_distances_m": best["snap_distances_m"],
        "source": request.source,
        "include_real": request.include_real,
        "warnings": warnings,
        "steps": best["steps"],
    }


def _route_limit(settings: Any) -> int:
    return settings.ors_alternative_target_count if settings.ors_alternative_routes_enabled else 1


def _snap_distances(request: RouteRequest, line: LineString) -> dict:
    return {
        "start": abs(_GEOD.inv(*request.start.coordinates(), *line.coords[0])[2]),
        "end": abs(_GEOD.inv(*request.end.coordinates(), *line.coords[-1])[2]),
    }


def _linear_length_m(geometry) -> float:
    if geometry.is_empty:
        return 0.0
    if geometry.geom_type == "LineString":
        return _GEOD.geometry_length(geometry)
    return sum(_linear_length_m(part) for part in getattr(geometry, "geoms", ()))


def _rank_routes(trips: list[_Trip], request: RouteRequest, current: dict, limit: int, settings: Any) -> list[dict]:
    warnings = [
        (shape(feature["geometry"]), feature["properties"])
        for feature in current.get("warning_zones", {}).get("features", [])
    ]
    metric_zones = []
    for zone, _ in warnings:
        center = zone.centroid
        local = CRS.from_proj4(
            f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m"
        )
        project = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
        metric_zones.append((project, transform(zone, project, interleaved=False)))
    ranked = []
    for line, distance, duration, steps in trips:
        hits = [(zone, props) for zone, props in warnings if line.intersects(zone)]
        exposure = _linear_length_m(line.intersection(unary_union([zone for zone, _ in hits]))) if hits else 0
        stations = [
            {key: props[key] for key in ("station_id", "name", "source", "water_depth_cm")}
            for _, props in hits
        ]
        clearance = 0.0 if hits else min(
            (transform(line, project, interleaved=False).distance(zone) for project, zone in metric_zones),
            default=None,
        )
        ranked.append((round(exposure, 1), duration, distance, line, steps, stations,
                       None if clearance is None else round(clearance, 1)))
    ranked.sort(key=lambda item: item[:3])
    ordered = []
    for _, exposure_group in groupby(ranked, key=lambda item: item[0]):
        group = list(exposure_group)
        start = 0
        while start < len(group):
            # Anchor each window to its fastest remaining route. Pairwise ETA tolerances are not transitive.
            end = start + 1
            while end < len(group) and group[end][1] - group[start][1] <= settings.route_warning_proximity_eta_tolerance_s:
                end += 1
            window = group[start:end]
            window.sort(key=lambda item: -min(item[6] or 0.0, settings.route_warning_proximity_limit_m))
            ordered.extend(window)
            start = end
    routes = []
    seen = []
    for exposure, duration, distance, line, steps, stations, clearance in ordered:
        if any(line.equals(previous) for previous in seen):
            continue
        seen.append(line)
        rank = len(routes) + 1
        routes.append({
            "id": f"route-{rank}", "rank": rank,
            "route": {"type": "Feature", "geometry": mapping(line), "properties": {}},
            "distance_m": distance, "duration_s": duration, "steps": steps,
            "snap_distances_m": _snap_distances(request, line),
            "assessment": {
                "warning_zone_count": len(stations), "warning_exposure_m": round(exposure, 1),
                "nearest_warning_zone_distance_m": clearance,
                "warning_stations": stations,
            },
        })
        if rank == limit:
            break
    return routes


def _select_non_intersecting(
    trips: list[_Trip],
    start_pt: list[float],
    end_pt: list[float],
    zones,
) -> list[_Trip]:
    candidates = []
    for trip in trips:
        checked = LineString([start_pt, *trip[0].coords, end_pt])
        if zones.is_empty or not checked.intersects(zones):
            candidates.append(trip)
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


def _finalize_fallback(request, settings, current, candidates, engine, profile):
    vehicle = getattr(request, "vehicle", "car")
    current_zones = zones_from(current, scale=_zone_scale(vehicle, settings))
    require_data(current, request, current_zones)
    checked = _select_non_intersecting(candidates, request.start.coordinates(), request.end.coordinates(), current_zones)
    if not checked:
        raise RoutingError("NO_SUITABLE_ROUTE", "Tình hình ngập vừa cập nhật và giao với tuyến đã tìm. Vui lòng thử lại.")
    return _finalize_route_response(
        request=request, trips=checked,
        settings=settings, current_snapshot=current, engine=engine, profile=profile,
    )


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

    return _finalize_fallback(
        request, settings, get_snapshot(), candidates, "osrm", "driving-car" if vehicle == "car" else vehicle,
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

    return _finalize_fallback(
        request, settings, await anyio.to_thread.run_sync(get_snapshot), candidates, "osrm",
        "driving-car" if vehicle == "car" else vehicle,
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

    return _finalize_fallback(
        request, settings, get_snapshot(), candidates, "valhalla", "driving-car" if vehicle == "car" else vehicle,
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

    return _finalize_fallback(
        request, settings, await anyio.to_thread.run_sync(get_snapshot), candidates, "valhalla",
        "driving-car" if vehicle == "car" else vehicle,
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
    if settings.ors_alternative_routes_enabled and _route_limit(settings) > 1:
        body["alternative_routes"] = {
            "target_count": _route_limit(settings),
            "weight_factor": settings.ors_alternative_weight_factor,
            "share_factor": settings.ors_alternative_share_factor,
        }
    return url, body


def _validate_ors_results(request, settings, trips, zones, current, current_zones) -> list[_Trip]:
    require_data(current, request, current_zones)
    snapped = [
        trip for trip in trips
        if all(offset <= settings.ors_max_snap_m for offset in _snap_distances(request, trip[0]).values())
    ]
    if not snapped:
        raise RoutingError("NO_SUITABLE_ROUTE", "Điểm trên đường cách điểm đã chọn quá xa.")
    # Check the short snapped connectors too, but do not represent them as drivable roads.
    return _select_non_intersecting(
        snapped, request.start.coordinates(), request.end.coordinates(), zones.union(current_zones),
    )


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
            trips = parse_ors_routes(response)
        except RoutingError as exc:
            if exc.code == "ROUTING_UNAVAILABLE" and getattr(settings, "ors_fallback_to_valhalla", False):
                return find_route_valhalla(request, settings, get_snapshot, client)
            raise

        current = get_snapshot()
        current_zones = zones_from(current, scale=scale)
        valid = _validate_ors_results(request, settings, trips, zones, current, current_zones)
        if valid:
            return _finalize_route_response(
                request=request, trips=valid, settings=settings,
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
            trips = parse_ors_routes(response)
        except RoutingError as exc:
            if exc.code == "ROUTING_UNAVAILABLE" and getattr(settings, "ors_fallback_to_valhalla", False):
                return await async_find_route_valhalla(request, settings, get_snapshot, client)
            raise

        current = await anyio.to_thread.run_sync(get_snapshot)
        current_zones = zones_from(current, scale=scale)
        valid = _validate_ors_results(request, settings, trips, zones, current, current_zones)
        if valid:
            return _finalize_route_response(
                request=request, trips=valid, settings=settings,
                current_snapshot=current, engine="ors", profile=ors_profile,
            )
        data = current
    raise RoutingError("NO_SUITABLE_ROUTE", "Không tìm được tuyến tránh vùng cấm sau hai lần kiểm tra.")
