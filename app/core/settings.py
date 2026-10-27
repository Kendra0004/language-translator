"""Persistent app settings (window geometry, language pair, theme...).

App id was renamed from ``limited-translator`` to ``language-translator``
along with the GitHub repo; prefs are migrated once so nothing is lost.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings

_ORG = "Kendra0004"
_APP = "language-translator"
_LEGACY_APP = "limited-translator"
_MIGRATED_KEY = "_migrated_from_limited_translator"

_settings = QSettings(_ORG, _APP)


def _migrate_legacy_settings() -> None:
    """Copy prefs from the pre-rename settings file, exactly once."""
    try:
        if _MIGRATED_KEY in _settings.allKeys():
            return
        legacy = QSettings(_ORG, _LEGACY_APP)
        if os.path.exists(legacy.fileName()):
            for key in legacy.allKeys():
                if key != _MIGRATED_KEY:
                    _settings.setValue(key, legacy.value(key))
        _settings.setValue(_MIGRATED_KEY, True)
        _settings.sync()
    except Exception:  # noqa: BLE001 - losing prefs must not break startup
        pass


_migrate_legacy_settings()

# The Fix accents toggle was removed - correction is unconditional now.
# Drop the obsolete key (leftover from the toggle era) if present.
try:
    if _settings.contains("fix_accents"):
        _settings.remove("fix_accents")
        _settings.sync()
except Exception:  # noqa: BLE001 - stale key must not break startup
    pass


def get_str(key: str, default: str = "") -> str:
    return str(_settings.value(key, default))


def set_str(key: str, value: str) -> None:
    _settings.setValue(key, value)


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(_settings.value(key, default))
    except (TypeError, ValueError):
        return default


def set_int(key: str, value: int) -> None:
    _settings.setValue(key, int(value))


def get_double(key: str, default: float = 1.0) -> float:
    try:
        return float(_settings.value(key, default))
    except (TypeError, ValueError):
        return default


def set_double(key: str, value: float) -> None:
    _settings.setValue(key, float(value))


def get_bool(key: str, default: bool = True) -> bool:
    value = _settings.value(key, default)
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def set_bool(key: str, value: bool) -> None:
    _settings.setValue(key, bool(value))
