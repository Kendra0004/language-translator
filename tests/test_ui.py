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

    moon = window.dark_btn.icon()
    assert not moon.isNull(), "light mode must show the drawn moon"
    assert window.dark_btn.text() == "", "icon-only button (no emoji)"

    window.dark_btn.setChecked(True)
    assert window.dark_btn.isChecked()
    assert "1e1f26" in qapp.styleSheet(), "dark stylesheet not applied"
    sun = window.dark_btn.icon()
    assert not sun.isNull(), "dark mode must show the drawn sun"
    assert sun.cacheKey() != moon.cacheKey(), "icon must swap on toggle"
    assert st.get_bool("dark_mode", False) is True
    pal = qapp.palette()
    assert pal.color(pal.ColorRole.Window).name() == "#1e1f26"

    window.dark_btn.setChecked(False)
    assert "1e1f26" not in qapp.styleSheet()
    assert window.dark_btn.icon().cacheKey() != sun.cacheKey(), \
        "moon must come back"
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


# ------------------------------------------------------- no flag emoji
def test_language_labels_are_plain_names():
    from app.core import languages
    for code, text in languages.combo_items():
        assert text == languages.get(code).name
        assert text.isascii(), f"label {text!r} must not carry emoji"
    assert "flag" not in languages.Language.__dataclass_fields__, \
        "the flag field was removed with the emoji"


def test_combo_and_panel_chip_have_no_emoji(window, qapp):
    items = [window.src_combo.itemText(i)
             for i in range(window.src_combo.count())]
    assert "French" in items and "English" in items
    assert all(t.isascii() for t in items)
    window.src_combo.setCurrentIndex(window.src_combo.findData("fr"))
    qapp.processEvents()
    assert window.panel.lang_chip.text() == "French"
    assert window.panel.lang_chip.text().isascii()


def test_captions_sit_below_the_controls_row(window, qapp):
    """'Type here' must be under the language dropdown, not above it."""
    grid = window._bar_grid
    combo_row = grid.getItemPosition(grid.indexOf(window.src_combo))[0]
    src_row = grid.getItemPosition(grid.indexOf(window.src_label))[0]
    tgt_row = grid.getItemPosition(grid.indexOf(window.tgt_label))[0]
    assert src_row > combo_row, "'Type here' must be below the dropdown"
    assert tgt_row == src_row, "both captions share the row below controls"
    # controls still occupy the row above the captions
    tr_row = grid.getItemPosition(grid.indexOf(window.translate_btn))[0]
    assert tr_row == combo_row


def test_window_title_is_plain_app_name(window, qapp):
    assert window.windowTitle() == "Language Translator"


def test_mode_icon_draws_visible_pixels():
    from PySide6.QtGui import QColor
    from app.theme import mode_icon
    for dark in (False, True):
        pm = mode_icon(dark, 24, QColor("#000000"))
        assert not pm.isNull() and pm.width() == 24
        img = pm.toImage()
        opaque = sum(1 for y in range(24) for x in range(24)
                     if img.pixelColor(x, y).alpha() > 0)
        assert opaque > 12, f"{'sun' if dark else 'moon'} drew nothing"


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


def test_resolve_scale_priority():
    """LT_UI_SCALE > saved per-screen choice > auto-detect."""
    from app.theme import resolve_scale
    assert resolve_scale(96, 1920, 1080) == 1.0             # auto
    assert resolve_scale(96, 1920, 1080, saved=1.3) == 1.3  # saved wins
    assert resolve_scale(96, 1366, 768, saved=1.3) == 1.3   # saved > auto bump
    assert resolve_scale(96, 1920, 1080, saved=1.3,
                         env="1.0") == 1.0                   # env wins over all
    assert resolve_scale(96, 1920, 1080, saved=99.0) == 3.0  # clamped
    assert resolve_scale(120, 1920, 1080) == 1.25            # OS scaling


