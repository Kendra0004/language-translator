"""Application themes: light and dark stylesheets + matching palettes.

`apply_theme(app, dark)` swaps both at once - the QSS covers the widgets
that accept styling, the palette covers everything QSS cannot reach
(text selection, placeholder text, disabled groups, native dialogs).

Sizing: every stylesheet is parameterized by a scale factor so the whole
UI can grow on small/low-DPI screens. Call `set_scale()` once at startup
(`scale_for_screen` resolves it per monitor); `px()` converts a design
pixel to the current scale - layout code uses it for margins/spacing.
The A-/A+ toolbar buttons step through `STEPS` and remember the choice
per screen.
"""
from __future__ import annotations

import os

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .core import settings

# --------------------------------------------------------------------- scale
_SCALE = 1.0

# Manual size ladder used by the A-/A+ toolbar buttons.
STEPS = (0.85, 1.0, 1.15, 1.3, 1.5)

# Screens <= this (a classic small laptop panel) get the medium tier.
SMALL_SCREEN = (1366, 768)


def set_scale(s: float) -> None:
    """Set the global UI scale factor (1.0 = design size)."""
    global _SCALE
    _SCALE = max(0.5, min(float(s), 3.0))


def scale() -> float:
    return _SCALE


def px(n: int) -> int:
    """Design pixels at the current scale; used by layout code."""
    return max(1, int(round(n * _SCALE)))


def compute_scale(dpi: float, screen_w: int, screen_h: int,
                  override: str | None = None) -> float:
    """Pick the automatic UI scale from OS DPI + screen size.

    - OS scaling (125% -> 120 DPI) grows the UI proportionally, clamped
      to [1.0, 2.0] so nothing becomes unusably huge;
    - screens <= 1366x768 are bumped to 1.2 - the "medium" tier for
      small-resolution laptops;
    - an override string (LT_UI_SCALE) replaces everything.
    """
    if override:
        try:
            return max(0.5, min(float(override), 3.0))
        except ValueError:
            import logging
            logging.getLogger(__name__).warning(
                "ignoring bad LT_UI_SCALE=%r", override)
    s = dpi / 96.0
    s = max(1.0, min(s, 2.0))
    if screen_w <= SMALL_SCREEN[0] and screen_h <= SMALL_SCREEN[1]:
        s = max(s, 1.2)
    return round(s, 2)


def resolve_scale(dpi: float, screen_w: int, screen_h: int,
                  saved: float = 0.0, env: str | None = None) -> float:
    """Priority: LT_UI_SCALE env > saved per-screen choice > auto-detect."""
    if env:
        return compute_scale(dpi, screen_w, screen_h, env)
    if saved > 0:
        return round(max(0.5, min(saved, 3.0)), 2)
    return compute_scale(dpi, screen_w, screen_h, None)


def scale_key(screen_name: str) -> str:
    """Settings key holding the manual size chosen on a given screen."""
    return f"ui_scale@{screen_name}"


def scale_for_screen(screen, env: str | None = None) -> float:
    """Resolve the UI scale for a QScreen (saved choice, else auto)."""
    geo = screen.availableGeometry()
    saved = settings.get_double(scale_key(screen.name()), 0.0)
    return resolve_scale(screen.logicalDotsPerInch(), geo.width(),
                         geo.height(), saved,
                         os.environ.get("LT_UI_SCALE") if env is None else env)


def step(current: float, direction: int) -> float:
    """Neighbour on the size ladder; clamped at the ends.

    Values not on the ladder (auto tiers like 1.2) snap to the next
    rung above/below them.
    """
    eps = 1e-6
    if direction > 0:
        for s in STEPS:
            if s > current + eps:
                return s
        return STEPS[-1]
    for s in reversed(STEPS):
        if s < current - eps:
            return s
    return STEPS[0]


def _values(s: float) -> dict[str, int]:
    def p(n: int) -> int:
        return max(1, int(round(n * s)))

    return {
        "fs": p(14),          # base widget font
        "fs_edit": p(15),     # text panes
        "fs_tool": p(18),     # toolbar tool buttons
        "fs_big": p(21),      # big "say" line in the panel
        "fs_small": p(13),    # card IPA line
        "fs_tiny": p(12),     # liaison notes
        "pad_s": p(4),        # small padding
        "pad_m": p(8),        # medium padding (sides)
        "pad_btn_y": p(5),
        "pad_btn_x": p(14),
        "pad_tool_y": p(2),
        "pad_tool_x": p(10),
        "r": p(6),            # control corner radius
        "r_chip": p(9),
        "pad_chip_y": p(3),
        "pad_chip_x": p(12),
        "sb_w": p(11),        # scrollbar thickness
        "sb_r": p(5),
        "sb_min": p(24),      # scrollbar handle minimum length
        "tip_pad": p(6),
    }


