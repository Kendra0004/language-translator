"""Text-to-speech: Google Translate voice (natural native speakers) with
mp3 caching; graceful fallbacks when offline."""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import urllib.parse

import requests

log = logging.getLogger(__name__)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0 Safari/537.36"}
MAX_CHARS = 190  # endpoint limit is ~200 per request


def _cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") \
        or os.path.join(tempfile.gettempdir(), "language-translator")
    path = os.path.join(base, "tts-cache")
    os.makedirs(path, exist_ok=True)
    return path


def fetch(text: str, lang: str) -> str | None:
    """Return a local mp3 path for `text` in `lang`, or None on failure.

    Playback speed is handled client-side (QMediaPlayer.playbackRate),
    so one cached file serves every speed.
    """
    text = text.strip()[:MAX_CHARS]
    if not text:
        return None
    name = hashlib.sha1(f"{lang}|{text}".encode("utf-8")).hexdigest() + ".mp3"
    path = os.path.join(_cache_dir(), name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    params = {"ie": "UTF-8", "client": "tw-ob", "tl": lang, "q": text}
    url = "https://translate.google.com/translate_tts?" + \
        urllib.parse.urlencode(params)
    try:
        resp = requests.get(url, headers=_UA, timeout=15)
        resp.raise_for_status()
        if not resp.content or b"<html" in resp.content[:200].lower():
            return None
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(resp.content)
        os.replace(tmp, path)
        return path
    except Exception as exc:  # noqa: BLE001
        log.warning("tts fetch failed: %s", exc)
        return None
