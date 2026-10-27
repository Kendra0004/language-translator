"""Language registry: single source of truth for every supported language."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str        # app code, also Google gtx target code
    name: str
    tts: str         # Google TTS voice code
    argos: str       # Argostranslate package code
    speak: str       # "French" - used in panel copy


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", "en", "en", "English"),
    "fr": Language("fr", "French", "fr", "fr", "French"),
    "es": Language("es", "Spanish", "es", "es", "Spanish"),
    "de": Language("de", "German", "de", "de", "German"),
    "it": Language("it", "Italian", "it", "it", "Italian"),
    "pt": Language("pt", "Portuguese", "pt", "pt", "Portuguese"),
}

# Languages the pronunciation panel can analyse (everything except English).
SPOKEN_LANGUAGES: tuple[str, ...] = ("fr", "es", "de", "it", "pt")

DEFAULT_SOURCE = "en"
DEFAULT_TARGET = "fr"


def get(code: str) -> Language:
    return LANGUAGES.get(code) or LANGUAGES[DEFAULT_SOURCE]


def label(code: str) -> str:
    """Plain picker label - no flag emoji (fonts for those are missing on
    some systems and rendered as empty boxes)."""
    return get(code).name


def combo_items() -> list[tuple[str, str]]:
    """(code, label) pairs in a stable display order."""
    order = ("fr", "en", "es", "de", "it", "pt")
    return [(c, label(c)) for c in order]
