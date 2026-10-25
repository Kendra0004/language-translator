"""Text -> per-word pronunciation analysis (IPA, syllables, stress, reading)."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

from . import phonetics

_WORD_RE = re.compile(r"\S+")

_epitran_lock = threading.Lock()
_epitran_cache: dict[str, object] = {}
_ipa_cache: dict[tuple[str, str], str] = {}

# French: word-final schwa stays only for short function words.
_FR_FUNCTION_WORDS = {
    "je", "me", "te", "se", "ne", "le", "de", "ce", "que", "je", "leurs",
}
# French: 3rd person plural verb endings are silent (nouns like "talent" are not).
_FR_VERB_ENT = {
    "parlent", "donnent", "mangent", "viennent", "peuvent", "veulent",
    "aiment", "travaillent", "dorment", "comprennent", "prennent",
    "entrent", "montrent", "sentent", "courent", "meurent", "pleurent",
    "trouvent", "jouent", "restent", "passent", "laissent", "connaissent",
    "appartiennent", "souffrent", "offrent", "vivent", "ecrivent",
    "écrivent", "reçoivent", "croient", "achètent", "procèdent", "sèchent",
    "frappent", "arrêtent", "achètent", "jettent", "dent", "font", "ont",
}
_FR_ENT_PATTERNS = ("nnent", "llent", "nnent")
# French words whose final -s really is pronounced (/s/)
_FR_S_PRONOUNCED = {"os", "bus", "plus", "fils"}


@dataclass
class WordPron:
    word: str                 # display form (no leading punctuation)
    core: str                 # lowercase letters only
    ipa: str = ""
    syllables: list[str] = field(default_factory=list)
    respell: list[str] = field(default_factory=list)
    stress: int = -1
    liaison: str = ""         # liaison sound appended after this word
    ok: bool = True


@dataclass
class Analysis:
    lang: str
    words: list[WordPron]
    separators: list[str]     # interleaved non-word text (" ", ", " ...)

    @property
    def respelling(self) -> str:
        return self._join(lambda w: "-".join(w.respell) or w.core)

    @property
    def ipa_line(self) -> str:
        return self._join(lambda w: ".".join(w.syllables) or w.ipa)

    @property
    def syllable_line(self) -> str:
        """Readable syllables with the stressed one shouted out."""
        def render(w: WordPron) -> str:
            syls = w.respell or ([w.ipa] if w.ipa else [w.core])
            return " • ".join(
                s.upper() if i == w.stress else s
                for i, s in enumerate(syls)
            )
        return self._join(render)

    def _join(self, render) -> str:
        out: list[str] = []
        for i, w in enumerate(self.words):
            out.append(render(w))
            if i < len(self.separators):
                out.append(self.separators[i])
        return "".join(out)


def _epitran(lang: str):
    with _epitran_lock:
        if lang not in _epitran_cache:
            import epitran
            codes = {"fr": "fra-Latn", "es": "spa-Latn", "de": "deu-Latn",
                     "it": "ita-Latn", "pt": "por-Latn"}
            _epitran_cache[lang] = epitran.Epitran(codes[lang])
        return _epitran_cache[lang]


def word_ipa(word: str, lang: str) -> str:
    core = _core(word)
    if not core:
        return ""
    key = (core, lang)
    if key in _ipa_cache:
        return _ipa_cache[key]
    try:
        ipa = _epitran(lang).transliterate(core)
    except Exception:
        ipa = ""
    ipa = _postprocess(core, ipa, lang)
    _ipa_cache[key] = ipa
    return ipa


def _core(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalpha() and c.isascii()
                   or (not c.isascii() and c.isalpha()))


def _postprocess(core: str, ipa: str, lang: str) -> str:
    if lang == "fr":
        if (core.endswith("ent") and len(core) > 4
                and (core in _FR_VERB_ENT
                     or core.endswith(_FR_ENT_PATTERNS))):
            for suffix in ("ɑ̃", "ɛ̃", "ɑ", "a"):
                if ipa.endswith(suffix):
                    ipa = ipa[: -len(suffix)]
                    break
        elif ipa.endswith("ə") and core not in _FR_FUNCTION_WORDS:
            ipa = ipa[:-1]
        # plural / 3rd person final -s is silent unless a liaison adds it back
        if (ipa.endswith("s") and core.endswith("s")
                and core not in _FR_S_PRONOUNCED):
            ipa = ipa[:-1]
    return ipa


def analyze(text: str, lang: str) -> Analysis | None:
    """Analyse `text` as `lang`. Returns None when there is nothing to say."""
    if not text.strip() or lang not in phonetics._ONSETS:
        return None
    tokens = _WORD_RE.findall(text)
    if not tokens:
        return None

    words: list[WordPron] = []
    seps: list[str] = []
    # separators = the gaps between tokens
    pos = 0
    for i, tok in enumerate(tokens):
        idx = text.find(tok, pos)
        if idx > pos:
            seps.append(text[pos:idx])
        elif i > 0:
            seps.append(" ")
        pos = idx + len(tok)

    for tok in tokens:
        core = _core(tok)
        wp = WordPron(word=tok, core=core)
        if core and any(c.isalpha() for c in core):
            ipa = word_ipa(tok, lang)
            wp.ipa = ipa
            if ipa:
                syls = phonetics.syllabify_ipa(ipa, lang)
                wp.syllables = syls
                wp.stress = phonetics.stress_index(core, syls, lang)
                if wp.stress >= len(syls):
                    wp.stress = len(syls) - 1
                wp.respell = [phonetics.respell(s, lang) for s in syls]
        else:
            wp.ok = False
        words.append(wp)

    if lang == "fr":
        _apply_liaisons(words)
    if not any(w.ipa for w in words):
        return None
    return Analysis(lang=lang, words=words, separators=seps)


_LIAISON_AFTER = {"s": "z", "x": "z", "z": "z", "t": "t", "d": "t",
                  "p": "p", "f": "f", "n": "n"}


def _apply_liaisons(words: list[WordPron]) -> None:
    for prev, nxt in zip(words, words[1:]):
        if not prev.ipa or not nxt.core:
            continue
        first = nxt.core[0]
        if first.isalpha() and first in "aeiouyh":
            last = prev.core[-1:] if prev.core else ""
            sound = _LIAISON_AFTER.get(last)
            if sound and not prev.ipa.endswith(sound):
                prev.liaison = sound
                prev.ipa += sound
                if prev.syllables:
                    prev.syllables[-1] += sound
                    if prev.respell:
                        prev.respell[-1] += phonetics.respell(sound, "fr")
