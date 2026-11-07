from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Measurement, Station
from app.schemas import Telemetry


def save_telemetry(session, topic: str, payload: bytes) -> bool:
    if len(payload) > 8192:
        raise ValueError("MQTT payload too large")
    message = Telemetry.model_validate_json(payload)
    if topic != f"flood/{message.device_id}/telemetry":
        raise ValueError("Topic and device_id do not match")
    station = session.scalar(select(Station).where(Station.id == message.device_id))
    if station is None or not station.is_active:
        raise ValueError("Unknown or inactive station")
    values = message.model_dump(exclude={"device_id"})
    statement = (
        insert(Measurement).values(station_id=message.device_id, **values)
        .on_conflict_do_nothing(constraint="uq_measurement_message")
        .returning(Measurement.id)
    )
    created = session.scalar(statement) is not None
    session.commit()
    return created
