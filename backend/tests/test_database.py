"""Explicitly enabled integration tests; use a uniquely named temporary station."""
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.flood import snapshot
from app.models import Measurement, Station
from app.telemetry import save_telemetry

pytestmark = pytest.mark.skipif(os.getenv("RUN_DATABASE_TESTS") != "1", reason="Set RUN_DATABASE_TESTS=1 with migrated PostgreSQL")


@pytest.fixture
def station_session():
    engine = create_engine(Settings().database_url)
    station_id = "test-" + uuid4().hex
    with Session(engine) as session:
        session.add(Station(id=station_id, name="Integration test", latitude=10.77, longitude=106.7))
        session.commit()
        try:
            yield session, station_id
        finally:
            session.rollback()
            session.execute(delete(Measurement).where(Measurement.station_id == station_id))
            session.execute(delete(Station).where(Station.id == station_id))
            session.commit()
    engine.dispose()


def send(session, station_id, seq=1, depth=23, age=0, sensor_ok=True):
    return save_telemetry(session, f"flood/{station_id}/telemetry", json.dumps({
        "device_id": station_id, "boot_id": "test-boot", "seq": seq,
        "measured_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
        "water_depth_cm": depth, "sensor_ok": sensor_ok,
    }).encode())


def state(session, station_id):
    data = snapshot(session, 15)
    station = next(s for s in data["stations"] if s["id"] == station_id)
    features = [f for f in data["flood_zones"]["features"] if f["properties"]["station_id"] == station_id]
    return station, features


def test_duplicate(station_session):
    session, station_id = station_session
    assert send(session, station_id)
    assert not send(session, station_id)
    assert session.scalar(select(func.count()).select_from(Measurement).where(Measurement.station_id == station_id)) == 1


def test_old_arrival_does_not_clear_danger(station_session):
    session, station_id = station_session
    send(session, station_id)
    send(session, station_id, seq=0, depth=0, age=60)
    station, features = state(session, station_id)
    assert station["hazard_state"] == "danger"
    assert len(features) == 1


def test_stale_danger_retained(station_session):
    session, station_id = station_session
    send(session, station_id, age=60)
    station, features = state(session, station_id)
    assert station["hazard_state"] == "unknown"
    assert station["data_quality"] == "stale"
    assert features[0]["properties"]["retained_due_to_uncertainty"]


def test_invalid_does_not_clear_danger(station_session):
    session, station_id = station_session
    send(session, station_id)
    send(session, station_id, seq=2, depth=None, sensor_ok=False)
    station, features = state(session, station_id)
    assert station["data_quality"] == "invalid"
    assert station["hazard_state"] == "unknown"
    assert len(features) == 1


def test_missing(station_session):
    session, station_id = station_session
    station, features = state(session, station_id)
    assert station["data_quality"] == "missing"
    assert not features


def test_topic_mismatch(station_session):
    session, station_id = station_session
    with pytest.raises(ValueError):
        save_telemetry(session, "flood/other/telemetry", json.dumps({
            "device_id": station_id, "boot_id": "test", "seq": 0,
            "sensor_ok": True, "water_depth_cm": 2,
        }).encode())
