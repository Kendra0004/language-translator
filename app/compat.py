"""Force UTF-8 as the default text-file encoding (Windows ANSI fix).

Why this exists
---------------
On Windows, ``open(path)`` without an encoding uses the ANSI codepage
(cp1252 on Western systems) instead of UTF-8. Several pronunciation-engine
data files are UTF-8 with multi-byte IPA characters, so reading them
crashed with exactly:

    'charmap' codec can't decode byte 0x90 in position 970

(the first failure is ``panphon/data/ipa_all.csv``; ``ipa_bases.csv``,
``ipa-xsampa.csv``, ``diacritic_definitions.yml`` and jamo's JSON files
are affected too - they all go through encoding-less ``open()`` /
``Path.open()`` inside third-party code we don't control).

Patching ``locale.getpreferredencoding`` does NOT help: CPython resolves
the default encoding at C level (verified - the probe still failed).
There are therefore three escape hatches to close, all verified under a
simulated ANSI locale (LC_ALL=C, coercion and UTF-8 mode disabled):

1. ``builtins.open`` / ``io.open`` - the main entry points.
2. ``io.text_encoding(None)`` - Python 3.13's pathlib calls this BEFORE
   ``io.open``, which would otherwise hand our wrapper a pre-resolved
   'ascii'/'cp1252' string instead of None.
3. ``pathlib.Path.open`` / ``Path.read_text`` - wrapped directly too, so
   C-accelerated pathlib builds (Python 3.14+, which may call the C-level
   open without going through the patched ``io.open`` attribute) stay
   covered.

Binary mode and explicit encodings are untouched everywhere.

Installed automatically by ``app/__init__.py`` - the one choke point
that runs before any app or third-party module reads data files, in
source runs, frozen builds, and tests alike.
"""
from __future__ import annotations

import builtins
import io
import pathlib

__all__ = ["install_utf8_defaults"]

# Captured before any patching, so the wrappers always call the real thing.
_ORIGINAL_IO_OPEN = io.open
_ORIGINAL_PATH_OPEN = pathlib.Path.open
_ORIGINAL_PATH_READ_TEXT = pathlib.Path.read_text

# Marks the wrapper set so installing stays idempotent even if this module
# is loaded twice (source vs frozen, re-exec, etc.).
_MARKER = "_lt_utf8_defaults"


def _utf8_open(file, mode="r", buffering=-1, encoding=None, errors=None,
               newline=None, closefd=True, opener=None):
    """io.open with encoding='utf-8' injected for encoding-less text opens.

    Full positional signature on purpose: pathlib passes ``encoding``
    *positionally* (``io.open(self, mode, buffering, encoding, ...)``),
    so a ``*args``-style wrapper would collide on that argument.
    """
    if encoding is None and isinstance(mode, str) and "b" not in mode:
        encoding = "utf-8"
    return _ORIGINAL_IO_OPEN(file, mode, buffering, encoding, errors,
                             newline, closefd, opener)


setattr(_utf8_open, _MARKER, True)


def _utf8_text_encoding(encoding=None):
    """io.text_encoding with UTF-8 as the resolved default.

    The real one returns locale.getencoding() for None (the ANSI codepage
    on Windows); Python's own pathlib pre-resolves through it, so it must
    agree with what our open() would use.
    """
    if encoding is None:
        return "utf-8"
    return encoding


def _utf8_path_open(self, mode="r", buffering=-1, encoding=None,
                    errors=None, newline=None):
    """Path.open with UTF-8 injected (belt and braces for C pathlib)."""
    if encoding is None and isinstance(mode, str) and "b" not in mode:
        encoding = "utf-8"
    return _ORIGINAL_PATH_OPEN(self, mode, buffering, encoding, errors,
                               newline)


def _utf8_path_read_text(self, encoding=None, errors=None):
    """Path.read_text with UTF-8 injected (belt and braces for C pathlib)."""
    if encoding is None:
        encoding = "utf-8"
    return _ORIGINAL_PATH_READ_TEXT(self, encoding, errors)


def install_utf8_defaults() -> None:
    """Patch every stdlib path that resolves a default text encoding.

    Idempotent: a second call (or a second copy of this module) is a no-op.
    """
    if getattr(io.open, _MARKER, False):
        return
    io.open = _utf8_open
    builtins.open = _utf8_open
    io.text_encoding = _utf8_text_encoding
    pathlib.Path.open = _utf8_path_open
    pathlib.Path.read_text = _utf8_path_read_text
