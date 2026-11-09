"""Design system for Resume Analyzer AI.

Single source of truth for colour, type and spacing. Generated from the
ui-ux-pro-max design system (Minimalism / Swiss, professional navy) and
documented in design-system/resume-analyzer-ai/MASTER.md.

Nothing in this module knows about resumes or scraping - it is presentation
only, so the app layer can stop hand-writing inline styles.
"""

from __future__ import annotations

import html

import streamlit as st

# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

TOKENS: dict[str, str] = {
    "primary": "#1E3A5F",
    "on-primary": "#FFFFFF",
    "secondary": "#2563EB",
    "on-secondary": "#FFFFFF",
    "accent": "#16A34A",
    # Black, not white: white on #16A34A is ~3:1 and fails WCAG AA for
    # body text, while black clears 6.9:1.
    "on-accent": "#000000",
    "background": "#F8FAFC",
    "foreground": "#0F172A",
    "card": "#FFFFFF",
    "muted": "#E9EEF5",
    "muted-foreground": "#475569",
    "border": "#CBD5E1",
    "destructive": "#DC2626",
    "on-destructive": "#FFFFFF",
    "ring": "#1E3A5F",
}

SPACE = {
    "xs": "8px",
    "sm": "12px",
    "md": "16px",
    "lg": "24px",
    "xl": "40px",
    "xxl": "64px",
}

FONT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Open+Sans:wght@400;500;600;700&family=Poppins:wght@500;600;700&display=swap"
)


def _declarations() -> str:
    colors = "\n".join(f"      --color-{k}: {v};" for k, v in TOKENS.items())
    spacing = "\n".join(f"      --space-{k}: {v};" for k, v in SPACE.items())
    return colors + "\n" + spacing


# --------------------------------------------------------------------------
# Global stylesheet
# --------------------------------------------------------------------------

_CSS_TEMPLATE = """
<style>
@import url('__FONT_URL__');

:root {
__DECLARATIONS__
  --radius: 10px;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, .06), 0 1px 3px rgba(15, 23, 42, .08);
  --transition: 200ms cubic-bezier(.4, 0, .2, 1);
}

[data-testid="stHeader"] { background: rgba(0, 0, 0, 0); }

html, body, [class*="st-"], .stMarkdown {
  font-family: 'Open Sans', system-ui, -apple-system, sans-serif;
  color: var(--color-foreground);
}

h1, h2, h3, h4, h5 {
  font-family: 'Poppins', system-ui, sans-serif;
  color: var(--color-primary);
  letter-spacing: -.01em;
  line-height: 1.25;
}

.stMarkdown p, .stMarkdown li { line-height: 1.6; }

/* ---- masthead ------------------------------------------------------ */
.ra-masthead {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-md);
  margin-bottom: var(--space-lg);
}
.ra-masthead h1 { margin: 0 0 4px; font-size: 1.75rem; }
.ra-masthead p {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: .95rem;
}

/* ---- section heading ----------------------------------------------- */
.ra-section {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin: var(--space-lg) 0 var(--space-sm);
}
.ra-section h2 { margin: 0; font-size: 1.15rem; white-space: nowrap; }
.ra-section .ra-rule { flex: 1; height: 1px; background: var(--color-border); }

/* ---- cards ---------------------------------------------------------- */
.ra-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-md);
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--transition), transform var(--transition);
  height: 100%;
}
.ra-card:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, .10);
  transform: translateY(-1px);
}
.ra-card h3 { margin: var(--space-xs) 0 4px; font-size: 1rem; }
.ra-card p {
  margin: 0;
  font-size: .9rem;
  color: var(--color-muted-foreground);
  line-height: 1.55;
}
.ra-card svg { color: var(--color-secondary); }

/* ---- result panel ---------------------------------------------------- */
.ra-result {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-accent);
  border-radius: var(--radius);
  padding: var(--space-md) var(--space-lg);
  margin-top: var(--space-sm);
}

/* ---- job posting ------------------------------------------------------ */
.ra-job {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-md);
  margin-bottom: var(--space-sm);
  background: var(--color-card);
}
.ra-job-title {
  font-family: 'Poppins', sans-serif;
  font-weight: 600;
  color: var(--color-primary);
  font-size: 1.05rem;
}
.ra-job-meta {
  color: var(--color-muted-foreground);
  font-size: .875rem;
  margin-top: 2px;
}

/* ---- numbered steps ---------------------------------------------------- */
.ra-steps { counter-reset: step; list-style: none; padding: 0; margin: 0; }
.ra-steps li {
  counter-increment: step;
  position: relative;
  padding: 0 0 var(--space-sm) var(--space-xl);
  color: var(--color-muted-foreground);
  line-height: 1.6;
}
.ra-steps li::before {
  content: counter(step);
  position: absolute;
  left: 0;
  top: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: .8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ra-steps li strong { color: var(--color-foreground); }

/* ---- controls ----------------------------------------------------------- */
.stButton > button, .stFormSubmitButton > button {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius);
  font-family: 'Poppins', sans-serif;
  font-weight: 500;
  min-height: 44px;            /* 44x44 minimum touch target */
  padding: 0 var(--space-lg);
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition);
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  background: #16314F;
  border-color: #16314F;
  color: var(--color-on-primary);
}
.stButton > button:focus-visible,
.stFormSubmitButton > button:focus-visible,
input:focus-visible, select:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--color-ring);
  outline-offset: 2px;
}

[data-testid="stFileUploaderDropzone"] {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
  background: var(--color-card);
  transition: border-color var(--transition), background var(--transition);
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--color-secondary);
  background: var(--color-muted);
}

[data-testid="stSidebar"] {
  background: var(--color-card);
  border-right: 1px solid var(--color-border);
}

.ra-hint {
  color: var(--color-muted-foreground);
  font-size: .85rem;
  margin-top: -6px;
}
.ra-hint a { color: var(--color-secondary); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: .01ms !important;
    animation-duration: .01ms !important;
  }
  .ra-card:hover { transform: none; }
}

@media (max-width: 640px) {
  .ra-masthead h1 { font-size: 1.4rem; }
  .ra-result { padding: var(--space-md); }
}
</style>
"""


