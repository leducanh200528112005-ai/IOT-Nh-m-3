from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from app.flood import classify, circle
from app.models import Station
from app.schemas import Telemetry


@pytest.mark.parametrize("depth,expected", [(0, "normal"), (9.9, "normal"), (10, "warning"), (20, "warning"), (20.1, "danger")])
def test_thresholds(depth, expected):
    assert classify(depth, 10, 20) == expected


def payload(**changes):
    return {"device_id": "station-01", "boot_id": "test", "seq": 1,
            "measured_at": datetime.now(timezone.utc), "sensor_ok": True, "water_depth_cm": 15, **changes}


@pytest.mark.parametrize("changes", [
    {"water_depth_cm": None}, {"sensor_ok": False}, {"water_depth_cm": -1},
    {"seq": True}, {"seq": -1}, {"water_depth_cm": float("nan")},
    {"measured_at": datetime(2026, 1, 1)},
    {"measured_at": datetime.now(timezone.utc) + timedelta(days=1)},
])
def test_reject_invalid_payload(changes):
    with pytest.raises(ValidationError):
        Telemetry.model_validate(payload(**changes))


def test_sensor_error():
    assert not Telemetry.model_validate(payload(sensor_ok=False, water_depth_cm=None)).sensor_ok


def test_circle_geojson():
    result = circle(Station(latitude=10.77, longitude=106.7, exclusion_radius_m=40))
    assert result["type"] == "Polygon"
    lon, lat = result["coordinates"][0][0]
    assert abs(lon - 106.7) < 0.001 and abs(lat - 10.77) < 0.001
