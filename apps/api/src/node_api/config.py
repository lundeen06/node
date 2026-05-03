"""Application settings and physical constants (scaffold values)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from node_api.repo_root import api_project_root

# apps/api/.env — always loaded from the API project root (not the shell cwd).
_ENV_FILE = api_project_root() / ".env"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="NODE_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
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
    spacetrack_identity: str | None = Field(
        default=None,
        description="Space-Track username (https://www.space-track.org). Used with spacetrack_password.",
    )
    spacetrack_password: str | None = Field(
        default=None,
        description="Space-Track password. Never commit real credentials.",
    )
    spacetrack_user_agent: str = Field(
        default="node-api/0.1 (constellation ops; configure NODE_SPACETRACK_USER_AGENT)",
        description="Required identifiable User-Agent for Space-Track API compliance.",
    )
    database_url: str | None = Field(
        default=None,
        description="SQLAlchemy URL. Default: sqlite file under apps/api/node.sqlite.",
    )


# Canonical Earth gravitational parameter for two-body scaffolding (km^3/s^2).
# Replace with operational ephemeris constants in production code paths.
EARTH_MU_KM3_S2: float = 398_600.4418

settings = Settings()
