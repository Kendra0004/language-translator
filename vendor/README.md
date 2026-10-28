# vendor/

Vendored, dependency-free pieces the app needs but that can't come from
PyPI on every supported Python.

## `editdistance/` + `wheels/`

A pure-Python, API-compatible stand-in for the [`editdistance`](https://pypi.org/project/editdistance/)
C extension, plus its pre-built wheel (`wheels/editdistance-0.8.1-py3-none-any.whl`).

**Why:** the real package's final release (0.8.1, Feb 2024) has wheels only
up to Python 3.12 — on 3.13/3.14 Windows pip tries to compile C and dies
without the MSVC Build Tools. Only `panphon/distance.py` imports it, and
Language Translator never runs that module; it's installed purely to
satisfy panphon's declared requirement.

Both `build.sh` and `build.ps1` install the bundled wheel **before** the
requirements, so `pip install -r requirements.txt` finds `editdistance`
already satisfied and never touches the compiler. The same wheel works on
every Python >= 3.10 and every OS (pure Python, no binary parts).

To rebuild the wheel after changing the shim:

```bash
cd vendor/editdistance
pip wheel --no-deps -w ../wheels .
```
