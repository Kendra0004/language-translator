"""Entry point: python -m app.main (or the PyInstaller-built binary)."""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from . import theme
from .core import settings
from .ui.main_window import MainWindow

# Re-exported so existing callers/tests keep working: the scale logic
# lives in app.theme now (the window needs it too when the user drags
# the app to another screen).
compute_scale = theme.compute_scale

# First-run window size relative to the screen on small displays.
FIRST_RUN_FILL = 0.92


def fit_to_screen(win, avail: QRect, others: tuple = ()) -> bool:
    """Clamp the window into `avail` (returns True when it was changed).

    A window restored from a previous session on a bigger monitor (or a
    resolution change) must never open off-screen or larger than the
    display. Windows that already fit - including ones on secondary
    monitors passed in `others` - are left completely alone.
    """
    g = win.geometry()
    for r in (avail, *others):
        if (r.contains(g.topLeft()) and g.width() <= r.width()
                and g.height() <= r.height()):
            return False
    w = min(g.width(), avail.width())
    h = min(g.height(), avail.height())
    x = min(max(g.x(), avail.x()), avail.x() + avail.width() - w)
    y = min(max(g.y(), avail.y()), avail.y() + avail.height() - h)
    win.setGeometry(x, y, w, h)
    return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Language Translator")
    app.setOrganizationName("Kendra0004")

    # --- scale, before the first widget exists (no resize flash) ----------
    # priority: LT_UI_SCALE > this screen's saved manual size > auto-detect
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        s = theme.scale_for_screen(screen)
    else:
        geo = QRect(0, 0, 1920, 1080)
        s = theme.resolve_scale(96.0, geo.width(), geo.height(),
                                env=os.environ.get("LT_UI_SCALE"))
    theme.set_scale(s)
    logging.getLogger(__name__).info("UI scale: %.2f", s)

    # theme is applied before the first widget exists: no light->dark flash
    theme.apply_theme(app, settings.get_bool("dark_mode", False))

    window = MainWindow()
    # first run: fill most of a small screen; later runs: keep saved size
    if not settings.get_str("geometry"):
        window.resize(min(window.width(), int(geo.width() * FIRST_RUN_FILL)),
                      min(window.height(), int(geo.height() * FIRST_RUN_FILL)))
    others = tuple(scr.availableGeometry()
                   for scr in app.screens() if scr is not screen)
    fit_to_screen(window, geo, others)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
