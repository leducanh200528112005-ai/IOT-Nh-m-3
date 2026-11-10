"""Opt-in station configuration. The station id is the MQTT device_id, so it is immutable."""
from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import Measurement, Station
from app.routing import RoutingError
from app.schemas import StationCreate, StationPatch, StationResponse


def require_stations(settings):
    if not settings.stations_enabled:
        raise RoutingError("STATIONS_DISABLED", "Quản lý trạm chưa được bật trên server.", 403)


def create_station_router(settings, sessions):
    def enabled():
        require_stations(settings)

    router = APIRouter(prefix="/api/stations", tags=["Stations"], dependencies=[Depends(enabled)])

    def get_station(session, station_id):
        station = session.get(Station, station_id)
        if station is None:
            raise RoutingError("STATION_NOT_FOUND", "Không tìm thấy trạm.", 404)
        return station

    @router.get("", response_model=list[StationResponse])
    def list_stations():
        with sessions() as session:
            return list(session.scalars(select(Station).order_by(Station.created_at, Station.id)))

    @router.post("", response_model=StationResponse, status_code=201)
    def create_station(request: StationCreate):
        with sessions() as session:
            if session.get(Station, request.id) is not None:
                raise RoutingError("STATION_EXISTS", "Mã trạm này đã tồn tại.", 409)
            station = Station(**request.model_dump())
            session.add(station)
            session.commit()
            session.refresh(station)
            return StationResponse.model_validate(station)

    @router.patch("/{station_id}", response_model=StationResponse)
    def update_station(station_id: str, request: StationPatch):
        with sessions() as session:
            station = get_station(session, station_id)
            values = StationCreate.model_validate(station, from_attributes=True).model_dump()
            values.update(request.model_dump(exclude_unset=True))
            try:
                validated = StationCreate.model_validate(values)
            except ValidationError:
                raise RoutingError("INVALID_INPUT", "Ngưỡng nguy hiểm phải lớn hơn ngưỡng cảnh báo.") from None
            # id is the MQTT device_id: never rewritten by a PATCH.
            for key, value in validated.model_dump(exclude={"id"}).items():
                setattr(station, key, value)
            session.commit()
            session.refresh(station)
            return StationResponse.model_validate(station)

    @router.delete("/{station_id}", status_code=204)
    def delete_station(station_id: str):
        with sessions() as session:
            station = get_station(session, station_id)
            measurements = session.scalar(
                select(func.count()).select_from(Measurement).where(Measurement.station_id == station_id)
            )
            if measurements:
                raise RoutingError(
                    "STATION_HAS_MEASUREMENTS",
                    f"Trạm đã có {measurements} số đo. Tắt trạm thay vì xóa để giữ lịch sử.",
                    409,
                )
            session.delete(station)
            session.commit()
        return Response(status_code=204)

    return router
