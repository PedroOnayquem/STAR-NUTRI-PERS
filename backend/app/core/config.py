from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE, override=True)


def parse_frontend_origins() -> list[str]:
    raw_origins = getenv("FRONTEND_ORIGINS") or getenv("FRONTEND_ORIGIN")

    if not raw_origins:
        raw_origins = (
            "http://localhost:5173,"
            "http://localhost:5174,"
            "http://localhost:8080,"
            "http://127.0.0.1:5173,"
            "http://127.0.0.1:5174,"
            "http://127.0.0.1:8080"
        )

    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


class Settings:
    def __init__(self) -> None:
        # Reload the backend env explicitly so every process spawned by uvicorn
        # sees the same values on Windows reload mode.
        load_dotenv(ENV_FILE, override=True)

        self.app_name: str = getenv("APP_NAME", "Star Nutri API")
        self.app_env: str = getenv("APP_ENV", "development")
        self.frontend_origins: list[str] = parse_frontend_origins()
        self.supabase_url: str | None = getenv("SUPABASE_URL")
        self.supabase_service_role_key: str | None = getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.openai_api_key: str | None = getenv("OPENAI_API_KEY")
        self.openai_base_url: str = getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )
        self.openai_model: str = getenv("OPENAI_MODEL", "chat-latest")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
