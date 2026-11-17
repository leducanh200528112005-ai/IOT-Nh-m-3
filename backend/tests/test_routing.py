import copy
from datetime import datetime, timezone
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

from app.config import Settings
from app.main import create_app
from app.routing import RoutingError, find_route
from app.schemas import RouteRequest

START, END = [106.69, 10.77], [106.71, 10.77]
DIRECT = [START, END]
DETOUR = [START, [106.69, 10.772], [106.71, 10.772], END]


def request():
    return RouteRequest(start={"longitude": START[0], "latitude": START[1]}, end={"longitude": END[0], "latitude": END[1]})


def settings(**changes):
    return Settings(db_password="test", mqtt_password="test", mqtt_enabled=False, ors_api_key="test-key", **changes)


def data(zone=False, sufficient=True):
    return {"routing_data_sufficient": sufficient, "generated_at": datetime.now(timezone.utc),
            "flood_zones": {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": mapping(box(106.699, 10.7695, 106.701, 10.7705)), "properties": {}}
            ] if zone else []}}


def response(coords=DIRECT):
    return httpx.Response(200, json={"features": [{"type": "Feature", "geometry": {
        "type": "LineString", "coordinates": coords}, "properties": {"summary": {"distance": 2500, "duration": 300}}}]})


def call(client, snapshots=None, config=None):
    provider = Mock(return_value=data()) if snapshots is None else Mock(side_effect=snapshots)
    return find_route(request(), config or settings(), provider, client)


def test_no_zones_omits_avoid_options():
    client = Mock(post=Mock(return_value=response()))
    result = call(client)
    assert result["profile"] == "driving-car"
    assert result["distance_m"] == 2500
    assert "options" not in client.post.call_args.kwargs["json"]
    assert client.post.call_args.kwargs["headers"] == {"Authorization": "test-key"}


def test_avoid_zones_and_validate_detour():
    client = Mock(post=Mock(return_value=response(DETOUR)))
    call(client, [data(True), data(True)])
    assert client.post.call_args.kwargs["json"]["options"]["avoid_polygons"]["type"] == "Polygon"


def test_intersection_retries_once_with_larger_zone():
    client = Mock(post=Mock(side_effect=[response(), response(DETOUR)]))
    call(client, [data(True)] * 3)
    assert client.post.call_count == 2
    from shapely.geometry import shape
    areas = [shape(c.kwargs["json"]["options"]["avoid_polygons"]).area for c in client.post.call_args_list]
    assert areas[1] > areas[0]


def test_never_returns_intersecting_fallback():
    client = Mock(post=Mock(return_value=response()))
    with pytest.raises(RoutingError, match="hai lần"):
        call(client, [data(True)] * 3)
    assert client.post.call_count == 2


def test_flood_appears_during_request():
    client = Mock(post=Mock(side_effect=[response(), response(DETOUR)]))
    call(client, [data(), data(True), data(True)])
    assert client.post.call_count == 2


@pytest.mark.parametrize("snapshots", [[data(sufficient=False)], [data(), data(sufficient=False)]])
def test_reject_stale_before_or_after_ors(snapshots):
    with pytest.raises(RoutingError) as error:
        call(Mock(post=Mock(return_value=response())), snapshots)
    assert error.value.code == "INSUFFICIENT_DATA"


def test_endpoint_in_zone_skips_upstream():
    snapshot = data(True)
    snapshot["flood_zones"]["features"][0]["geometry"] = mapping(box(106.689, 10.769, 106.691, 10.771))
    client = Mock()
    with pytest.raises(RoutingError) as error:
        call(client, [snapshot])
    assert error.value.code == "POINT_IN_FLOOD_ZONE"
    client.post.assert_not_called()


@pytest.mark.parametrize("status,body,code", [
    (429, {}, "ROUTING_RATE_LIMITED"), (401, {}, "ROUTING_UNAVAILABLE"),
    (403, {}, "ROUTING_UNAVAILABLE"), (500, {}, "ROUTING_UNAVAILABLE"),
    (404, {"error": {"code": 2009}}, "NO_SUITABLE_ROUTE"),
    (404, {"error": {"code": 2010}}, "NO_SUITABLE_ROUTE"),
    (200, {"features": []}, "ROUTING_UNAVAILABLE"),
])
def test_upstream_errors(status, body, code):
    with pytest.raises(RoutingError) as error:
        call(Mock(post=Mock(return_value=httpx.Response(status, json=body))))
    assert error.value.code == code


def test_timeout():
    with pytest.raises(RoutingError) as error:
        call(Mock(post=Mock(side_effect=httpx.ReadTimeout("secret upstream details"))))
    assert error.value.code == "ROUTING_UNAVAILABLE"
    assert "secret" not in error.value.message


def test_malformed_json():
    with pytest.raises(RoutingError):
        call(Mock(post=Mock(return_value=httpx.Response(200, text="not json"))))


