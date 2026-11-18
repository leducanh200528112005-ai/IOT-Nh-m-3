from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_and_openapi_without_database():
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/flood-zones" in paths
        assert "/api/routes/safe" in paths


def test_frontend_cors():
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, cors_origins=["http://localhost:5173"])
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_admin_api_key_optional_guard():
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, demo_enabled=True, admin_api_key="secret-123")
    with TestClient(create_app(settings)) as client:
        denied = client.post("/api/demo-points", json={
            "name": "Test", "latitude": 20.98, "longitude": 105.77,
        })
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "UNAUTHORIZED"


def test_geocode_and_routing_status_endpoints(monkeypatch):
    import httpx

    async def fake_get(self, url, **kwargs):
        url_str = str(url)
        if "photon" in url_str:
            return httpx.Response(200, json={
                "type": "FeatureCollection",
                "features": [{
                    "geometry": {"coordinates": [105.7703, 20.9826]},
                    "properties": {"countrycode": "VN", "name": "Ngã tư Vạn Phúc", "city": "Hà Nội", "district": "Hà Đông"},
                }],
            })
        return httpx.Response(200, json={"code": "Ok", "version": "3.9.1"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    settings = Settings(db_password="test", mqtt_password="test", mqtt_enabled=False)
    with TestClient(create_app(settings)) as client:
        geo = client.get("/api/geocode?q=Van%20Phuc")
        assert geo.status_code == 200
        assert geo.json()["results"][0]["label"].startswith("Ngã tư Vạn Phúc")
        status = client.get("/api/routing-status")
        assert status.status_code == 200
        assert status.json()["valhalla"]["status"] == "ok"
        assert status.json()["osrm"]["status"] == "ok"
        admin = client.get("/api/admin/overview")
        assert admin.status_code == 200
        assert "routing" in admin.json()
        assert "flags" in admin.json()
