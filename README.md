# Language Translator

A desktop translator for **English ⇄ French, Spanish, German, Italian and
Portuguese** with a killer extra: a **Pronunciation side panel** that shows
how a native speaker would actually say your sentence — IPA transcription,
syllables with the stressed one highlighted, an English-friendly reading
(`bon-zhoor`), liaison notes, and a **native voice you can play back**,
including 0.6× / 0.8× slow motion for learners.

<!-- screenshot placeholder: two text panes + pronunciation dock -->

## Features

- **Translate on demand** — a single **Translate ▶** button is the only way
  to start a translation (no requests are fired while you type, so no rate
  limits are wasted); the button disables and shows `Translating…` while a
  job runs, `Ctrl+Enter`/`Enter` do nothing
- **Dark mode** — the toolbar's moon/sun toggle (drawn in code, not an
  emoji, so it renders on any system) switches the whole app (panes,
  toolbar, pronunciation cards, scrollbars, selection colors) between
  light and dark; the choice is saved and applied before the first
  frame, no flash
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
- **Automatic word correction** (always on — no button to press):
  - restores missing accents/cedillas as you type and again when you
    translate: `tres → très`, `cancion → canción`, `citta → città`,
    `coracao → coração`, `uber → über`
  - fixes simple typos: `bonjur → bonjour`
  - applied to **both panes** (typed text and translation output — the
    engine always receives clean text, and accents it drops are restored),
    every changed word gets an amber underline with the original on hover,
    and the status bar reports `✓ 2 accent(s)`
  - ambiguity-safe: real unaccented words (`ou`, `la`, `a`, `cuando`, `si`)
    are never "corrected" — a change only happens when the accented spelling
    is far more frequent; the word you are currently typing is never touched
- **Adjustable UI size** — fonts, controls and spacing scale together:
  - **`A−` / `A+` toolbar buttons** step the size (85% → 100% → 115% →
    130% → 150%) and apply instantly, no restart
  - the choice is remembered **per screen**, so a monitor and a laptop
    each keep their own size when you drag the window between them
  - auto-detection still sets a sensible start: OS display scaling
    (125%/150%) is honoured, screens ≤ 1366×768 get the medium tier
    (120%); the window never opens larger than the display;
    `LT_UI_SCALE=1.5` overrides everything for testing
- Find-in-text box, persisted window layout & language pair

## Installation

