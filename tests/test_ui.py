"""UI behaviour tests: manual-only translation, theme toggle, clean shutdown."""
from __future__ import annotations

import os
import time

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QPlainTextEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    from app.theme import apply_theme
    apply_theme(app, False)  # never leak the dark theme into other tests


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """Write QSettings to a temp file so tests never touch real prefs."""
    from PySide6.QtCore import QSettings
    from app.core import settings as st
    fake = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(st, "_settings", fake)
    return fake


@pytest.fixture()
def window(qapp, isolated_settings):
    from app.theme import apply_theme
    from app.ui.main_window import MainWindow
    apply_theme(qapp, False)
    w = MainWindow()
    yield w
    w.close()
    w.deleteLater()
    qapp.processEvents()


def _spy(w) -> list:
    """Replace worker.start with a recorder; returns the call list."""
    calls: list = []
    w._worker.start = lambda *a: calls.append(a)
    return calls


# ------------------------------------------------------- manual translation
def test_typing_never_dispatches(window, qapp):
    calls = _spy(window)
    window.src_combo.setCurrentIndex(window.src_combo.findData("fr"))
    window.src_text.setPlainText("bonjour tout le monde")
    window.src_text.appendPlainText("encore du texte")
    qapp.processEvents()
    time.sleep(0.6)  # would have been the old 400ms debounce window
    qapp.processEvents()
    assert calls == [], "typing must not fire a translation request"


def test_language_change_never_dispatches(window, qapp):
    calls = _spy(window)
    window.src_text.setPlainText("hello")
    window.tgt_combo.setCurrentIndex(window.tgt_combo.findData("es"))
    qapp.processEvents()
    assert calls == []


def test_translate_button_dispatches_exactly_once(window):
    calls = _spy(window)
    window.src_text.setPlainText("hello world")
    window.translate_btn.click()
    assert len(calls) == 1
    job_id, text, src, tgt = calls[0]
    assert text == "hello world"
    assert src == "en" and tgt == "fr"
    assert not window.translate_btn.isEnabled(), "button must disable in flight"
    assert window.translate_btn.text() != "Translate \u25b6"


def test_result_reenables_button_and_fills_output(window, qapp):
    calls = _spy(window)
    window.src_text.setPlainText("hello")
    window.translate_btn.click()
    job_id = calls[0][0]
    window._worker.result.emit(job_id, "Bonjour tout le monde", "google")
    qapp.processEvents()  # queued delivery back to the GUI thread
    assert window.translate_btn.isEnabled()
    assert window.translate_btn.text() == "Translate \u25b6"
    assert window.out_text.toPlainText() == "Bonjour tout le monde"


def test_stale_result_is_ignored(window, qapp):
    calls = _spy(window)
    window.src_text.setPlainText("hello")
    window.translate_btn.click()
    window._worker.result.emit(calls[0][0] + 7, "OLD", "google")
    qapp.processEvents()
    assert window.out_text.toPlainText() == ""
    assert not window.translate_btn.isEnabled(), "job still in flight"


def test_failure_reenables_button(window, qapp):
    calls = _spy(window)
    window.src_text.setPlainText("hello")
    window.translate_btn.click()
    window._worker.failed.emit(calls[0][0], "boom")
    qapp.processEvents()
    assert window.translate_btn.isEnabled()


# ------------------------------------------------------------ no shortcuts
def test_enter_and_ctrl_enter_do_not_translate(window, qapp):
    calls = _spy(window)
    window.src_text.setPlainText("hello")
    window.src_text.setFocus()
    for mods in (Qt.KeyboardModifier.NoModifier,
                 Qt.KeyboardModifier.ControlModifier):
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QApplication.sendEvent(
                window.src_text,
                QKeyEvent(QEvent.Type.KeyPress, key, mods))
    qapp.processEvents()
    assert calls == [], "Enter/Ctrl+Enter must not start a translation"


def test_no_shortcut_actions_registered(window):
    assert all(action.shortcut().isEmpty() for action in window.actions())


# ----------------------------------------------------------------- dark mode
def test_dark_mode_toggle_styles_and_persists(qapp, isolated_settings, window):
    from app.core import settings as st
    from app.theme import DARK_STYLE, LIGHT_STYLE

    assert not window.dark_btn.isChecked()
    assert "1e1f26" not in qapp.styleSheet()

    window.dark_btn.setChecked(True)
    assert window.dark_btn.isChecked()
    assert "1e1f26" in qapp.styleSheet(), "dark stylesheet not applied"
    assert window.dark_btn.text() != "\U0001f319", "icon should show sun"
    assert st.get_bool("dark_mode", False) is True
    pal = qapp.palette()
    assert pal.color(pal.ColorRole.Window).name() == "#1e1f26"

    window.dark_btn.setChecked(False)
    assert "1e1f26" not in qapp.styleSheet()
    assert window.dark_btn.text() == "\U0001f319"
    assert st.get_bool("dark_mode", True) is False


def test_correction_underline_switches_with_theme(window, qapp):
    from app.core import correction
    window.src_text.setPlainText("tres joli")
    changes = [correction.Change("tres", "très", "accent", 0, 4)]
    window.dark_btn.setChecked(True)
    window._highlight(window.src_text, changes)
    sels = window.src_text.extraSelections()
    assert sels and sels[0].format.underlineColor().name() == "#ffab4d"
    window.dark_btn.setChecked(False)
    window._highlight(window.src_text, changes)
    sels = window.src_text.extraSelections()
    assert sels and sels[0].format.underlineColor().name() == "#ffa500"
    window._clear_highlights(window.src_text)


