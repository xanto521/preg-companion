from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREG_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

    data_dir: Path = PROJECT_ROOT / "data"
    timezone: str = "Asia/Shanghai"
    public_domain: str = "localhost"
    share_token_ttl_days: PositiveInt = 30
    backup_retention_days: PositiveInt = 30
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("expected an IANA time zone") from exc
        return value

    @property
    def database_path(self) -> Path:
        return PROJECT_ROOT / self.data_dir / "app.db"
