"""Main application window: two translation panes + pronunciation dock."""
from __future__ import annotations

import base64
import logging

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QKeySequence, QTextCharFormat
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QGridLayout, QLabel, QLineEdit, QPlainTextEdit,
    QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget, QMainWindow,
)

from ..core import correction, languages, settings, translator
from ..core.pronunciation import analyze
from .pronunciation_panel import PronunciationPanel

log = logging.getLogger(__name__)

DEBOUNCE_MS = 400


class TranslateWorker(QObject):
    result = Signal(int, str, str)     # job id, translated text, engine
    failed = Signal(int, str)          # job id, error
    busy = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._active: int | None = None

    @Slot(int, str, str, str)
    def run(self, job_id: int, text: str, src: str, tgt: str) -> None:
        self._active = job_id
        self.busy.emit(True)
        try:
            res = translator.translate(text, src, tgt, allow_offline=True)
            if self._active == job_id:
                self.result.emit(job_id, res.text, res.engine)
        except Exception as exc:  # noqa: BLE001 - surfaced in the status bar
            if self._active == job_id:
                self.failed.emit(job_id, str(exc))
        finally:
            self.busy.emit(False)


class MainWindow(QMainWindow):
    submitted = Signal(int, str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("Limited Translator - FR / EN and more"))
        self.resize(1120, 680)
        self._job = 0
        self._latest = 0
        self._correcting = False
        self._engine_status = ""

        # ---------------------------------------------------------- thread
        self._thread = QThread(self)
        self._worker = TranslateWorker()
        self._worker.moveToThread(self._thread)
        # explicit QueuedConnection: PySide6 would otherwise run the slot in
        # the emitting thread and touch GUI objects from the worker
        queued = Qt.ConnectionType.QueuedConnection
        self.submitted.connect(self._worker.run, queued)
        self._worker.result.connect(self._on_result, queued)
        self._worker.failed.connect(self._on_failed, queued)
        self._thread.start()

        # ---------------------------------------------------------- toolbar
        bar = QWidget()
        grid = QGridLayout(bar)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(6)

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
        self.find_edit.setPlaceholderText(self.tr("Find in text..."))
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMaximumWidth(200)
        self.find_edit.textChanged.connect(self._find)

        self.fix_btn = QToolButton()
        self.fix_btn.setCheckable(True)
        self.fix_btn.setText(self.tr("Fix accents \u2714"))
        self.fix_btn.setToolTip(self.tr(
            "Auto-correct missing accents and simple typos\n"
            "in both panes (amber underline shows changes)"))
        self.fix_btn.setChecked(settings.get_bool("fix_accents", True))
        self.fix_btn.clicked.connect(self._on_fix_toggled)

        self.src_label = QLabel(self.tr("Type here"))
        self.tgt_label = QLabel(self.tr("Translation"))

        grid.addWidget(self.src_label, 0, 0)
        grid.addWidget(self.tgt_label, 0, 3)
        grid.addWidget(self.src_combo, 1, 0)
        grid.addWidget(self.swap_btn, 1, 1)
        grid.addWidget(self.tgt_combo, 1, 2)
        grid.addWidget(self.fix_btn, 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.find_edit, 1, 4, alignment=Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(3, 1)

        # ------------------------------------------------------------- panes
        self.src_text = QPlainTextEdit()
        self.src_text.setPlaceholderText(
            self.tr("Write or paste your text... translation appears as you type"))
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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        # ------------------------------------------------------------- dock
        self.panel = PronunciationPanel()
        dock = QDockWidget(self.tr("Pronunciation"), self)
        dock.setObjectName("pronDock")
        dock.setWidget(self.panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._dock = dock

        # ---------------------------------------------------------- signals
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._dispatch)
        self.src_text.textChanged.connect(self._on_source_changed)
        self.src_combo.currentIndexChanged.connect(self._on_lang_changed)
        self.tgt_combo.currentIndexChanged.connect(self._on_lang_changed)

        force = QAction(self)
        force.setShortcut(QKeySequence("Ctrl+Return"))
        force.triggered.connect(self._dispatch)
        self.addAction(force)

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
        if not self._correcting and self.fix_btn.isChecked():
            self._correct_source()
        self._debounce.start()
        self._refresh_panel()

    @Slot()
    def _on_lang_changed(self) -> None:
        if self.fix_btn.isChecked():
            self._correct_source()
        self._debounce.start()
        self._refresh_panel()

    # ---------------------------------------------------------- correction
    def _correct_source(self) -> None:
        """Auto-fix accents/typos in the pane the user types into."""
        text = self.src_text.toPlainText()
        lang = self.src_combo.currentData()
        if not text.strip() or lang not in correction.LANGS:
            return
        pos = self.src_text.textCursor().position()
        skip = correction.word_range_at(text, pos)  # never fight live typing
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

    @Slot(bool)
    def _on_fix_toggled(self, checked: bool) -> None:
        settings.set_bool("fix_accents", checked)
        if checked:
            self._correct_source()
            self._debounce.start()
            self._refresh_panel()
        else:
            self._clear_highlights(self.src_text)
            self._clear_highlights(self.out_text)
            self.statusBar().showMessage(
                self._engine_status or self.tr("Ready"))

    def _highlight(self, pane: QPlainTextEdit,
                   changes: list[correction.Change]) -> None:
        fmt = QTextCharFormat()
        fmt.setUnderlineColor(QColor(255, 165, 0))
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

    def _clear_highlights(self, pane: QPlainTextEdit) -> None:
        pane.setExtraSelections([])

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
        text = self.src_text.toPlainText().strip()
        if not text:
            self.out_text.clear()
            return
        self._job += 1
        self._latest = self._job
        self.submitted.emit(self._job, text,
                            self.src_combo.currentData(),
                            self.tgt_combo.currentData())
        self.statusBar().showMessage(self.tr("Translating..."))

    @Slot(int, str, str)
    def _on_result(self, job_id: int, text: str, engine: str) -> None:
        if job_id != self._latest:
            return
        names = {"google": "Google", "mymemory": "MyMemory",
                 "offline": self.tr("offline model")}
        self._engine_status = self.tr("Translated with {engine}").format(
            engine=names.get(engine, engine))
        out, changes = text, []
        if self.fix_btn.isChecked():
            res = correction.correct(text, self.tgt_combo.currentData())
            if res.changes:
                out, changes = res.text, res.changes
        self.out_text.setPlainText(out)
        if changes:
            self._highlight(self.out_text, changes)
        else:
            self._clear_highlights(self.out_text)
        if changes:
            self._report(changes)
        else:
            self.statusBar().showMessage(self._engine_status)
        self._refresh_panel()

    @Slot(int, str)
    def _on_failed(self, job_id: int, message: str) -> None:
        if job_id != self._latest:
            return
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
        self._debounce.start()
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
        except Exception:  # noqa: BLE001 - analysis must never crash the UI
            log.exception("pronunciation analysis failed")
            self.panel.clear()

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
        settings.set_bool("fix_accents", self.fix_btn.isChecked())
        self._thread.quit()
        self._thread.wait(2000)
        super().closeEvent(event)
