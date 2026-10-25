"""Translation with a fallback chain: Google public endpoint -> MyMemory
-> Argostranslate offline models (downloaded on demand)."""
from __future__ import annotations

import json
import logging
import re
import threading
import urllib.parse
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 12
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0 Safari/537.36"}


class TranslationError(Exception):
    pass


@dataclass
class TranslationResult:
    text: str
    engine: str  # "google" | "mymemory" | "offline"


# ------------------------------------------------------------------ Google
def _google(text: str, src: str, tgt: str) -> str:
    params = {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text}
    url = "https://translate.googleapis.com/translate_a/single?" + \
        urllib.parse.urlencode(params)
    resp = requests.get(url, headers=_UA, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return "".join(chunk[0] for chunk in data[0] if chunk and chunk[0])


# --------------------------------------------------------------- MyMemory
def _mymemory(text: str, src: str, tgt: str) -> str:
    url = "https://api.mymemory.translated.net/get"
    resp = requests.get(
        url,
        params={"q": text[:480], "langpair": f"{src}|{tgt}"},
        headers=_UA,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    translated = data.get("responseData", {}).get("translatedText")
    if not translated or "MYMEMORY WARNING" in str(translated).upper():
        raise TranslationError("mymemory returned nothing useful")
    # strip MyMemory attribution / watermark noise
    translated = re.sub(r"\s*Provided by:.*$", "", str(translated),
                        flags=re.IGNORECASE | re.DOTALL)
    translated = re.sub(r"\s*x{5,}\s*$", "", translated).strip()
    if not translated:
        raise TranslationError("mymemory returned nothing useful")
    return translated


# ------------------------------------------------------- Argostranslate
_argos_lock = threading.Lock()
_argos_ready: set[tuple[str, str]] = set()
_argos_progress: dict[str, str] = {}


def offline_status(src: str, tgt: str) -> str | None:
    """Progress message while a model downloads, else None."""
    return _argos_progress.get(f"{src}-{tgt}")


def offline_available(src: str, tgt: str) -> bool:
    try:
        import argostranslate.translate as at
        return at.get_translation_from_codes(src, tgt) is not None
    except Exception:
        return False


def _ensure_offline(src: str, tgt: str) -> None:
    """Download the offline model once (idempotent)."""
    key = (src, tgt)
    if key in _argos_ready:
        return
    with _argos_lock:
        if key in _argos_ready:
            return
        label = f"{src}-{tgt}"
        try:
            import argostranslate.package as apkg
            import argostranslate.translate as at
            if at.get_translation_from_codes(src, tgt) is None:
                _argos_progress[label] = "checking offline models…"
                apkg.update_package_index()
                candidates = [
                    p for p in apkg.get_available_packages()
                    if p.from_code == src and p.to_code == tgt
                ]
                if not candidates:
                    raise TranslationError(
                        f"no offline model for {src}->{tgt}")
                pkg = candidates[-1]
                path = pkg.download()
                _argos_progress[label] = "installing offline model…"
                apkg.install_from_path(path)
            _argos_ready.add(key)
        finally:
            _argos_progress.pop(label, None)


def _offline(text: str, src: str, tgt: str) -> str:
    _ensure_offline(src, tgt)
    import argostranslate.translate as at
    return at.translate(text, src, tgt)


def _looks_like_echo(src_text: str, out: str) -> bool:
    """An engine that returns the input unchanged has not translated."""
    strip = lambda s: "".join(c for c in s.lower() if c.isalnum())  # noqa: E731
    return bool(out.strip()) and strip(src_text) == strip(out)


# ------------------------------------------------------------------ API
def translate(text: str, src: str, tgt: str,
              allow_offline: bool = True) -> TranslationResult:
    """Translate, trying engines in order. Raises TranslationError."""
    if not text.strip():
        return TranslationResult("", "none")
    if src == tgt:
        return TranslationResult(text, "identity")

    errors: list[str] = []
    for name, fn in (("google", _google), ("mymemory", _mymemory)):
        try:
            out = fn(text, src, tgt)
            if _looks_like_echo(text, out):
                raise TranslationError("engine echoed the input")
            return TranslationResult(out, name)
        except Exception as exc:  # noqa: BLE001 - chain must keep going
            errors.append(f"{name}: {exc}")
            log.warning("engine %s failed: %s", name, exc)
    if allow_offline:
        try:
            return TranslationResult(_offline(text, src, tgt), "offline")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"offline: {exc}")
            log.warning("offline engine failed: %s", exc)
    raise TranslationError("; ".join(errors) or "no engine available")
