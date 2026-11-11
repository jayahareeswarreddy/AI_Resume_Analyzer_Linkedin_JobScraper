"""Skill and entity extraction with spaCy.

Two passes over the same document:

1. A PhraseMatcher over a curated taxonomy. Skills are a closed vocabulary -
   "React" is a skill, "reacted" is not - so matching known phrases beats
   trying to infer skills statistically, and it never hallucinates one.
2. Named-entity recognition for employers, places and dates, which is where
   a statistical model genuinely helps.

The PhraseMatcher pass works on a blank English pipeline, so the module
degrades to rules-only rather than failing when the statistical model has
not been downloaded.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

import spacy
from spacy.language import Language
from spacy.matcher import PhraseMatcher

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Taxonomy: canonical name -> surface forms that should match it
# --------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "programming": {
        "Python": ["python", "python3"],
        "SQL": ["sql"],
        "JavaScript": ["javascript", "js", "es6"],
        "TypeScript": ["typescript", "ts"],
        "Java": ["java"],
        "C++": ["c++", "cpp"],
        "Go": ["golang", "go lang"],
        "Bash": ["bash", "shell scripting"],
    },
    "generative_ai": {
        "LLMs": ["llm", "llms", "large language model", "large language models"],
        "Prompt Engineering": ["prompt engineering", "prompting"],
        "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "Embeddings": ["embedding", "embeddings"],
        "Vector Search": ["vector search", "semantic search", "similarity search"],
        "Tool Calling": ["tool calling", "function calling"],
        "Structured Outputs": ["structured output", "structured outputs", "json mode"],
        "LoRA": ["lora"],
        "QLoRA": ["qlora"],
        "Fine-tuning": ["fine tuning", "fine-tuning", "finetuning"],
        "OpenAI API": ["openai", "gpt-4", "gpt-4o", "chatgpt api"],
        "Copilot": ["copilot", "copilot studio", "github copilot"],
        "Workato": ["workato"],
    },
    "ml_dl": {
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch", "torch"],
        "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn", "scikit"],
        "Keras": ["keras"],
        "CNN": ["cnn", "convolutional neural network"],
        "VGG16": ["vgg16", "vgg-16"],
        "NLP": ["nlp", "natural language processing"],
        "Named Entity Recognition": ["named entity recognition", "ner"],
        "spaCy": ["spacy"],
        "Pandas": ["pandas"],
        "Tableau": ["tableau"],
        "Power BI": ["power bi", "powerbi"],
        "NumPy": ["numpy"],
    },
    "backend": {
        "FastAPI": ["fastapi", "fast api"],
        "REST APIs": ["rest api", "rest apis", "restful", "rest"],
        "Flask": ["flask"],
        "Django": ["django"],
        "Node.js": ["node.js", "nodejs", "node js"],
        "Express": ["express.js", "expressjs", "express"],
        "GraphQL": ["graphql"],
        "Microservices": ["microservice", "microservices"],
    },
    "databases": {
        "MongoDB": ["mongodb", "mongo"],
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "Redis": ["redis"],
        "Supabase": ["supabase"],
        "Milvus": ["milvus"],
        "FAISS": ["faiss"],
        "Elasticsearch": ["elasticsearch"],
        "SQLite": ["sqlite"],
        "BigQuery": ["bigquery"],
        "Snowflake": ["snowflake"],
    },
    "cloud_devops": {
        "Docker": ["docker", "containerisation", "containerization"],
        "Kubernetes": ["kubernetes", "k8s"],
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure"],
        "GCP": ["gcp", "google cloud"],
        "CI/CD": ["ci/cd", "continuous integration", "continuous deployment"],
        "Git": ["git"],
        "GitHub": ["github"],
        "Linux": ["linux"],
        "Terraform": ["terraform"],
        "Ansible": ["ansible"],
        "Jenkins": ["jenkins"],
        "Agile": ["agile", "scrum", "kanban"],
        "SaaS": ["saas"],
        "Postman": ["postman"],
    },
    "frontend": {
        "React": ["react", "react.js", "reactjs"],
        "Next.js": ["next.js", "nextjs"],
        "Vue": ["vue", "vue.js"],
        "Tailwind CSS": ["tailwind", "tailwind css"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"],
        "Streamlit": ["streamlit"],
    },
    "automation_testing": {
        "Selenium": ["selenium", "webdriver"],
        "API Testing": ["api testing"],
        "Workflow Automation": ["workflow automation", "process automation"],
        "Pytest": ["pytest"],
        "Web Scraping": ["web scraping", "scraping", "crawler"],
        "Error Handling": ["error handling", "exception handling"],
        "Troubleshooting": ["troubleshooting", "debugging"],
    },
}

# Flattened: surface form -> (canonical, category)
_SURFACE_INDEX: dict[str, tuple[str, str]] = {
    surface: (canonical, category)
    for category, entries in SKILL_TAXONOMY.items()
    for canonical, surfaces in entries.items()
    for surface in surfaces
}

_YEARS_PATTERN = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ExtractionResult:
    skills: list[str] = field(default_factory=list)
    by_category: dict[str, list[str]] = field(default_factory=dict)
    organisations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    years_experience: float | None = None


class SkillExtractor:
    """Extracts skills and entities from free text."""

    def __init__(self, model: str = "en_core_web_md") -> None:
        self.model_name = model
        self.nlp, self.has_ner = _load_pipeline(model)
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        for surface in _SURFACE_INDEX:
            self.matcher.add(surface, [self.nlp.make_doc(surface)])

    @property
    def pipeline(self) -> str:
        return "full" if self.has_ner else "rules-only"

    def extract(self, text: str) -> ExtractionResult:
        if not text or not text.strip():
            return ExtractionResult()

        doc = self.nlp(text)

        canonical: set[str] = set()
        grouped: dict[str, set[str]] = {}
        for match_id, _start, _end in self.matcher(doc):
            surface = self.nlp.vocab.strings[match_id]
            name, category = _SURFACE_INDEX[surface]
            canonical.add(name)
            grouped.setdefault(category, set()).add(name)

        orgs: list[str] = []
        people: list[str] = []
        locations: list[str] = []
        dates: list[str] = []
        if self.has_ner:
            for ent in doc.ents:
                bucket = {
                    "ORG": orgs,
                    "PERSON": people,
                    "GPE": locations,
                    "LOC": locations,
                    "DATE": dates,
                }.get(ent.label_)
                if bucket is None:
                    continue
                value = _clean_span(ent.text)
                if not value or value in bucket:
                    continue
                previous = doc[ent.start - 1] if ent.start > 0 else None
                keep = _keep_entity(
                    ent.label_,
                    value,
                    is_nominal=ent.root.pos_ in {"PROPN", "NOUN", "X"},
                    preceded_by_cue=(
                        previous is not None
                        and previous.text.lower() in _EMPLOYER_CUES
                    ),
                )
                if keep:
                    bucket.append(value)

        return ExtractionResult(
            skills=sorted(canonical),
            by_category={k: sorted(v) for k, v in sorted(grouped.items())},
            organisations=orgs[:25],
            people=people[:10],
            locations=locations[:15],
            dates=dates[:25],
            years_experience=_max_years(text),
        )


# Words that head a resume section. The NER sees them glued to the text
# that follows ("Backend & Databases: FastAPI...") and reports the whole
# run-on as an employer.
# Every surface form and every canonical name, lowercased. Used to veto
# NER spans: a span naming a technology is not an employer or a person.
_TECHNOLOGY_TERMS: frozenset[str] = frozenset(
    list(_SURFACE_INDEX)
    + [canonical.lower() for canonical, _cat in _SURFACE_INDEX.values()]
)

# A resume names employers next to degrees, coursework and job titles, and
# the model cannot tell them apart. Rather than guess, an ORG span has to
# carry positive evidence that it is a company or institution.
_ORG_KEYWORDS: frozenset[str] = frozenset({
    "inc", "inc.", "ltd", "ltd.", "limited", "llc", "llp", "plc", "gmbh",
    "pvt", "private", "corp", "corporation", "incorporated", "holdings",
    "university", "college", "institute", "academy", "foundation",
})

# Prepositions that introduce an employer: "at Wipro", "with Infosys".
_EMPLOYER_CUES: frozenset[str] = frozenset({
    "at", "with", "for", "@", "joined", "from",
})

# Title words the model reads as part of an employer name.
_ROLE_WORDS: frozenset[str] = frozenset({
    "engineer", "developer", "freelance", "intern", "internship", "analyst",
    "consultant", "manager", "architect", "scientist", "lead", "specialist",
    "junior", "senior", "associate", "trainee", "designer", "administrator",
})

_SECTION_WORDS: frozenset[str] = frozenset({
    "education", "experience", "skills", "certifications", "projects",
    "summary", "programming", "backend", "databases", "cloud", "devops",
    "automation", "testing", "generative", "coursework", "professional",
    "technical", "selected", "github", "linkedin", "portfolio", "contact",
    "ml/dl", "objective", "achievements", "publications", "languages",
})

_PERSON_RE = re.compile(r"^[A-Z][a-z'\-]+(?: [A-Z][a-z'\-]+){1,3}$")


def _clean_span(raw: str) -> str:
    """Flatten PDF line breaks and strip bullet glyphs and separators."""
    value = " ".join(raw.split())
    value = value.strip(" .,;:()[]|-•·–—")
    # The NER often swallows the article: "the Cisco Networking Academy".
    for article in ("the ", "The ", "a ", "A ", "an ", "An "):
        if value.startswith(article):
            value = value[len(article):]
            break
    return value


def _keep_entity(
    label: str,
    value: str,
    *,
    is_nominal: bool = True,
    preceded_by_cue: bool = False,
) -> bool:
    """Decide whether a span is a real entity or extraction noise.

    The model is trained on news prose. A resume is a dense two-column
    layout of headers and comma lists, so most of what it proposes here is
    an artefact. These rules throw away the artefacts.
    """
    if len(value) < 2 or len(value) > 60:
        return False
    # The tagger knows "Evaluated" is a verb even when the NER calls it an
    # organisation. Only nouns can name a thing.
    if not is_nominal:
        return False
    if not any(ch.isalpha() for ch in value):
        return False

    words = value.lower().replace("&", " ").replace("/", " ").split()
    if not words:
        return False

    # Anything naming a technology is not an employer, person or place.
    if any(w.strip(".,") in _TECHNOLOGY_TERMS for w in words):
        return False
    if value.lower() in _TECHNOLOGY_TERMS:
        return False

    if label == "DATE":
        # A date needs a number in it. "React.js" does not.
        return any(ch.isdigit() for ch in value)

    # Section headings and run-ons that swallowed one.
    if any(w in _SECTION_WORDS for w in words):
        return False

    # ALL-CAPS runs are headings in a resume, not entity names.
    letters = [c for c in value if c.isalpha()]
    if len(letters) > 3 and all(c.isupper() for c in letters):
        return False

    if label == "PERSON":
        return bool(_PERSON_RE.match(value))

    if label in {"GPE", "LOC"}:
        return len(words) <= 4

    # ORG, the noisiest bucket by far.
    if any(ch.isdigit() for ch in value):
        return False
    if any(w in _ROLE_WORDS for w in words):
        return False
    if any(len(w) > 2 and w.isupper() for w in value.split()):
        return False
    if len(words) > 6:
        return False
    # Shape alone is not evidence: a capitalised word at the start of a
    # bullet ("Evaluated...", "Coordinated...") looks exactly like a
    # company name. Require the span either to name itself a legal or
    # academic entity, or to sit after a preposition that introduces an
    # employer.
    return any(w in _ORG_KEYWORDS for w in words) or preceded_by_cue


def _max_years(text: str) -> float | None:
    """Largest "N years" figure mentioned, a crude seniority signal."""
    values = [float(m) for m in _YEARS_PATTERN.findall(text)]
    plausible = [v for v in values if 0 < v <= 50]
    return max(plausible) if plausible else None


def _load_pipeline(model: str) -> tuple[Language, bool]:
    try:
        nlp = spacy.load(model, disable=["lemmatizer"])
        return nlp, "ner" in nlp.pipe_names
    except OSError:
        log.warning(
            "spaCy model %r not installed - falling back to rules-only "
            "extraction. Run: python -m spacy download %s",
            model,
            model,
        )
        return spacy.blank("en"), False


@lru_cache(maxsize=4)
def get_extractor(model: str = "en_core_web_md") -> SkillExtractor:
    """Build the extractor once per model name; it is expensive to construct."""
    return SkillExtractor(model)
