"""Tests for skill extraction, entity filtering and relevance scoring."""

from __future__ import annotations

import pytest

from app.nlp.matching import band_for, rank_jobs, score_match, skill_gap
from app.nlp.skills import get_extractor
from app.services.resume_parser import ResumeParseError, extract_text, normalise


@pytest.fixture(scope="module")
def extractor():
    return get_extractor()


# --------------------------------------------------------------------------
# Skill extraction
# --------------------------------------------------------------------------

def test_aliases_resolve_to_one_canonical_name(extractor):
    result = extractor.extract("Worked with sklearn, scikit learn and Scikit-learn.")
    assert result.skills.count("Scikit-learn") == 1


def test_skills_are_grouped_by_category(extractor):
    result = extractor.extract("Python, FastAPI, Docker and MongoDB.")
    assert result.by_category["programming"] == ["Python"]
    assert result.by_category["backend"] == ["FastAPI"]
    assert result.by_category["cloud_devops"] == ["Docker"]
    assert result.by_category["databases"] == ["MongoDB"]


def test_multi_word_skills_are_matched(extractor):
    skills = extractor.extract("Experience with retrieval augmented generation.").skills
    assert "RAG" in skills


def test_matching_is_case_insensitive(extractor):
    assert "Kubernetes" in extractor.extract("KUBERNETES and kubernetes").skills


def test_a_word_that_merely_contains_a_skill_is_not_matched(extractor):
    """'Java' must not fire on 'JavaScript' as a separate false positive."""
    skills = extractor.extract("I write JavaScript every day.").skills
    assert "JavaScript" in skills
    assert "Java" not in skills


def test_empty_text_yields_nothing(extractor):
    result = extractor.extract("   ")
    assert result.skills == [] and result.years_experience is None


def test_years_of_experience_takes_the_largest_plausible_figure(extractor):
    assert extractor.extract("3 years here, 7 years there").years_experience == 7.0


def test_absurd_year_counts_are_ignored(extractor):
    assert extractor.extract("99 years of experience").years_experience is None


# --------------------------------------------------------------------------
# Entity recognition
# --------------------------------------------------------------------------

def test_technologies_are_not_reported_as_people_or_employers(extractor):
    """The small models tag Docker as a PERSON; the taxonomy overrides them."""
    result = extractor.extract(
        "Priya Sharma worked at Infosys in Bangalore using Docker, "
        "Kubernetes, Milvus and RAG pipelines."
    )
    technologies = {"Docker", "Kubernetes", "Milvus", "RAG"}
    assert not technologies & set(result.organisations)
    assert not technologies & set(result.people)
    assert not technologies & set(result.locations)


@pytest.mark.skipif(
    get_extractor().pipeline != "full", reason="statistical model not installed"
)
def test_real_organisations_and_places_survive_the_filter(extractor):
    result = extractor.extract(
        "Priya Sharma worked at Infosys in Bangalore using Docker."
    )
    assert any("Infosys" in o for o in result.organisations)
    assert "Bangalore" in result.locations


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def test_full_coverage_scores_100():
    skills = ["Python", "Docker", "FastAPI", "MongoDB"]
    result = score_match(skills, skills)
    assert result.score == 100.0 and result.band == "strong"


def test_a_thinly_described_posting_cannot_read_as_a_strong_match():
    """One detected skill is not evidence of a strong fit, even at 100%."""
    result = score_match(["Python"], ["Python"])
    assert result.score == 100.0
    assert result.band == "weak"


def test_a_few_skills_cap_the_band_at_moderate():
    result = score_match(["Python", "Docker"], ["Python", "Docker"])
    assert result.score == 100.0
    assert result.band == "moderate"


def test_no_overlap_scores_zero_and_lists_everything_missing():
    result = score_match(["Python"], ["Java", "Spring"])
    assert result.score == 0.0
    assert result.missing == ["Java", "Spring"]


def test_a_posting_with_no_detected_skills_scores_zero_not_full():
    """Absence of evidence must not read as a perfect match."""
    assert score_match(["Python"], []).score == 0.0


def test_extra_resume_skills_do_not_inflate_the_score():
    """Scoring is coverage of the posting, not of the resume."""
    lean = score_match(["Python"], ["Python"])
    padded = score_match(["Python", "Go", "Rust", "Perl"], ["Python"])
    assert lean.score == padded.score == 100.0


def test_weighting_favours_the_categories_hiring_screens_on():
    programming = score_match(["Python"], ["Python", "Streamlit"])
    frontend = score_match(["Streamlit"], ["Python", "Streamlit"])
    assert programming.score > frontend.score


def test_duplicate_requirements_are_counted_once():
    assert score_match(["Python"], ["Python", "Python"]).score == 100.0


def test_bands_follow_the_thresholds():
    assert band_for(90) == "strong"
    assert band_for(50) == "moderate"
    assert band_for(10) == "weak"


def test_ranking_orders_by_score_then_by_breadth():
    jobs = [
        {"title": "weak", "skills": ["Java", "Spring"]},
        {"title": "strong", "skills": ["Python", "FastAPI"]},
    ]
    ranked = rank_jobs(["Python", "FastAPI"], jobs)
    assert [job["title"] for job, _ in ranked] == ["strong", "weak"]


def test_ranking_respects_the_limit():
    jobs = [{"title": str(i), "skills": ["Python"]} for i in range(10)]
    assert len(rank_jobs(["Python"], jobs, limit=3)) == 3


def test_skill_gap_counts_demand_and_excludes_held_skills():
    jobs = [
        {"skills": ["Python", "Docker"]},
        {"skills": ["Docker", "Kubernetes"]},
    ]
    gaps = dict(skill_gap(["Python"], jobs))
    assert gaps == {"Docker": 2, "Kubernetes": 1}


# --------------------------------------------------------------------------
# PDF parsing
# --------------------------------------------------------------------------

def test_non_pdf_bytes_are_rejected():
    with pytest.raises(ResumeParseError, match="not a PDF"):
        extract_text(b"hello world")


def test_empty_bytes_are_rejected():
    with pytest.raises(ResumeParseError):
        extract_text(b"")


def test_normalise_rejoins_words_split_across_lines():
    assert "machine learning" in normalise("machine\nlearning").replace("\n", " ")


def test_normalise_removes_hyphenation_at_line_breaks():
    assert normalise("micro-\nservices") == "microservices"


def test_normalise_collapses_runs_of_blank_lines():
    assert "\n\n\n" not in normalise("a\n\n\n\n\nb")
