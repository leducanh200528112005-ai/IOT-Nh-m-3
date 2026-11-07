"""Opt-in local demo management and shared source selection for map/routing."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import select

from app.flood import circle, classify, snapshot
from app.models import DemoPoint
from app.routing import RoutingError
from app.schemas import DemoPointCreate, DemoPointPatch, DemoPointResponse


def require_demo(settings):
    if not settings.demo_enabled:
        raise RoutingError("DEMO_DISABLED", "Chế độ demo chưa được bật trên server.", 403)


def selected_snapshot(session, settings, source="real", include_real=False):
    if source == "real":
        if include_real:
            raise RoutingError("INVALID_INPUT", "include_real chỉ dùng với source=demo.")
        data = snapshot(session, settings.data_stale_seconds)
    else:
        require_demo(settings)
        data = snapshot(session, settings.data_stale_seconds) if include_real else {
            "generated_at": datetime.now(timezone.utc), "stations": [],
            "flood_zones": {"type": "FeatureCollection", "features": []},
        }
        for point in session.scalars(select(DemoPoint).where(DemoPoint.is_active).order_by(DemoPoint.id)):
            hazard = classify(point.water_depth_cm, point.warning_threshold_cm, point.danger_threshold_cm)
            data["stations"].append({
                "id": point.id, "name": point.name, "source": "demo",
                "latitude": point.latitude, "longitude": point.longitude,
                "water_depth_cm": point.water_depth_cm,
                "hazard_state": hazard, "data_quality": "fresh",
                # No fabricated measurement timestamps: these are manually configured values.
                "measured_at": None, "received_at": None, "updated_at": point.updated_at,
            })
            if hazard == "danger":
                data["flood_zones"]["features"].append({
                    "type": "Feature", "geometry": circle(point), "properties": {
                        "station_id": point.id, "source": "demo", "radius_m": point.exclusion_radius_m,
                        "retained_due_to_uncertainty": False,
                    },
                })
        data["routing_data_sufficient"] = bool(data["stations"]) and all(
            station["data_quality"] == "fresh" for station in data["stations"]
        )
    data["source"] = source
    data["include_real"] = include_real
    data["generated_at"] = datetime.now(timezone.utc)
    return data


def create_demo_router(settings, sessions):
    def enabled():
        require_demo(settings)

    router = APIRouter(prefix="/api/demo-points", tags=["Demo"], dependencies=[Depends(enabled)])

    def get_point(session, point_id):
        point = session.get(DemoPoint, point_id)
        if point is None:
            raise RoutingError("DEMO_POINT_NOT_FOUND", "Không tìm thấy điểm demo.", 404)
        return point

    @router.get("", response_model=list[DemoPointResponse])
    def list_points():
        with sessions() as session:
            return list(session.scalars(select(DemoPoint).order_by(DemoPoint.created_at, DemoPoint.id)))

    @router.post("", response_model=DemoPointResponse, status_code=201)
    def create_point(request: DemoPointCreate):
        with sessions() as session:
            point = DemoPoint(id="demo-" + uuid4().hex, **request.model_dump())
            session.add(point)
            session.commit()
            session.refresh(point)
            return DemoPointResponse.model_validate(point)

    @router.patch("/{point_id}", response_model=DemoPointResponse)
    def update_point(point_id: str, request: DemoPointPatch):
        with sessions() as session:
            point = get_point(session, point_id)
            values = DemoPointCreate.model_validate(point, from_attributes=True).model_dump()
            values.update(request.model_dump(exclude_unset=True))
            try:
                validated = DemoPointCreate.model_validate(values)
            except ValidationError:
                raise RoutingError("INVALID_INPUT", "Ngưỡng nguy hiểm phải lớn hơn ngưỡng cảnh báo.") from None
            for key, value in validated.model_dump().items():
                setattr(point, key, value)
            session.commit()
            session.refresh(point)
            return DemoPointResponse.model_validate(point)

    @router.delete("/{point_id}", status_code=204)
    def delete_point(point_id: str):
        with sessions() as session:
            session.delete(get_point(session, point_id))
            session.commit()
        return Response(status_code=204)

    return router
