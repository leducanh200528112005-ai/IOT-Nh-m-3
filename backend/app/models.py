from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Identity, Index, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90"),
        CheckConstraint("longitude BETWEEN -180 AND 180"),
        CheckConstraint("warning_threshold_cm >= 0 AND danger_threshold_cm > warning_threshold_cm"),
        CheckConstraint("exclusion_radius_m > 0"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    warning_threshold_cm: Mapped[float] = mapped_column(Float, default=10)
    danger_threshold_cm: Mapped[float] = mapped_column(Float, default=20)
    exclusion_radius_m: Mapped[float] = mapped_column(Float, default=40)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("station_id", "boot_id", "seq", name="uq_measurement_message"),
        CheckConstraint("seq >= 0"),
        CheckConstraint("(sensor_ok AND water_depth_cm IS NOT NULL AND water_depth_cm >= 0) OR (NOT sensor_ok AND water_depth_cm IS NULL)"),
        Index("ix_measurements_station_received", "station_id", "received_at", "id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    boot_id: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(BigInteger)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    water_depth_cm: Mapped[float | None] = mapped_column(Float)
    sensor_ok: Mapped[bool] = mapped_column(Boolean)