def _stylesheet() -> str:
    return _CSS_TEMPLATE.replace("__FONT_URL__", FONT_URL).replace(
        "__DECLARATIONS__", _declarations()
    )


# --------------------------------------------------------------------------
# Inline SVG icons (Lucide geometry).
#
# SVG rather than emoji: emoji render differently on every platform, cannot
# inherit the token colours, and are announced by screen readers as their
# unicode name ("direct hit" for a target emoji).
# --------------------------------------------------------------------------

_ICON_PATHS: dict[str, str] = {
    "file-text": (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
        '<path d="M14 2v5h5"/><path d="M8 13h8"/><path d="M8 17h8"/>'
    ),
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "target": (
        '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/>'
        '<circle cx="12" cy="12" r="1"/>'
    ),
    "key": (
        '<path d="m15.5 7.5 3 3L22 7l-3-3"/><path d="m21 2-9.6 9.6"/>'
        '<circle cx="7.5" cy="15.5" r="5.5"/>'
    ),
    "list-checks": (
        '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/>'
        '<path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>'
    ),
}


def icon(name: str, size: int = 22) -> str:
    """Return an inline SVG string, or empty string for an unknown name."""
    path = _ICON_PATHS.get(name)
    if not path:
        return ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true" focusable="false">'
        f"{path}</svg>"
    )


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

def inject() -> None:
    """Apply the stylesheet. Call once, immediately after set_page_config."""
    st.markdown(_stylesheet(), unsafe_allow_html=True)


def masthead(title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="ra-masthead">'
        f"<h1>{html.escape(title)}</h1>"
        f"<p>{html.escape(subtitle)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(
        '<div class="ra-section">'
        f"<h2>{html.escape(title)}</h2>"
        '<span class="ra-rule"></span>'
        "</div>",
        unsafe_allow_html=True,
    )


def card(icon_name: str, title: str, body: str) -> str:
    """Return card markup. Caller renders it, so cards can sit in columns."""
    return (
        '<div class="ra-card">'
        f"{icon(icon_name)}"
        f"<h3>{html.escape(title)}</h3>"
        f"<p>{html.escape(body)}</p>"
        "</div>"
    )


def hint(text_html: str) -> None:
    """A short helper line under a field. Caller supplies trusted markup."""
    st.markdown(f'<p class="ra-hint">{text_html}</p>', unsafe_allow_html=True)


def result(title: str, body: str) -> None:
    """Render a successful analysis result inside a panel."""
    section(title)
    st.markdown('<div class="ra-result">', unsafe_allow_html=True)
    st.write(body)
    st.markdown("</div>", unsafe_allow_html=True)
