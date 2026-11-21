from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "flood_monitor"
    db_user: str = "flood_admin"
    db_password: SecretStr
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = "backend"
    mqtt_password: SecretStr
    mqtt_enabled: bool = True
    mqtt_client_id: str = "flood-backend"
    data_stale_seconds: int = Field(default=120, gt=0)
    cors_origins: list[str] = ["http://localhost:5173"]
    ors_api_key: SecretStr = SecretStr("")
    ors_base_url: str = "https://api.heigit.org/openrouteservice"
    ors_alternative_routes_enabled: bool = True
    ors_alternative_target_count: int = Field(default=3, ge=1, le=3)
    ors_alternative_weight_factor: float = Field(default=1.4, ge=1, allow_inf_nan=False)
    ors_alternative_share_factor: float = Field(default=0.6, ge=0, le=1)
    route_warning_proximity_limit_m: float = Field(default=50, ge=0, allow_inf_nan=False)
    route_warning_proximity_eta_tolerance_s: float = Field(default=60, ge=0, allow_inf_nan=False)
    ors_timeout_seconds: float = Field(default=15, gt=0, le=60)
    ors_max_snap_m: float = Field(default=50, gt=0, le=500)
    ors_fallback_to_valhalla: bool = False
    valhalla_url: str = "https://valhalla1.openstreetmap.de/route"
    valhalla_status_url: str = "https://valhalla1.openstreetmap.de/status"
    valhalla_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    photon_base_url: str = "https://photon.komoot.io"
    motorcycle_zone_scale: float = Field(default=0.65, gt=0.1, le=1.0)
    pedestrian_zone_scale: float = Field(default=0.5, gt=0.1, le=1.0)
    motorcycle_speed_kmh: float = Field(default=28.0, gt=1.0, le=120.0)
    pedestrian_speed_kmh: float = Field(default=5.0, gt=0.5, le=20.0)
    max_demo_points: int = Field(default=30, gt=0, le=200)
    rate_limit_route_per_min: int = Field(default=30, ge=0)
    admin_api_key: SecretStr = SecretStr("")
    demo_enabled: bool = False
    stations_enabled: bool = False

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg", username=self.db_user,
            password=self.db_password.get_secret_value(), host=self.db_host,
            port=self.db_port, database=self.db_name, query={"connect_timeout": "5"},
        )
