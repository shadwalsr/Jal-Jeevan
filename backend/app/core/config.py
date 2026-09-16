"""
JalJeev — central configuration.
All values are loaded from environment variables (.env). See .env.example
for the full list, including which data-source credentials need registration.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # In Docker, env vars come from docker-compose's `env_file: .env` (repo
    # root) directly. When running locally from backend/, fall back to
    # reading the repo-root .env file directly.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    ENV: str = "development"
    SECRET_KEY: str = "dev"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    REDIS_URL: str

    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "jaljeev"
    S3_SECRET_KEY: str = "jaljeev_dev_password"
    S3_BUCKET: str = "jaljeev-raw"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Tier-1 data source credentials
    MOSDAC_USERNAME: str | None = None
    MOSDAC_PASSWORD: str | None = None
    IMD_API_KEY: str | None = None
    COPERNICUS_MARINE_USERNAME: str | None = None
    COPERNICUS_MARINE_PASSWORD: str | None = None
    CDS_API_URL: str | None = None
    CDS_API_KEY: str | None = None
    EARTHDATA_USERNAME: str | None = None
    EARTHDATA_PASSWORD: str | None = None
    EARTHDATA_TOKEN: str | None = None
    PROTECTED_PLANET_API_KEY: str | None = None
    GFW_API_TOKEN: str | None = None

    # Public / no-auth endpoints (safe defaults, overridable)
    INCOIS_ERDDAP_URL: str = "https://erddap.incois.gov.in/erddap"
    NOAA_ERDDAP_URL: str = "https://coastwatch.pfeg.noaa.gov/erddap"
    OPEN_METEO_MARINE_URL: str = "https://marine-api.open-meteo.com/v1/marine"


settings = Settings()
