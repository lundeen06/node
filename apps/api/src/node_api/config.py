"""Application settings and physical constants (scaffold values)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="NODE_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "node API"
    debug: bool = False
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins.",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (NODE_OPENAI_API_KEY).",
    )


# Canonical Earth gravitational parameter for two-body scaffolding (km^3/s^2).
# Replace with operational ephemeris constants in production code paths.
EARTH_MU_KM3_S2: float = 398_600.4418

settings = Settings()
