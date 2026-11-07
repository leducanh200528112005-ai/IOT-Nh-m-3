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
    data_stale_seconds: int = Field(default=15, gt=0)
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg", username=self.db_user,
            password=self.db_password.get_secret_value(), host=self.db_host,
            port=self.db_port, database=self.db_name, query={"connect_timeout": "5"},
        )
