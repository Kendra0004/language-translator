"""Side panel: how a native speaker would say the text (IPA, syllables,
reading approximation, audio playback)."""
from __future__ import annotations

import logging
import os
import shutil
import sys
import threading

from PySide6.QtCore import (
    QObject, QProcess, QProcessEnvironment, Qt, QUrl, Signal,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..core import languages, tts
from ..core.pronunciation import Analysis, WordPron
from ..theme import px

log = logging.getLogger(__name__)


def _child_env(env: dict) -> dict:
    """Environment for the external player: bundle-free LD_LIBRARY_PATH.

    The frozen app's bootloader prepends the bundle to LD_LIBRARY_PATH so
    Qt finds its libraries - but the bundle also ships Qt's own FFmpeg
    copies (``libavutil.so.61``). On any machine whose system FFmpeg
    uses the same SONAME (e.g. FFmpeg 8.x: avutil.61/avfilter.12), the
    system ffplay then binds Qt's stripped copy and dies with
    ``symbol lookup error ... undefined symbol`` - silent no-sound on
    machines where the SONAMEs differ, hard failure where they match.

    So: remove only the entries inside our own bundle; anything the user
    set themselves stays. No-op in source runs (no ``sys.frozen``).
    """
    out = dict(env)
    ld = out.get("LD_LIBRARY_PATH")
    if not ld or not getattr(sys, "frozen", False):
        return out
    base = os.path.realpath(getattr(sys, "_MEIPASS", "") or "")
    if not base:
        return out
    keep = []
    for entry in ld.split(os.pathsep):
        if not entry:
            continue
        real = os.path.realpath(entry)
        if real == base or real.startswith(base + os.sep):
            continue  # our bundle - Qt's FFmpeg must not leak into ffplay
        keep.append(entry)
    if keep:
        out["LD_LIBRARY_PATH"] = os.pathsep.join(keep)
    else:
        out.pop("LD_LIBRARY_PATH", None)
    return out


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
        self._proc: QProcess | None = None   # watched ffplay, if running
        self._ext_reason: str = ""           # why the system player failed

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
    def _show_hint(self, msg: str) -> None:
        """One place every hint/failure message goes - never stay silent."""
        self.empty_label.setText(msg)
        self.empty_label.show()

    def _show_fetching(self) -> None:
        # The TTS download takes 1-2s; without this the click looked dead.
        self._ext_reason = ""
        self._show_hint(self.tr("Getting audio..."))

    def _play_word(self, word: WordPron, lang: str) -> None:
        self._show_fetching()
        self._worker.request(word.core, lang, self._speed)

    def _play_sentence(self) -> None:
        if self._analysis is None or not any(
                w.core for w in self._analysis.words):
            self._show_hint(self.tr(
                "Nothing to play yet - translate some text first."))
            return
        text = " ".join(w.core for w in self._analysis.words)
        self._show_fetching()
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
            self._show_hint(self.tr(
                "Audio unavailable (offline?) - reading still works."))
            return
        self.empty_label.hide()
        self._current_path = path
        # Qt's FFmpeg audio backend segfaults on WSLg (no PipeWire config),
        # so on Linux prefer the system player; Windows uses Qt first.
        if not sys.platform.startswith("win") and self._start_external(
                path, self._speed):
            return  # watched; a failure is surfaced by _on_external_finished
        self._play_qt()

    def _play_qt(self) -> None:
        """Play through Qt's backend (Windows' primary path)."""
        if not self._current_path:
            return
        try:
            player = self._ensure_player()
            player.setSource(QUrl.fromLocalFile(self._current_path))
            player.setPlaybackRate(self._speed)
            self._audio.setVolume(0.9)
            player.play()
        except Exception:  # noqa: BLE001 - audio is optional sugar
            log.warning("qt playback failed", exc_info=True)
            if sys.platform.startswith("win") and self._start_external(
                    self._current_path, self._speed):
                return  # Windows fallback: the system's default player
            self._surface_failure(self.tr("Qt player could not start"))

    def _on_player_error(self, error, message: str) -> None:
        """Qt has no usable audio device - try the system player once,
        then say why instead of going quiet."""
        if not self._ext_reason and self._start_external(
                self._current_path or "", self._speed):
            return
        self._surface_failure(message)

    def _surface_failure(self, detail: str) -> None:
        """Every audio failure ends up here: logged and shown in the
        panel. The old code returned on Popen() *starting* ffplay with
        -loglevel quiet, so a dead audio device meant total silence and
        no message at all."""
        if self._ext_reason and self._ext_reason not in detail:
            detail = f"{detail}; {self._ext_reason}"
        log.warning("audio playback unavailable: %s", detail)
        self._show_hint(self.tr(
            "Audio playback failed here ({detail}). "
            "Reading still works.").format(detail=detail))

    def _start_external(self, path: str, speed: float = 1.0) -> bool:
        """Play via the system player.

        Windows opens the file with the default app (synchronous).
        Linux starts ffplay as a *watched* QProcess: starting it does not
        mean sound came out, so the exit code and stderr decide whether
        playback worked. Returns False when no external player is
        available, so the caller can fall back to Qt.
        """
        if not path:
            return False
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
                return True
            ffplay = shutil.which("ffplay")
            if not ffplay:
                return False
            cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "warning"]
            if abs(speed - 1.0) > 0.01:
                cmd += ["-af", f"atempo={speed:g}"]
            cmd.append(path)
            old, self._proc = self._proc, None
            if old is not None and old.state() != \
                    QProcess.ProcessState.NotRunning:
                old.kill()  # a new Play click supersedes the old sound
            proc = QProcess(self)
            proc.setProcessChannelMode(
                QProcess.ProcessChannelMode.MergedChannels)
            # never let the bootloader-injected bundle libs (Qt's FFmpeg)
            # leak into the system player - see _child_env
            qenv = QProcessEnvironment()
            for key, val in _child_env(dict(os.environ)).items():
                qenv.insert(key, val)
            proc.setProcessEnvironment(qenv)
            proc.finished.connect(self._on_external_finished)
            proc.finished.connect(proc.deleteLater)
            proc.errorOccurred.connect(self._on_external_error)
            self._proc = proc
            proc.start(ffplay, cmd[1:])
            return True
        except Exception:  # noqa: BLE001
            log.warning("external playback failed", exc_info=True)
            return False

    def _on_external_finished(self, code: int, _status) -> None:
        proc = self.sender()
        if proc is not self._proc:
            return  # superseded by a newer Play click
        self._proc = None
        if code == 0:
            return  # played to the end - stay quiet
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        detail = lines[-1] if lines else f"ffplay exited with code {code}"
        # On Linux we do NOT fall through to Qt here: the Qt FFmpeg
        # backend is the one that segfaults on WSLg (see _on_fetched).
        self._ext_reason = "ffplay: " + detail
        self._surface_failure(self._ext_reason)

    def _on_external_error(self, error, _message: str) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return  # runtime problems arrive via finished()
        proc = self.sender()
        if proc is not self._proc:
            return
        self._proc = None
        self._ext_reason = "ffplay failed to start"
        # Same as "no external player": give Qt a chance.
        self._play_qt()
