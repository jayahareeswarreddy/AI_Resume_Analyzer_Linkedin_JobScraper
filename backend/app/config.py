"""Application settings, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    Defaults point at a local MongoDB so the API runs with no setup beyond
    `mongod` being up.
    """

    mongo_uri: str = field(
        default_factory=lambda: os.getenv("MONGO_URI", "mongodb://localhost:27017")
    )
    mongo_db: str = field(
        default_factory=lambda: os.getenv("MONGO_DB", "resume_analyzer")
    )
    spacy_model: str = field(
        default_factory=lambda: os.getenv("SPACY_MODEL", "en_core_web_md")
    )
    # Selenium runs headless by default; set SCRAPER_HEADLESS=0 to watch it.
    scraper_headless: bool = field(
        default_factory=lambda: os.getenv("SCRAPER_HEADLESS", "1") != "0"
    )
    scraper_max_jobs: int = field(
        default_factory=lambda: int(os.getenv("SCRAPER_MAX_JOBS", "25"))
    )
    server_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("MONGO_TIMEOUT_MS", "5000"))
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings, constructing them on first use."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Drop the cached settings. Used by tests that patch the environment."""
    global _settings
    _settings = None
