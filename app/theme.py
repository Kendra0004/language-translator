"""Application themes: light and dark stylesheets + matching palettes.

`apply_theme(app, dark)` swaps both at once - the QSS covers the widgets
that accept styling, the palette covers everything QSS cannot reach
(text selection, placeholder text, disabled groups, native dialogs).
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# --------------------------------------------------------------------- light
LIGHT_STYLE = """
QWidget { font-size: 14px; }
QPlainTextEdit { font-size: 15px; }
QComboBox { padding: 4px 8px; }
QToolButton { font-size: 18px; padding: 2px 10px; border-radius: 6px; }
QToolButton:hover { background: #e8e5fb; }
QToolButton:checked { background: #7a5cff; color: white; }
QPushButton { padding: 5px 14px; border-radius: 6px;
              background: #7a5cff; color: white; border: none;
              font-weight: bold; }
QPushButton:hover { background: #6a4be6; }
QPushButton:disabled { background: #d8d4f5; color: #8a86a8; }
QLabel#chip { background: #eee9ff; color: #4b3bbf; border-radius: 9px;
              padding: 3px 12px; font-weight: bold; }
QLabel#bigSay { font-size: 21px; font-weight: bold; color: #26224a; }
QLabel#ipa { font-size: 14px; color: #6b6890;
             font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#syl { font-size: 15px; color: #3d3a63; }
QLabel#sectionTitle { font-weight: bold; color: #4b3bbf; }
QLabel#hint { color: #8a86a8; font-style: italic; }
QFrame#card { background: #f6f5fb; border-radius: 9px; }
QLabel#cardIpa { color: #6b6890; font-size: 13px;
                 font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#liaison { color: #0a8f5b; font-size: 12px; }
QScrollArea { background: transparent; }
QDockWidget::title { background: #eee9ff; color: #4b3bbf;
                     padding: 4px 8px; font-weight: bold; }
QStatusBar { background: #f0eefb; color: #4b4870; }
QSplitter::handle { background: #e3e0f4; }
QLineEdit { padding: 4px 8px; border: 1px solid #d5d1ee;
            border-radius: 6px; background: white; }
"""

# ---------------------------------------------------------------------- dark
DARK_STYLE = """
QWidget { font-size: 14px; color: #e6e7ef; }
QPlainTextEdit { font-size: 15px; background-color: #23242c;
                 color: #e8e9f2; border: 1px solid #343642;
                 border-radius: 6px;
                 selection-background-color: #7a5cff;
                 selection-color: #ffffff; }
QComboBox { padding: 4px 8px; background-color: #2a2c36; color: #e8e9f2;
            border: 1px solid #3a3d4a; border-radius: 6px; }
QComboBox:hover { border-color: #7a5cff; }
QComboBox QAbstractItemView { background-color: #2a2c36; color: #e8e9f2;
                              selection-background-color: #7a5cff;
                              selection-color: #ffffff;
                              border: 1px solid #3a3d4a; }
QLineEdit { padding: 4px 8px; border: 1px solid #3a3d4a;
            border-radius: 6px; background-color: #23242c; color: #e8e9f2; }
QLineEdit:focus { border-color: #7a5cff; }
QToolButton { font-size: 18px; padding: 2px 10px; border-radius: 6px;
              color: #e6e7ef; background-color: transparent;
              border: 1px solid transparent; }
QToolButton:hover { background-color: #333641; border-color: #454859; }
QToolButton:checked { background-color: #7a5cff; color: white;
                      border-color: #7a5cff; }
QToolButton::menu-indicator { image: none; }
QPushButton { padding: 5px 14px; border-radius: 6px;
              background-color: #7a5cff; color: white; border: none;
              font-weight: bold; }
QPushButton:hover { background-color: #8f7bff; }
QPushButton:disabled { background-color: #3a3d4a; color: #7a7d8c; }
QLabel#chip { background-color: #312a5e; color: #c3b8ff; border-radius: 9px;
              padding: 3px 12px; font-weight: bold; }
QLabel#bigSay { font-size: 21px; font-weight: bold; color: #f0f1f8; }
QLabel#ipa { font-size: 14px; color: #9d9ac2;
             font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#syl { font-size: 15px; color: #c9c7e6; }
QLabel#sectionTitle { font-weight: bold; color: #a99dff; }
QLabel#hint { color: #7a7d8c; font-style: italic; }
QFrame#card { background-color: #2a2c36; border-radius: 9px; }
QLabel#cardIpa { color: #9d9ac2; font-size: 13px;
                 font-family: 'Segoe UI', 'DejaVu Sans'; }
QLabel#liaison { color: #3fd39a; font-size: 12px; }
QScrollArea { background: transparent; }
QDockWidget { color: #e6e7ef; }
QDockWidget::title { background-color: #26272f; color: #c3b8ff;
                     padding: 4px 8px; font-weight: bold; }
QStatusBar { background-color: #1a1b21; color: #c9c7e6; }
QStatusBar::item { border: none; }
QSplitter::handle { background-color: #343642; }
QScrollBar:vertical { background-color: #1e1f26; width: 11px;
                      margin: 0; border: none; }
QScrollBar::handle:vertical { background-color: #3a3d4a; border-radius: 5px;
                              min-height: 24px; }
QScrollBar::handle:vertical:hover { background-color: #4d5162; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent; }
QScrollBar:horizontal { background-color: #1e1f26; height: 11px;
                        margin: 0; border: none; }
QScrollBar::handle:horizontal { background-color: #3a3d4a; border-radius: 5px;
                                min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { background-color: #2a2c36; color: #e8e9f2;
           border: 1px solid #454859; padding: 4px 6px; }
"""

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
    """Swap the whole app between dark and light."""
    pal = _palette(dark)
    app.setStyleSheet(DARK_STYLE if dark else LIGHT_STYLE)
    app.setPalette(pal)
    # Qt does NOT propagate an app-level palette change while a style sheet
    # is active - the scroll-area content widget kept painting the light
    # background. Set every existing widget explicitly; widgets created
    # later resolve their palette from these parents.
    for widget in app.allWidgets():
        widget.setPalette(pal)
