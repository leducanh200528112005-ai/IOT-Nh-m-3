"""Opt-in local demo management and shared source selection for map/routing."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text

from app.ai.predictor import predict_flood_risk
from app.flood import circle, classify, snapshot
from app.models import DemoPoint
from app.routing import RoutingError
from app.schemas import DemoPointCreate, DemoPointPatch, DemoPointResponse
from app.security import verify_admin_key


def require_demo(settings):
    if not settings.demo_enabled:
        raise RoutingError("DEMO_DISABLED", "Chế độ demo chưa được bật trên server.", 403)


def _acquire_demo_lock(session):
    bind = session.get_bind() if hasattr(session, "get_bind") else None
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(730011)"))


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
            rise_rate = float(getattr(point, "rise_rate_cm_min", 0.0) or 0.0)
            ai_info = None
            if rise_rate > 0:
                lag_10 = max(0.0, point.water_depth_cm - rise_rate * 10.0)
                lag_5 = max(0.0, point.water_depth_cm - rise_rate * 5.0)
                ai_info = predict_flood_risk(point.water_depth_cm, lag_5, lag_10, point.danger_threshold_cm)
                if hazard != "danger" and ai_info["is_predicted_danger"]:
                    hazard = "predicted_danger"

            data["stations"].append({
                "id": point.id, "name": point.name, "source": "demo",
                "latitude": point.latitude, "longitude": point.longitude,
                "water_depth_cm": point.water_depth_cm,
                "rise_rate_cm_min": rise_rate,
                "hazard_state": hazard, "data_quality": "fresh",
                "ai_prediction": ai_info,
                # No fabricated measurement timestamps: these are manually configured values.
                "measured_at": None, "received_at": None, "updated_at": point.updated_at,
            })
            if hazard in ("danger", "predicted_danger"):
                is_predicted = (hazard == "predicted_danger")
                data["flood_zones"]["features"].append({
                    "type": "Feature", "geometry": circle(point), "properties": {
                        "station_id": point.id, "source": "demo", "radius_m": point.exclusion_radius_m,
                        "retained_due_to_uncertainty": False,
                        "is_predicted": is_predicted,
                        "warning_message": ai_info["warning_message"] if is_predicted and ai_info else None,
                        "predicted_15m": ai_info["predicted_15m"] if ai_info else None,
                    },
                })
        data["routing_data_sufficient"] = all(
            station["data_quality"] == "fresh" for station in data["stations"]
        )
    data["source"] = source
    data["include_real"] = include_real
    data["generated_at"] = datetime.now(timezone.utc)
    return data


def create_demo_router(settings, sessions):
    def enabled():
        require_demo(settings)

    def admin_guard(x_api_key: str | None = Header(default=None)):
        verify_admin_key(settings, x_api_key)

    max_points = getattr(settings, "max_demo_points", 30)
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

    @router.post("", response_model=DemoPointResponse, status_code=201, dependencies=[Depends(admin_guard)])
    def create_point(request: DemoPointCreate):
        with sessions() as session:
            _acquire_demo_lock(session)
            count = session.scalar(select(func.count(DemoPoint.id))) or 0
            if count >= max_points:
                raise RoutingError("MAX_POINTS_EXCEEDED", f"Hệ thống cho phép tối đa {max_points} điểm demo.", 400)
            point = DemoPoint(id="demo-" + uuid4().hex, **request.model_dump())
            session.add(point)
            session.commit()
            session.refresh(point)
            return DemoPointResponse.model_validate(point)

    @router.post("/batch", response_model=list[DemoPointResponse], status_code=201, dependencies=[Depends(admin_guard)])
    def batch_create_points(requests: list[DemoPointCreate]):
        if not requests:
            return []
        with sessions() as session:
            _acquire_demo_lock(session)
            count = session.scalar(select(func.count(DemoPoint.id))) or 0
            if count + len(requests) > max_points:
                raise RoutingError(
                    "MAX_POINTS_EXCEEDED",
                    f"Vượt quá giới hạn {max_points} điểm demo (hiện có {count}, thêm {len(requests)}).",
                    400,
                )
            created: list[DemoPoint] = []
            for req in requests:
                point = DemoPoint(id="demo-" + uuid4().hex, **req.model_dump())
                session.add(point)
                created.append(point)
            session.commit()
            for p in created:
                session.refresh(p)
            return [DemoPointResponse.model_validate(p) for p in created]

    @router.delete("", status_code=204, dependencies=[Depends(admin_guard)])
    def clear_all_points():
        with sessions() as session:
            session.execute(delete(DemoPoint))
            session.commit()
        return Response(status_code=204)

    @router.patch("/{point_id}", response_model=DemoPointResponse, dependencies=[Depends(admin_guard)])
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

    @router.delete("/{point_id}", status_code=204, dependencies=[Depends(admin_guard)])
    def delete_point(point_id: str):
        with sessions() as session:
            session.delete(get_point(session, point_id))
            session.commit()
        return Response(status_code=204)

    return router
