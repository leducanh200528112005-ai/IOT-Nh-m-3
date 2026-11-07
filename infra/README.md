# PostgreSQL + Mosquitto cho he thong IoT

## 1. Chuan bi va khoi chay

Can Docker Desktop dang chay voi Linux containers / WSL2. Mo PowerShell:

```powershell
cd D:\CODE\IOT\infra
powershell -ExecutionPolicy Bypass -File .\setup.ps1
docker compose up -d
docker compose ps
docker compose logs --tail=100 postgres mosquitto
```

`setup.ps1` tao `.env` voi mat khau ngau nhien va file hash MQTT `mosquitto/config/passwords`. Chay lai script khong ghi de cac file nay. Runtime mount cau hinh MQTT read-only; helper tao tai khoan moi duoc mount read/write.

Khong dua `.env` va `mosquitto/config/passwords` len Git. Mat khau MQTT trong `.env` dung de cau hinh thiet bi/backend, khong duoc tu dong nap vao broker: broker doc file hash `passwords`.

## 2. Phien ban

- `postgres:17`: nhanh PostgreSQL 17, nhan cac ban va khi pull image moi.
- `eclipse-mosquitto:2.0.22`: co dinh ban Mosquitto, ho tro MQTT QoS 1.
- Khong can build image hay cai PostgreSQL/Mosquitto truc tiep tren Windows.
- PostgreSQL 17 dung volume tai `/var/lib/postgresql/data`. Khong tu y doi major image voi du lieu cu; can backup va migration. Tag major 17 khong co nghia image da pull se tu cap nhat.

## 3. Ket noi PostgreSQL / DBeaver

| Truong | Gia tri |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `flood_monitor` |
| User | `flood_admin` |
| Password | `POSTGRES_PASSWORD` trong `.env` |

Database chi publish tren loopback laptop, khong mo ra LAN. Tai khoan khoi tao co quyen quan tri; nen tao user it quyen rieng cho backend khi trien khai that.

Kiem tra:

```powershell
docker compose exec postgres psql -U flood_admin -d flood_monitor -c "SELECT version();"
```

## 4. Ket noi MQTT

| Client | Host | Port | Username | Password |
|---|---|---|---|---|
| FastAPI chay tren laptop | `localhost` | 1883 | `backend` | `MQTT_BACKEND_PASSWORD` trong `.env` |
| ESP32 | IPv4 Wi-Fi cua laptop | 1883 | `station-01` | `MQTT_STATION_PASSWORD` trong `.env` |

- ESP32 khong dung `localhost`. Dung `ipconfig` de tim IP laptop.
- ESP32 publish QoS 1, backend subscribe QoS 1.
- Thiet bi chi duoc publish `flood/station-01/telemetry` va `flood/station-01/status`.
- Backend chi duoc subscribe telemetry/status cac tram.
- Telemetry khong retain. Status nen retain, kem Last Will offline.
- Last Will va keepalive do MQTT client cau hinh, khong phai file Compose.
- MQTT chua co TLS: chi dung LAN tin cay, khong port-forward ra Internet.
- Cho phep TCP 1883 tren Windows Firewall, profile Private va pham vi Local subnet neu can. Cau hinh nay khong tu sua firewall.
- Neu FastAPI sau nay chay cung Compose: dung hostname `postgres` va `mosquitto`, khong dung `localhost`.

### Thu MQTT

Mo hai terminal tai thu muc nay. Thay placeholder bang mat khau trong `.env`.

Terminal 1:

```powershell
docker compose exec mosquitto mosquitto_sub -h localhost -u backend -P "MAT_KHAU_BACKEND" -t "flood/+/telemetry" -q 1 -v
```

Terminal 2:

```powershell
docker compose exec mosquitto mosquitto_pub -h localhost -u station-01 -P "MAT_KHAU_THIET_BI" -t "flood/station-01/telemetry" -q 1 -m "test-message"
```

Terminal 1 phai nhan duoc message. Day chi la thu broker, khong phai JSON telemetry hop le. Dung tai khoan thu nghiem: lenh co the luu mat khau trong lich su shell.

## 5. Du lieu va van hanh

```powershell
docker compose stop
docker compose start
docker compose down
```

`down` xoa container/network nhung giu named volumes. **Khong dung `docker compose down -v` neu can giu du lieu**: lenh do xoa volumes. Volume khong thay the backup.

- PostgreSQL luu lich su vao volume `postgres_data`.
- Mosquitto persistence luu trang thai MQTT can thiet vao `mosquitto_data`, khong thay the lich su so do trong PostgreSQL.
- Sua mat khau PostgreSQL trong `.env` khong doi mat khau DB da khoi tao; can doi bang SQL.
- Sua mat khau MQTT trong `.env` khong doi file hash da ton tai; can cap nhat tai khoan bang `mosquitto_passwd` qua helper read/write va restart broker. Khong xoa file hash hay volume de doi mat khau mot cach tuy tien.
- Neu cong 5432 hoac 1883 da bi chiem, doi cong ben trai trong `ports` va cap nhat client tuong ung.
- Ban hash MQTT nhay cam, can bao ve thu muc du an bang quyen truy cap Windows phu hop.