def build_style(dark: bool, s: float) -> str:
    """Render a stylesheet at scale `s` (templates use %(...)s, no braces)."""
    tpl = _DARK_QSS if dark else _LIGHT_QSS
    return tpl % _values(s)


# QSS templates. Placeholders are %(name)s so the literal braces that QSS
# needs for rule blocks never collide with Python's str.format.
_LIGHT_QSS = """
QWidget { font-size: %(fs)spx; }
QPlainTextEdit { font-size: %(fs_edit)spx; }
QComboBox { padding: %(pad_s)spx %(pad_m)spx; }
QToolButton { font-size: %(fs_tool)spx; padding: %(pad_tool_y)spx %(pad_tool_x)spx;
              border-radius: %(r)spx; }
QToolButton:hover { background: #e8e5fb; }
QToolButton:checked { background: #7a5cff; color: white; }
QPushButton { padding: %(pad_btn_y)spx %(pad_btn_x)spx; border-radius: %(r)spx;
              background: #7a5cff; color: white; border: none;
              font-weight: bold; }
QPushButton:hover { background: #6a4be6; }
QPushButton:disabled { background: #d8d4f5; color: #8a86a8; }
QLabel#chip { background: #eee9ff; color: #4b3bbf;
              border-radius: %(r_chip)spx;
              padding: %(pad_chip_y)spx %(pad_chip_x)spx; font-weight: bold; }
QLabel#bigSay { font-size: %(fs_big)spx; font-weight: bold; color: #26224a; }
QLabel#ipa { font-size: %(fs)spx; color: #6b6890;
             font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#syl { font-size: %(fs_edit)spx; color: #3d3a63; }
QLabel#sectionTitle { font-weight: bold; color: #4b3bbf; }
QLabel#hint { color: #8a86a8; font-style: italic; }
QFrame#card { background: #f6f5fb; border-radius: %(r_chip)spx; }
QLabel#cardIpa { color: #6b6890; font-size: %(fs_small)spx;
                 font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#liaison { color: #0a8f5b; font-size: %(fs_tiny)spx; }
QScrollArea { background: transparent; }
QDockWidget::title { background: #eee9ff; color: #4b3bbf;
                     padding: %(pad_s)spx %(pad_m)spx; font-weight: bold; }
QStatusBar { background: #f0eefb; color: #4b4870; }
QSplitter::handle { background: #e3e0f4; }
QLineEdit { padding: %(pad_s)spx %(pad_m)spx; border: 1px solid #d5d1ee;
            border-radius: %(r)spx; background: white; }
"""

_DARK_QSS = """
QWidget { font-size: %(fs)spx; color: #e6e7ef; }
QPlainTextEdit { font-size: %(fs_edit)spx; background-color: #23242c;
                 color: #e8e9f2; border: 1px solid #343642;
                 border-radius: %(r)spx;
                 selection-background-color: #7a5cff;
                 selection-color: #ffffff; }
QComboBox { padding: %(pad_s)spx %(pad_m)spx; background-color: #2a2c36;
            color: #e8e9f2;
            border: 1px solid #3a3d4a; border-radius: %(r)spx; }
QComboBox:hover { border-color: #7a5cff; }
QComboBox QAbstractItemView { background-color: #2a2c36; color: #e8e9f2;
                              selection-background-color: #7a5cff;
                              selection-color: #ffffff;
                              border: 1px solid #3a3d4a; }
QLineEdit { padding: %(pad_s)spx %(pad_m)spx; border: 1px solid #3a3d4a;
            border-radius: %(r)spx; background-color: #23242c; color: #e8e9f2; }
QLineEdit:focus { border-color: #7a5cff; }
QToolButton { font-size: %(fs_tool)spx; padding: %(pad_tool_y)spx %(pad_tool_x)spx;
              border-radius: %(r)spx;
              color: #e6e7ef; background-color: transparent;
              border: 1px solid transparent; }
QToolButton:hover { background-color: #333641; border-color: #454859; }
QToolButton:checked { background-color: #7a5cff; color: white;
                      border-color: #7a5cff; }
QToolButton::menu-indicator { image: none; }
QPushButton { padding: %(pad_btn_y)spx %(pad_btn_x)spx; border-radius: %(r)spx;
              background-color: #7a5cff; color: white; border: none;
              font-weight: bold; }
QPushButton:hover { background-color: #8f7bff; }
QPushButton:disabled { background-color: #3a3d4a; color: #7a7d8c; }
QLabel#chip { background-color: #312a5e; color: #c3b8ff;
              border-radius: %(r_chip)spx;
              padding: %(pad_chip_y)spx %(pad_chip_x)spx; font-weight: bold; }
QLabel#bigSay { font-size: %(fs_big)spx; font-weight: bold; color: #f0f1f8; }
QLabel#ipa { font-size: %(fs)spx; color: #9d9ac2;
             font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#syl { font-size: %(fs_edit)spx; color: #c9c7e6; }
QLabel#sectionTitle { font-weight: bold; color: #a99dff; }
QLabel#hint { color: #7a7d8c; font-style: italic; }
QFrame#card { background-color: #2a2c36; border-radius: %(r_chip)spx; }
QLabel#cardIpa { color: #9d9ac2; font-size: %(fs_small)spx;
                 font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#liaison { color: #3fd39a; font-size: %(fs_tiny)spx; }
QScrollArea { background: transparent; }
QDockWidget { color: #e6e7ef; }
QDockWidget::title { background-color: #26272f; color: #c3b8ff;
                     padding: %(pad_s)spx %(pad_m)spx; font-weight: bold; }
QStatusBar { background-color: #1a1b21; color: #c9c7e6; }
QStatusBar::item { border: none; }
QSplitter::handle { background-color: #343642; }
QScrollBar:vertical { background-color: #1e1f26; width: %(sb_w)spx;
                      margin: 0; border: none; }
QScrollBar::handle:vertical { background-color: #3a3d4a;
                              border-radius: %(sb_r)spx;
                              min-height: %(sb_min)spx; }
QScrollBar::handle:vertical:hover { background-color: #4d5162; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent; }
QScrollBar:horizontal { background-color: #1e1f26; height: %(sb_w)spx;
                         margin: 0; border: none; }
QScrollBar::handle:horizontal { background-color: #3a3d4a;
                                border-radius: %(sb_r)spx;
                                min-width: %(sb_min)spx; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { background-color: #2a2c36; color: #e8e9f2;
           border: 1px solid #454859; padding: %(pad_s)spx %(tip_pad)spx; }
"""