# --------------------------------------------------------------- shutdown
def test_window_uses_no_qthread(qapp, isolated_settings):
    """Regression guard: QThread destruction mid-translation aborted (134)."""
    from PySide6.QtCore import QThread
    from app.ui.main_window import MainWindow
    w = MainWindow()
    assert w.findChild(QThread) is None, "translations must use daemon threads"
    w.close()
    w.deleteLater()


def test_close_during_inflight_translation_is_clean(qapp, isolated_settings,
                                                    monkeypatch):
    def slow_translate(*args, **kwargs):
        time.sleep(0.5)

        class R:
            text = "x"
            engine = "google"
        return R()

    monkeypatch.setattr("app.core.translator.translate", slow_translate)
    from app.ui.main_window import MainWindow
    w = MainWindow()
    w.src_text.setPlainText("hello")
    w.translate_btn.click()          # job now in flight
    w.close()                        # user closes immediately after
    assert w._worker.closed is True, "in-flight worker must be flagged"
    w.deleteLater()
    time.sleep(0.6)                  # let the daemon thread finish quietly
    qapp.processEvents()


# --------------------------------------------------- always-on correction
def test_fix_accents_toggle_is_gone(window):
    """Correction has no button anymore - it is unconditional."""
    assert not hasattr(window, "fix_btn")
    assert not hasattr(window, "_on_fix_toggled")


def test_dispatch_always_sends_corrected_text(window):
    """Even if typing-time correction was skipped, Translate sends clean text."""
    calls = _spy(window)
    window.src_combo.setCurrentIndex(window.src_combo.findData("fr"))
    window.src_text.blockSignals(True)          # pretend typing correction off
    window.src_text.setPlainText("je suis tres content")
    window.src_text.blockSignals(False)
    window.translate_btn.click()
    assert len(calls) == 1
    assert calls[0][1] == "je suis très content"


def test_output_is_always_corrected_and_highlighted(window, qapp):
    calls = _spy(window)
    window.src_combo.setCurrentIndex(window.src_combo.findData("fr"))
    window.src_text.setPlainText("bonjour")
    window.translate_btn.click()
    window._worker.result.emit(calls[0][0], "hello, je suis tres content",
                               "mymemory")
    qapp.processEvents()
    assert "très" in window.out_text.toPlainText()
    assert window.out_text.extraSelections(), "amber underline expected"
    assert window._out_changes
    assert "\u2713" in window.statusBar().currentMessage(), \
        "status bar must report what was fixed"


def test_status_keeps_fix_report_when_output_needs_no_fix(window, qapp):
    """Source-pane fixes stay reported even if the engine output is clean."""
    calls = _spy(window)
    window.src_combo.setCurrentIndex(window.src_combo.findData("fr"))
    window.src_text.blockSignals(True)
    window.src_text.setPlainText("tres bien")     # typing correction skipped
    window.src_text.blockSignals(False)
    window.translate_btn.click()                  # dispatch corrects it
    assert calls[0][1] == "très bien"
    window._worker.result.emit(calls[0][0], "very good", "google")
    qapp.processEvents()
    assert "\u2713" in window.statusBar().currentMessage()


# ----------------------------------------------------------------- scaling
def test_compute_scale_tiers():
    from app.main import compute_scale
    assert compute_scale(96, 1920, 1080) == 1.0        # normal desktop
    assert compute_scale(120, 1920, 1080) == 1.25      # OS at 125%
    assert compute_scale(144, 2560, 1440) == 1.5       # OS at 150%
    assert compute_scale(96, 1366, 768) == 1.2         # small -> medium tier
    assert compute_scale(144, 1366, 768) == 1.5        # scaling wins if bigger
    assert compute_scale(96, 1920, 1080, "1.3") == 1.3  # env override
    assert compute_scale(96, 1920, 1080, "9") == 3.0    # clamped
    assert compute_scale(96, 1920, 1080, "bogus") == 1.0  # bad value ignored


def test_theme_scale_grows_styles():
    from app import theme
    try:
        theme.set_scale(1.25)
        assert theme.px(4) == 5
        assert theme.px(14) == 18
        style = theme.build_style(True, 1.25)
        assert "font-size: 18px" in style      # 14 * 1.25 base font
        assert "font-size: 19px" in style      # 15 * 1.25 text panes
        assert "1e1f26" in style               # still dark
    finally:
        theme.set_scale(1.0)
    assert theme.px(14) == 14
    assert theme.build_style(False, 1.0) == theme.LIGHT_STYLE
    assert theme.build_style(True, 1.0) == theme.DARK_STYLE


def test_fit_to_screen_clamps_oversized_window(qapp, isolated_settings):
    from PySide6.QtCore import QRect
    from app.main import fit_to_screen
    from app.ui.main_window import MainWindow
    w = MainWindow()
    w.setGeometry(0, 0, 4000, 3000)           # saved on a bigger screen
    avail = QRect(0, 0, 1366, 720)
    assert fit_to_screen(w, avail) is True
    g = w.geometry()
    assert g.width() <= avail.width() and g.height() <= avail.height()
    # a window that already fits is left completely alone
    w.setGeometry(10, 10, 800, 600)
    assert fit_to_screen(w, avail) is False
    assert w.geometry().width() == 800
    w.close()
    w.deleteLater()


# ---------------------------------------------------------------- packaging
def test_linux_build_script_exists_and_is_executable():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "build.sh")
    assert os.path.isfile(path), "build.sh is missing"
    assert os.access(path, os.X_OK), "build.sh must be executable"
