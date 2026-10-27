# Language Translator

A desktop translator for **English ⇄ French, Spanish, German, Italian and
Portuguese** with a killer extra: a **Pronunciation side panel** that shows
how a native speaker would actually say your sentence — IPA transcription,
syllables with the stressed one highlighted, an English-friendly reading
(`bon-zhoor`), liaison notes, and a **native voice you can play back**,
including 0.6× / 0.8× slow motion for learners.

![layout: two text panes + pronunciation dock]

## Features

- **Translate on demand** — a single **Translate ▶** button is the only way
  to start a translation (no requests are fired while you type, so no rate
  limits are wasted); the button disables and shows `Translating…` while a
  job runs, `Ctrl+Enter`/`Enter` do nothing
- **Dark mode** — 🌙 toolbar toggle switches the whole app (panes, toolbar,
  pronunciation cards, scrollbars, selection colors) between light and dark;
  the choice is saved and applied before the first frame, no flash
- **Manual language pickers** + one-click swap (swaps the texts too)
- **Pronunciation panel** (right dock) for every non-English language:
  - big readable approximation: `bon-ZHOOR a too kaw-mahnt …`
  - IPA line: `/bɔ̃.ʒuʀ a tu kɔ.mɑ̃t …/`
  - syllable breakdown with stress shouted out: `bon • ZHOOR`
  - word-by-word cards with per-word play buttons
  - French **liaison** notes (`les amis` → the `s` links as `/z/`)
  - native-voice playback with speed control (Google TTS, cached to disk)
- **Three translation engines**, chosen automatically:
  1. Google's public endpoint
  2. MyMemory
  3. *optional* Argostranslate offline model (auto-downloaded, cached)
- **Auto word correction** (`Fix accents ✔` toggle, on by default):
  - restores missing accents/cedillas: `tres → très`, `cancion → canción`,
    `citta → città`, `coracao → coração`, `uber → über`
  - fixes simple typos: `bonjur → bonjour`
  - applied to **both panes** (typed text and translation output), every
    changed word gets an amber underline with the original on hover, and the
    status bar reports `✓ 2 accent(s)`
  - ambiguity-safe: real unaccented words (`ou`, `la`, `a`, `cuando`, `si`)
    are never "corrected" — a change only happens when the accented spelling
    is far more frequent; the word you are currently typing is never touched
- Find-in-text box, persisted window layout & language pair

## Running from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.main          # add requirements-offline.txt for offline mode
```

Tests: `.venv/bin/python -m pytest tests -q`

## Building the Windows .exe

On Windows (PowerShell) inside this folder:

```powershell
.\build.ps1              # -> dist\LanguageTranslator\LanguageTranslator.exe
.\build.ps1 -OneFile     # single-file variant (slower to start)
.\build.ps1 -Offline     # also bundle the offline engine (~1 GB extra)
```

`build.ps1` creates the venv, installs pinned dependencies, runs the tests
and invokes PyInstaller — nothing else to do.

### Why offline is a build flag
The offline engine (Argostranslate) depends on stanza/torch/spacy, which adds
roughly a GB to the executable. The app works fully without it (three online
engines), and the offline engine is included automatically when the library
is present — so the default build stays lean.

## Project layout

```
app/
  main.py                  entry point (applies persisted theme)
  theme.py                 light/dark stylesheets + palettes
  ui/main_window.py        panes, language pickers, threading, status bar
  ui/pronunciation_panel.py the dock: reading, IPA, cards, audio
  core/languages.py        language registry (add a language in one place)
  core/translator.py       engine fallback chain
  core/correction.py       accent restoration + typo fixing
  core/pronunciation.py    word -> IPA, syllables, stress, liaisons
  core/phonetics.py        syllabification, stress rules, respelling tables
  core/tts.py              native-voice mp3 fetch + cache
  core/settings.py         persisted preferences
tests/                     pytest coverage of the language engine
translator.spec            PyInstaller configuration
build.ps1                  one-command Windows build
```

## Notes

- Pronunciation is rule-based on top of [epitran](https://github.com/appien/epitran)
  tables, so it is fast, offline and works the moment you type.
- Translation and audio need internet; everything else works offline.
- Pushed to <https://github.com/Kendra0004/language-translator>.
