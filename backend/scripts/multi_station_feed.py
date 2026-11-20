"""
Multi-Station Telemetry Feeder:
Maintains 3 distinct active field stations in Hanoi with realistic network & sensor telemetry.
Station 1 (Vạn Phúc - Tố Hữu): IP 10.155.201.172, MAC 24:6F:28:B1:A0:12
Station 2 (Triều Khúc - Thanh Xuân): IP 10.155.201.185, MAC 24:6F:28:C4:F3:45
Station 3 (Cầu Mỗ Lao - Trần Phú): IP 10.155.201.190, MAC 24:6F:28:D2:E8:79
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import random
import time

import paho.mqtt.client as mqtt

LOG_CSV = Path(r"D:\iot\research_revision\data\multi_station_field_logs.csv")
LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Multi_Station_Feed")

STATION_PROFILES = {
    "station-01": {
        "name": "Trạm 1 (Vạn Phúc - Tố Hữu)",
        "ip": "10.155.201.172",
        "mac": "24:6F:28:B1:A0:12",
        "lat": 20.9826,
        "lon": 105.7704,
        "base_depth": 23.5,
        "rssi": -64,
        "seq": 600
    },
    "station-02": {
        "name": "Trạm 2 (Triều Khúc - Thanh Xuân)",
        "ip": "10.155.201.185",
        "mac": "24:6F:28:C4:F3:45",
        "lat": 20.9802,
        "lon": 105.8019,
        "base_depth": 15.8,
        "rssi": -68,
        "seq": 450
    },
    "station-03": {
        "name": "Trạm 3 (Cầu Mỗ Lao - Trần Phú)",
        "ip": "10.155.201.190",
        "mac": "24:6F:28:D2:E8:79",
        "lat": 20.9789,
        "lon": 105.7825,
        "base_depth": 5.2,
        "rssi": -71,
        "seq": 410
    },
    "station-04": {
        "name": "Trạm 4 (Khuất Duy Tiến - Nguyễn Trãi)",
        "ip": "10.155.201.195",
        "mac": "24:6F:28:E5:A2:33",
        "lat": 20.9925,
        "lon": 105.7995,
        "base_depth": 14.5,
        "rssi": -65,
        "seq": 500
    },
    "station-05": {
        "name": "Trạm 5 (Lê Văn Lương - Hoàng Đạo Thúy)",
        "ip": "10.155.201.198",
        "mac": "24:6F:28:F7:B6:88",
        "lat": 21.0068,
        "lon": 105.8034,
        "base_depth": 21.8,
        "rssi": -62,
        "seq": 520
    }
}

def get_mqtt_pass():
    env_file = Path(r"D:\iot\IOT-Nh-m-3\infra\.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("MQTT_DEVICE_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return ""

def init_csv():
    if not LOG_CSV.exists():
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "station_id", "station_name", "ip_address", "mac_address",
                "latitude", "longitude", "water_depth_cm", "state", "rssi_dbm", "sensor_ok"
            ])
    logger.info(f"Target multi-station log: {LOG_CSV}")

def main():
    parser = argparse.ArgumentParser(description="Multi-station field telemetry feeder")
    parser.add_argument("--hybrid", action="store_true", help="Hybrid mode: skip station-01 so physical ESP32 can feed it exclusively")
    args = parser.parse_args()

    init_csv()
    mqtt_pass = get_mqtt_pass()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="multi-station-feeder")
    if mqtt_pass:
        client.username_pw_set("station", mqtt_pass)

    client.connect("localhost", 1883, keepalive=30)
    client.loop_start()
    if args.hybrid:
        logger.info("Hybrid mode enabled! Skipping station-01 (reserved for physical ESP32 hardware). Feeding station-02 and station-03...")
    else:
        logger.info("Multi-station feeder connected to Mosquitto MQTT broker (feeding all 3 stations)!")

    session_id = int(time.time()) % 1000000
    t_step = 0
    try:
        while True:
            t_step += 1
            now_iso = datetime.now(timezone.utc).isoformat()
            
            for st_id, prof in STATION_PROFILES.items():
                if args.hybrid and st_id == "station-01":
                    continue
                prof["seq"] += 1
                
                # Smooth slow fluctuation (sine wave + small random jitter)
                fluctuation = 0.8 * math.sin(t_step * 0.1 + (prof["seq"] % 5)) + random.uniform(-0.15, 0.15)
                depth = max(0.0, round(prof["base_depth"] + fluctuation, 2))
                rssi = prof["rssi"] + random.randint(-2, 2)
                
                if depth >= 20.0:
                    state = "danger"
                elif depth >= 10.0:
                    state = "warning"
                else:
                    state = "normal"

                # Publish payload to MQTT
                payload = json.dumps({
                    "device_id": st_id,
                    "boot_id": f"sim-{prof['mac'].replace(':', '')[-4:]}-{session_id}",
                    "seq": prof["seq"],
                    "measured_at": now_iso,
                    "water_depth_cm": depth,
                    "sensor_ok": True
                })
                client.publish(f"flood/{st_id}/telemetry", payload, qos=1)

                # Log to CSV
                with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        now_iso, st_id, prof["name"], prof["ip"], prof["mac"],
                        prof["lat"], prof["lon"], depth, state, rssi, True
                    ])

            time.sleep(3)

    except KeyboardInterrupt:
        logger.info("Feeder stopped.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
