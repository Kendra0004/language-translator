"""Side panel: how a native speaker would say the text (IPA, syllables,
reading approximation, audio playback)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..core import languages, tts
from ..core.pronunciation import Analysis, WordPron
from ..theme import px

log = logging.getLogger(__name__)


class _TTSWorker(QObject):
    """Fetches mp3 files off the UI thread."""
    ready = Signal(str, str, str)  # text, lang, path ('' = failed)

    def request(self, text: str, lang: str, speed: float) -> None:
        def run() -> None:
            path = tts.fetch(text, lang) or ""
            self.ready.emit(text, lang, path)
        threading.Thread(target=run, daemon=True).start()


class PronunciationPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis: Analysis | None = None
        self._speed = 1.0
        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._current_path: str = ""

        self._worker = _TTSWorker()
        self._worker.ready.connect(self._on_fetched,
                                   Qt.ConnectionType.QueuedConnection)

        root = QVBoxLayout(self)
        root.setContentsMargins(px(12), px(10), px(12), px(10))
        root.setSpacing(px(8))
        self._root = root

        head = QHBoxLayout()
        self.lang_chip = QLabel("")
        self.lang_chip.setObjectName("chip")
        head.addWidget(self.lang_chip)
        head.addStretch(1)
        self.play_btn = QPushButton("\u25b6 Play")
        self.play_btn.setToolTip("Hear the whole sentence in a native voice")
        self.play_btn.clicked.connect(self._play_sentence)
        head.addWidget(self.play_btn)
        speed_box = QComboBox()
        speed_box.setToolTip("Playback speed")
        for label, rate in (("0.6\u00d7", 0.6), ("0.8\u00d7", 0.8),
                            ("1.0\u00d7", 1.0)):
            speed_box.addItem(label, rate)
        speed_box.setCurrentIndex(2)
        speed_box.currentIndexChanged.connect(
            lambda i: setattr(self, "_speed", speed_box.itemData(i)))
        head.addWidget(speed_box)
        root.addLayout(head)

        self.say_label = QLabel("")
        self.say_label.setObjectName("bigSay")
        self.say_label.setWordWrap(True)
        self.say_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.say_label)

        self.ipa_label = QLabel("")
        self.ipa_label.setObjectName("ipa")
        self.ipa_label.setWordWrap(True)
        self.ipa_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.ipa_label)

        self.syl_label = QLabel("")
        self.syl_label.setObjectName("syl")
        self.syl_label.setWordWrap(True)
        self.syl_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.syl_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        self.words_title = QLabel("Word by word")
        self.words_title.setObjectName("sectionTitle")
        root.addWidget(self.words_title)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("hint")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.cards_host = QWidget()
        self.cards = QVBoxLayout(self.cards_host)
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(px(6))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.cards_host)
        root.addWidget(scroll, 1)

        self.set_language(None)
        self.retranslate()

    def apply_scale(self) -> None:
        """Re-apply scaled metrics after a UI size change (A-/A+)."""
        self._root.setContentsMargins(px(12), px(10), px(12), px(10))
        self._root.setSpacing(px(8))
        self.cards.setSpacing(px(6))
        analysis = getattr(self, "_analysis", None)
        if analysis is not None:
            self.show_analysis(analysis)   # rebuild cards at the new size

    # ------------------------------------------------------------ state
    def retranslate(self) -> None:
        self.play_btn.setText(self.tr("\u25b6 Play"))
        self.words_title.setText(self.tr("Word by word"))

    def set_language(self, code: str | None) -> None:
        if code:
            lang = languages.get(code)
            self.lang_chip.setText(lang.speak)
            self.empty_label.hide()
        else:
            self.lang_chip.setText(self.tr("no target language"))
        self.setVisible(bool(code))

    def clear(self) -> None:
        self._analysis = None
        self.say_label.clear()
        self.ipa_label.clear()
        self.syl_label.clear()
        self._clear_cards()
        self.play_btn.setEnabled(False)

    def show_analysis(self, analysis: Analysis | None) -> None:
        self._analysis = analysis
        self._clear_cards()
        if analysis is None:
            self.clear()
            return
        lang = languages.get(analysis.lang)
        self.lang_chip.setText(lang.speak)
        self.say_label.setText(analysis.respelling)
        self.ipa_label.setText("/" + analysis.ipa_line + "/")
        self.syl_label.setText(analysis.syllable_line)
        self.play_btn.setEnabled(True)
        self.words_title.show()
        self.empty_label.hide()
        for word in analysis.words:
            if word.ipa:
                self.cards.addWidget(self._card(word, analysis.lang))
        self.cards.addStretch(1)

    def show_error(self, msg: str) -> None:
        """Surface an analysis failure instead of showing an empty dock."""
        self.words_title.hide()
        self.empty_label.setText(
            self.tr("Pronunciation unavailable: {msg}").format(msg=msg))
        self.empty_label.show()

    # ------------------------------------------------------------ pieces
    def _clear_cards(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _card(self, word: WordPron, lang: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        row = QHBoxLayout(frame)
        row.setContentsMargins(px(10), px(6), px(10), px(6))
        row.setSpacing(px(10))

        spoken = "-".join(word.respell) or word.core
        stressed = spoken
        if 0 <= word.stress < len(word.respell):
            parts = list(word.respell)
            parts[word.stress] = parts[word.stress].upper()
            stressed = "-".join(parts)

        display = word.word.strip(".,;:!?\"'()…") or word.core
        text = QLabel(f"<b>{display}</b> &nbsp;"
                      f"<span style='color:#7a5cff'>{stressed}</span>")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        row.addWidget(text, 1)

        ipa = QLabel("/" + ".".join(word.syllables) + "/")
        ipa.setObjectName("cardIpa")
        row.addWidget(ipa)

        if word.liaison:
            note = QLabel("+liaison " + word.liaison)
            note.setObjectName("liaison")
            note.setToolTip(
                "The final consonant is linked to the next word "
                "(liaison) instead of staying silent.")
            row.addWidget(note)

        play = QPushButton("\u25b6")
        play.setFixedWidth(px(34))
        play.setToolTip(self.tr("Hear this word"))
        play.clicked.connect(lambda _=False, w=word: self._play_word(w, lang))
        row.addWidget(play)
        return frame

    # ------------------------------------------------------------ audio
    def _play_word(self, word: WordPron, lang: str) -> None:
        self._worker.request(word.core, lang, self._speed)

    def _play_sentence(self) -> None:
        if not self._analysis:
            return
        text = " ".join(w.core for w in self._analysis.words)
        if text:
            self._worker.request(text, self._analysis.lang, self._speed)

    def _ensure_player(self) -> QMediaPlayer:
        if self._player is None:
            self._audio = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._audio)
            self._player.errorOccurred.connect(self._on_player_error)
        return self._player

    def _on_fetched(self, text: str, lang: str, path: str) -> None:
        if not path:
            self.empty_label.setText(
                self.tr("Audio unavailable (offline?) - reading still works."))
            self.empty_label.show()
            return
        self.empty_label.hide()
        self._current_path = path
        # Qt's FFmpeg audio backend segfaults on WSLg (no PipeWire config),
        # so on Linux prefer the system player; Windows uses Qt first.
        if not sys.platform.startswith("win") and self._play_external(
                path, self._speed):
            return
        try:
            player = self._ensure_player()
            player.setSource(QUrl.fromLocalFile(path))
            player.setPlaybackRate(self._speed)
            self._audio.setVolume(0.9)
            player.play()
        except Exception:  # noqa: BLE001 - audio is optional sugar
            log.warning("qt playback failed", exc_info=True)
            if not self._play_external(path, self._speed):
                self.empty_label.setText(
                    self.tr("Audio unavailable here - reading still works."))
                self.empty_label.show()

    def _on_player_error(self, error, message: str) -> None:
        """Qt has no usable audio device - try the OS player instead."""
        if not self._play_external(self._current_path or "", self._speed):
            self.empty_label.setText(
                self.tr("Audio unavailable here ({msg}). "
                        "Reading still works.").format(msg=message))
            self.empty_label.show()

    def _play_external(self, path: str, speed: float = 1.0) -> bool:
        if not path:
            return False
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
                return True
            ffplay = shutil.which("ffplay")
            if ffplay:
                cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet"]
                if abs(speed - 1.0) > 0.01:
                    cmd += ["-af", f"atempo={speed:g}"]
                cmd.append(path)
                subprocess.Popen(cmd)
                return True
        except Exception:  # noqa: BLE001
            log.warning("external playback failed", exc_info=True)
        return False
