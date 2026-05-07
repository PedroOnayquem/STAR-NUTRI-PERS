from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


def parse_frontend_origins() -> list[str]:
    raw_origins = getenv("FRONTEND_ORIGINS") or getenv("FRONTEND_ORIGIN")

    if not raw_origins:
        raw_origins = (
            "http://localhost:5173,"
            "http://localhost:5174,"
            "http://127.0.0.1:5173,"
            "http://127.0.0.1:5174"
        )

    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


class Settings:
    app_name: str = getenv("APP_NAME", "Star Nutri API")
    app_env: str = getenv("APP_ENV", "development")
    frontend_origins: list[str] = parse_frontend_origins()
    supabase_url: str | None = getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = getenv("SUPABASE_SERVICE_ROLE_KEY")
    glm_api_key: str | None = getenv("GLM_API_KEY")
    glm_base_url: str | None = getenv("GLM_BASE_URL")
    glm_model: str = getenv("GLM_MODEL", "glm-5.0")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