def test_scale_ladder_steps():
    from app.theme import STEPS, step
    assert step(1.0, +1) == 1.15
    assert step(1.0, -1) == 0.85
    assert step(1.15, +1) == 1.3
    assert step(1.5, +1) == 1.5      # top of the ladder
    assert step(0.85, -1) == 0.85    # bottom of the ladder
    assert step(1.2, +1) == 1.3      # auto tiers snap to nearest rung
    assert step(1.2, -1) == 1.15
    assert STEPS[0] < STEPS[-1]


# -------------------------------------------------------- manual ui size
def test_scale_buttons_step_apply_and_persist(window, qapp, isolated_settings):
    from app import theme
    from app.core import settings as st
    try:
        theme.set_scale(1.0)
        window.scale_up.click()
        assert theme.scale() == 1.15
        assert "font-size: 16px" in qapp.styleSheet()   # 14 * 1.15
        assert "115%" in window.scale_up.toolTip()
        key = theme.scale_key(window.screen().name())
        assert st._settings.value(key) is not None, "choice must be saved"

        window.scale_dn.click()
        assert theme.scale() == 1.0
        assert "font-size: 14px" in qapp.styleSheet()

        # clamped at the bottom of the ladder
        for _ in range(4):
            window.scale_dn.click()
        assert theme.scale() == 0.85
        for _ in range(6):
            window.scale_up.click()
        assert theme.scale() == 1.5
    finally:
        theme.set_scale(1.0)


def test_scale_change_keeps_correction_highlights(window, qapp):
    from app import theme
    from app.core import correction
    window.src_text.setPlainText("tres joli")
    changes = [correction.Change("tres", "très", "accent", 0, 4)]
    window._highlight(window.src_text, changes)
    try:
        window.scale_up.click()
        assert window.src_text.extraSelections(), \
            "underlines must survive a live scale change"
        assert window._src_changes
    finally:
        theme.set_scale(1.0)
        window._highlight(window.src_text, changes)
        window._clear_highlights(window.src_text)


def test_screen_change_applies_per_screen_size(window, qapp,
                                               isolated_settings):
    """Dragging to the other monitor loads that screen's saved size."""
    from PySide6.QtGui import QGuiApplication
    from app import theme
    from app.core import settings as st
    screen = QGuiApplication.primaryScreen()
    try:
        theme.set_scale(1.0)
        st.set_double(theme.scale_key(screen.name()), 1.3)
        window._on_screen_changed(screen)
        assert theme.scale() == 1.3
        assert "font-size: 18px" in qapp.styleSheet()   # 14 * 1.3

        # no saved size on this screen -> falls back to auto-detect
        st._settings.remove(theme.scale_key(screen.name()))
        window._on_screen_changed(screen)
        geo = screen.availableGeometry()
        expected = theme.resolve_scale(screen.logicalDotsPerInch(),
                                       geo.width(), geo.height())
        assert abs(theme.scale() - expected) < 1e-6
    finally:
        theme.set_scale(1.0)


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


