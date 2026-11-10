"""Publish a schema-valid sample using local infrastructure test credentials."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from paho.mqtt.publish import single

from app.config import Settings

parser = argparse.ArgumentParser()
parser.add_argument("--depth", type=float, default=23)
parser.add_argument("--invalid", action="store_true")
parser.add_argument("--device-id", default="station-01",
                    help="Station id; must exist in the stations table and match the topic.")
args = parser.parse_args()
settings = Settings()
infra = dict(line.split("=", 1) for line in (
    Path(__file__).resolve().parents[2] / "infra" / ".env"
).read_text().splitlines() if "=" in line and not line.startswith("#"))
message = {
    "device_id": args.device_id, "boot_id": str(uuid4()), "seq": 1,
    "measured_at": datetime.now(timezone.utc).isoformat(),
    "water_depth_cm": None if args.invalid else args.depth, "sensor_ok": not args.invalid,
}
single(f"flood/{args.device_id}/telemetry", json.dumps(message), qos=1,
       hostname=settings.mqtt_host, port=settings.mqtt_port,
       auth={"username": "station", "password": infra["MQTT_DEVICE_PASSWORD"]})
print(f"Published sample for {args.device_id}.")
