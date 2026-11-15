"""Application settings, loaded from the environment (prefix ``ZEST_API_``)."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars / a local ``.env`` file."""

    model_config = SettingsConfigDict(
        env_prefix="ZEST_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://zest:zest@localhost:5432/zest"
    db_echo: bool = False

    # HTTP / CORS
    cors_origins: list[str] = ["http://localhost:5173"]
    root_path: str = ""

    # Uploads
    max_upload_bytes: int = 64 * 1024 * 1024

    # Object storage (MinIO / S3-compatible). When storage_endpoint is empty, an
    # in-memory store is used instead — handy for tests and MinIO-less local runs.
    storage_endpoint: str = ""
    storage_access_key: str = "zest"
    storage_secret_key: str = "zest-minio-dev"
    storage_bucket: str = "datasets"
    storage_secure: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, value: object) -> object:
        """Accept a comma-separated string in addition to a JSON array."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Drop the cached settings (used by tests that mutate the environment)."""
    global _settings
    _settings = None