All you need is **Python 3.10 or newer** — any current version works,
**3.12 recommended** ([python.org](https://www.python.org/downloads/)).
Yes, even 3.13/3.14: the project bundles a small pure-Python stand-in for
the one dependency (`editdistance`) whose C wheels stop at Python 3.12, so
nothing has to be compiled on your machine. Git is optional (you can
download a ZIP instead). Internet is only needed for the first download
and for online translation.

### 1. Get the code

On GitHub, click the green **Code** button → **Download ZIP**, then
extract the ZIP anywhere (e.g. your Desktop). Or with git:

```bash
git clone https://github.com/Kendra0004/language-translator.git
```

### 2. Open a terminal in the project folder

- **Windows:** open the folder in Explorer, click the address bar,
  type `cmd` and press Enter
- **macOS:** press `Cmd+Space`, type `Terminal`, then `cd ` and drag
  the folder into the window
- **Linux:** right-click inside the folder → *Open in Terminal*

### 3. Install the dependencies

**Windows (PowerShell or Command Prompt):**

```bat
py -3 -m venv .venv
.\.venv\Scripts\pip install vendor\wheels\editdistance-0.8.1-py3-none-any.whl
.\.venv\Scripts\pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

(The `venv` step creates an isolated environment so the app's pinned
library versions can't break anything else on your machine. The bundled
`editdistance` wheel goes in **before** the requirements on purpose: it
satisfies panphon's one compile-only dependency, so Python 3.13/3.14 never
tries to build C code. The build scripts do both steps for you.)

### 4. Run the app

**Windows:**

```bat
.\.venv\Scripts\python -m app.main
```

**macOS / Linux:**

```bash
.venv/bin/python -m app.main
```

The window opens immediately — type text, pick the languages, click
**Translate ▶**.

### Optional: offline translation

**Windows:**

```bat
.\.venv\Scripts\pip install -r requirements-offline.txt
```

**macOS / Linux:**

```bash
.venv/bin/pip install -r requirements-offline.txt
```

This adds the Argostranslate engine (~1 GB). The translation model for
your language pair downloads automatically the first time the offline
engine is used.

### Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Re-run the Python installer and tick **Add python.exe to PATH**, or use `py -3` instead of `python` |
| `pip` install fails with SSL/certificate errors | Check your system clock (Settings → Time), or a corporate proxy is blocking PyPI |
| `Failed building wheel for editdistance` | You're building from **old files** — re-download the ZIP (or `git pull`); the updated scripts install the bundled pure-Python stand-in first. Doing it manually: `pip install vendor\wheels\editdistance-0.8.1-py3-none-any.whl` **before** `-r requirements.txt` |
| `Pronunciation unavailable: 'charmap' codec can't decode byte ...` | Old build on Windows: the pronunciation engine read its UTF-8 data files with the system codepage. Re-download the ZIP (or `git pull`) and rebuild — the app now forces UTF-8 for those reads |
| `running scripts is disabled on this system` (build.ps1) | Run `powershell -ExecutionPolicy Bypass -File .\build.ps1` |
| Translation says `429 Too Many Requests` | Google rate-limited the free endpoint — wait a minute and retry, or install offline mode above |
| Play button is silent | Install ffmpeg: `winget install ffmpeg` (Windows), `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux/WSL). **WSL:** if sound stopped everywhere, run `wsl --shutdown` in Windows PowerShell and reopen — the WSLg audio bridge goes stale. The panel now shows the exact playback error under the buttons instead of staying quiet |
| Windows SmartScreen says "Windows protected your PC" on a built `.exe` | Click **More info** → **Run anyway** (the binary isn't code-signed) |

Tests: `.venv/bin/python -m pytest tests -q`  
(Windows: `.\.venv\Scripts\python -m pytest tests -q`)

## Building

Use **one script per OS** — `build.sh` is bash-only (Linux/macOS/WSL),
`build.ps1` is the Windows one. Each runs: venv → dependencies → tests →
PyInstaller → a **smoke test** that starts the packaged binary and checks
the pronunciation panel works before declaring success.

### Windows (PowerShell)

```powershell
.\build.ps1              # -> dist\LanguageTranslator\LanguageTranslator.exe
.\build.ps1 -OneFile     # single-file variant (slower to start)
.\build.ps1 -Offline     # also bundle the offline engine (~1 GB extra)
```

Requires **Python 3.10 or newer** (3.12 recommended — see Installation).
If PowerShell refuses to run scripts, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

### Linux / macOS (bash)

```bash
./build.sh               # -> dist/LanguageTranslator/LanguageTranslator
./build.sh --onefile     # single-file variant
./build.sh --offline     # also bundle the offline engine (~1 GB extra)
```

Both scripts are otherwise self-contained — nothing else to do.
Internet is only needed the **first** time (to download the dependencies):
once `.venv-build` exists, the whole build — tests, packaging and the smoke
test — runs with no network at all.

### Why offline is a build flag
The offline engine (Argostranslate) depends on stanza/torch/spacy, which adds
roughly a GB to the executable. The app works fully without it (the two online
engines), and the offline engine is included automatically when the library
is present — so the default build stays lean.

## Project layout

```
app/
  main.py                  entry point (scale detection, screen fitting)
  theme.py                 scale-aware light/dark stylesheets + palettes, moon/sun icon
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
run.py                     PyInstaller entry point (imports app.main as a package)
translator.spec            PyInstaller configuration (Windows + Linux)
build.ps1                  one-command Windows build
build.sh                   one-command Linux build
vendor/                    bundled pure-Python editdistance stand-in + wheel
                           (keeps Python 3.13/3.14 builds compiler-free)
```

## Notes

- Pronunciation is rule-based on top of [epitran](https://github.com/appien/epitran)
  tables, so it is fast, offline and works the moment you type.
- Translation and audio need internet; everything else works offline.
