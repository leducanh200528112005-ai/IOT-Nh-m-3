import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, select

from app.config import Settings
from app.demo import selected_snapshot
from app.main import create_app
from app.models import DemoPoint
from app.schemas import DemoPointCreate, DemoPointPatch, RouteRequest


def settings(**changes):
    return Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, demo_enabled=True, **changes)


def point(**changes):
    return SimpleNamespace(id="demo-test", name="Demo", latitude=20.98, longitude=105.77,
        water_depth_cm=23, warning_threshold_cm=10, danger_threshold_cm=20,
        exclusion_radius_m=40, updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc), **changes)


def real_data(quality="stale"):
    return {"generated_at": datetime.now(timezone.utc), "stations": [{"id": "real-test", "source": "real", "data_quality": quality}],
        "flood_zones": {"type": "FeatureCollection", "features": []}, "routing_data_sufficient": quality == "fresh"}


def test_demo_never_expires_and_does_not_query_real():
    session = Mock()
    session.scalars.return_value = [point()]
    with patch("app.demo.snapshot") as real:
        data = selected_snapshot(session, settings(), "demo", False)
    real.assert_not_called()
    assert data["routing_data_sufficient"]
    station = data["stations"][0]
    assert station["data_quality"] == "fresh" and station["hazard_state"] == "danger"
    assert station["source"] == "demo" and station["measured_at"] is None
    assert data["flood_zones"]["features"][0]["properties"]["source"] == "demo"


@pytest.mark.parametrize("quality,sufficient", [("fresh", True), ("stale", False), ("invalid", False), ("missing", False)])
def test_combined_keeps_real_validation(quality, sufficient):
    session = Mock()
    session.scalars.return_value = [point()]
    with patch("app.demo.snapshot", return_value=real_data(quality)):
        data = selected_snapshot(session, settings(), "demo", True)
    assert data["routing_data_sufficient"] == sufficient
    assert {s["source"] for s in data["stations"]} == {"real", "demo"}


def test_no_active_demo_points_not_sufficient():
    session = Mock()
    session.scalars.return_value = []
    assert not selected_snapshot(session, settings(), "demo")["routing_data_sufficient"]


def test_real_mode_does_not_read_demo_table():
    session = Mock()
    with patch("app.demo.snapshot", return_value=real_data("fresh")):
        assert selected_snapshot(session, settings())["source"] == "real"
    session.scalars.assert_not_called()


def test_demo_disabled_endpoints_and_source():
    config = settings()
    config.demo_enabled = False
    with TestClient(create_app(config)) as client:
        for path in ("/api/demo-points", "/api/flood-zones?source=demo"):
            result = client.get(path)
            assert result.status_code == 403
            assert result.json()["error"]["code"] == "DEMO_DISABLED"


def test_source_validation():
    with pytest.raises(ValidationError):
        RouteRequest(source="real", include_real=True,
            start={"latitude": 10, "longitude": 100}, end={"latitude": 11, "longitude": 100})


def test_get_source_validation_without_database():
    with TestClient(create_app(settings())) as client:
        result = client.get("/api/flood-zones?source=real&include_real=true")
        assert result.status_code == 422
        assert result.json()["error"]["code"] == "INVALID_INPUT"
        assert client.get("/api/flood-zones?source=other").status_code == 422


def test_demo_routing_keeps_labels_and_warning():
    import httpx
    from app.routing import find_route

    config = settings()
    config.ors_api_key = type(config.ors_api_key)("test-key")
    route_request = RouteRequest(source="demo", include_real=True,
        start={"longitude": 105.75, "latitude": 20.98}, end={"longitude": 105.76, "latitude": 20.98})
    data = {"generated_at": datetime.now(timezone.utc), "routing_data_sufficient": True,
            "flood_zones": {"type": "FeatureCollection", "features": []}}
    client = Mock(post=Mock(return_value=httpx.Response(200, json={"features": [{
        "geometry": {"type": "LineString", "coordinates": [[105.75, 20.98], [105.76, 20.98]]},
        "properties": {"summary": {"distance": 1000, "duration": 120}},
    }]})))
    result = find_route(route_request, config, lambda: data, client)
    assert result["source"] == "demo" and result["include_real"]
    assert "MÔ PHỎNG" in result["warnings"][0]


@pytest.mark.parametrize("changes", [
    {"water_depth_cm": -1}, {"warning_threshold_cm": 30}, {"name": "  "},
    {"exclusion_radius_m": 0}, {"latitude": 90}, {"longitude": float("nan")},
])
def test_reject_invalid_demo_create(changes):
    values = {"name": "Demo", "latitude": 20.98, "longitude": 105.77, **changes}
    with pytest.raises(ValidationError):
        DemoPointCreate.model_validate(values)


def test_patch_rejects_explicit_null():
    with pytest.raises(ValidationError):
        DemoPointPatch(water_depth_cm=None)


@pytest.mark.skipif(os.getenv("RUN_DATABASE_TESTS") != "1", reason="Requires migrated development PostgreSQL")
def test_crud_and_snapshots_in_postgresql():
    config = Settings(mqtt_enabled=False, demo_enabled=True)
    engine = create_engine(config.database_url)
    created_ids = []
    try:
        with TestClient(create_app(config)) as client:
            result = client.post("/api/demo-points", json={
                "name": "Test-" + uuid4().hex, "latitude": 20.9826, "longitude": 105.7704, "water_depth_cm": 25,
            })
            assert result.status_code == 201, result.text
            created = result.json()
            identifier = created["id"]
            created_ids.append(identifier)
            assert identifier in [p["id"] for p in client.get("/api/demo-points").json()]
            data = client.get("/api/flood-zones?source=demo").json()
            assert data["routing_data_sufficient"]
            assert next(s for s in data["stations"] if s["id"] == identifier)["hazard_state"] == "danger"
            assert identifier not in [s["id"] for s in client.get("/api/flood-zones").json()["stations"]]

            result = client.patch(f"/api/demo-points/{identifier}", json={"warning_threshold_cm": 30})
            assert result.status_code == 422
            assert client.patch(f"/api/demo-points/{identifier}", json={"warning_threshold_cm": 30, "danger_threshold_cm": 40, "water_depth_cm": 35}).status_code == 200
            data = client.get("/api/flood-zones?source=demo").json()
            assert next(s for s in data["stations"] if s["id"] == identifier)["hazard_state"] == "warning"
            assert identifier not in [f["properties"]["station_id"] for f in data["flood_zones"]["features"]]
            assert client.patch(f"/api/demo-points/{identifier}", json={"is_active": False}).status_code == 200
            assert identifier not in [s["id"] for s in client.get("/api/flood-zones?source=demo").json()["stations"]]
            assert client.delete(f"/api/demo-points/{identifier}").status_code == 204
            assert client.delete(f"/api/demo-points/{identifier}").status_code == 404
    finally:
        with engine.begin() as connection:
            connection.execute(delete(DemoPoint).where(DemoPoint.id.in_(created_ids)))
        engine.dispose()
