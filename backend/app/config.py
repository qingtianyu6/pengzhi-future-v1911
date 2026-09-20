from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "棚智未来后端服务"
    app_version: str = "1.2.0"
    api_prefix: str = "/api"
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'pengzhi_future.db'}"
    )
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    )
    ai_api_key: str = os.getenv("AI_API_KEY", "").strip()
    ai_base_url: str = os.getenv("AI_BASE_URL", "").strip()
    ai_model: str = os.getenv("AI_MODEL", "").strip()
    sensor_ingest_key: str = os.getenv("SENSOR_INGEST_KEY", "").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