# Rendered at design scale for anything that wants a plain constant
# (tests, tooling); the app itself renders at the detected scale.
LIGHT_STYLE = build_style(False, 1.0)
DARK_STYLE = build_style(True, 1.0)

# Backwards-compatible alias (older scripts import APP_STYLE from app.main).
APP_STYLE = LIGHT_STYLE

# Amber used for correction underlines - brighter so it reads on dark panes.
CORRECTION_UNDERLINE_LIGHT = QColor(255, 165, 0)
CORRECTION_UNDERLINE_DARK = QColor("#ffab4d")


def _palette(dark: bool) -> QPalette:
    p = QPalette()
    if dark:
        colors = {
            "Window": "#1e1f26", "WindowText": "#e6e7ef", "Base": "#23242c",
            "AlternateBase": "#2a2c36", "Text": "#e8e9f2", "Button": "#2a2c36",
            "ButtonText": "#e6e7ef", "Highlight": "#7a5cff",
            "HighlightedText": "#ffffff", "PlaceholderText": "#8a86a8",
            "ToolTipBase": "#2a2c36", "ToolTipText": "#e8e9f2",
            "Link": "#8f7bff", "LinkVisited": "#a99dff",
            "Light": "#3a3d4a", "Midlight": "#333641", "Dark": "#15161a",
            "Mid": "#2a2c36", "Shadow": "#0f1013", "BrightText": "#ffffff",
        }
        for name, value in colors.items():
            p.setColor(getattr(QPalette.ColorRole, name), QColor(value))
        disabled = ("#6a6c78", "#7a7d8c")
        for role in ("WindowText", "Text", "ButtonText"):
            p.setColor(QPalette.ColorGroup.Disabled,
                       getattr(QPalette.ColorRole, role), QColor(disabled[0]))
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight,
                   QColor("#3a3d4a"))
        p.setColor(QPalette.ColorGroup.Disabled,
                   QPalette.ColorRole.HighlightedText,
                   QColor(disabled[1]))
    else:
        colors = {
            "Window": "#f7f7fb", "WindowText": "#22203a", "Base": "#ffffff",
            "AlternateBase": "#f6f5fb", "Text": "#22203a", "Button": "#f0eefc",
            "ButtonText": "#22203a", "Highlight": "#7a5cff",
            "HighlightedText": "#ffffff", "PlaceholderText": "#8a86a8",
            "Link": "#6a4be6", "ToolTipBase": "#eeecff", "ToolTipText": "#22203a",
        }
        for name, value in colors.items():
            p.setColor(getattr(QPalette.ColorRole, name), QColor(value))
    return p


def apply_theme(app: QApplication, dark: bool) -> None:
    """Swap the whole app between dark and light at the current scale."""
    pal = _palette(dark)
    app.setStyleSheet(build_style(dark, _SCALE))
    app.setPalette(pal)
    # Qt does NOT propagate an app-level palette change while a style sheet
    # is active - the scroll-area content widget kept painting the light
    # background. Set every existing widget explicitly; widgets created
    # later resolve their palette from these parents.
    for widget in app.allWidgets():
        widget.setPalette(pal)
