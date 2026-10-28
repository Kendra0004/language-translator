"""Pure-Python stand-in for the `editdistance` package.

Why this exists
---------------
`editdistance` is a C extension whose final release (0.8.1, Feb 2024)
ships wheels only up to Python 3.12. On Python 3.13/3.14 Windows, pip
would have to compile it, which requires the MSVC Build Tools - so the
whole dependency install used to fail on modern Pythons.

Only `panphon/distance.py` imports this package, and Language Translator
never calls that module (epitran uses `panphon.FeatureTable`, a different
code path). The dependency exists purely as panphon's declared requirement,
so this API-compatible Levenshtein implementation satisfies pip's
bookkeeping and is also a correct fallback if anyone ever does call it.

API: `distance(a, b)` and `eval(a, b)` (the name panphon uses) -> int.
"""
from __future__ import annotations

__version__ = "0.8.1"
__all__ = ["distance", "eval"]


def distance(a, b) -> int:
    """Levenshtein edit distance between two sequences."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # two-row dynamic programming: O(len(a) * len(b)) time, O(len(b)) space
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                prev[j] + 1,            # deletion
                current[-1] + 1,        # insertion
                prev[j - 1] + (ca != cb),  # substitution
            ))
        prev = current
    return prev[-1]


#: alias used by panphon.distance (`editdistance.eval(source, target)`)
eval = distance
