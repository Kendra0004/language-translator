"""Entry point: python -m app.main (or the PyInstaller-built exe)."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow

APP_STYLE = """
QWidget { font-size: 14px; }
QPlainTextEdit { font-size: 15px; }
QComboBox { padding: 4px 8px; }
QToolButton { font-size: 18px; padding: 2px 10px; }
QPushButton { padding: 5px 14px; border-radius: 6px;
              background: #7a5cff; color: white; border: none; }
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
"""


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Limited Translator")
    app.setOrganizationName("Kendra0004")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
