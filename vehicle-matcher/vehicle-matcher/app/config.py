"""Application settings, read from environment variables (or a .env file)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLAlchemy URL. SQLite by default; e.g. postgresql+psycopg://user:pw@host/db
    database_url: str = "sqlite:///./vehicles.db"
    # Default / maximum page size for GET /api/v1/vehicles
    default_page_limit: int = 10
    max_page_limit: int = 100
    # Seed the database automatically on startup if the vehicles table is empty
    auto_seed: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="VM_", extra="ignore")


settings = Settings()
