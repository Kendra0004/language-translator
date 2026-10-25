"""Regression tests for the TTS worker signal and fetch plumbing.

The Play button was dead because `ready` was declared with a float third
parameter while a str path was emitted - PySide6 silently dropped the
emission. These tests pin the contract.
"""
from __future__ import annotations

from app.ui.pronunciation_panel import _TTSWorker


def test_ready_signal_carries_three_strings():
    worker = _TTSWorker()
    received: list[tuple[str, str, str]] = []
    worker.ready.connect(lambda t, l, p: received.append((t, l, p)))

    # emit from the same thread -> direct delivery, no event loop needed
    worker.ready.emit("bonjour", "fr", "/tmp/x.mp3")

    assert received == [("bonjour", "fr", "/tmp/x.mp3")]


def test_ready_signal_accepts_empty_path_for_failures():
    worker = _TTSWorker()
    received: list[str] = []
    worker.ready.connect(lambda t, l, p: received.append(p))

    worker.ready.emit("mot", "fr", "")

    assert received == [""]


def test_cache_dir_is_created_and_writable(tmp_path, monkeypatch):
    from app.core import tts
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    path = tts._cache_dir()
    assert path.endswith("tts-cache")
    assert (tmp_path / "tts-cache").is_dir()


def test_fetch_uses_cache_file_when_present(tmp_path, monkeypatch):
    """A cached mp3 must be returned without any network access."""
    import hashlib
    from app.core import tts
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    text, lang = "bonjour", "fr"
    name = hashlib.sha1(f"{lang}|{text}".encode()).hexdigest() + ".mp3"
    cache = tmp_path / "tts-cache"
    cache.mkdir()
    (cache / name).write_bytes(b"\xff\xf3fake-mp3-bytes")

    def boom(*a, **k):  # no network allowed in this test
        raise AssertionError("network call made despite cache hit")

    monkeypatch.setattr(tts.requests, "get", boom)
    assert tts.fetch(text, lang) == str(cache / name)
