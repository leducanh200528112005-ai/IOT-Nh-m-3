import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.flood import snapshot
from app.mqtt import create_client


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine)

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

    app = FastAPI(title="Flood IoT API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=["*"])

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

    @app.get("/api/flood-zones")
    def flood_zones():
        with sessions() as session:
            return snapshot(session, settings.data_stale_seconds)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logging.getLogger(__name__).error("Database unavailable", exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=503, content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"}})

    return app
