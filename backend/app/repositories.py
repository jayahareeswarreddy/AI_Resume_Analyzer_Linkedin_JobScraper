"""Data access.

Routes depend on these classes, never on pymongo directly, so the API can
be tested against an in-memory double without a running database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class ResumeRepository(Protocol):
    def create(self, document: dict[str, Any]) -> str: ...
    def get(self, resume_id: str) -> dict[str, Any] | None: ...
    def list(self, limit: int = 50) -> list[dict[str, Any]]: ...
    def delete(self, resume_id: str) -> bool: ...


class JobRepository(Protocol):
    def upsert_many(self, documents: list[dict[str, Any]]) -> int: ...
    def list(self, limit: int = 100, skill: str | None = None) -> list[dict[str, Any]]: ...
    def count(self) -> int: ...


# --------------------------------------------------------------------------
# MongoDB implementations
# --------------------------------------------------------------------------

class MongoResumeRepository:
    def __init__(self, db: Database) -> None:
        self._col = db.resumes

    def create(self, document: dict[str, Any]) -> str:
        document = {**document, "created_at": document.get("created_at") or utcnow()}
        return str(self._col.insert_one(document).inserted_id)

    def get(self, resume_id: str) -> dict[str, Any] | None:
        oid = to_object_id(resume_id)
        if oid is None:
            return None
        found = self._col.find_one({"_id": oid})
        return _with_id(found)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self._col.find().sort("created_at", -1).limit(limit)
        return [_with_id(doc) for doc in cursor]

    def delete(self, resume_id: str) -> bool:
        oid = to_object_id(resume_id)
        if oid is None:
            return False
        return self._col.delete_one({"_id": oid}).deleted_count == 1


class MongoJobRepository:
    def __init__(self, db: Database) -> None:
        self._col = db.jobs

    def upsert_many(self, documents: list[dict[str, Any]]) -> int:
        """Insert postings, skipping ones already stored for the same URL.

        Returns the number newly stored. Re-running a scrape is therefore
        idempotent instead of filling the collection with duplicates.
        """
        stored = 0
        for doc in documents:
            payload = {**doc, "scraped_at": doc.get("scraped_at") or utcnow()}
            url = payload.get("url")
            try:
                if url:
                    result = self._col.update_one(
                        {"url": url}, {"$setOnInsert": payload}, upsert=True
                    )
                    stored += 1 if result.upserted_id is not None else 0
                else:
                    self._col.insert_one(payload)
                    stored += 1
            except DuplicateKeyError:
                continue
        return stored

    def list(self, limit: int = 100, skill: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"skills": skill} if skill else {}
        cursor = self._col.find(query).sort("scraped_at", -1).limit(limit)
        return [_with_id(doc) for doc in cursor]

    def count(self) -> int:
        return self._col.count_documents({})


# --------------------------------------------------------------------------
# In-memory doubles, used by the test suite
# --------------------------------------------------------------------------

class InMemoryResumeRepository:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._next = 1

    def create(self, document: dict[str, Any]) -> str:
        key = f"{self._next:024d}"
        self._next += 1
        self._items[key] = {
            **document,
            "id": key,
            "created_at": document.get("created_at") or utcnow(),
        }
        return key

    def get(self, resume_id: str) -> dict[str, Any] | None:
        return self._items.get(resume_id)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = sorted(self._items.values(), key=lambda d: d["created_at"], reverse=True)
        return rows[:limit]

    def delete(self, resume_id: str) -> bool:
        return self._items.pop(resume_id, None) is not None


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._next = 1

    def upsert_many(self, documents: list[dict[str, Any]]) -> int:
        seen = {d.get("url") for d in self._items if d.get("url")}
        stored = 0
        for doc in documents:
            if doc.get("url") and doc["url"] in seen:
                continue
            key = f"{self._next:024d}"
            self._next += 1
            self._items.append(
                {**doc, "id": key, "scraped_at": doc.get("scraped_at") or utcnow()}
            )
            if doc.get("url"):
                seen.add(doc["url"])
            stored += 1
        return stored

    def list(self, limit: int = 100, skill: str | None = None) -> list[dict[str, Any]]:
        rows = self._items
        if skill:
            rows = [r for r in rows if skill in r.get("skills", [])]
        rows = sorted(rows, key=lambda d: d["scraped_at"], reverse=True)
        return rows[:limit]

    def count(self) -> int:
        return len(self._items)


def _with_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Rename Mongo's _id to a string id the response models can use."""
    if document is None:
        return None
    out = dict(document)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out
