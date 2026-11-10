import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, delete

from app.config import Settings
from app.main import create_app
from app.models import Measurement, Station
from app.schemas import StationCreate, StationPatch


def settings(**changes):
    return Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, stations_enabled=True, **changes)


def test_stations_disabled_by_default():
    # Do not inherit the developer's .env: assert the model default itself.
    assert Settings.model_fields["stations_enabled"].default is False
    config = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, stations_enabled=False)
    with TestClient(create_app(config)) as client:
        for method, path in (("get", "/api/stations"), ("post", "/api/stations"), ("patch", "/api/stations/x"), ("delete", "/api/stations/x")):
            result = getattr(client, method)(path)
            assert result.status_code == 403
            assert result.json()["error"]["code"] == "STATIONS_DISABLED"


@pytest.mark.parametrize("changes", [
    {"id": "has space"}, {"id": "a/b"}, {"id": ""}, {"name": "  "},
    {"latitude": 90}, {"longitude": float("nan")}, {"exclusion_radius_m": 0},
    {"warning_threshold_cm": 30}, {"danger_threshold_cm": 0},
])
def test_reject_invalid_station_create(changes):
    values = {"id": "station-x", "name": "Trạm", "latitude": 20.98, "longitude": 105.77, **changes}
    with pytest.raises(ValidationError):
        StationCreate.model_validate(values)


def test_station_patch_rejects_null_and_id():
    with pytest.raises(ValidationError):
        StationPatch(name=None)
    with pytest.raises(ValidationError):
        StationPatch(id="other")


@pytest.mark.skipif(os.getenv("RUN_DATABASE_TESTS") != "1", reason="Requires migrated development PostgreSQL")
def test_station_crud_in_postgresql():
    config = Settings(mqtt_enabled=False, stations_enabled=True)
    engine = create_engine(config.database_url)
    station_id = "test-" + uuid4().hex
    try:
        with TestClient(create_app(config)) as client:
            result = client.post("/api/stations", json={
                "id": station_id, "name": "Trạm kiểm thử", "latitude": 20.9826, "longitude": 105.7704,
            })
            assert result.status_code == 201, result.text
            assert result.json()["id"] == station_id
            assert station_id in [s["id"] for s in client.get("/api/stations").json()]

            duplicate = client.post("/api/stations", json={
                "id": station_id, "name": "Trùng", "latitude": 20.98, "longitude": 105.77,
            })
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "STATION_EXISTS"

            result = client.patch(f"/api/stations/{station_id}", json={"latitude": 21.0, "is_active": False})
            assert result.status_code == 200
            assert result.json()["latitude"] == 21.0 and result.json()["is_active"] is False

            bad = client.patch(f"/api/stations/{station_id}", json={"warning_threshold_cm": 30})
            assert bad.status_code == 422
            assert bad.json()["error"]["code"] == "INVALID_INPUT"

            assert client.patch("/api/stations/missing", json={"is_active": True}).status_code == 404

            # A station with measurement history cannot be deleted; deactivation is the supported path.
            with engine.begin() as connection:
                connection.execute(Measurement.__table__.insert().values(
                    station_id=station_id, boot_id="test-boot", seq=1, sensor_ok=True, water_depth_cm=5,
                ))
            blocked = client.delete(f"/api/stations/{station_id}")
            assert blocked.status_code == 409
            assert blocked.json()["error"]["code"] == "STATION_HAS_MEASUREMENTS"

            with engine.begin() as connection:
                connection.execute(delete(Measurement).where(Measurement.station_id == station_id))
            assert client.delete(f"/api/stations/{station_id}").status_code == 204
            assert client.delete(f"/api/stations/{station_id}").status_code == 404
    finally:
        with engine.begin() as connection:
            connection.execute(delete(Measurement).where(Measurement.station_id == station_id))
            connection.execute(delete(Station).where(Station.id == station_id))
        engine.dispose()