def test_snap_too_far():
    with pytest.raises(RoutingError) as error:
        call(Mock(post=Mock(return_value=response([[106.68, 10.77], END]))))
    assert error.value.code == "NO_SUITABLE_ROUTE"


def test_empty_ors_key_uses_valhalla_with_steps():
    config = settings()
    config.ors_api_key = type(config.ors_api_key)("")
    valhalla_payload = {
        "trip": {
            "summary": {"length": 1.2, "time": 95.0},
            "legs": [{
                "shape": "_p~iF~ps|U_ulLnnqC",  # dummy valid 2-pt? Let's construct exact encoded pts below.
                "maneuvers": [{"instruction": "Đi thẳng", "length": 1.2, "time": 95.0, "type": 1}],
            }],
        }
    }
    # Encode polyline6 for [[106.69, 10.77], [106.71, 10.77]]
    def enc6(vals):
        out = []
        prev = [0, 0]
        for lat, lng in vals:
            for idx, v in enumerate((lat, lng)):
                cur = round(v * 1e6)
                d = cur - prev[idx]
                prev[idx] = cur
                d = ~(d << 1) if d < 0 else (d << 1)
                while d >= 0x20:
                    out.append(chr((0x20 | (d & 0x1F)) + 63))
                    d >>= 5
                out.append(chr(d + 63))
        return "".join(out)

    valhalla_payload["trip"]["legs"][0]["shape"] = enc6([(10.77, 106.69), (10.77, 106.71)])
    client = Mock(post=Mock(return_value=httpx.Response(200, json=valhalla_payload)))
    req = RouteRequest(start={"longitude": START[0], "latitude": START[1]}, end={"longitude": END[0], "latitude": END[1]}, vehicle="motorcycle")
    result = find_route(req, config, lambda: data(), client)
    assert result["engine"] == "valhalla"
    assert result["profile"] == "motorcycle"
    assert result["steps"][0]["instruction"] == "Đi thẳng"
    sent_json = client.post.call_args.kwargs["json"]
    assert sent_json["costing"] == "motorcycle"
    assert sent_json["costing_options"] == {"motorcycle": {"use_trails": 1.0}}


def test_ors_vehicle_profile_mapping():
    client = Mock(post=Mock(return_value=response()))
    for vehicle, expected_path in (("car", "driving-car"), ("motorcycle", "cycling-regular"), ("pedestrian", "foot-walking")):
        req = RouteRequest(start={"longitude": START[0], "latitude": START[1]}, end={"longitude": END[0], "latitude": END[1]}, vehicle=vehicle)
        find_route(req, settings(), lambda: data(), client)
        assert expected_path in client.post.call_args.args[0]


def test_valhalla_and_osrm_both_unavailable_raises_no_route():
    config = settings()
    config.ors_api_key = type(config.ors_api_key)("")
    client = Mock(post=Mock(side_effect=httpx.ConnectError("offline")), get=Mock(side_effect=httpx.ConnectError("offline")))
    with pytest.raises(RoutingError) as error:
        call(client, config=config)
    assert error.value.code == "NO_SUITABLE_ROUTE"


@pytest.mark.parametrize("change", [
    {"geometry": {"type": "Point", "coordinates": START}},
    {"geometry": {"type": "LineString", "coordinates": [[181, 10], END]}},
    {"properties": {"summary": {"distance": -1, "duration": 10}}},
])
def test_malformed_route(change):
    payload = copy.deepcopy(response().json())
    payload["features"][0].update(change)
    with pytest.raises(RoutingError):
        call(Mock(post=Mock(return_value=httpx.Response(200, json=payload))))


def test_actual_http_client_contract():
    def handler(upstream):
        assert upstream.url.path == "/v2/directions/driving-car/geojson"
        assert upstream.headers["Authorization"] == "test-key"
        return response()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert call(client)["distance_m"] == 2500


def test_endpoint_error_envelope_and_post_cors():
    config = settings()
    config.ors_api_key = type(config.ors_api_key)("")
    with TestClient(create_app(config)) as client:
        result = client.post("/api/routes/safe", json={"start": {"latitude": 999}})
        assert result.status_code == 422
        assert result.json()["error"]["code"] == "INVALID_INPUT"
        result = client.options("/api/routes/safe", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        assert result.status_code == 200
        # Rate limiter enforcement (per-minute limit = 2)
    limited_cfg = settings(rate_limit_route_per_min=1)
    with TestClient(create_app(limited_cfg)) as client:
        first = client.post("/api/routes/safe", json={"start": {"latitude": 999}})
        assert first.status_code == 422
        ok_req = request().model_dump()
        client.post("/api/routes/safe", json=ok_req)
        second = client.post("/api/routes/safe", json=ok_req)
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "ROUTING_RATE_LIMITED"
