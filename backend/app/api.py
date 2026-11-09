"""HTTP routes.

Dependencies are injected rather than imported at module level so the test
suite can swap MongoDB for the in-memory repositories.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from . import db as database
from .config import get_settings
from .nlp import matching
from .nlp.skills import get_extractor
from .repositories import (
    JobRepository,
    MongoJobRepository,
    MongoResumeRepository,
    ResumeRepository,
)
from .schemas import (
    HealthOut,
    JobOut,
    MatchOut,
    MatchResponse,
    ResumeEntities,
    ResumeOut,
    ResumeSkills,
    ResumeSummary,
    ScrapeRequest,
    ScrapeResult,
    SkillOverlap,
)
from .services.resume_parser import ResumeParseError, extract_text

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------

def get_resume_repository() -> ResumeRepository:
    return MongoResumeRepository(database.get_database())


def get_job_repository() -> JobRepository:
    return MongoJobRepository(database.get_database())


def _extractor():
    return get_extractor(get_settings().spacy_model)


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    reachable = database.ping()
    extractor = _extractor()
    return HealthOut(
        status="ok" if reachable else "degraded",
        database=reachable,
        spacy_model=extractor.model_name,
        pipeline=extractor.pipeline,
    )


# --------------------------------------------------------------------------
# Resumes
# --------------------------------------------------------------------------

resumes_router = APIRouter(prefix="/resumes", tags=["resumes"])


@resumes_router.post("", response_model=ResumeOut, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    repo: ResumeRepository = Depends(get_resume_repository),
) -> ResumeOut:
    """Parse a PDF resume, extract skills and entities, and store it."""
    raw = await file.read()
    try:
        text = extract_text(raw)
    except ResumeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = _extractor().extract(text)
    document = {
        "filename": file.filename or "resume.pdf",
        "characters": len(text),
        "text": text,
        "skills": result.skills,
        "skills_by_category": result.by_category,
        "organisations": result.organisations,
        "people": result.people,
        "locations": result.locations,
        "dates": result.dates,
        "years_experience": result.years_experience,
    }
    resume_id = repo.create(document)
    stored = repo.get(resume_id)
    if stored is None:  # pragma: no cover - only on a write/read race
        raise HTTPException(status_code=500, detail="Resume was not persisted.")
    return _resume_out(stored)


@resumes_router.get("", response_model=list[ResumeSummary])
def list_resumes(
    limit: int = Query(default=50, ge=1, le=200),
    repo: ResumeRepository = Depends(get_resume_repository),
) -> list[ResumeSummary]:
    return [
        ResumeSummary(
            id=row["id"],
            filename=row.get("filename", "resume.pdf"),
            skill_count=len(row.get("skills", [])),
            created_at=row["created_at"],
        )
        for row in repo.list(limit)
    ]


@resumes_router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: str, repo: ResumeRepository = Depends(get_resume_repository)
) -> ResumeOut:
    found = repo.get(resume_id)
    if found is None:
        raise HTTPException(status_code=404, detail="No resume with that id.")
    return _resume_out(found)


@resumes_router.delete("/{resume_id}", status_code=204, response_class=Response)
def delete_resume(
    resume_id: str, repo: ResumeRepository = Depends(get_resume_repository)
) -> Response:
    if not repo.delete(resume_id):
        raise HTTPException(status_code=404, detail="No resume with that id.")
    return Response(status_code=204)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


@jobs_router.get("", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    skill: str | None = Query(default=None),
    repo: JobRepository = Depends(get_job_repository),
) -> list[JobOut]:
    return [_job_out(row) for row in repo.list(limit, skill)]


@jobs_router.post("/scrape", response_model=ScrapeResult)
def scrape_jobs(
    request: ScrapeRequest, repo: JobRepository = Depends(get_job_repository)
) -> ScrapeResult:
    """Scrape LinkedIn for a title and location, then store the postings.

    Selenium is imported inside the handler: the rest of the API, and the
    whole test suite, should not need a browser driver present.
    """
    from .services.linkedin import LinkedInScraper, ScraperError

    extractor = _extractor()
    try:
        scraper = LinkedInScraper()
        postings = scraper.search(request.title, request.location, request.limit)
    except ScraperError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    for posting in postings:
        blob = " ".join(
            filter(None, [posting.get("title"), posting.get("description")])
        )
        posting["skills"] = extractor.extract(blob).skills

    stored = repo.upsert_many(postings)
    return ScrapeResult(
        requested=request.limit,
        scraped=len(postings),
        stored=stored,
        jobs=[_job_out(p) for p in repo.list(limit=request.limit)],
    )


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

matches_router = APIRouter(prefix="/matches", tags=["matching"])


@matches_router.get("/{resume_id}", response_model=MatchResponse)
def match_resume(
    resume_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    resumes: ResumeRepository = Depends(get_resume_repository),
    jobs: JobRepository = Depends(get_job_repository),
) -> MatchResponse:
    """Rank stored postings by how well the resume covers their skills."""
    resume = resumes.get(resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume with that id.")

    pool = jobs.list(limit=500)
    ranked = matching.rank_jobs(resume.get("skills", []), pool, limit, min_score)

    return MatchResponse(
        resume_id=resume_id,
        considered=len(pool),
        returned=len(ranked),
        matches=[
            MatchOut(
                job_id=str(job.get("id", "")),
                title=job.get("title", "Untitled role"),
                company=job.get("company"),
                location=job.get("location"),
                url=job.get("url"),
                score=score.score,
                band=score.band,
                overlap=SkillOverlap(matched=score.matched, missing=score.missing),
            )
            for job, score in ranked
        ],
    )


@matches_router.get("/{resume_id}/gaps", response_model=list[dict])
def skill_gaps(
    resume_id: str,
    top: int = Query(default=10, ge=1, le=50),
    resumes: ResumeRepository = Depends(get_resume_repository),
    jobs: JobRepository = Depends(get_job_repository),
) -> list[dict]:
    """Skills the market asks for that this resume does not mention."""
    resume = resumes.get(resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume with that id.")
    gaps = matching.skill_gap(resume.get("skills", []), jobs.list(limit=500), top)
    return [{"skill": name, "postings": count} for name, count in gaps]


# --------------------------------------------------------------------------
# Serialisation helpers
# --------------------------------------------------------------------------

def _resume_out(row: dict) -> ResumeOut:
    return ResumeOut(
        id=row["id"],
        filename=row.get("filename", "resume.pdf"),
        characters=row.get("characters", 0),
        skills=ResumeSkills(
            all=row.get("skills", []),
            by_category=row.get("skills_by_category", {}),
        ),
        entities=ResumeEntities(
            organisations=row.get("organisations", []),
            people=row.get("people", []),
            locations=row.get("locations", []),
            dates=row.get("dates", []),
        ),
        years_experience=row.get("years_experience"),
        created_at=row["created_at"],
    )


def _job_out(row: dict) -> JobOut:
    return JobOut(
        id=str(row.get("id", "")),
        title=row.get("title", "Untitled role"),
        company=row.get("company"),
        location=row.get("location"),
        url=row.get("url"),
        description=row.get("description"),
        skills=row.get("skills", []),
        scraped_at=row["scraped_at"],
    )
