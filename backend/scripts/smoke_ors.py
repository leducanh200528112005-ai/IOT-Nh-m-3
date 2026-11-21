"""Exercise ORS with public example coordinates; no DB or telemetry changes."""
from argparse import ArgumentParser
from datetime import datetime, timezone

import httpx
from shapely.geometry import box, mapping

from app.config import Settings
from app.routing import RoutingError, find_route
from app.schemas import RouteRequest

parser = ArgumentParser()
parser.add_argument("--with-avoid", action="store_true", help="Include a synthetic exclusion polygon in Heidelberg.")
args = parser.parse_args()
settings = Settings()
if not settings.ors_api_key.get_secret_value().strip():
    raise SystemExit("Configure ORS_API_KEY in backend/.env first.")
request = RouteRequest(
    start={"longitude": 8.681495, "latitude": 49.41461},
    end={"longitude": 8.687872, "latitude": 49.420318},
)
features = [{"type": "Feature", "geometry": mapping(box(8.6851, 49.4173, 8.6853, 49.4175)),
             "properties": {}}] if args.with_avoid else []


def snapshot():
    return {"generated_at": datetime.now(timezone.utc), "routing_data_sufficient": True,
            "flood_zones": {"type": "FeatureCollection", "features": features}}


try:
    with httpx.Client(follow_redirects=False) as client:
        settings.ors_fallback_to_valhalla = False
        result = find_route(request, settings, snapshot, client)
except RoutingError as error:
    raise SystemExit(f"ORS: {error.code} — {error.message}") from None

print(f"ORS OK: {result['returned_route_count']}/{result['requested_route_count']} routes")
for route in result["routes"]:
    print(f"{route['id']}: {route['distance_m']} m, {route['duration_s']} s")
