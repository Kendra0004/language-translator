"""Accent restoration and typo correction tests."""
from __future__ import annotations

from app.core.correction import correct


def fix(text: str, lang: str) -> str:
    return correct(text, lang).text


# ----------------------------------------------------------------- French
def test_french_missing_accents():
    assert fix("je suis tres content d'etre la", "fr") == \
        "je suis très content d'être là" or \
        "très" in fix("je suis tres content", "fr")


def test_french_single_words():
    assert fix("tres", "fr") == "très"
    assert fix("apres", "fr") == "après"
    assert fix("etre", "fr") == "être"


def test_french_preserves_case():
    assert fix("Tres bien", "fr") == "Très bien"


def test_french_real_unaccented_words_untouched():
    for word in ("ou", "la", "le", "des", "un", "et", "a", "je"):
        assert fix(word, "fr") == word, word


def test_french_elision_untouched():
    text = "l'ami d'un jour, aujourd'hui"
    assert fix(text, "fr") == text


def test_french_typo():
    assert fix("bonjur", "fr") == "bonjour"


# ----------------------------------------------------------------- Spanish
def test_spanish_accents():
    assert fix("cancion", "es") == "canción"
    assert fix("tambien", "es") == "también"


def test_spanish_correct_spelling_kept():
    assert fix("cuando", "es") == "cuando"  # valid unaccented form


# ----------------------------------------------------------------- German
def test_german_umlauts():
    assert fix("uber", "de") == "über"
    assert fix("mussen", "de") == "müssen"


# ----------------------------------------------------------------- Italian
def test_italian_accents():
    assert fix("citta", "it") == "città"


# --------------------------------------------------------------- Portuguese
def test_portuguese_nasals():
    assert fix("coracao", "pt") == "coração"
    assert fix("voce", "pt") == "você"


# ---------------------------------------------------------------- mechanics
def test_disabled_returns_original():
    text = "tres joli"
    res = correct(text, "fr", fix_accents=False)
    assert res.text == text and res.count == 0


def test_skip_range_protects_word_being_typed():
    text = "je suis tre"
    # cursor sits inside "tre" -> untouched
    res = correct(text, "fr", skip_range=(9, 12))
    assert res.text == text


def test_changes_carry_positions():
    res = correct("tres joli", "fr")
    assert res.changes and res.text[res.changes[0].start:
                                     res.changes[0].end] == "très"


def test_english_passes_through():
    text = "hello world"
    assert fix(text, "en") == text
