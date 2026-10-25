"""Language engine tests: IPA, syllables, stress, reading, liaisons."""
from __future__ import annotations

from app.core.pronunciation import analyze, word_ipa


def _read(text: str, lang: str) -> str:
    return analyze(text, lang).respelling


def _syllables(word: str, lang: str) -> list[str]:
    a = analyze(word, lang)
    return a.words[0].syllables


# ------------------------------------------------------------------ French
def test_bonjour_reading_matches_target():
    assert _read("bonjour", "fr") == "bon-zhoor"


def test_bonjour_syllables_and_stress():
    a = analyze("bonjour", "fr")
    w = a.words[0]
    assert len(w.syllables) == 2
    assert w.stress == 1  # French stresses the final syllable


def test_final_schwa_dropped_but_function_word_kept():
    assert word_ipa("grande", "fr").endswith("d")
    assert word_ipa("de", "fr") == "də"


def test_verb_ent_is_silent_but_noun_ent_is_not():
    assert not word_ipa("parlent", "fr").endswith("ɑ̃")
    assert word_ipa("lentement", "fr").endswith("ɑ̃")


def test_final_s_voiced_before_silent_e():
    assert word_ipa("rose", "fr").endswith("z")
    assert word_ipa("fraises", "fr").endswith("z")


def test_plural_final_s_stays_silent():
    assert not word_ipa("les", "fr").endswith("s")


def test_liaison_marks_z_between_les_and_amis():
    a = analyze("les amis", "fr")
    assert a.words[0].liaison == "z"
    assert a.words[0].ipa.endswith("z")


def test_syllable_line_uppercases_stress():
    assert "ZHOOR" in analyze("bonjour", "fr").syllable_line


# ------------------------------------------------------------------ Spanish
def test_spanish_stress_penult_when_final_vowel():
    a = analyze("bonita", "es")
    assert a.words[0].stress == 1  # bo-NI-ta


def test_spanish_stress_final_after_consonant():
    a = analyze("ciudad", "es")
    assert a.words[0].stress == len(a.words[0].syllables) - 1


# ------------------------------------------------------------------ German
def test_german_stress_first_syllable():
    assert analyze("Wasser", "de").words[0].stress == 0


def test_german_umlaut_readable():
    assert "SHEUN" in _read("schön", "de").upper()


# ------------------------------------------------------------------ Italian
def test_italian_stress_penult_ending_in_vowel():
    a = analyze("tavola", "it")
    assert a.words[0].stress == len(a.words[0].syllables) - 2


def test_italian_stress_final_when_accented():
    a = analyze("città", "it")
    assert a.words[0].stress == len(a.words[0].syllables) - 1


# --------------------------------------------------------------- Portuguese
def test_portuguese_paroxitona():
    a = analyze("cidade", "pt")
    assert a.words[0].stress == len(a.words[0].syllables) - 2


# ------------------------------------------------------------------- engine
def test_identity_translation_needs_no_network():
    from app.core.translator import translate
    r = translate("hello", "en", "en")
    assert r.text == "hello" and r.engine == "identity"


def test_google_json_parser(monkeypatch):
    from app.core import translator

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [[["Bonjour. ", "Hello. ", None, None, 3]],
                    [None, None]]

    monkeypatch.setattr(translator.requests, "get",
                        lambda *a, **k: FakeResp())
    r = translator._google("Hello.", "en", "fr")
    assert r == "Bonjour. "
