from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_and_openapi_without_database():
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/flood-zones" in paths
        assert "/api/routes/safe" not in paths


def test_frontend_cors():
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
