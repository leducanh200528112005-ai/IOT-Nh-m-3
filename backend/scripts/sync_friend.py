"""
Sync real station data from friend's machine into local database and MQTT broker.
Runs as a background service without altering any existing project files.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.models import Station

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_friend")

FRIEND_API_URL = "http://10.155.201.172:5173/api/flood-zones?source=real"

def ensure_station_registered(engine, station_data):
    st_id = station_data.get("id", "station-01")
    name = station_data.get("name", "Trạm 1 (Thực tế)")
    lat = float(station_data.get("latitude", 20.9826))
    lon = float(station_data.get("longitude", 105.7704))
    
    with engine.begin() as conn:
        stmt = insert(Station).values(
            id=st_id,
            name=name,
            latitude=lat,
            longitude=lon,
            warning_threshold_cm=10.0,
            danger_threshold_cm=20.0,
            exclusion_radius_m=40.0,
            is_active=True,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"name": name, "latitude": lat, "longitude": lon, "is_active": True}
        )
        conn.execute(stmt)
    logger.info(f"Station {st_id} verified/registered in local database.")

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)
    
    infra_env = Path(__file__).resolve().parents[2] / "infra" / ".env"
    infra_vars = dict(
        line.split("=", 1)
        for line in infra_env.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    mqtt_pass = infra_vars.get("MQTT_DEVICE_PASSWORD")

    # Persistent MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="friend-sync-agent")
    client.username_pw_set("station", mqtt_pass)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_start()
    
    logger.info(f"Connected to local MQTT broker. Starting sync from {FRIEND_API_URL}...")
    seq = 1
    last_seen_state = None
    station_ensured = False

    try:
        while True:
            try:
                req = urllib.request.Request(
                    FRIEND_API_URL,
                    headers={"User-Agent": "FloodSyncAgent/1.0"}
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                
                stations = data.get("stations", [])
                if stations:
                    st = stations[0]
                    st_id = st.get("id", "station-01")
                    
                    if not station_ensured:
                        ensure_station_registered(engine, st)
                        station_ensured = True
                    
                    depth = st.get("water_depth_cm")
                    quality = st.get("data_quality", "missing")
                    hazard = st.get("hazard_state")
                    current_state = (depth, quality, hazard)
                    
                    sensor_ok = (depth is not None and quality != "invalid")
                    
                    msg = {
                        "device_id": st_id,
                        "boot_id": "friend-esp32-stream",
                        "seq": seq,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                        "water_depth_cm": float(depth) if sensor_ok else None,
                        "sensor_ok": sensor_ok
                    }
                    
                    client.publish(f"flood/{st_id}/telemetry", json.dumps(msg), qos=1)
                    
                    if current_state != last_seen_state:
                        logger.info(
                            f"==> Synced update: {st_id} ({st.get('name')}) | Depth: {depth} cm | Quality: {quality} | Hazard: {hazard}"
                        )
                        last_seen_state = current_state
                    
                    seq += 1
            except urllib.error.URLError as e:
                logger.warning(f"Connection to friend's machine failed: {e}")
            except Exception as e:
                logger.error(f"Sync error: {e}")
                
            time.sleep(2.5)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
