"""UTF-8 default-encoding fix (app/compat.py + app/__init__.py hook).

Windows reads encoding-less files with the ANSI codepage (cp1252), which
crashed the pronunciation engine's UTF-8 IPA tables with
'charmap' codec can't decode byte 0x90 in position 970. The fix wraps
io.open/builtins.open; these tests prove it works in an ANSI-like
locale and that it stays out of the way everywhere else.
"""
from __future__ import annotations

import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 970 ASCII chars + an emoji: UTF-8 bytes F0 9F 98 80. Byte-for-byte this
# reproduces the failure class behind the real error message (undefined
# byte at position ~970): 'ascii' dies on 0xF0 at 970, cp1252 on 0x9F at
# 971. Built via chr() inside the child script because argv/source must
# stay ASCII in an ANSI locale.
_PAYLOAD = "A" * 970 + chr(0x1F600)

# Child script: pure ASCII only (it runs under an ANSI locale).
_CHILD = r'''
import sys
path = sys.argv[1]
marker = chr(0x1F600)

# 1) Prove the environment simulates Windows' ANSI default encoding.
try:
    open(path).read()
    print("SKIP: default encoding is already UTF-8 here")
    sys.exit(0)
except UnicodeDecodeError:
    pass

# 2) Importing the app package must install the fix...
import app  # noqa: F401

# 3) ...after which every encoding-less text open works,
data = open(path).read()
assert marker in data, "builtin open() still broken"
from pathlib import Path
assert marker in Path(path).open().read(), "Path.open() still broken"
assert marker in Path(path).read_text(), "Path.read_text() still broken"

# 4) explicit-encoding text opens are untouched,
assert open(path, encoding="utf-8").read() == data
# 5) and binary mode is untouched.
assert open(path, "rb").read().startswith(b"A")
assert Path(path).read_bytes().startswith(b"A")
print("PROBE OK")
'''


def test_utf8_defaults_survive_ansi_locale(tmp_path):
    """The definitive regression: under an ANSI-like locale (Windows'
    mechanism) raw open() fails on UTF-8 data, but after `import app`
    builtin open, Path.open and Path.read_text all succeed, while
    binary and explicit-encoding opens stay untouched. Skips itself on
    platforms whose default encoding is already UTF-8 (nothing to fix).
    """
    payload = tmp_path / "ipa_all.csv"
    payload.write_text(_PAYLOAD, encoding="utf-8")

    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LC_CTYPE": "C", "LANG": "C",
                "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"})
    env["PYTHONPATH"] = _ROOT + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [sys.executable, "-c", _CHILD, str(payload)],
        cwd=_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout} stderr={proc.stderr}"
    assert "PROBE OK" in proc.stdout or "SKIP" in proc.stdout, proc.stdout


def test_compat_wrapper_installed_once_and_passes_through(tmp_path):
    """The app package must install the io.open/builtins.open wrapper on
    import, exactly once, without changing binary or explicit-encoding
    behaviour - including the positional-encoding call pathlib makes."""
    import builtins
    import io

    import app.compat as compat

    compat.install_utf8_defaults()
    compat.install_utf8_defaults()  # idempotent

    assert io.open is builtins.open, "both names must point at the wrapper"
    assert getattr(io.open, "_lt_utf8_defaults", False), "wrapper missing"
    assert io.text_encoding(None) == "utf-8", \
        "pathlib pre-resolves through io.text_encoding - must agree"
    assert io.text_encoding("latin-1") == "latin-1", \
        "explicit encodings must pass through text_encoding too"
    from pathlib import Path as _P
    assert _P.open is compat._utf8_path_open, \
        "Path.open must be wrapped (C pathlib bypasses io.open)"
    assert _P.read_text is compat._utf8_path_read_text, \
        "Path.read_text must be wrapped (C pathlib bypasses io.open)"

    bin_file = tmp_path / "raw.bin"
    bin_file.write_bytes(b"\x90\xff\x00abc")
    assert open(bin_file, "rb").read() == b"\x90\xff\x00abc"

    latin = tmp_path / "latin.txt"
    latin.write_bytes("café".encode("latin-1"))
    assert open(latin, encoding="latin-1").read() == "café"

    utf8 = tmp_path / "utf8.txt"
    utf8.write_text(_PAYLOAD, encoding="utf-8")
    assert open(utf8).read() == _PAYLOAD          # default now utf-8
    # pathlib-style positional call: io.open(self, mode, buffering, encoding)
    assert open(utf8, "r", -1, None).read() == _PAYLOAD
    from pathlib import Path
    assert Path(utf8).open().read() == _PAYLOAD   # positional-encoding caller
    assert Path(utf8).read_text() == _PAYLOAD
