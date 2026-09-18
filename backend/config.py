"""Product configuration. A database URL is required for product endpoints."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    dependency_base_url: str
    dependency_timeout_seconds: float


def get_settings() -> Settings:
    timeout = float(os.getenv("DEPENDENCY_TIMEOUT_SECONDS", "2"))
    if timeout <= 0:
        raise ValueError("DEPENDENCY_TIMEOUT_SECONDS must be positive")
    return Settings(
        database_url=os.getenv("DATABASE_URL") or None,
        dependency_base_url=os.getenv(
            "DEPENDENCY_BASE_URL", "http://127.0.0.1:8001"
        ).rstrip("/"),
        dependency_timeout_seconds=timeout,
    )
