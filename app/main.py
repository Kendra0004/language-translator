"""Entry point: python -m app.main (or the PyInstaller-built exe)."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .core import settings
from .theme import APP_STYLE, apply_theme  # noqa: F401 - APP_STYLE re-exported
from .ui.main_window import MainWindow


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Limited Translator")
    app.setOrganizationName("Kendra0004")
    # theme is applied before the first widget exists: no light->dark flash
    apply_theme(app, settings.get_bool("dark_mode", False))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
