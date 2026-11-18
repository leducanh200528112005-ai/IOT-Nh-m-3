"""
ESP32 Serial Bridge:
Reads real ultrasonic sensor data directly from ESP32 over USB COM port.
Logs real measurements to research CSV and forwards to local MQTT/database when available.
"""
import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("pyserial not found! Please run: pip install pyserial")
    sys.exit(1)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

LOG_CSV = Path(r"D:\iot\research_revision\data\real_hardware_logs.csv")
LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ESP32_Bridge")

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
            writer.writerow(["timestamp", "device_id", "seq", "water_depth_cm", "sensor_ok"])
    logger.info(f"Target real dataset: {LOG_CSV}")

def log_to_csv(dev_id, seq, water_depth_cm, sensor_ok):
    ts = datetime.now(timezone.utc).isoformat()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([ts, dev_id, seq, water_depth_cm if water_depth_cm is not None else "", sensor_ok])

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "CP210" in p.description or "CH340" in p.description or "USB Serial" in p.description or "COM3" in p.device:
            return p.device
    if ports:
        return ports[0].device
    return None

def main():
    init_csv()
    port = find_esp32_port() or "COM3"
    baud = 115200
    
    logger.info(f"Opening Serial port {port} at {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        logger.error(f"Cannot open port {port}: {e}")
        return

    # MQTT client setup if broker is running
    mqtt_client = None
    if mqtt:
        try:
            mqtt_pass = get_mqtt_pass()
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="usb-serial-bridge")
            if mqtt_pass:
                mqtt_client.username_pw_set("station", mqtt_pass)
            mqtt_client.connect("localhost", 1883, keepalive=30)
            mqtt_client.loop_start()
            logger.info("Connected to local Mosquitto MQTT broker!")
        except Exception:
            logger.warning("Local MQTT broker not reachable; data will be logged directly to CSV.")
            mqtt_client = None

    seq = 0
    dev_id = "station-01"
    
    # Regex patterns to parse ESP32 outputs
    re_water = re.compile(r"water\s*=\s*([0-9.]+)\s*cm", re.IGNORECASE)
    re_dist = re.compile(r"distance\s*=\s*([0-9.]+)\s*cm", re.IGNORECASE)
    re_raw = re.compile(r"raw_cm\s*=\s*([0-9.]+)", re.IGNORECASE)
    re_echo = re.compile(r"echo_us\s*=\s*([0-9]+)", re.IGNORECASE)
    re_state = re.compile(r"(DANGEROUS|WARNING|SAFE|NORMAL)", re.IGNORECASE)

    logger.info("Ready! Listening for real sensor readings from ESP32...")
    
    try:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            
            # Print raw line for debugging if it starts with SENSOR or LOCAL
            if line.startswith("SENSOR:") or line.startswith("LOCAL:") or line.startswith("NETWORK:"):
                # Parse
                water_depth = None
                distance = None
                sensor_ok = True
                
                m_w = re_water.search(line)
                m_d = re_dist.search(line)
                m_r = re_raw.search(line)
                m_e = re_echo.search(line)
                m_st = re_state.search(line)

                if "reason=NO_ECHO" in line or "SENSOR_ERROR" in line:
                    sensor_ok = False

                if m_w:
                    water_depth = float(m_w.group(1))
                if m_d:
                    distance = float(m_d.group(1))
                elif m_r and float(m_r.group(1)) > 0:
                    distance = float(m_r.group(1))
                    if water_depth is None:
                        water_depth = max(0.0, 30.0 - distance)

                if line.startswith("LOCAL:") and water_depth is not None:
                    seq += 1
                    log_to_csv(dev_id, seq, water_depth, True)
                    
                    if water_depth >= 20.0:
                        st_indicator = "🔴 NGUY HIEM (DANGER - MUC NUOC CAO)"
                    elif water_depth >= 10.0:
                        st_indicator = "🟡 CANH BAO (WARNING)"
                    else:
                        st_indicator = "🟢 AN TOAN (SAFE)"

                    print(f"[THUC TE] #{seq:03d} | Khoang cach vat can: {distance:.1f} cm | Muc nuoc: {water_depth:.1f} cm | {st_indicator}", flush=True)

                    if mqtt_client and mqtt_client.is_connected():
                        payload = json.dumps({
                            "device_id": dev_id,
                            "boot_id": "usb-bridge",
                            "seq": seq,
                            "measured_at": datetime.now(timezone.utc).isoformat(),
                            "water_depth_cm": round(water_depth, 2),
                            "sensor_ok": True
                        })
                        mqtt_client.publish(f"flood/{dev_id}/telemetry", payload, qos=1)

                elif "NO_ECHO" in line and not line.startswith("LOCAL:"):
                    print("[CHU Y] Cam bien chua thay vat can trong pham vi 2 - 30 cm (Hoac dang chuc xuong khong khi/day hoi long). Hay de ban tay truoc mat cam bien ~15cm!", flush=True)

    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    finally:
        ser.close()
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

if __name__ == "__main__":
    main()
