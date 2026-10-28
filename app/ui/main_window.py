"""Main application window: two translation panes + pronunciation dock."""
from __future__ import annotations

import base64
import logging
import threading

from PySide6.QtCore import QObject, QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QGridLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QPushButton, QSplitter, QTextEdit,
    QToolButton, QVBoxLayout, QWidget,
)

from ..core import correction, languages, settings, translator
from ..core.pronunciation import analyze
from .. import theme
from ..theme import CORRECTION_UNDERLINE_DARK, CORRECTION_UNDERLINE_LIGHT
from ..theme import apply_theme, px
from .pronunciation_panel import PronunciationPanel

log = logging.getLogger(__name__)


class TranslateWorker(QObject):
    """Runs translations on daemon threads.

    Deliberately not a QThread: closing the window while a request is in
    flight used to abort the process (QThread destroyed while running).
    Daemon threads are simply abandoned at interpreter exit, and the
    `closed` flag stops them from touching dead widgets on the way out.
    """

    result = Signal(int, str, str)     # job id, translated text, engine
    failed = Signal(int, str)          # job id, error

    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def start(self, job_id: int, text: str, src: str, tgt: str) -> None:
        threading.Thread(target=self._run, daemon=True,
                         name=f"translate-{job_id}",
                         args=(job_id, text, src, tgt)).start()

    def _run(self, job_id: int, text: str, src: str, tgt: str) -> None:
        if self.closed:
            return
        try:
            res = translator.translate(text, src, tgt, allow_offline=True)
            if not self.closed:
                self.result.emit(job_id, res.text, res.engine)
        except Exception as exc:  # noqa: BLE001 - surfaced in the status bar
            if not self.closed:
                self.failed.emit(job_id, str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("Language Translator"))
        self.resize(px(1120), px(680))
        self._job = 0
        self._latest = 0
        self._correcting = False
        self._engine_status = ""
        self._src_changes: list[correction.Change] = []
        self._out_changes: list[correction.Change] = []
        self._screen_hooked = False

        # -------------------------------------------------- translate worker
        # lives in the GUI thread; jobs run on daemon threads and emit back
        # through explicit queued connections (see TranslateWorker docstring)
        self._worker = TranslateWorker()
        queued = Qt.ConnectionType.QueuedConnection
        self._worker.result.connect(self._on_result, queued)
        self._worker.failed.connect(self._on_failed, queued)

        # ---------------------------------------------------------- toolbar
        bar = QWidget()
        grid = QGridLayout(bar)

        self.src_combo = QComboBox()
        self.tgt_combo = QComboBox()
        for code, text in languages.combo_items():
            self.src_combo.addItem(text, code)
            self.tgt_combo.addItem(text, code)
        self.src_combo.setCurrentIndex(
            self.src_combo.findData(settings.get_str("source", "en")))
        self.tgt_combo.setCurrentIndex(
            self.tgt_combo.findData(settings.get_str("target", "fr")))
        if self.tgt_combo.currentIndex() < 0:
            self.tgt_combo.setCurrentIndex(self.tgt_combo.findData("fr"))

        self.swap_btn = QToolButton()
        self.swap_btn.setText("\u21c4")
        self.swap_btn.setToolTip(self.tr("Swap languages"))
        self.swap_btn.clicked.connect(self._swap)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(self.tr("Find..."))
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMaximumWidth(px(130))
        self.find_edit.textChanged.connect(self._find)

        self.translate_btn = QPushButton(self.tr("Translate \u25b6"))
        self.translate_btn.setToolTip(self.tr(
            "Translate the text (this is the only way to start a\n"
            "translation - typing never fires a request)"))
        self.translate_btn.clicked.connect(self._dispatch)

        self.dark_btn = QToolButton()
        self.dark_btn.setCheckable(True)
        self.dark_btn.setToolTip(self.tr("Dark mode"))
        self.dark_btn.setChecked(settings.get_bool("dark_mode", False))
        self.dark_btn.toggled.connect(self._on_dark_toggled)
        self._refresh_dark_icon()

        # manual size control: A- / A+ step through theme.STEPS and the
        # choice is remembered per screen (monitor vs laptop)
        self.scale_dn = QToolButton()
        self.scale_dn.setText("A\u2212")
        self.scale_dn.clicked.connect(lambda: self._step_scale(-1))
        self.scale_up = QToolButton()
        self.scale_up.setText("A+")
        self.scale_up.clicked.connect(lambda: self._step_scale(1))

        self.src_label = QLabel(self.tr("Type here"))
        self.tgt_label = QLabel(self.tr("Translation"))

        # controls on top, captions directly above their panes (so
        # "Type here" sits below the language dropdown, not above it)
        grid.addWidget(self.src_combo, 0, 0)
        grid.addWidget(self.swap_btn, 0, 1)
        grid.addWidget(self.tgt_combo, 0, 2)
        grid.addWidget(self.translate_btn, 0, 3)
        grid.addWidget(self.scale_dn, 0, 4)
        grid.addWidget(self.scale_up, 0, 5)
        grid.addWidget(self.dark_btn, 0, 6)
        grid.addWidget(self.find_edit, 0, 7, alignment=Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.src_label, 1, 0)
        grid.addWidget(self.tgt_label, 1, 2, 1, 6,
                       Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(7, 1)

        # ------------------------------------------------------------- panes
        self.src_text = QPlainTextEdit()
        self.src_text.setPlaceholderText(
            self.tr("Write or paste your text... then click Translate"))
        self.out_text = QPlainTextEdit()
        self.out_text.setReadOnly(True)
        self.out_text.setPlaceholderText(self.tr("Translation"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.src_text)
        splitter.addWidget(self.out_text)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)
        self._bar_grid = grid
        self._central_layout = layout

        # ------------------------------------------------------------- dock
        self.panel = PronunciationPanel()
        dock = QDockWidget(self.tr("Pronunciation"), self)
        dock.setObjectName("pronDock")
        dock.setWidget(self.panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._dock = dock

        # scaled layout metrics (also re-run by A-/A+ and screen changes)
        self._apply_metrics()
        self._update_scale_buttons()

        # ---------------------------------------------------------- signals
        # NOTE: no auto-translate - translation starts only via the button
        self.src_text.textChanged.connect(self._on_source_changed)
        self.src_combo.currentIndexChanged.connect(self._on_lang_changed)
        self.tgt_combo.currentIndexChanged.connect(self._on_lang_changed)

        geo = settings.get_str("geometry")
        if geo:
            try:
                self.restoreGeometry(base64.b64decode(geo))
            except Exception:  # noqa: BLE001 - corrupt state is not fatal
                log.warning("could not restore window geometry")
        self._refresh_panel()
        self.statusBar().showMessage(self.tr("Ready"))

    # ---------------------------------------------------------- translation
    @Slot()
    def _on_source_changed(self) -> None:
        """Typing corrects + updates pronunciation - never requests."""
        if not self._correcting:
            self._correct_source()
        self._refresh_panel()

    @Slot()
    def _on_lang_changed(self) -> None:
        if not self._correcting:
            self._correct_source()
        self._refresh_panel()

    # ---------------------------------------------------------- correction
    def _correct_source(self, force: bool = False) -> None:
        """Auto-fix accents/typos in the pane the user types into.

        Always on - no toggle. While typing, the word under the cursor is
        left alone (never fight live input); `force=True` (used right
        before dispatch) corrects everything, so the engine always
        receives clean text.
        """
        text = self.src_text.toPlainText()
        lang = self.src_combo.currentData()
        if not text.strip() or lang not in correction.LANGS:
            return
        pos = self.src_text.textCursor().position()
        skip = None if force else correction.word_range_at(text, pos)
        res = correction.correct(text, lang, True, skip)
        if not res.changes:
            return
        self._correcting = True
        self.src_text.blockSignals(True)
        tc = self.src_text.textCursor()
        tc.beginEditBlock()
        tc.select(QTextCursor.SelectionType.Document)
        tc.insertText(res.text)
        tc.endEditBlock()
        delta = 0
        for c in res.changes:
            if c.start < pos:
                delta += len(c.fixed) - len(c.original)
        tc.setPosition(max(0, min(pos + delta, len(res.text))))
        self.src_text.setTextCursor(tc)
        self.src_text.blockSignals(False)
        self._correcting = False
        self._highlight(self.src_text, res.changes)
        self._report(res.changes)

    def _highlight(self, pane: QPlainTextEdit,
                   changes: list[correction.Change]) -> None:
        fmt = QTextCharFormat()
        fmt.setUnderlineColor(
            CORRECTION_UNDERLINE_DARK if self.dark_btn.isChecked()
            else CORRECTION_UNDERLINE_LIGHT)
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        sels = []
        for c in changes:
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.format.setToolTip(f"{c.original} \u2192 {c.fixed}")
            sel.cursor = QTextCursor(pane.document())
            sel.cursor.setPosition(c.start)
            sel.cursor.setPosition(c.end, QTextCursor.MoveMode.KeepAnchor)
            sels.append(sel)
        pane.setExtraSelections(sels)
        if pane is self.src_text:
            self._src_changes = changes
        else:
            self._out_changes = changes

    def _clear_highlights(self, pane: QPlainTextEdit) -> None:
        pane.setExtraSelections([])
        if pane is self.src_text:
            self._src_changes = []
        else:
            self._out_changes = []

    def _report(self, changes: list[correction.Change]) -> None:
        accents = sum(1 for c in changes if c.kind == "accent")
        typos = len(changes) - accents
        bits = []
        if accents:
            bits.append(self.tr("{n} accent(s)").format(n=accents))
        if typos:
            bits.append(self.tr("{n} typo(s)").format(n=typos))
        base = self._engine_status or self.tr("Ready")
        self.statusBar().showMessage(
            base + "  \u00b7  \u2713 " + ", ".join(bits))

    @Slot()
    def _dispatch(self) -> None:
        # last-chance full correction: even if typing-time correction was
        # skipped (word in flight), the engine always receives clean text
        self._correct_source(force=True)
        text = self.src_text.toPlainText().strip()
        if not text:
            self.out_text.clear()
            return
        self._refresh_panel()
        self._job += 1
        self._latest = self._job
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText(self.tr("Translating\u2026"))
        self._worker.start(self._job, text,
                           self.src_combo.currentData(),
                           self.tgt_combo.currentData())
        self.statusBar().showMessage(self.tr("Translating..."))

    def _translate_done(self) -> None:
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText(self.tr("Translate \u25b6"))

    @Slot(int, str, str)
    def _on_result(self, job_id: int, text: str, engine: str) -> None:
        if job_id != self._latest:
            return  # stale result from an older click: never overwrite
        self._translate_done()
        names = {"google": "Google", "mymemory": "MyMemory",
                 "offline": self.tr("offline model")}
        self._engine_status = self.tr("Translated with {engine}").format(
            engine=names.get(engine, engine))
        # output correction is always on: repair accents the engine dropped
        res = correction.correct(text, self.tgt_combo.currentData())
        out, changes = (res.text, res.changes) if res.changes else (text, [])
        self.out_text.setPlainText(out)
        if changes:
            self._highlight(self.out_text, changes)
        else:
            self._clear_highlights(self.out_text)
        # keep the "what was fixed" report visible after translating:
        # output fixes win, otherwise still report the source-pane fixes
        if changes:
            self._report(changes)
        elif self._src_changes:
            self._report(self._src_changes)
        else:
            self.statusBar().showMessage(self._engine_status)
        self._refresh_panel()

    @Slot(int, str)
    def _on_failed(self, job_id: int, message: str) -> None:
        if job_id != self._latest:
            return
        self._translate_done()
        self.statusBar().showMessage(self.tr("Translation failed: {m}").format(
            m=message[:160]), 8000)

    @Slot()
    def _swap(self) -> None:
        src, tgt = self.src_combo.currentData(), self.tgt_combo.currentData()
        self.src_combo.blockSignals(True)
        self.tgt_combo.blockSignals(True)
        self.src_combo.setCurrentIndex(self.src_combo.findData(tgt))
        self.tgt_combo.setCurrentIndex(self.tgt_combo.findData(src))
        self.src_combo.blockSignals(False)
        self.tgt_combo.blockSignals(False)
        source = self.src_text.toPlainText()
        translated = self.out_text.toPlainText()
        if translated:
            self.src_text.setPlainText(translated)
            self.out_text.setPlainText(source)
        self._refresh_panel()

    # -------------------------------------------------------------- ui size
    def _apply_metrics(self) -> None:
        """(Re-)apply scale-dependent layout measurements."""
        self._bar_grid.setContentsMargins(px(4), px(4), px(4), px(4))
        self._bar_grid.setSpacing(px(6))
        self._central_layout.setContentsMargins(px(6), px(6), px(6), px(6))
        self._central_layout.setSpacing(px(6))
        self.find_edit.setMaximumWidth(px(130))
        self.panel.apply_scale()
        self._refresh_dark_icon()   # icon grows/shrinks with the UI

    def _step_scale(self, direction: int) -> None:
        """A-/A+: move one rung on the size ladder, saved for this screen."""
        self._apply_scale(theme.step(theme.scale(), direction), save=True)

    def _apply_scale(self, s: float, save: bool) -> None:
        """Switch the whole UI to scale `s` live (no restart needed)."""
        theme.set_scale(s)
        app = QApplication.instance()
        if app is not None:
            # rebuilds the stylesheet at the new scale; Qt re-polishes the
            # widgets so fonts/paddings change immediately
            apply_theme(app, self.dark_btn.isChecked())
        self._apply_metrics()
        self._update_scale_buttons()
        # stylesheet swap clears extra selections on some styles: repaint
        if self._src_changes:
            self._highlight(self.src_text, self._src_changes)
        if self._out_changes:
            self._highlight(self.out_text, self._out_changes)
        if save:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                settings.set_double(theme.scale_key(screen.name()), s)

    def _update_scale_buttons(self) -> None:
        pct = f"{round(theme.scale() * 100)}%"
        tip = self.tr("Size: {pct} - click to change").format(pct=pct)
        self.scale_dn.setToolTip(tip)
        self.scale_up.setToolTip(tip)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and not self._screen_hooked:
            handle.screenChanged.connect(self._on_screen_changed)
            self._screen_hooked = True

    def _on_screen_changed(self, screen) -> None:
        """Two-monitor setup: each screen keeps its own size choice."""
        if screen is None:
            return
        s = theme.scale_for_screen(screen)
        if abs(s - theme.scale()) > 1e-6:
            self._apply_scale(s, save=False)

    # ------------------------------------------------------------ dark mode
    def _refresh_dark_icon(self) -> None:
        """Draw the moon/sun toggle icon (emoji were rendering as boxes)."""
        dark = self.dark_btn.isChecked()
        color = (QColor("#ffffff") if dark else
                 self.dark_btn.palette().color(QPalette.ColorRole.WindowText))
        pm = theme.mode_icon(dark, px(18), color)
        self.dark_btn.setIcon(QIcon(pm))
        self.dark_btn.setIconSize(QSize(px(18), px(18)))

    @Slot(bool)
    def _on_dark_toggled(self, dark: bool) -> None:
        settings.set_bool("dark_mode", dark)
        if QApplication.instance() is not None:
            apply_theme(QApplication.instance(), dark)
        self._refresh_dark_icon()   # after apply_theme: palette decides color
        # re-paint corrections so the underline color matches the theme
        if self._src_changes:
            self._highlight(self.src_text, self._src_changes)
        if self._out_changes:
            self._highlight(self.out_text, self._out_changes)
        self._refresh_panel()

    # ------------------------------------------------------------- panel
    def _refresh_panel(self) -> None:
        src = self.src_combo.currentData()
        tgt = self.tgt_combo.currentData()
        code: str | None = None
        text = ""
        if src in languages.SPOKEN_LANGUAGES:
            code, text = src, self.src_text.toPlainText()
        elif tgt in languages.SPOKEN_LANGUAGES and self.out_text.toPlainText():
            code, text = tgt, self.out_text.toPlainText()
        if code is None:
            self.panel.set_language(None)
            self.panel.clear()
            return
        self.panel.set_language(code)
        if not text.strip():
            self.panel.clear()
            self.panel.show_analysis(None)
            return
        try:
            self.panel.show_analysis(analyze(text, code))
        except Exception as exc:  # noqa: BLE001 - analysis must never crash UI
            log.exception("pronunciation analysis failed")
            self.panel.clear()
            # never fail silently: say what broke instead of an empty dock
            self.panel.show_error(str(exc) or exc.__class__.__name__)
            self.statusBar().showMessage(
                self.tr("Pronunciation unavailable: {msg}").format(
                    msg=exc))

    # ------------------------------------------------------------ find box
    def _find(self, needle: str) -> None:
        if not needle:
            return
        for box in (self.src_text, self.out_text):
            if box.find(needle):
                box.setFocus()
                return

    # ------------------------------------------------------------ shutdown
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        settings.set_str("geometry", base64.b64encode(
            self.saveGeometry()).decode())
        settings.set_str("source", self.src_combo.currentData())
        settings.set_str("target", self.tgt_combo.currentData())
        settings.set_bool("dark_mode", self.dark_btn.isChecked())
        # stop in-flight translation threads from touching dead widgets;
        # daemon threads are abandoned and die with the process (no abort)
        self._worker.closed = True
        super().closeEvent(event)
