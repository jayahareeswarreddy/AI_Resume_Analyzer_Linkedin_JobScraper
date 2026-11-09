"""Resume Analyzer AI - Streamlit front end.

Talks to the FastAPI backend over HTTP; it holds no parsing, NLP or
database logic of its own. Styling comes from theme.py, which is generated
from design-system/resume-analyzer-ai/MASTER.md.

Run the API first:  uvicorn app.main:app --port 8765   (from backend/)
Then:               streamlit run dashboard.py
"""

from __future__ import annotations

import os

import requests
import streamlit as st

import theme

API = os.getenv("API_URL", "http://127.0.0.1:8765")
TIMEOUT = 120

st.set_page_config(
    page_title="Resume Analyzer AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.inject()


# --------------------------------------------------------------------------
# API helpers
# --------------------------------------------------------------------------

def api_get(path: str, **params):
    try:
        r = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as exc:
        detail = _detail(exc.response)
        return None, detail
    except requests.RequestException:
        return None, f"Cannot reach the API at {API}. Is the backend running?"


def api_post(path: str, **kwargs):
    try:
        r = requests.post(f"{API}{path}", timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as exc:
        return None, _detail(exc.response)
    except requests.RequestException:
        return None, f"Cannot reach the API at {API}. Is the backend running?"


def _detail(response) -> str:
    try:
        return response.json().get("detail", response.text)
    except Exception:
        return f"HTTP {response.status_code}"


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Resume Analyzer AI")
    page = st.radio(
        "Section",
        ["Overview", "Analyse a resume", "Job matches", "Skill gaps", "Job postings"],
        label_visibility="collapsed",
    )

    st.divider()
    health, health_err = api_get("/health")
    if health_err:
        st.error("API offline")
        st.caption(f"Expected at {API}")
    else:
        db_ok = health["database"]
        st.success("API online") if db_ok else st.warning("API up, database down")
        st.caption(f"Model: `{health['spacy_model']}`")
        if health["pipeline"] == "full":
            st.caption("Pipeline: **full** — statistical NER active")
        else:
            st.caption("Pipeline: **rules-only** — NER model not installed")

    resumes, _ = api_get("/resumes")
    resumes = resumes or []
    if resumes:
        labels = {f"{r['filename']} · {r['skill_count']} skills": r["id"] for r in resumes}
        chosen = st.selectbox("Active resume", list(labels), key="resume_pick")
        st.session_state["resume_id"] = labels[chosen]

resume_id = st.session_state.get("resume_id")


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------

if page == "Overview":
    theme.masthead(
        "Resume Analyzer AI",
        "Extract skills from a resume, then rank real job postings by how well you cover them.",
    )

    cols = st.columns(3)
    cards = [
        ("file-text", "Parse & extract",
         "Upload a PDF. A spaCy pipeline pulls out skills, employers, places and dates."),
        ("search", "Scrape postings",
         "Selenium collects public LinkedIn listings for a title and location."),
        ("target", "Rank by fit",
         "Every posting is scored on how much of its skill demand you actually cover."),
    ]
    for col, (ic, title, body) in zip(cols, cards):
        col.markdown(theme.card(ic, title, body), unsafe_allow_html=True)

    theme.section("How the scoring works")
    st.markdown(
        "The score is **weighted coverage of the posting's requirements** — not of "
        "your resume. Three consequences, all deliberate:"
    )
    st.markdown(
        """
- Padding your resume with unrelated skills **cannot** raise a score.
- A posting with no detectable skills scores **0**, not 100. Absence of
  evidence is not a perfect match.
- Every score breaks down into *matched* and *missing*, so a ranking can
  always be explained — which is where the skill-gap view comes from.
"""
    )

    theme.section("Getting started")
    st.markdown(
        '<ol class="ra-steps">'
        "<li><strong>Analyse a resume</strong> — upload your PDF.</li>"
        "<li><strong>Job postings</strong> — scrape some listings, or use what is stored.</li>"
        "<li><strong>Job matches</strong> — see the ranking and the gaps.</li>"
        "</ol>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Analyse a resume
# --------------------------------------------------------------------------

elif page == "Analyse a resume":
    theme.masthead("Analyse a resume", "Upload a text-based PDF. Scans will be rejected.")

    with st.form("upload"):
        pdf = st.file_uploader("Resume (PDF)", type="pdf")
        submitted = st.form_submit_button("Analyse")

    if submitted:
        if pdf is None:
            # Error sits with the field it belongs to, not as a page banner.
            st.error("Choose a PDF file first.")
        else:
            with st.spinner("Extracting skills and entities…"):
                data, err = api_post(
                    "/resumes",
                    files={"file": (pdf.name, pdf.getvalue(), "application/pdf")},
                )
            if err:
                st.error(err)
            else:
                st.session_state["resume_id"] = data["id"]
                st.success(f"Analysed **{data['filename']}** — {data['characters']:,} characters.")

                theme.section("Skills found")
                st.metric("Total skills", len(data["skills"]["all"]))
                for category, items in data["skills"]["by_category"].items():
                    st.markdown(f"**{category.replace('_', ' ').title()}** — {', '.join(items)}")

                theme.section("Entities (statistical NER)")
                e = data["entities"]
                c1, c2, c3 = st.columns(3)
                c1.markdown("**Employers**")
                c1.write(e["organisations"] or "—")
                c2.markdown("**Locations**")
                c2.write(e["locations"] or "—")
                c3.markdown("**Dates**")
                c3.write(e["dates"][:8] or "—")


# --------------------------------------------------------------------------
# Job matches
# --------------------------------------------------------------------------

elif page == "Job matches":
    theme.masthead("Job matches", "Stored postings ranked by how well your resume covers them.")

    if not resume_id:
        st.info("Upload a resume first — see **Analyse a resume** in the sidebar.")
    else:
        min_score = st.slider("Minimum score", 0, 100, 0, 5)
        data, err = api_get(f"/matches/{resume_id}", min_score=min_score, limit=50)
        if err:
            st.error(err)
        elif not data["matches"]:
            st.info(
                f"No postings at or above {min_score}. "
                "Scrape some listings in **Job postings**, or lower the threshold."
            )
        else:
            st.caption(f"{data['returned']} of {data['considered']} stored postings")
            for m in data["matches"]:
                badge = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}[m["band"]]
                with st.container(border=True):
                    top, right = st.columns([0.78, 0.22])
                    with top:
                        st.markdown(f"**{m['title']}**")
                        bits = [b for b in (m.get("company"), m.get("location")) if b]
                        st.caption(" · ".join(bits) or "—")
                    right.metric("Fit", f"{m['score']:.0f}%", help=f"{badge} {m['band']}")

                    st.progress(min(m["score"] / 100, 1.0))
                    if m["overlap"]["matched"]:
                        st.markdown("**You have:** " + ", ".join(m["overlap"]["matched"]))
                    if m["overlap"]["missing"]:
                        st.markdown("**Missing:** " + ", ".join(m["overlap"]["missing"]))
                    if m.get("url"):
                        st.markdown(f"[Open posting]({m['url']})")


# --------------------------------------------------------------------------
# Skill gaps
# --------------------------------------------------------------------------

elif page == "Skill gaps":
    theme.masthead("Skill gaps", "What the stored postings ask for that your resume does not mention.")

    if not resume_id:
        st.info("Upload a resume first — see **Analyse a resume** in the sidebar.")
    else:
        gaps, err = api_get(f"/matches/{resume_id}/gaps", top=20)
        if err:
            st.error(err)
        elif not gaps:
            st.success("No gaps across the stored postings.")
        else:
            st.caption("Ordered by how many postings ask for it — learn from the top.")
            st.bar_chart(
                {g["skill"]: g["postings"] for g in gaps},
                horizontal=True,
                color="#1E3A5F",
            )
            st.dataframe(gaps, hide_index=True, use_container_width=True)


# --------------------------------------------------------------------------
# Job postings
# --------------------------------------------------------------------------

elif page == "Job postings":
    theme.masthead("Job postings", "Scrape LinkedIn, or browse what is already stored.")

    with st.form("scrape"):
        c1, c2, c3 = st.columns([0.45, 0.35, 0.20])
        title = c1.text_input("Job title", placeholder="Backend Engineer")
        location = c2.text_input("Location", placeholder="Hyderabad, India")
        limit = c3.number_input("Limit", 1, 100, 25)
        go = st.form_submit_button("Scrape")

    if go:
        if not title.strip():
            st.error("Enter a job title to search for.")
        else:
            with st.spinner("Driving a headless browser — this takes a minute…"):
                data, err = api_post(
                    "/jobs/scrape",
                    json={"title": title, "location": location, "limit": int(limit)},
                )
            if err:
                st.error(err)
            else:
                st.success(f"Scraped {data['scraped']}, stored {data['stored']} new.")

    theme.section("Stored postings")
    jobs, err = api_get("/jobs", limit=100)
    if err:
        st.error(err)
    elif not jobs:
        st.info("Nothing stored yet. Run a scrape above.")
    else:
        st.caption(f"{len(jobs)} postings")
        for j in jobs:
            with st.container(border=True):
                st.markdown(f"**{j['title']}**")
                st.caption(" · ".join(b for b in (j.get("company"), j.get("location")) if b) or "—")
                if j["skills"]:
                    st.markdown("**Skills detected:** " + ", ".join(j["skills"]))
                if j.get("url"):
                    st.markdown(f"[Open posting]({j['url']})")
