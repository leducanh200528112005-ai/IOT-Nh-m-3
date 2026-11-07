"""One real ORS call with public example coordinates; no DB or telemetry changes."""
import httpx

from app.config import Settings
from app.routing import parse_route

settings = Settings()
key = settings.ors_api_key.get_secret_value().strip()
if not key:
    raise SystemExit("Configure ORS_API_KEY in backend/.env first.")
try:
    with httpx.Client(follow_redirects=False) as client:
        response = client.post(
            settings.ors_base_url.rstrip("/") + "/v2/directions/driving-car/geojson",
            headers={"Authorization": key},
            json={"coordinates": [[8.681495, 49.41461], [8.687872, 49.420318]], "instructions": False},
            timeout=settings.ors_timeout_seconds,
        )
    line, distance, duration = parse_route(response)
    print(f"ORS OK: {len(line.coords)} vertices, {distance} m, {duration} s")
except httpx.RequestError:
    raise SystemExit("ORS network error or timeout; no credentials printed.") from None
