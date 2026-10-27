#!/usr/bin/env bash
#
# One-command Linux build: produces dist/LanguageTranslator/LanguageTranslator
#
# Options:
#   --onefile   Single executable instead of a folder (slower to start:
#               it unpacks to /tmp on every launch).
#   --offline   Bundle the offline translation engine (argostranslate +
#               torch: ~1 GB extra). Without it the app still falls back
#               offline later if you pip-install requirements-offline.txt.
#   -h, --help  This text.
#
# Example: ./build.sh            ./build.sh --onefile --offline
#
set -euo pipefail
cd "$(dirname "$0")"

ONEDIR=1
OFFLINE=0
for arg in "$@"; do
    case "$arg" in
        --onefile) ONEDIR=0 ;;
        --offline) OFFLINE=1 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || {
    echo "Python 3.10+ not found. Install python3 and re-run." >&2
    exit 1
}

echo "[1/4] Creating virtual environment..."
[ -d .venv-build ] || "$PYTHON" -m venv .venv-build
PIP=.venv-build/bin/pip
PYI=.venv-build/bin/pyinstaller

echo "[2/4] Installing dependencies (PySide6 is ~200 MB, first run only)..."
"$PIP" install --upgrade pip
if [ "$OFFLINE" -eq 1 ]; then
    "$PIP" install -r requirements-offline.txt pyinstaller
else
    "$PIP" install -r requirements.txt pyinstaller
fi

echo "[3/4] Running tests..."
"$PIP" install pytest >/dev/null
QT_QPA_PLATFORM=offscreen .venv-build/bin/python -m pytest tests -q

echo "[4/4] Building the binary..."
if [ "$ONEDIR" -eq 1 ]; then
    "$PYI" translator.spec --noconfirm
else
    "$PYI" translator.spec --noconfirm --onefile
fi

BIN=dist/LanguageTranslator/LanguageTranslator
if [ -x "$BIN" ]; then
    echo
    echo "BUILD OK -> $BIN"
    [ "$ONEDIR" -eq 0 ] && echo "(onefile variant: dist/LanguageTranslator)"
else
    echo "Build finished but no binary found - check the log above." >&2
    exit 1
fi
