"""IPA syllabification, stress assignment and learner-friendly respelling.

Input is an IPA string produced by epitran; this module splits it into
syllables, decides which syllable carries the stress (per language) and
renders each syllable the way an English speaker can read aloud.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- IPA vowels
VOWEL_BASE = set("aeiouyɑɐɒɜɞɘəɵɤɯɨɪʊœøæɛɔãõẽĩũäöüàáèéìíòóùúâêîôû")
COMBINING = {"̃", "̃", "ː", "̯", "̈", "̥", "̩", "̰", "̪", "̻", "ʲ", "ʷ", "ˤ"}


def is_vowel(ch: str) -> bool:
    if ch in VOWEL_BASE:
        return True
    if unicodedata.combining(ch):
        return False
    return False


def _is_nucleus_char(ch: str, prev_vowel: bool) -> bool:
    """A combining nasal/tongue-length mark belongs to the vowel before it."""
    if is_vowel(ch):
        return True
    return prev_vowel and ch in COMBINING


# ---------------------------------------------------------------- syllabify
# Allowed onsets per language (longest match wins). Anything not listed falls
# back to a single final consonant as onset.
_ONSETS: dict[str, set[str]] = {
    "fr": set("pbtdkgfvszmlnrjʒʃɲ") | {
        "pr", "br", "tr", "dr", "gr", "kr", "fr", "vr", "bl", "cl", "fl",
        "pl", "gl", "ml", "sj", "sj", "ʃt", "st",
    },
    "es": set("pbtdkgfvszmlnrθxʝɾɲ") | {
        "pr", "br", "tr", "dr", "gr", "kr", "kr", "fr", "pl", "bl", "cl",
        "fl", "gl", "ɾt",
    },
    "de": set("pbtdkgfvszmlnrjʃçxʁts") | {
        "ʃp", "ʃt", "ʃk", "ps", "ks", "ts", "pf", "bv", "kv", "gn",
        "pr", "br", "tr", "dr", "gr", "kr", "fr", "vr", "pl", "bl", "cl",
        "fl", "gl", "zl", "zʁ", "ʁn", "ʁm", "ŋk", "ŋg", "çt", "st", "sp",
    },
    "it": set("pbtdkgfvszmlnrjʃɲʎ") | {
        "tr", "pr", "br", "dr", "gr", "kr", "fr", "pl", "bl", "cl", "fl",
        "gl", "gn", "sk", "sp", "st",
    },
    "pt": set("pbtdkgfvszmlnrjʃɲʎɾʁ") | {
        "tr", "pr", "br", "dr", "gr", "kr", "fr", "pl", "bl", "cl", "fl",
        "gl", "mn", "ɾt",
    },
}


def syllabify_ipa(ipa: str, lang: str) -> list[str]:
    """Split an IPA string into syllables (nucleus-centred, onset-maximal)."""
    ipa = ipa.strip()
    if not ipa:
        return []
    if " " in ipa:  # multi-word input: analyse per word
        return ipa.split()

    # 1. find nucleus spans
    nuclei: list[tuple[int, int]] = []
    i = 0
    while i < len(ipa):
        if _is_nucleus_char(ipa[i], False):
            j = i + 1
            while j < len(ipa) and _is_nucleus_char(ipa[j], True):
                j += 1
            # attach a following glide-like consonant in nasal diphthongs? keep simple
            nuclei.append((i, j))
            i = j
        else:
            i += 1
    if not nuclei:
        return [ipa]  # no vowels (acronym etc.) - keep as one chunk

    onsets = _ONSETS.get(lang, _ONSETS["fr"])
    parts: list[str] = []
    prev_end = 0
    for idx, (s, e) in enumerate(nuclei):
        if idx == 0:
            start = 0  # leading material is onset of first syllable
        else:
            start = _split_cluster(ipa[prev_end:s], onsets, ipa, s, e)
        if parts:
            parts[-1] += ipa[prev_end:start]  # coda stays with previous syllable
        parts.append(ipa[start:e])
        prev_end = e
    tail = ipa[prev_end:]
    if tail:
        parts[-1] += tail
    return parts


def _split_cluster(cluster: str, onsets: set[str], ipa: str,
                    ns: int, ne: int) -> int:
    """Return the IPA index where the next syllable's onset begins."""
    if not cluster or ns == 0:
        return ns
    # onset is the longest allowed SUFFIX of the cluster
    for length in range(len(cluster), 0, -1):
        if cluster[-length:] in onsets:
            return ns - length
    # nothing matched: give the last real consonant (plus its length mark)
    # to the onset
    k = ns - 1
    while k > ns - len(cluster) and (ipa[k] in COMBINING
                                     or unicodedata.combining(ipa[k])):
        k -= 1
    return k


# ---------------------------------------------------------------- stress
_ACCENTED = set("áéíóúàèìòùâêîôûãẽĩõũ")


def stress_index(word: str, syllables: list[str], lang: str) -> int:
    """Index of the stressed syllable, based on orthographic cues."""
    n = len(syllables)
    if n <= 1:
        return 0
    w = word.lower()
    letters = [c for c in w if c.isalpha()]

    if lang == "fr":
        return n - 1
    if lang == "de":
        return _german_stress(w, letters, n)

    accented = [i for i, c in enumerate(letters) if c in _ACCENTED]
    if lang == "es":
        if accented:
            return min(_vowels_before(letters, accented[0]), n - 1)
        return n - 2 if (not letters or letters[-1] in "aeiouáéíóúns") else n - 1
    if lang == "it":
        if accented and accented[0] == len(letters) - 1:
            return n - 1
        if letters and letters[-1] in "aeiou":
            return n - 2
        return n - 1
    if lang == "pt":
        if accented:
            return min(_vowels_before(letters, accented[0]), n - 1)
        last = letters[-1] if letters else "a"
        if last in "lr":
            return n - 1
        return n - 2  # default paroxítona
    return n - 1


