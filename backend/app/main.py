import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.ai.predictor import predict_flood_risk
from app.config import Settings
from app.demo import create_demo_router, require_demo, selected_snapshot
from app.flood import classify, snapshot
from app.models import DemoPoint, Measurement, Station
from app.mqtt import create_client
from app.routing import RoutingError, async_find_route
from app.schemas import RouteRequest
from app.security import SlidingWindowLimiter
from app.stations import create_station_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine)
    route_limiter = SlidingWindowLimiter(getattr(settings, "rate_limit_route_per_min", 30))

    routing_cache: dict[str, Any] = {"expires_at": 0.0, "data": None}
    geocode_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO)
        client = None
        try:
            if settings.mqtt_enabled:
                client = create_client(settings, sessions)
                client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=30)
                client.loop_start()
            app.state.mqtt_client = client
            yield
        finally:
            if client:
                client.disconnect()
                client.loop_stop()
            engine.dispose()

    app = FastAPI(title="Flood IoT API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(create_demo_router(settings, sessions))
    app.include_router(create_station_router(settings, sessions))

    async def check_routing_services(force: bool = False) -> dict:
        now_m = time.monotonic()
        if not force and routing_cache["data"] is not None and now_m < routing_cache["expires_at"]:
            return {**routing_cache["data"], "cached": True}

        results: dict[str, Any] = {
            "valhalla": {"status": "unknown"},
            "osrm": {"status": "unknown"},
            "ors": {
                "status": "configured" if settings.ors_api_key.get_secret_value().strip() else "unconfigured",
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
        valhalla_status_url = getattr(settings, "valhalla_status_url", "https://valhalla1.openstreetmap.de/status")
        osrm_check_url = getattr(settings, "osrm_base_url", "https://router.project-osrm.org").rstrip("/") + "/nearest/v1/driving/105.77,20.98"

        # follow_redirects=False prevents SSRF/open-redirect hops to unintended internal targets.
        async with httpx.AsyncClient(follow_redirects=False) as client:
            for key, url in (("valhalla", valhalla_status_url), ("osrm", osrm_check_url)):
                started = time.perf_counter()
                try:
                    resp = await client.get(url, timeout=4.0)
                    latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
                    if resp.status_code == 200:
                        results[key] = {"status": "ok", "latency_ms": latency_ms}
                    else:
                        results[key] = {"status": f"error_{resp.status_code}", "latency_ms": latency_ms}
                except httpx.RequestError as exc:
                    results[key] = {"status": f"unreachable ({type(exc).__name__})"}

        routing_cache["data"] = results
        routing_cache["expires_at"] = now_m + 60.0
        return results

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM stations LIMIT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
        client = getattr(app.state, "mqtt_client", None)
        mqtt_ok = not settings.mqtt_enabled or (client is not None and client.is_connected())
        return JSONResponse(status_code=200 if mqtt_ok else 503, content={
            "status": "ready" if mqtt_ok else "not_ready", "database": "ok",
            "mqtt": "disabled" if not settings.mqtt_enabled else ("connected" if mqtt_ok else "disconnected"),
        })

    @app.get("/api/routing-status")
    async def routing_status(refresh: bool = False):
        return await check_routing_services(force=refresh)

    @app.get("/api/geocode")
    async def geocode(q: str = Query(min_length=2, max_length=120), limit: int = Query(default=6, ge=1, le=10)):
        cleaned = q.strip()
        if len(cleaned) < 2:
            raise RoutingError("INVALID_INPUT", "Từ khóa tìm kiếm phải có ít nhất 2 ký tự.")
        cache_key = (cleaned.lower(), limit)
        now_m = time.monotonic()
        cached = geocode_cache.get(cache_key)
        if cached and now_m < cached[0]:
            return {"query": cleaned, "results": cached[1], "cached": True}

        photon_url = getattr(settings, "photon_base_url", "https://photon.komoot.io").rstrip("/") + "/api/"
        params = {"q": cleaned, "lat": 20.98, "lon": 105.77, "limit": min(limit * 2, 15)}
        async with httpx.AsyncClient(follow_redirects=False) as client:
            try:
                resp = await client.get(
                    photon_url,
                    params=params,
                    headers={"User-Agent": "FloodSafeRouteWebGIS/1.0"},
                    timeout=6.0,
                )
            except httpx.RequestError as exc:
                logger.warning("Geocoding upstream error: %s", exc)
                raise RoutingError("GEOCODE_UNAVAILABLE", "Không kết nối được dịch vụ tìm kiếm địa chỉ.", 502) from None
        if resp.status_code != 200:
            raise RoutingError("GEOCODE_UNAVAILABLE", "Dịch vụ tìm kiếm địa chỉ tạm gián đoạn.", 502)

        features = resp.json().get("features", [])
        vn_first = sorted(features, key=lambda f: 0 if f.get("properties", {}).get("countrycode") == "VN" else 1)
        items = []
        seen = set()
        for f in vn_first:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if len(coords) != 2:
                continue
            name = props.get("name") or props.get("street") or props.get("district") or cleaned
            parts = [p for p in (name, props.get("street") if props.get("street") != name else None, props.get("district"), props.get("city") or props.get("state")) if p]
            label = ", ".join(dict.fromkeys(parts))
            dedup_key = (label, round(coords[1], 5), round(coords[0], 5))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            items.append({
                "label": label,
                "latitude": float(coords[1]),
                "longitude": float(coords[0]),
                "city": props.get("city") or props.get("state") or "",
                "district": props.get("district") or "",
            })
            if len(items) >= limit:
                break

        geocode_cache[cache_key] = (now_m + 300.0, items)
        return {"query": cleaned, "results": items, "cached": False}

    @app.get("/api/flood-zones")
    def flood_zones(source: Literal["real", "demo"] = "real", include_real: bool = False):
        with sessions() as session:
            return selected_snapshot(session, settings, source, include_real)

    @app.get("/api/flood-zones/stream")
    async def flood_zones_stream(source: Literal["real", "demo"] = "real", include_real: bool = False):
        if source == "real" and include_real:
            raise RoutingError("INVALID_INPUT", "include_real chỉ dùng với source=demo.")
        if source == "demo":
            require_demo(settings)

        async def event_gen():
            last_payload: str | None = None
            idle_ticks = 0
            while True:
                try:
                    def read_snap():
                        with sessions() as session:
                            return selected_snapshot(session, settings, source, include_real)

                    snap = await asyncio.to_thread(read_snap)
                    comparable = json.dumps({
                        "stations": snap["stations"],
                        "flood_zones": snap["flood_zones"],
                        "routing_data_sufficient": snap["routing_data_sufficient"],
                    }, default=str, sort_keys=True)
                    if comparable != last_payload:
                        last_payload = comparable
                        idle_ticks = 0
                        yield f"data: {json.dumps(snap, default=str)}\n\n"
                    else:
                        idle_ticks += 1
                        if idle_ticks >= 5:
                            idle_ticks = 0
                            yield ": ping\n\n"
                except RoutingError:
                    break
                except Exception as exc:
                    logger.warning("SSE stream read error: %s", exc)
                    yield ": retry\n\n"
                await asyncio.sleep(3.0)

        return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/flood-zones/{point_id}/history")
    def flood_history(point_id: str, source: Literal["real", "demo"] = "real", limit: int = Query(default=36, ge=2, le=100)):
        with sessions() as session:
            if source == "demo":
                require_demo(settings)
                pt = session.get(DemoPoint, point_id)
                if pt is None:
                    raise RoutingError("DEMO_POINT_NOT_FOUND", "Không tìm thấy điểm demo.", 404)
                rate = float(getattr(pt, "rise_rate_cm_min", 0.0) or 0.0)
                d_now = float(pt.water_depth_cm)
                d_10 = round(max(0.0, d_now - rate * 10.0), 1)
                d_5 = round(max(0.0, d_now - rate * 5.0), 1)
                ai_info = predict_flood_risk(d_now, d_5, d_10, pt.danger_threshold_cm) if rate > 0 else None
                d_15 = ai_info["predicted_15m"] if ai_info else round(d_now, 1)
                d_30 = ai_info["predicted_30m"] if ai_info else round(d_now, 1)
                return {
                    "id": pt.id,
                    "name": pt.name,
                    "source": "demo",
                    "warning_threshold_cm": pt.warning_threshold_cm,
                    "danger_threshold_cm": pt.danger_threshold_cm,
                    "ai_prediction": ai_info,
                    "points": [
                        {"label": "-10p", "depth_cm": d_10, "is_forecast": False},
                        {"label": "-5p", "depth_cm": d_5, "is_forecast": False},
                        {"label": "Hiện tại", "depth_cm": round(d_now, 1), "is_forecast": False},
                        {"label": "+15p (AI)", "depth_cm": d_15, "is_forecast": True},
                        {"label": "+30p (AI)", "depth_cm": d_30, "is_forecast": True},
                    ],
                }

            station = session.get(Station, point_id)
            if station is None:
                raise RoutingError("STATION_NOT_FOUND", "Không tìm thấy trạm.", 404)
            rows = list(
                session.scalars(
                    select(Measurement)
                    .where(Measurement.station_id == point_id, Measurement.sensor_ok.is_(True))
                    .order_by(Measurement.id.desc())
                    .limit(limit)
                )
            )
            rows.reverse()
            points = []
            for row in rows:
                ts = row.measured_at or row.received_at
                points.append({
                    "label": ts.astimezone(timezone(timedelta(hours=7))).strftime("%H:%M:%S") if ts else f"#{row.seq}",
                    "depth_cm": round(float(row.water_depth_cm or 0.0), 1),
                    "is_forecast": False,
                })
            return {
                "id": station.id,
                "name": station.name,
                "source": "real",
                "warning_threshold_cm": station.warning_threshold_cm,
                "danger_threshold_cm": station.danger_threshold_cm,
                "ai_prediction": None,
                "points": points,
            }

    @app.get("/api/admin/overview")
    async def admin_overview():
        db_ok = True
        try:
            with sessions() as session:
                all_stations = list(session.scalars(select(Station)))
                real_snap = snapshot(session, settings.data_stale_seconds)
                all_demo = list(session.scalars(select(DemoPoint))) if settings.demo_enabled else []
                demo_snap = selected_snapshot(session, settings, "demo", False) if settings.demo_enabled else {"stations": [], "flood_zones": {"features": []}}
        except SQLAlchemyError:
            db_ok = False
            all_stations, all_demo = [], []
            real_snap = {"stations": [], "flood_zones": {"features": []}}
            demo_snap = {"stations": [], "flood_zones": {"features": []}}

        client = getattr(app.state, "mqtt_client", None)
        mqtt_status = "disabled" if not settings.mqtt_enabled else ("connected" if (client is not None and client.is_connected()) else "disconnected")
        quality_counts = {"fresh": 0, "stale": 0, "invalid": 0, "missing": 0}
        real_danger = 0
        for s in real_snap["stations"]:
            q = s.get("data_quality", "missing")
            if q in quality_counts:
                quality_counts[q] += 1
            if s.get("hazard_state") in ("danger", "predicted_danger"):
                real_danger += 1

        demo_danger = sum(1 for s in demo_snap["stations"] if s.get("hazard_state") == "danger")
        demo_predicted = sum(1 for s in demo_snap["stations"] if s.get("hazard_state") == "predicted_danger")
        routing = await check_routing_services(force=False)

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "ok" if db_ok else "unavailable",
            "mqtt": mqtt_status,
            "routing": routing,
            "flags": {
                "demo_enabled": settings.demo_enabled,
                "stations_enabled": settings.stations_enabled,
                "admin_auth_required": bool(settings.admin_api_key.get_secret_value().strip()),
                "rate_limit_route_per_min": settings.rate_limit_route_per_min,
            },
            "stations": {
                "total": len(all_stations),
                "active": len(real_snap["stations"]),
                "quality": quality_counts,
                "danger_or_predicted": real_danger,
            },
            "demo_points": {
                "total": len(all_demo),
                "active": len(demo_snap["stations"]),
                "max": settings.max_demo_points,
                "danger": demo_danger,
                "predicted_danger": demo_predicted,
            },
        }

    @app.post("/api/routes/safe")
    async def safe_route(request: RouteRequest, raw_request: Request):
        route_limiter.check(raw_request)

        def get_snapshot():
            # Each read is a new transaction: do not retain an old snapshot during upstream routing I/O.
            with sessions() as session:
                return selected_snapshot(session, settings, request.source, request.include_real)

        # follow_redirects=False blocks malicious HTTP redirects during external routing calls.
        async with httpx.AsyncClient(follow_redirects=False) as client:
            return await async_find_route(request, settings, get_snapshot, client)

    @app.exception_handler(RoutingError)
    async def routing_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"error": {
            "code": "INVALID_INPUT", "message": "Request không hợp lệ. Kiểm tra tọa độ và các trường bắt buộc.",
        }})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.error("Database unavailable", exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=503, content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"}})

    return app
