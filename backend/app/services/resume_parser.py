"""Turn an uploaded PDF into plain text."""

from __future__ import annotations

import io
import re

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

MAX_BYTES = 10 * 1024 * 1024  # 10 MB, matching the Streamlit upload cap


class ResumeParseError(ValueError):
    """The upload was not a PDF we could read text out of."""


def extract_text(data: bytes) -> str:
    """Extract text from PDF bytes.

    Raises ResumeParseError for anything unusable, so the route can answer
    with a 400 and a message the user can act on rather than a 500.
    """
    if not data:
        raise ResumeParseError("The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise ResumeParseError("The file is larger than the 10 MB limit.")
    if not data.startswith(b"%PDF"):
        raise ResumeParseError("That file is not a PDF.")

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as exc:
        raise ResumeParseError(f"Could not read the PDF: {exc}") from exc

    text = normalise("\n".join(pages))
    if not text.strip():
        raise ResumeParseError(
            "No text found. The PDF looks like a scan - export a text-based "
            "PDF, or run OCR over it first."
        )
    return text


def normalise(text: str) -> str:
    """Collapse the whitespace PDF extraction leaves behind.

    Line breaks mid-sentence are an artefact of PDF layout, and they break
    multi-word phrase matching ("machine\\nlearning"), so they are flattened
    before the text reaches spaCy.
    """
    text = text.replace(" ", " ").replace("’", "'")
    text = re.sub(r"-\n(?=\w)", "", text)      # de-hyphenate across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
