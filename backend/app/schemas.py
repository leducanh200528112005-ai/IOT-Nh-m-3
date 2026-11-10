from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    boot_id: str = Field(min_length=1, max_length=64)
    seq: int = Field(ge=0, le=9223372036854775807, strict=True)
    measured_at: datetime | None = None
    water_depth_cm: float | None = Field(default=None, ge=0)
    sensor_ok: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_measurement(self):
        if self.sensor_ok != (self.water_depth_cm is not None):
            raise ValueError("sensor_ok must agree with water_depth_cm")
        if self.measured_at is not None:
            if self.measured_at.utcoffset() is None:
                raise ValueError("measured_at requires timezone")
            if self.measured_at > datetime.now(timezone.utc) + timedelta(seconds=30):
                raise ValueError("measured_at is in the future")
        return self


class RoutePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(gt=-90, lt=90)

    def coordinates(self) -> list[float]:
        return [self.longitude, self.latitude]


class SourceSelection(BaseModel):
    source: Literal["real", "demo"] = "real"
    include_real: bool = False

    @model_validator(mode="after")
    def validate_source(self):
        if self.source == "real" and self.include_real:
            raise ValueError("include_real is only supported with source=demo")
        return self


class RouteRequest(SourceSelection):
    model_config = ConfigDict(extra="forbid")
    start: RoutePoint
    end: RoutePoint

    @model_validator(mode="after")
    def distinct_points(self):
        if self.start == self.end:
            raise ValueError("Start and end must differ")
        return self


class DemoPointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    latitude: float = Field(gt=-90, lt=90)
    longitude: float = Field(ge=-180, le=180)
    water_depth_cm: float = Field(default=0, ge=0, le=10000)
    warning_threshold_cm: float = Field(default=10, ge=0, le=10000)
    danger_threshold_cm: float = Field(default=20, gt=0, le=10000)
    exclusion_radius_m: float = Field(default=40, gt=0, le=1000)
    is_active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.danger_threshold_cm <= self.warning_threshold_cm:
            raise ValueError("Danger threshold must exceed warning threshold")
        return self


class DemoPointPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: float | None = Field(default=None, gt=-90, lt=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    water_depth_cm: float | None = Field(default=None, ge=0, le=10000)
    warning_threshold_cm: float | None = Field(default=None, ge=0, le=10000)
    danger_threshold_cm: float | None = Field(default=None, gt=0, le=10000)
    exclusion_radius_m: float | None = Field(default=None, gt=0, le=1000)
    is_active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def reject_nulls(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Explicit null is not supported")
        return self


class DemoPointResponse(DemoPointCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class StationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    # Must match the device_id the firmware publishes on flood/<id>/telemetry.
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    latitude: float = Field(gt=-90, lt=90)
    longitude: float = Field(ge=-180, le=180)
    warning_threshold_cm: float = Field(default=10, ge=0, le=10000)
    danger_threshold_cm: float = Field(default=20, gt=0, le=10000)
    exclusion_radius_m: float = Field(default=40, gt=0, le=1000)
    is_active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.danger_threshold_cm <= self.warning_threshold_cm:
            raise ValueError("Danger threshold must exceed warning threshold")
        return self


class StationPatch(BaseModel):
    """The station id is the MQTT device_id and cannot change after creation."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: float | None = Field(default=None, gt=-90, lt=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    warning_threshold_cm: float | None = Field(default=None, ge=0, le=10000)
    danger_threshold_cm: float | None = Field(default=None, gt=0, le=10000)
    exclusion_radius_m: float | None = Field(default=None, gt=0, le=1000)
    is_active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def reject_nulls(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Explicit null is not supported")
        return self


class StationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    latitude: float
    longitude: float
    warning_threshold_cm: float
    danger_threshold_cm: float
    exclusion_radius_m: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
