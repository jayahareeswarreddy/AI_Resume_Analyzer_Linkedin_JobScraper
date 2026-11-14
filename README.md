# AI Resume Analyzer & LinkedIn Job Matcher

This repository contains two related applications:

- A Streamlit app (`app.py`) for Groq-powered resume summaries, analysis, job-title suggestions, and Selenium-based LinkedIn job search.
- A FastAPI backend (`backend/`) for PDF parsing, deterministic skill extraction, job matching, and API-driven LinkedIn scraping.

## Streamlit app

### Requirements

- Python 3.10 or newer
- A Groq API key for resume summary, analysis, and job-title features
- Chrome and an internet connection for LinkedIn scraping

### Run locally

From the repository root:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. The app asks for the Groq key in its UI when an AI feature is used. `HUGGINGFACEHUB_API_TOKEN` can optionally be loaded from a local `.env` file for the Hugging Face embedding integration. Do not commit API keys or `.env` files.

The Streamlit workflow is: upload a PDF, extract its text, then request a summary, resume analysis, or suggested job titles. The LinkedIn Jobs section searches by title and location and uses Selenium to collect public job listing details.

## FastAPI backend

The backend is a separate service with its own dependencies and configuration.

### Run locally

```bash
cd backend
python -m venv .venv
# Activate the environment using the command for your operating system.
python -m pip install -r requirements.txt
python -m spacy download en_core_web_md
uvicorn app.main:app --reload
```

The API defaults to MongoDB at `mongodb://localhost:27017`; start MongoDB first or configure `MONGO_URI`. The spaCy model is optional: the API falls back to deterministic skill extraction without it. Scraping requires Chrome. Open `/docs` for interactive API documentation and `/health` for service status.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection |
| `MONGO_DB` | `resume_analyzer` | Database name |
| `SPACY_MODEL` | `en_core_web_md` | Optional spaCy model |
| `SCRAPER_HEADLESS` | `1` | Set to `0` to show the browser |
| `SCRAPER_MAX_JOBS` | `25` | Per-scrape job limit |

### Backend tests

```bash
cd backend
python -m pip install -r requirements.txt
pytest
```

The backend test suite uses in-memory repositories and does not require MongoDB or Chrome.

## Repository layout

```text
app.py                 Streamlit application
requirements.txt       Streamlit app dependencies
backend/               FastAPI application, tests, and separate requirements
start.bat              Windows Streamlit launcher
setup.bat              Windows Streamlit dependency setup
```

## Known limitations

- LinkedIn's public page markup can change, which may break scraping selectors.
- Resume skill matching uses a curated vocabulary; skills not in that vocabulary may be missed.
- The Streamlit app and FastAPI backend are separate implementations with different workflows and dependencies.

## License

MIT. See [LICENSE](LICENSE).
