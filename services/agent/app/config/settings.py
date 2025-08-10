import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore


@dataclass
class Settings:
    # Agent
    AGENT_TYPE: str = "manufacturing"

    # Cognito / Auth
    USER_POOL_ID: Optional[str] = None
    USER_POOL_CLIENT_ID: Optional[str] = None
    REGION: Optional[str] = None

    # ADOSEA Core integration
    ADOSEA_BASE_URL: Optional[str] = None
    ADOSEA_API_KEY: Optional[str] = None


def load_settings() -> Settings:
    # Best-effort local .env loading when running outside container
    if load_dotenv is not None:
        # Prefer explicit DOTENV_PATH, fallback to ./config/.env or ./.env
        dotenv_path = os.environ.get("DOTENV_PATH")
        candidates = [
            Path(dotenv_path) if dotenv_path else None,
            Path(__file__).resolve().parents[3] / "config/.env",  # repo root/config/.env
            Path(__file__).resolve().parents[3] / ".env",         # repo root/.env
        ]
        for candidate in candidates:
            if candidate and candidate.exists():
                load_dotenv(dotenv_path=str(candidate), override=False)
                break

    # Load from environment (.env locally, or injected in AWS via secrets)
    return Settings(
        AGENT_TYPE=os.environ.get("AGENT_TYPE", "manufacturing"),
        USER_POOL_ID=os.environ.get("USER_POOL_ID"),
        USER_POOL_CLIENT_ID=os.environ.get("USER_POOL_CLIENT_ID"),
        REGION=os.environ.get("REGION"),
        ADOSEA_BASE_URL=os.environ.get("ADOSEA_BASE_URL"),
        ADOSEA_API_KEY=os.environ.get("ADOSEA_API_KEY"),
    )


