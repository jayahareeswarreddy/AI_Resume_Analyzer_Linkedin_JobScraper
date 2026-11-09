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
    },
    "ml_dl": {
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch", "torch"],
        "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
        "Keras": ["keras"],
        "CNN": ["cnn", "convolutional neural network"],
        "VGG16": ["vgg16", "vgg-16"],
        "NLP": ["nlp", "natural language processing"],
        "Named Entity Recognition": ["named entity recognition", "ner"],
        "spaCy": ["spacy"],
        "Pandas": ["pandas"],
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
        for match_id, start, end in self.matcher(doc):
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
                # PDF extraction leaves hard line breaks inside spans, so
                # an entity can arrive as a name glued to a job title.
                # Flatten the whitespace, then discard anything too long
                # to be a real name or place.
                # discard anything too long to be a real name or place.
                value = " ".join(ent.text.split())
                if not value or value in bucket or len(value) > 60:
                    continue
                if not any(ch.isalpha() for ch in value):
                    continue
                # The general-purpose NER was trained on news text, where
                # "Docker" and "Milvus" do not appear. On a resume it tags
                # them PERSON or ORG with real confidence. The taxonomy is
                # ground truth for what is a technology, so it wins.
                if ent.label_ in {"ORG", "PERSON", "GPE", "LOC"} and _is_technology(value):
                    continue
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


# Canonical names and every surface form, lowercased, for the NER filter.
_TECHNOLOGY_TERMS: frozenset[str] = frozenset(
    list(_SURFACE_INDEX)
    + [canonical.lower() for _, (canonical, _c) in _SURFACE_INDEX.items()]
)

# Job-title words that the NER reads as a person's name or an employer.
_ROLE_WORDS: frozenset[str] = frozenset(
    {
        "engineer",
        "developer",
        "freelance",
        "intern",
        "analyst",
        "consultant",
        "manager",
        "architect",
        "scientist",
        "lead",
        "specialist",
    }
)


def _is_technology(value: str) -> bool:
    """True when a span names a technology or a job role, not an entity."""
    lowered = value.lower().strip(" .,;:()")
    if lowered in _TECHNOLOGY_TERMS:
        return True
    tokens = set(lowered.split())
    if tokens & _ROLE_WORDS:
        return True
    # "Python and FastAPI" style spans: every word is a known technology.
    words = [w for w in lowered.replace(",", " ").split() if w not in {"and", "&"}]
    return bool(words) and all(w in _TECHNOLOGY_TERMS for w in words)


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
