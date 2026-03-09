"""
config.py — Central app settings loaded from .env
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./fashion_trends.db"

    # ── Redis ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── API Keys ──────────────────────────────────────────
    TAGWALK_API_KEY: str = ""
    GOOGLE_VISION_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── App ───────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-change-me"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # ── Trend scoring weights ─────────────────────────────
    WEIGHT_RUNWAY: float = 0.50
    WEIGHT_SEARCH: float = 0.30
    WEIGHT_SOCIAL: float = 0.20

    # ── Season ────────────────────────────────────────────
    ACTIVE_SEASON: str = "FW26"
    ACTIVE_CITIES: str = "Paris,Milan,London,New_York"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def active_cities_list(self) -> List[str]:
        return [c.strip() for c in self.ACTIVE_CITIES.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
