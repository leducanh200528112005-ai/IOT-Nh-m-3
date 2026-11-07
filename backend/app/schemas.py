from datetime import datetime, timezone, timedelta

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
