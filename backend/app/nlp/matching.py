"""Candidate-to-job relevance scoring.

Deliberately transparent: the score is arithmetic over two skill sets, so
every ranking can be explained to the candidate ("you matched 6 of 9 skills
this posting asks for, and these 3 are missing"). A dense embedding model
would rank slightly better and explain nothing, which is the wrong trade
for a tool whose job is to tell someone what to learn next.
"""

from __future__ import annotations

from dataclasses import dataclass

# Categories a hiring manager screens hardest on get the most weight.
CATEGORY_WEIGHTS: dict[str, float] = {
    "programming": 1.4,
    "backend": 1.3,
    "databases": 1.2,
    "cloud_devops": 1.2,
    "generative_ai": 1.2,
    "ml_dl": 1.1,
    "automation_testing": 1.0,
    "frontend": 1.0,
}
DEFAULT_WEIGHT = 1.0

STRONG_THRESHOLD = 65.0
MODERATE_THRESHOLD = 35.0

# A posting whose text yields only one or two recognisable skills gives us
# too little to judge on: matching its single skill would otherwise read as
# a perfect fit. Bands are capped until there is enough evidence.
STRONG_MIN_EVIDENCE = 4
MODERATE_MIN_EVIDENCE = 2


@dataclass(frozen=True)
class MatchScore:
    score: float
    band: str
    matched: list[str]
    missing: list[str]


def _weight_for(skill: str, index: dict[str, str]) -> float:
    return CATEGORY_WEIGHTS.get(index.get(skill, ""), DEFAULT_WEIGHT)


def build_category_index() -> dict[str, str]:
    """Map canonical skill -> taxonomy category, for weighting."""
    from .skills import SKILL_TAXONOMY

    return {
        canonical: category
        for category, entries in SKILL_TAXONOMY.items()
        for canonical in entries
    }


def score_match(
    resume_skills: list[str],
    job_skills: list[str],
    category_index: dict[str, str] | None = None,
) -> MatchScore:
    """Score how well a resume covers a posting's required skills.

    The score is weighted coverage: the share of the posting's skill demand
    the candidate satisfies, where each skill carries its category weight.
    A posting with no detected skills scores 0 rather than 100 - we cannot
    claim a match we have no evidence for.
    """
    index = category_index if category_index is not None else build_category_index()

    required = list(dict.fromkeys(job_skills))
    held = set(resume_skills)

    if not required:
        return MatchScore(0.0, "weak", [], [])

    matched = [s for s in required if s in held]
    missing = [s for s in required if s not in held]

    earned = sum(_weight_for(s, index) for s in matched)
    total = sum(_weight_for(s, index) for s in required)
    score = round(100.0 * earned / total, 1) if total else 0.0

    return MatchScore(score, band_for(score, len(required)), matched, missing)


def band_for(score: float, evidence: int | None = None) -> str:
    """Classify a score, capped by how much evidence supported it.

    `evidence` is the number of skills detected in the posting. Pass None
    to classify a bare score with no cap.
    """
    if evidence is not None and evidence < MODERATE_MIN_EVIDENCE:
        return "weak"
    if score >= STRONG_THRESHOLD:
        if evidence is not None and evidence < STRONG_MIN_EVIDENCE:
            return "moderate"
        return "strong"
    if score >= MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


def rank_jobs(
    resume_skills: list[str],
    jobs: list[dict],
    limit: int = 20,
    min_score: float = 0.0,
) -> list[tuple[dict, MatchScore]]:
    """Score every job and return the best ones, highest first.

    Ties break on the number of matched skills, so between two postings at
    the same percentage the richer match ranks first.
    """
    index = build_category_index()
    scored = [
        (job, score_match(resume_skills, job.get("skills", []), index)) for job in jobs
    ]
    kept = [pair for pair in scored if pair[1].score >= min_score]
    kept.sort(key=lambda pair: (pair[1].score, len(pair[1].matched)), reverse=True)
    return kept[:limit]


def skill_gap(resume_skills: list[str], jobs: list[dict], top: int = 10) -> list[tuple[str, int]]:
    """Skills demanded across postings that the resume does not have.

    Returned most-demanded first - this is the "what should I learn next"
    answer, and it falls straight out of the same data as the ranking.
    """
    held = set(resume_skills)
    counts: dict[str, int] = {}
    for job in jobs:
        for skill in set(job.get("skills", [])):
            if skill not in held:
                counts[skill] = counts.get(skill, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
