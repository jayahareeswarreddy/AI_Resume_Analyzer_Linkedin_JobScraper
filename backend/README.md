# Backend — AI Resume Analyzer & Job Matcher

FastAPI service that parses resumes, extracts skills with spaCy, stores
everything in MongoDB, scrapes LinkedIn postings with Selenium, and ranks
those postings by how well a candidate covers them.

```
POST   /resumes              upload a PDF -> skills, entities, experience
GET    /resumes              list stored resumes
GET    /resumes/{id}         full extraction for one resume
DELETE /resumes/{id}         remove a resume
GET    /jobs                 stored postings, filterable by ?skill=
POST   /jobs/scrape          scrape LinkedIn for a title + location
GET    /matches/{id}         postings ranked by relevance to that resume
GET    /matches/{id}/gaps    skills the market wants that the resume lacks
GET    /health               database reachability + which NLP pipeline is live
```

Interactive docs at `/docs` once running.

## How the NLP works

Two passes over the same spaCy document, because the two problems are not
the same problem:

**Skills — rules.** A `PhraseMatcher` over a curated taxonomy of ~90
technologies with their aliases (`sklearn`, `scikit learn` and
`Scikit-learn` all resolve to one canonical name). Skills are a closed
vocabulary, so dictionary matching beats statistical inference here and,
more importantly, it can never invent a skill the resume does not contain.
This part is deterministic. It is not AI, and the code does not pretend
otherwise.

**Entities — statistics.** `en_core_web_md`'s NER finds employers, people,
places and dates. This genuinely is a trained neural model.

The two passes correct each other. The NER was trained on news text, where
"Docker" and "Milvus" never appear, so on a resume it confidently tags them
`PERSON` or `ORG`. The taxonomy is ground truth for what counts as a
technology, so any span naming a known technology is dropped from the
entity buckets. Without that filter the extractor reports Kubernetes as a
city.

If the statistical model is not installed the service still runs: it falls
back to a blank pipeline, skill extraction continues to work, and
`/health` reports `"pipeline": "rules-only"` instead of `"full"` rather
than quietly implying an intelligence it does not have.

## How matching works

The score is weighted coverage of the *posting's* requirements:

```
score = 100 * (weight of matched skills) / (weight of all required skills)
```

Categories a hiring manager screens hardest on carry more weight, so
missing Python costs more than missing Streamlit. Three properties follow
deliberately:

- Padding a resume with unrelated skills cannot raise a score — it measures
  coverage of the job, not of the candidate.
- A posting with no detected skills scores 0, not 100. Absence of evidence
  is not a perfect match.
- Every score decomposes into `matched` and `missing`, so a ranking can
  always be explained, and `/matches/{id}/gaps` falls straight out of the
  same data as the "what should I learn next" answer.

A dense embedding model would rank marginally better and explain nothing,
which is the wrong trade for a tool whose purpose is to tell someone what
to fix.

## Layout

```
app/
  main.py              FastAPI app, lifespan, CORS
  api.py               all routes + dependency providers
  config.py            env-driven settings
  db.py                Mongo client, indexes, ping
  repositories.py      data access + in-memory doubles for tests
  schemas.py           Pydantic request/response models
  nlp/skills.py        taxonomy, PhraseMatcher, NER, entity filtering
  nlp/matching.py      scoring, ranking, skill-gap analysis
  services/
    resume_parser.py   PDF -> normalised text
    linkedin.py        Selenium scraper, context-managed driver
tests/                 41 tests, no database and no browser required
```

Routes depend on repository classes rather than on pymongo, so the whole
suite runs against in-memory doubles via FastAPI dependency overrides.

## Running it

Needs Python 3.10+, MongoDB, and Chrome (only for scraping).

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_md
uvicorn app.main:app --reload
```

Configuration is environment-driven, with working defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017` | database server |
| `MONGO_DB` | `resume_analyzer` | database name |
| `SPACY_MODEL` | `en_core_web_md` | NLP model |
| `SCRAPER_HEADLESS` | `1` | set `0` to watch the browser |
| `SCRAPER_MAX_JOBS` | `25` | per-scrape ceiling |

## Tests

```bash
pytest
```

41 tests, no MongoDB and no Chrome driver needed. They cover the scoring
invariants above, alias resolution, the `Java`/`JavaScript` false-positive
trap, entity filtering, PDF rejection paths, scrape de-duplication, and
every route's success and 404 behaviour.

## Known gaps

- Scraping depends on LinkedIn's public guest markup; their CSS class names
  change without notice, and `_parse_card` is where that breaks first.
- The taxonomy is hand-maintained. A skill that is not in it is invisible
  to both extraction and matching.
- `years_experience` is a regex over "N years", so it reads the largest
  figure on the page and can be fooled by "10 years of company history".
