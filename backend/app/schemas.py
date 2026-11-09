"""Pydantic request and response models.

Every endpoint declares its shape here, which is what gives the API its
generated OpenAPI docs and its request validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Resumes
# --------------------------------------------------------------------------

class ResumeSkills(BaseModel):
    """Skills extracted from a resume, grouped by the taxonomy category."""

    all: list[str] = Field(default_factory=list)
    by_category: dict[str, list[str]] = Field(default_factory=dict)


class ResumeEntities(BaseModel):
    """Named entities spaCy found in the resume text."""

    organisations: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)


class ResumeOut(BaseModel):
    id: str
    filename: str
    characters: int
    skills: ResumeSkills
    entities: ResumeEntities
    years_experience: float | None = None
    created_at: datetime


class ResumeSummary(BaseModel):
    """Lightweight row for the resume list endpoint."""

    id: str
    filename: str
    skill_count: int
    created_at: datetime


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

class JobOut(BaseModel):
    id: str
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    scraped_at: datetime


class ScrapeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=120)
    limit: int = Field(default=25, ge=1, le=100)


class ScrapeResult(BaseModel):
    requested: int
    scraped: int
    stored: int
    jobs: list[JobOut]


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

class SkillOverlap(BaseModel):
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class MatchOut(BaseModel):
    job_id: str
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None
    score: float = Field(ge=0.0, le=100.0)
    band: Literal["strong", "moderate", "weak"]
    overlap: SkillOverlap


class MatchResponse(BaseModel):
    resume_id: str
    considered: int
    returned: int
    matches: list[MatchOut]


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------

class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    spacy_model: str
    pipeline: Literal["full", "rules-only"]


class ErrorOut(BaseModel):
    detail: str
