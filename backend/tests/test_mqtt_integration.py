"""Real local broker -> FastAPI subscriber -> PostgreSQL -> HTTP smoke test."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from paho.mqtt.publish import single
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import Measurement


@pytest.mark.skipif(os.getenv("RUN_MQTT_TESTS") != "1", reason="Set RUN_MQTT_TESTS=1 for local broker smoke test")
def test_real_mqtt_to_database_to_http():
    settings = Settings(mqtt_client_id="integration-" + uuid4().hex)
    infra = dict(line.split("=", 1) for line in (
        Path(__file__).resolve().parents[2] / "infra" / ".env"
    ).read_text().splitlines() if "=" in line and not line.startswith("#"))
    boot_id = "test-" + uuid4().hex
    engine = create_engine(settings.database_url)
    try:
        with TestClient(create_app(settings)) as client:
            deadline = time.monotonic() + 20
            while client.get("/api/ready").status_code != 200:
                assert time.monotonic() < deadline, "Subscriber failed to connect"
                threading.Event().wait(0.1)
            message = json.dumps({"device_id": "station-01", "boot_id": boot_id, "seq": 1,
                                  "measured_at": datetime.now(timezone.utc).isoformat(),
                                  "water_depth_cm": 23, "sensor_ok": True})
            # Retry publishing same id until subscriber is ready; unique key must deduplicate.
            while True:
                single("flood/station-01/telemetry", message, qos=1,
                       hostname=settings.mqtt_host, port=settings.mqtt_port,
                       auth={"username": "station-01", "password": infra["MQTT_STATION_PASSWORD"]})
                with Session(engine) as session:
                    found = session.scalar(select(Measurement.id).where(Measurement.boot_id == boot_id))
                if found:
                    break
                assert time.monotonic() < deadline, "MQTT message not persisted"
                threading.Event().wait(0.1)
            response = client.get("/api/flood-zones")
            assert response.status_code == 200
            station = next(s for s in response.json()["stations"] if s["id"] == "station-01")
            assert station["hazard_state"] == "danger"
    finally:
        with engine.begin() as connection:
            connection.execute(delete(Measurement).where(Measurement.boot_id == boot_id, Measurement.station_id == "station-01"))
        engine.dispose()
