"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api import health_router, jobs_router, matches_router, resumes_router
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("Connecting to MongoDB at %s/%s", settings.mongo_uri, settings.mongo_db)
    db.ensure_indexes()
    # Warm the spaCy pipeline now rather than on the first upload, which
    # would otherwise pay a several-second penalty mid-request.
    from .nlp.skills import get_extractor

    extractor = get_extractor(settings.spacy_model)
    log.info("spaCy pipeline: %s (%s)", extractor.model_name, extractor.pipeline)
    yield
    db.close_client()


app = FastAPI(
    title="AI Resume Analyzer & Job Matcher",
    version="2.0.0",
    summary=(
        "Parses resumes, extracts skills with spaCy, scrapes LinkedIn "
        "postings with Selenium, and ranks them by candidate relevance."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # The Streamlit client is the only browser consumer.
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(matches_router)


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    return {"service": "AI Resume Analyzer & Job Matcher", "docs": "/docs"}
