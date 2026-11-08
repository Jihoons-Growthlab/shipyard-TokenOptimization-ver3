"""환경 설정. 경로 값은 저장소 루트 기준 상대경로를 허용한다."""
import os
import secrets
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "database" / "migrations"
SEED_FILE = ROOT / "reference" / "seed" / "seed.json"

# 모든 "오늘"은 이 기준일을 쓴다.
TODAY = "2026-10-19"

_SECRET = os.environ.get("APP_SECRET") or secrets.token_urlsafe(48)


def today() -> date:
    return date.fromisoformat(TODAY)


def _path(env: str, default: str) -> Path:
    p = Path(os.environ.get(env) or default)
    return p if p.is_absolute() else ROOT / p


def db_path() -> Path:
    return _path("SHIPYARD_DB_PATH", "database/shipyard.db")


def file_dir() -> Path:
    return _path("SHIPYARD_FILE_DIR", "storage/drawings")


def app_secret() -> str:
    return _SECRET


def token_ttl() -> int:
    return int(os.environ.get("TOKEN_TTL") or 28800)


def otp_token_ttl() -> int:
    return int(os.environ.get("OTP_TOKEN_TTL") or 300)


def weather_provider() -> str:
    return (os.environ.get("WEATHER_PROVIDER") or "").strip()