_DE_PREFIXES = (
    "be", "ge", "er", "ver", "zer", "ent", "emp", "miss", "ab", "an", "aus",
    "um", "un", "wi", "ver", "zer", "auf", "um",
)


def _german_stress(word: str, letters: list[str], n: int) -> int:
    if word.startswith(_DE_PREFIXES):
        for i, c in enumerate(letters):
            if is_vowel(c) and i > 0:
                return min(_vowels_before(letters, i), n - 1)
    return 0


def _vowels_before(letters: list[str], pos: int) -> int:
    return sum(1 for c in letters[:pos] if is_vowel(c))


# ---------------------------------------------------------------- respelling
# English-friendly reading of IPA. Shared defaults, overridden per language.
_SHARED = {
    "ʃ": "sh", "ʒ": "zh", "ɲ": "ny", "ʎ": "ly", "ʝ": "y", "ɾ": "r",
    "ʀ": "r", "ʁ": "r", "ʀ": "r", "x": "kh", "ç": "kh", "ɣ": "g",
    "θ": "th", "t͡ʃ": "ch", "d͡ʒ": "j", "tʃ": "ch", "dʒ": "j",
    "ts": "ts", "ŋ": "ng", "ɐ": "uh", "ə": "uh", "ɪ": "i", "ʊ": "oo",
    "æ": "a", "ɛ": "eh", "ɔ": "aw", "œ": "uh", "ø": "uh", "ɑ": "ah",
    "ɐ̃": "ahn", "ɑ̃": "ahn", "ɛ̃": "an", "ɔ̃": "on", "œ̃": "uhn",
    "ã": "ahn", "õ": "ohn", "ẽ": "ehn", "ĩ": "een", "ũ": "oohn",
    "a": "a", "e": "eh", "i": "ee", "o": "oh", "u": "oo", "y": "ew",
    "ɜ": "er", "ɞ": "er", "ɘ": "uh", "ɵ": "oo", "ɤ": "oo", "ɨ": "ih",
    "ɒ": "aw", "ɶ": "aw", "ɯ": "oo", "ː": "", "̃": "n", "̯": "",
    "̈": "", "̥": "", "̩": "", "̪": "", "̻": "", "̰": "",
    "j": "y", "h": "h", "w": "w", "v": "v", "z": "z", "s": "s",
    "m": "m", "n": "n", "l": "l", "r": "r", "b": "b", "d": "d",
    "g": "g", "ɡ": "g", "k": "k", "p": "p", "t": "t", "f": "f",
    "ɥ": "w", "ʁ": "r", "ʀ": "r",
}

_LANG_OVERRIDE: dict[str, dict[str, str]] = {
    "fr": {"ø": "eu", "œ": "eu", "y": "ew", "u": "oo", "ɔ": "aw",
           "ɔ̃": "on", "ɑ̃": "ahn", "ɛ̃": "an", "œ̃": "uhn", "ə": "uh",
           "ʀ": "r", "ʁ": "r"},
    "de": {"ø": "eu", "œ": "eu", "y": "oo", "ʏ": "oo", "aː": "ah",
           "eː": "ay", "iː": "ee", "oː": "oh", "uː": "oo", "ɛː": "eh",
           "ɔ": "aw", "ɐ": "er", "ɐ̯": "er", "ɪ": "i", "aɪ": "eye",
           "aʊ": "ow", "ɔɪ": "oy", "eːɐ̯": "ayr"},
    "es": {"a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo",
           "θ": "th", "x": "kh", "ʝ": "y", "ɾ": "r", "r": "r"},
    "it": {"a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo",
           "t͡ʃ": "ch", "d͡ʒ": "j", "ɲ": "ny", "ʎ": "ly", "ʃ": "sh",
           "ts": "ts", "ɛ": "eh", "ɔ": "aw"},
    "pt": {"a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo",
           "ɐ": "uh", "ɐ̃": "ahn", "õ": "ohn", "ɐ̃w̃": "ahnw",
           "ɛ": "eh", "ɔ": "aw", "ɾ": "r", "ʁ": "r", "ʃ": "sh",
           "ɲ": "ny", "ʎ": "ly", "j": "y", "w": "w"},
}

# longest keys first so multi-char sequences win
_ORDER: dict[str, list[tuple[str, str]]] = {}


def _table(lang: str) -> list[tuple[str, str]]:
    if lang not in _ORDER:
        merged = dict(_SHARED)
        merged.update(_LANG_OVERRIDE.get(lang, {}))
        _ORDER[lang] = sorted(merged.items(), key=lambda kv: -len(kv[0]))
    return _ORDER[lang]


def respell(syllable_ipa: str, lang: str) -> str:
    """Render one IPA syllable as an English-friendly approximation."""
    out: list[str] = []
    i = 0
    text = syllable_ipa
    table = _table(lang)
    while i < len(text):
        for key, repl in table:
            if text.startswith(key, i):
                out.append(repl)
                i += len(key)
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)
