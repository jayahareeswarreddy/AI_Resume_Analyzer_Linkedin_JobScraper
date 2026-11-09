"""MongoDB connection and index management."""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from .config import get_settings

log = logging.getLogger(__name__)

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return the shared client, created on first call.

    PyMongo pools connections internally, so one client per process is the
    documented way to use it - creating one per request exhausts sockets.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=settings.server_timeout_ms,
            tz_aware=True,
        )
    return _client


def get_database() -> Database:
    return get_client()[get_settings().mongo_db]


def ping() -> bool:
    """True when the server answers. Used by the health endpoint."""
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError as exc:
        log.warning("MongoDB ping failed: %s", exc)
        return False


def ensure_indexes() -> None:
    """Create the indexes the queries rely on. Safe to call repeatedly."""
    try:
        db = get_database()
        # Dedupe scraped postings on their LinkedIn URL.
        db.jobs.create_index([("url", ASCENDING)], unique=True, sparse=True)
        db.jobs.create_index([("scraped_at", DESCENDING)])
        db.jobs.create_index([("skills", ASCENDING)])
        db.resumes.create_index([("created_at", DESCENDING)])
    except PyMongoError as exc:
        # An API that cannot index is still an API that can serve reads,
        # so log and carry on rather than refusing to start.
        log.warning("Could not create indexes: %s", exc)


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
