"""Word correction: accent restoration and typo fixing.

Strategy per word (lowercased):
  1. already a known word            -> keep (protects ou/la/a from guessing)
  2. folded form maps to a canonical -> restore accents (tres -> très)
  3. otherwise                       -> one-edit typo fix, frequency ranked
Ambiguous inputs are only changed when the input is not a word at all, so
common unaccented words are never "corrected" by accident.
"""
from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass, field

from wordfreq import word_frequency, top_n_list

LANGS = ("fr", "es", "de", "it", "pt", "en")
_LIST_SIZE = 200000
# An accented form only replaces its unaccented twin when it is at least
# this much more frequent (protects ou/où, cuando/cuándo, mas/más, ...)
_FIX_RATIO = 6.0

# Words that are legitimately written without accents in context
_ELISIONS = {"l", "d", "j", "n", "m", "s", "c", "qu", "t",
             "jusqu", "lorsqu", "puisqu", "quoiqu", "presqu"}

_word_re = re.compile(r"[^\W\d_]+(?:['’\u2019-][^\W\d_]+)*", re.UNICODE)

_lock = threading.Lock()
_lex: dict[str, "Lexicon"] = {}


@dataclass
class Change:
    original: str
    fixed: str
    kind: str                    # "accent" | "typo"
    start: int = 0               # span in CorrectionResult.text
    end: int = 0


@dataclass
class CorrectionResult:
    text: str
    changes: list[Change] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.changes)


def _fold(word: str) -> str:
    """Strip accents and fold special letters: ç->c, ß->ss."""
    word = word.lower().replace("ß", "ss")
    word = unicodedata.normalize("NFD", word)
    word = "".join(c for c in word if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", word)


class Lexicon:
    def __init__(self, lang: str) -> None:
        self.lang = lang
        words = top_n_list(lang, _LIST_SIZE)
        self.words = set(words)
        # folded form -> {surface form: frequency}
        self.folded: dict[str, dict[str, float]] = {}
        for w in words:
            f = _fold(w)
            if f:
                self.folded.setdefault(f, {})[w] = word_frequency(w, lang)
        # typo engine seeded with the same vocabulary
        from spellchecker import SpellChecker
        self.spell = SpellChecker(distance=1)
        self.spell.word_frequency.load_words(words)

    def accent_fix(self, word: str) -> str | None:
        lower = word.lower()
        cands = self.folded.get(_fold(lower))
        if not cands:
            return None
        best = max(cands, key=cands.get)     # type: ignore[arg-type]
        if best == lower:
            return None
        # The input may itself be a real word (ou/où, cuando/cuándo, tres).
        # Only fix when the accented form dominates the frequency - that
        # keeps common legitimate spellings untouched.
        own = word_frequency(lower, self.lang)
        if own and own * _FIX_RATIO > cands[best]:
            return None
        return _match_case(word, best)

    def typo_fix(self, word: str) -> str | None:
        lower = word.lower()
        if lower in self.words:
            return None
        candidates = self.spell.candidates(lower) or set()
        if not candidates:
            return None
        # prefer the accent-restoring candidate, else highest frequency
        folded = _fold(lower)
        ranked = sorted(
            candidates,
            key=lambda c: (1 if _fold(c) == folded else 0,
                           word_frequency(c, self.lang)),
            reverse=True,
        )
        best = ranked[0]
        if best == lower or best not in self.words:
            return None
        return _match_case(word, best)


def _match_case(original: str, replacement: str) -> str:
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def get_lexicon(lang: str) -> Lexicon:
    with _lock:
        if lang not in _lex:
            _lex[lang] = Lexicon(lang)
        return _lex[lang]


def correct(text: str, lang: str, fix_accents: bool = True,
            skip_range: tuple[int, int] | None = None) -> CorrectionResult:
    """Correct `text` as `lang`.

    `skip_range` is a (start, end) span of the word the user is currently
    typing - that word is never touched, so typing is never fought.
    """
    result = CorrectionResult(text=text)
    if not fix_accents or not text.strip() or lang not in LANGS:
        return result
    try:
        lex = get_lexicon(lang)
    except Exception:
        return result

    out: list[str] = []
    written = 0
    pos = 0
    for m in _word_re.finditer(text):
        token = m.group(0)
        start, end = m.span()
        if skip_range and not (end <= skip_range[0] or start >= skip_range[1]):
            out.append(text[pos:end])
            written += end - pos
            pos = end
            continue
        out.append(text[pos:start])
        written += start - pos
        fixed_token, changes = _fix_token(token, lex, lang)
        if changes:
            for ch in changes:
                ch.start = written
                ch.end = written + len(fixed_token)
        out.append(fixed_token)
        written += len(fixed_token)
        result.changes.extend(changes)
        pos = end
    out.append(text[pos:])
    if result.changes:
        result.text = "".join(out)
    return result


def word_range_at(text: str, pos: int) -> tuple[int, int] | None:
    """Span of the word containing `pos` (the one being typed)."""
    for m in _word_re.finditer(text):
        if m.start() <= pos <= m.end():
            return m.span()
    return None


def _fix_token(token: str, lex: Lexicon, lang: str) -> tuple[str, list[Change]]:
    changes: list[Change] = []
    # split on apostrophes / hyphens, keep elisions intact
    parts = re.split(r"(['’\u2019-])", token)
    for i in range(0, len(parts), 2):
        part = parts[i]
        if not part or _fold(part) in _ELISIONS or len(part) < 2:
            continue
        fixed = lex.accent_fix(part) or lex.typo_fix(part)
        if fixed and fixed != part:
            kind = "accent" if _fold(fixed) == _fold(part) else "typo"
            changes.append(Change(original=part, fixed=fixed, kind=kind))
            parts[i] = fixed
    if not changes:
        return token, []
    return "".join(parts), changes
