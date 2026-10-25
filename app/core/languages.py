"""Language registry: single source of truth for every supported language."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str        # app code, also Google gtx target code
    name: str
    flag: str
    tts: str         # Google TTS voice code
    argos: str       # Argostranslate package code
    speak: str       # "French" - used in panel copy


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", "\U0001F1EC\U0001F1E7", "en", "en", "English"),
    "fr": Language("fr", "French", "\U0001F1EB\U0001F1F7", "fr", "fr", "French"),
    "es": Language("es", "Spanish", "\U0001F1EA\U0001F1F8", "es", "es", "Spanish"),
    "de": Language("de", "German", "\U0001F1E9\U0001F1EA", "de", "de", "German"),
    "it": Language("it", "Italian", "\U0001F1EE\U0001F1F9", "it", "it", "Italian"),
    "pt": Language("pt", "Portuguese", "\U0001F1E7\U0001F1F7", "pt", "pt", "Portuguese"),
}

# Languages the pronunciation panel can analyse (everything except English).
SPOKEN_LANGUAGES: tuple[str, ...] = ("fr", "es", "de", "it", "pt")

DEFAULT_SOURCE = "en"
DEFAULT_TARGET = "fr"


def get(code: str) -> Language:
    return LANGUAGES.get(code) or LANGUAGES[DEFAULT_SOURCE]


def label(code: str) -> str:
    lang = get(code)
    return f"{lang.flag} {lang.name}"


def combo_items() -> list[tuple[str, str]]:
    """(code, label) pairs in a stable display order."""
    order = ("fr", "en", "es", "de", "it", "pt")
    return [(c, label(c)) for c in order]
