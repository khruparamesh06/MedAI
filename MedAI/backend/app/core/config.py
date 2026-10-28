"""Application settings loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MedAI"
    app_env: str = Field(default="development", description="development | test | production")

    # Database: SQLite by default for local development, PostgreSQL in production.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'medai.db').as_posix()}"

    # Security
    jwt_secret_key: str = Field(default="", description="Required. Long random string.")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS: comma-separated list of allowed frontend origins
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Abuse protection (in-memory, per process; see app/services/rate_limit.py)
    rate_limit_enabled: bool = True
    # Maximum size of non-upload request bodies (JSON forms), in KB
    max_json_body_kb: int = 1024

    # Swagger/ReDoc. Defaults to on outside production and off in production.
    enable_api_docs: bool | None = None

    # Uploads (private storage, never served statically)
    upload_dir: Path = BACKEND_DIR / "storage" / "xrays"
    max_upload_mb: int = 10

    # Appointments: doctor availability hours and booking times are interpreted in this time zone.
    clinic_timezone: str = "UTC"

    # AI model
    model_config_path: Path = PROJECT_DIR / "ai" / "model_config.json"

    @field_validator("upload_dir", "model_config_path", mode="after")
    @classmethod
    def _resolve_relative(cls, value: Path) -> Path:
        # Relative paths are resolved against the project root, not the CWD.
        return value if value.is_absolute() else (PROJECT_DIR / value).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def api_docs_enabled(self) -> bool:
        return (not self.is_production) if self.enable_api_docs is None else self.enable_api_docs


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY is missing or shorter than 32 characters. "
            "Copy .env.example to .env and set a long random value "
            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    if settings.is_production and settings.database_url.startswith("sqlite"):
        raise RuntimeError("SQLite is not supported when APP_ENV=production. Use PostgreSQL.")
    if settings.is_production:
        if any(o == "*" for o in settings.cors_origin_list):
            raise RuntimeError("CORS_ORIGINS must list exact origins in production; '*' is not allowed.")
        if any(o.startswith("http://") and "localhost" not in o and "127.0.0.1" not in o
               for o in settings.cors_origin_list):
            raise RuntimeError("Production CORS_ORIGINS must use https:// origins.")
        if not settings.rate_limit_enabled:
            raise RuntimeError("RATE_LIMIT_ENABLED cannot be disabled in production.")
    return settings
