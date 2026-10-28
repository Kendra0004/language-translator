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

echo "[1/5] Creating virtual environment..."
[ -d .venv-build ] || "$PYTHON" -m venv .venv-build
PIP=.venv-build/bin/pip
PYI=.venv-build/bin/pyinstaller

echo "[2/5] Installing dependencies (PySide6 is ~200 MB, first run only)..."
# Self-upgrade is best-effort: it needs the package index, but once
# .venv-build exists the build must also succeed with no network at all
# (everything else below is already satisfied locally).
"$PIP" install --upgrade pip --retries 1 --timeout 5 2>/dev/null \
    || echo "  (pip self-upgrade skipped - no network?)"
# Bundled pure-Python editdistance stand-in FIRST: panphon requires the
# package, the real C extension has no wheels past Python 3.12 (so pip
# would compile it and die), and nothing in the app ever calls it.
# --force-reinstall makes every environment end up on the stand-in even if
# a real editdistance of the same version slipped in earlier.
"$PIP" install --force-reinstall vendor/wheels/editdistance-0.8.1-py3-none-any.whl
if [ "$OFFLINE" -eq 1 ]; then
    "$PIP" install -r requirements-offline.txt pyinstaller
else
    "$PIP" install -r requirements.txt pyinstaller
fi

echo "[3/5] Running tests..."
"$PIP" install pytest >/dev/null
QT_QPA_PLATFORM=offscreen .venv-build/bin/python -m pytest tests -q

echo "[4/5] Building the binary..."
# NOTE: PyInstaller rejects --onefile/--onedir whenever a .spec file is
# given, so the spec reads LT_ONEFILE from the environment instead.
rm -rf dist
if [ "$ONEDIR" -eq 1 ]; then
    "$PYI" translator.spec --noconfirm
    BIN=dist/LanguageTranslator/LanguageTranslator
else
    LT_ONEFILE=1 "$PYI" translator.spec --noconfirm
    BIN=dist/LanguageTranslator
fi

if [ ! -x "$BIN" ]; then
    echo "Build finished but no binary found - check the log above." >&2
    exit 1
fi
echo
echo "BUILD OK -> $BIN"

echo "[5/5] Smoke-testing the binary (startup + pronunciation panel)..."
SMOKE_OUT="$(LT_SMOKE=1 QT_QPA_PLATFORM=offscreen timeout 180 "$BIN" 2>&1 || true)"
if echo "$SMOKE_OUT" | grep -q "SMOKE OK"; then
    echo "$SMOKE_OUT" | grep "SMOKE OK"
    echo "SMOKE OK"
else
    echo "Smoke test FAILED - binary output:" >&2
    echo "$SMOKE_OUT" | tail -30 >&2
    exit 1
fi
