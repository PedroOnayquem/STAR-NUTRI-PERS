from functools import lru_cache
from os import getenv


class Settings:
    app_name: str = getenv("APP_NAME", "Star Nutri API")
    app_env: str = getenv("APP_ENV", "development")
    frontend_origin: str = getenv("FRONTEND_ORIGIN", "http://localhost:5173")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
