from datetime import datetime, timezone

from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping
from shapely import transform
from sqlalchemy import func, select

from app.models import Measurement, Station


def classify(depth: float, warning: float, danger: float) -> str:
    if depth > danger:
        return "danger"
    return "warning" if depth >= warning else "normal"


def circle(station) -> dict:
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={station.latitude} +lon_0={station.longitude} +datum=WGS84 +units=m"
    )
    to_geo = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
    return mapping(transform(Point(0, 0).buffer(station.exclusion_radius_m), to_geo.transform, interleaved=False))


def snapshot(session, stale_seconds: int) -> dict:
    now = datetime.now(timezone.utc)
    stations, features = [], []
    for station in session.scalars(select(Station).where(Station.is_active).order_by(Station.id)):
        # Timestamped messages are ordered by event time, not arrival time.
        # Unsynchronized messages use received_at, but cannot establish freshness.
        latest = session.scalar(
            select(Measurement).where(Measurement.station_id == station.id)
            .order_by(func.coalesce(Measurement.measured_at, Measurement.received_at).desc(), Measurement.id.desc())
            .limit(1)
        )
        quality, hazard = "missing", "unknown"
        if latest:
            if not latest.sensor_ok:
                quality = "invalid"
            elif latest.measured_at is None or (now - latest.measured_at).total_seconds() > stale_seconds:
                quality = "stale"
            else:
                quality = "fresh"
                hazard = classify(latest.water_depth_cm, station.warning_threshold_cm, station.danger_threshold_cm)
        # Keep the last confirmed danger zone if the latest data becomes unusable.
        last_valid = session.scalar(
            select(Measurement).where(Measurement.station_id == station.id, Measurement.sensor_ok.is_(True))
            .order_by(func.coalesce(Measurement.measured_at, Measurement.received_at).desc(), Measurement.id.desc()).limit(1)
        )
        retained = quality != "fresh" and last_valid is not None and last_valid.water_depth_cm > station.danger_threshold_cm
        if hazard == "danger" or retained:
            features.append({"type": "Feature", "geometry": circle(station), "properties": {
                "station_id": station.id, "radius_m": station.exclusion_radius_m, "retained_due_to_uncertainty": retained, "source": "real",
            }})
        stations.append({
            "id": station.id, "name": station.name, "source": "real",
            "latitude": station.latitude, "longitude": station.longitude,
            "water_depth_cm": latest.water_depth_cm if latest else None,
            "measured_at": latest.measured_at if latest else None,
            "received_at": latest.received_at if latest else None,
            "hazard_state": hazard, "data_quality": quality,
        })
    return {"generated_at": now, "stations": stations,
            "flood_zones": {"type": "FeatureCollection", "features": features},
            "routing_data_sufficient": bool(stations) and all(s["data_quality"] == "fresh" for s in stations)}
