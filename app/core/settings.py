"""Persistent app settings (window geometry, language pair, voice speed)."""
from __future__ import annotations

from PySide6.QtCore import QSettings

_settings = QSettings("Kendra0004", "limited-translator")


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