def test_pyinstaller_entry_bootstraps_package_main():
    """run.py must import app.main as a package (relative imports break
    when PyInstaller executes app/main.py directly - regression guard."""
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "run.py")
    assert os.path.isfile(path), "run.py entry point is missing"
    spec = importlib.util.spec_from_file_location("_lt_run_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # must not raise on import
    assert callable(mod.main)
    spec_file = os.path.join(root, "translator.spec")
    with open(spec_file, encoding="utf-8") as fh:
        assert '["run.py"]' in fh.read(), "spec must use run.py entry"


def test_spec_bundles_all_pronunciation_data_files():
    """Regression: panphon's feature tables were never collected, so in the
    frozen app Epitran('fra-Latn') raised on startup of the panel, every
    word came back empty, and the dock stayed blank. Every package whose
    data files are opened at runtime must be listed in the spec."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "translator.spec"), encoding="utf-8") as fh:
        spec = fh.read()
    for pkg in ("epitran",      # OVM pronunciation rules
                "jamo",         # jamo name tables (read at epitran import)
                "panphon",      # phoneme feature tables (epitran needs these)
                "wordfreq",     # word frequency lists (correction)
                "langcodes",    # language tag data for wordfreq
                "spellchecker"):  # typo dictionary
        assert f'collect_data_files("{pkg}")' in spec, \
            f"spec must bundle {pkg}'s data files"


def test_build_scripts_use_onefile_env_not_illegal_flag():
    """PyInstaller rejects --onefile whenever a .spec file is given, so the
    spec must read LT_ONEFILE from the environment instead (regression:
    `./build.sh --onefile` died with 'makespec options not valid')."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "translator.spec"), encoding="utf-8") as fh:
        spec = fh.read()
    assert 'os.environ.get("LT_ONEFILE")' in spec, "spec must branch on LT_ONEFILE"
    assert "COLLECT" in spec and "ONEFILE" in spec
    with open(os.path.join(root, "build.sh"), encoding="utf-8") as fh:
        sh = fh.read()
    assert "translator.spec --noconfirm --onefile" not in sh
    assert 'LT_ONEFILE=1 "$PYI" translator.spec' in sh
    assert "SMOKE" in sh, "Linux build must smoke-test the binary"
    with open(os.path.join(root, "build.ps1"), encoding="utf-8") as fh:
        ps1 = fh.read()
    assert "translator.spec --noconfirm --onefile" not in ps1
    assert "LT_ONEFILE" in ps1


def test_build_ps1_fails_fast_and_prefers_python312():
    """Windows regressions: a failing pip used to cascade into misleading
    'pyinstaller.exe not recognized', and Python 3.13 tried to compile
    editdistance (no wheel). Both must be guarded."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "build.ps1"), encoding="utf-8") as fh:
        ps1 = fh.read()
    assert "LASTEXITCODE" in ps1, "native command failures must stop the build"
    assert "-3.12" in ps1, "must prefer a Python that has prebuilt wheels"
    assert "editdistance" in ps1, "the refusal must explain WHY"
    assert "LT_SMOKE" in ps1, "Windows build must smoke-test the exe"


def test_build_scripts_tolerate_offline_pip_self_upgrade():
    """The pip self-upgrade is the one step that must reach the index; with
    .venv-build already populated the whole build has to survive wifi being
    down, so that single call may warn but never abort (regression)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "build.sh"), encoding="utf-8") as fh:
        sh = fh.read()
    assert "set -euo pipefail" in sh, "build.sh still fails fast overall"
    i = sh.index("install --upgrade pip")
    assert "||" in sh[i:i + 160], "build.sh self-upgrade must be best-effort"
    with open(os.path.join(root, "build.ps1"), encoding="utf-8") as fh:
        ps1 = fh.read()
    assert 'Step "pip self-upgrade"' not in ps1, \
        "build.ps1 self-upgrade must warn, not Fail"
    assert "no network?" in sh and "no network?" in ps1, \
        "both scripts must say why the upgrade was skipped"


def test_smoke_mode_reports_ok(tmp_path):
    """LT_SMOKE=1 is the packaged-build self test (startup + panel analysis
    + correction): exit code 0 and a SMOKE OK report on stdout and in the
    LT_SMOKE_LOG file the build scripts read."""
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log = tmp_path / "smoke.log"
    env = dict(os.environ)
    env.update(LT_SMOKE="1", LT_SMOKE_LOG=str(log),
               QT_QPA_PLATFORM="offscreen")
    env.pop("LT_UI_SCALE", None)
    proc = subprocess.run([sys.executable, "-m", "app.main"], cwd=root,
                          env=env, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SMOKE OK" in proc.stdout, proc.stdout
    assert "SMOKE OK" in log.read_text(encoding="utf-8")
