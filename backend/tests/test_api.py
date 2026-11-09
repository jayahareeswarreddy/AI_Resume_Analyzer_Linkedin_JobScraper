"""End-to-end API tests.

MongoDB is swapped for the in-memory repositories via dependency
overrides, so the suite runs with no database and no Chrome driver.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter

from app.api import get_job_repository, get_resume_repository
from app.main import app
from app.repositories import InMemoryJobRepository, InMemoryResumeRepository


@pytest.fixture()
def repos():
    return InMemoryResumeRepository(), InMemoryJobRepository()


@pytest.fixture()
def client(repos, monkeypatch):
    resumes, jobs = repos
    # The lifespan would hit Mongo and warm spaCy; neither is wanted here.
    monkeypatch.setattr("app.db.ensure_indexes", lambda: None)
    app.dependency_overrides[get_resume_repository] = lambda: resumes
    app.dependency_overrides[get_job_repository] = lambda: jobs
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _pdf_bytes(pages: int = 1) -> bytes:
    """A structurally valid PDF. It carries no text layer."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Health and routing
# --------------------------------------------------------------------------

def test_root_points_at_the_docs(client):
    assert client.get("/").json()["docs"] == "/docs"


def test_health_reports_the_pipeline(client):
    body = client.get("/health").json()
    assert body["pipeline"] in {"full", "rules-only"}
    assert "spacy_model" in body


def test_openapi_schema_builds(client):
    schema = client.get("/openapi.json").json()
    assert "/resumes" in schema["paths"]
    assert "/matches/{resume_id}" in schema["paths"]


# --------------------------------------------------------------------------
# Resume upload validation
# --------------------------------------------------------------------------

def test_rejects_a_non_pdf_upload(client):
    response = client.post(
        "/resumes", files={"file": ("cv.txt", b"just text", "text/plain")}
    )
    assert response.status_code == 400
    assert "not a PDF" in response.json()["detail"]


def test_rejects_an_empty_upload(client):
    response = client.post(
        "/resumes", files={"file": ("cv.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400


def test_rejects_a_pdf_with_no_text_layer(client):
    """A scanned PDF has pages but no extractable text - say so clearly."""
    response = client.post(
        "/resumes", files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}
    )
    assert response.status_code == 400
    assert "scan" in response.json()["detail"].lower()


def test_unknown_resume_id_is_404(client):
    assert client.get("/resumes/does-not-exist").status_code == 404


# --------------------------------------------------------------------------
# Resume lifecycle, driven through the repository
# --------------------------------------------------------------------------

def test_stored_resume_is_listed_and_retrievable(client, repos):
    resumes, _ = repos
    resume_id = resumes.create(
        {
            "filename": "jaya.pdf",
            "characters": 120,
            "skills": ["Python", "FastAPI"],
            "skills_by_category": {"programming": ["Python"]},
        }
    )

    listed = client.get("/resumes").json()
    assert [row["id"] for row in listed] == [resume_id]
    assert listed[0]["skill_count"] == 2

    detail = client.get(f"/resumes/{resume_id}").json()
    assert detail["skills"]["all"] == ["Python", "FastAPI"]


def test_delete_removes_the_resume(client, repos):
    resumes, _ = repos
    resume_id = resumes.create({"filename": "x.pdf", "skills": []})
    assert client.delete(f"/resumes/{resume_id}").status_code == 204
    assert client.get(f"/resumes/{resume_id}").status_code == 404


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def test_jobs_can_be_filtered_by_skill(client, repos):
    _, jobs = repos
    jobs.upsert_many(
        [
            {"title": "Backend Engineer", "url": "u1", "skills": ["Python", "Docker"]},
            {"title": "Frontend Engineer", "url": "u2", "skills": ["React"]},
        ]
    )
    titles = [j["title"] for j in client.get("/jobs?skill=Docker").json()]
    assert titles == ["Backend Engineer"]


def test_rescraping_the_same_url_does_not_duplicate(repos):
    _, jobs = repos
    posting = [{"title": "Engineer", "url": "https://x/1", "skills": []}]
    assert jobs.upsert_many(posting) == 1
    assert jobs.upsert_many(posting) == 0
    assert jobs.count() == 1


def test_scrape_rejects_an_empty_title(client):
    assert client.post("/jobs/scrape", json={"title": "", "limit": 5}).status_code == 422


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def test_matches_rank_by_coverage_and_explain_the_gap(client, repos):
    resumes, jobs = repos
    resume_id = resumes.create(
        {"filename": "cv.pdf", "skills": ["Python", "FastAPI", "MongoDB"]}
    )
    jobs.upsert_many(
        [
            {
                "title": "Perfect fit",
                "url": "u1",
                "skills": ["Python", "FastAPI", "MongoDB"],
            },
            {"title": "Partial fit", "url": "u2", "skills": ["Python", "Kubernetes"]},
            {"title": "No fit", "url": "u3", "skills": ["Java", "Spring"]},
        ]
    )

    body = client.get(f"/matches/{resume_id}").json()
    assert body["considered"] == 3
    ordered = [m["title"] for m in body["matches"]]
    assert ordered[0] == "Perfect fit"
    assert ordered[-1] == "No fit"

    best = body["matches"][0]
    assert best["score"] == 100.0
    assert best["band"] == "strong"
    assert best["overlap"]["missing"] == []

    partial = next(m for m in body["matches"] if m["title"] == "Partial fit")
    assert partial["overlap"]["missing"] == ["Kubernetes"]


def test_min_score_filters_weak_matches(client, repos):
    resumes, jobs = repos
    resume_id = resumes.create({"filename": "cv.pdf", "skills": ["Python"]})
    jobs.upsert_many(
        [
            {"title": "Match", "url": "u1", "skills": ["Python"]},
            {"title": "Miss", "url": "u2", "skills": ["Java", "Spring", "Kubernetes"]},
        ]
    )
    body = client.get(f"/matches/{resume_id}?min_score=50").json()
    assert [m["title"] for m in body["matches"]] == ["Match"]


def test_skill_gaps_rank_by_demand(client, repos):
    resumes, jobs = repos
    resume_id = resumes.create({"filename": "cv.pdf", "skills": ["Python"]})
    jobs.upsert_many(
        [
            {"title": "A", "url": "u1", "skills": ["Python", "Docker"]},
            {"title": "B", "url": "u2", "skills": ["Docker", "Kubernetes"]},
        ]
    )
    gaps = client.get(f"/matches/{resume_id}/gaps").json()
    assert gaps[0] == {"skill": "Docker", "postings": 2}
    assert {"skill": "Kubernetes", "postings": 1} in gaps
    assert all(g["skill"] != "Python" for g in gaps)


def test_matching_an_unknown_resume_is_404(client):
    assert client.get("/matches/nope").status_code == 404
