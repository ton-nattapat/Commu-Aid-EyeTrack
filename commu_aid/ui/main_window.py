"""The full-screen window: message bar, the two pages, calibration and settings.

The layout is drawn on a fixed 1920x1080 canvas and scaled to fit the screen, so it looks the
same on any monitor. Every 16 ms the window reads new gaze samples, finds the button under the
gaze, and feeds the dwell engine.

Caregiver keys: F2 recalibrate, F3 settings, F4 pause / resume, Ctrl+G gaze dot on/off, F11 full screen, Ctrl+Q quit.
"""

from __future__ import annotations

import datetime
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QLabel, QWidget

from ..config import AppConfig, NeedTile
from ..dwell import DwellEngine
from ..gaze.filters import make_gaze_filter
from ..gaze.source import GazeSample, GazeSource
from ..predict import Predictor
from ..speech import Speaker
from ..targets import pick_target
from ..translate import TranslationError, Translator
from . import theme
from .calibration import CalibrationScreen
from .dwell_button import DwellButton
from .gaze_dot import GazeDot
from .message_bar import MessageBar
from .pages import KeyboardPage, NeedsPage, Page
from .pause_screen import PauseScreen
from .settings import SettingsPage

log = logging.getLogger(__name__)

DATA_DIR = Path("~/.commu_aid").expanduser()
SETTINGS_HINT_MIN_H = 30  # with a smaller bottom margin there is no room for the hint below the buttons


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(theme.CANVAS_W, theme.CANVAS_H)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(f"background: {theme.BACKGROUND.name()};")


class MainWindow(QGraphicsView):
    _translated = Signal(int, str, str, bool)  # request id, english, spoken text, ok

    def __init__(
        self,
        cfg: AppConfig,
        source: GazeSource,
        speaker: Speaker,
        translator: Translator,
        sounds,
        calibrate_on_start: bool = True,
    ):
        self._scene = QGraphicsScene()
        super().__init__(self._scene)
        self.cfg = cfg
        self.source = source
        self.speaker = speaker
        self.translator = translator
        self.sounds = sounds

        self.setWindowTitle("Communication Aid")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QBrush(Qt.black))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setMouseTracking(True)

        self.canvas = Canvas()
        self._scene.addWidget(self.canvas)
        self._scene.setSceneRect(QRectF(0, 0, theme.CANVAS_W, theme.CANVAS_H))

        area = theme.content_area(cfg.display.side_margin_px, cfg.display.bottom_margin_px)
        # Pause sits at the right end of the message bar row, lined up with the buttons below it.
        w = theme.BAR_BUTTON_W
        pause_x = area[0] + area[2] - w
        self.pause_button = self._bar_button("pause", "Pause", self.pause, "⏸️", pause_x)
        # On the keyboard page Speak and Needs sit beside Pause, and the message bar gives up the room for them.
        needs_x = pause_x - theme.GAP - w
        self.needs_button = self._bar_button("needs", "Needs", lambda: self.show_page(self.needs_page), "🏠", needs_x)
        speak_x = needs_x - theme.GAP - w
        self.speak_button = self._bar_button("speak", "Speak", self._on_speak, "🔊", speak_x)
        self.bar = MessageBar(self.canvas)
        self._bar_widths = {"needs": pause_x - theme.GAP - theme.MARGIN, "keyboard": speak_x - theme.GAP - theme.MARGIN}
        self.bar.setGeometry(theme.MARGIN, theme.BAR_Y, self._bar_widths["needs"], theme.BAR_H)

        self.needs_page = NeedsPage(
            cfg.needs, self._on_need, lambda: self.show_page(self.keyboard_page), area, self.canvas
        )
        self.predictor = Predictor(DATA_DIR / "words.json", extra_words=[n.label for n in cfg.needs])
        # The keyboard's side columns are big enough to sit nearer the screen edges than the keys.
        keyboard_area = theme.content_area(
            min(cfg.display.side_margin_px, theme.KEYBOARD_SIDE_MARGIN), cfg.display.bottom_margin_px
        )
        self.keyboard_page = KeyboardPage(
            self._on_letter, self._on_word, self._on_delete, self._on_clear, self._on_answer,
            keyboard_area, self.canvas,
        )
        self.page: Page = self.needs_page
        self.keyboard_page.hide()

        # A quiet hint for the nurse in the strip below the buttons; Settings, Pause and calibration cover it.
        self.settings_hint = QLabel("Caregiver: press F3 for Settings  (fn + F3 on a Mac)", self.canvas)
        self.settings_hint.setFont(theme.font(22))
        self.settings_hint.setStyleSheet(f"color: {theme.TEXT_QUIET.name()}; background: transparent;")
        self.settings_hint.setAlignment(Qt.AlignCenter)
        hint_top = area[1] + area[3]
        self.settings_hint.setGeometry(0, hint_top, theme.CANVAS_W, theme.CANVAS_H - hint_top)
        self.settings_hint.setVisible(theme.CANVAS_H - hint_top >= SETTINGS_HINT_MIN_H)

        self.settings = SettingsPage(cfg, self._apply_settings, self.close_settings, self.canvas)
        self.settings.hide()
        self.calibration: Optional[CalibrationScreen] = None
        self.pause_screen = PauseScreen(self.resume, cfg.pause.resume_dwell_s, self.canvas)
        self.pause_screen.hide()

        self.gaze_dot = GazeDot(self.canvas)
        self.gaze_dot.setGeometry(0, 0, theme.CANVAS_W, theme.CANVAS_H)
        self.show_gaze_dot = cfg.display.show_gaze_dot
        # The canvas is already in the scene, so children start hidden until shown.
        for widget in (self.bar, self.pause_button, self.needs_page, self.gaze_dot):
            widget.show()

        d = cfg.dwell
        self.dwell = DwellEngine(d.dwell_time_s, d.blink_grace_s, d.cooldown_s)
        self.resume_dwell = DwellEngine(cfg.pause.resume_dwell_s, d.blink_grace_s, d.cooldown_s)
        self.smoother = make_gaze_filter(
            cfg.gaze_filter, (cfg.display.width, cfg.display.height), reset_after_s=d.blink_grace_s
        )
        self.last_sample: Optional[GazeSample] = None
        self.typed = ""
        self.keyboard_page.set_suggestions(self.predictor.suggest(self.typed, KeyboardPage.SUGGESTIONS))
        self._request_id = 0
        self._translated.connect(self._on_translated)

        for keys, slot in (
            ("F2", self.open_calibration),
            ("F3", self.open_settings),
            ("F4", self.toggle_pause),
            ("Ctrl+G", self._toggle_gaze_dot),
            ("F11", self._toggle_full_screen),
            ("Ctrl+Q", self.close),
        ):
            QShortcut(QKeySequence(keys), self, activated=slot)

        if hasattr(source, "screen_provider"):
            source.screen_provider = self._screen
        source.start()

        self.bar.show_message(f"Look at a button for {d.dwell_time_s:g} seconds to choose it")
        if source.supports_calibration:
            if calibrate_on_start and cfg.calibration.on_startup:
                QTimer.singleShot(0, self.open_calibration)
            else:
                self._use_saved_calibration()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # Geometry

    def _screen(self):
        return self.screen()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def map_to_canvas(self, x: float, y: float) -> QPointF:
        """Gaze (0..1 across the monitor) to canvas coordinates."""
        geo = self._screen().geometry()
        global_pt = QPoint(round(geo.x() + x * geo.width()), round(geo.y() + y * geo.height()))
        return self.mapToScene(self.mapFromGlobal(global_pt))

    # Gaze loop

    def _tick(self) -> None:
        now = time.monotonic()
        for raw in self.source.poll():
            self.last_sample = self.smoother.add(raw)
            if self.calibration is not None:
                self.calibration.feed(raw)  # unfiltered: the calibration screen shows and measures every sample

        if self.calibration is not None or self.settings.isVisible():
            self.gaze_dot.set_point(None)
            return

        point = None
        s = self.last_sample
        if s is not None and s.valid and now - s.t <= self.cfg.dwell.blink_grace_s:
            point = self.map_to_canvas(s.x, s.y)

        if self.paused:
            buttons, engine = self.pause_screen.buttons, self.resume_dwell
        else:
            buttons, engine = [*self.page.buttons, *self._bar_buttons()], self.dwell

        target = None
        if point is not None:
            rects = []
            for b in buttons:
                if not b.isHidden():
                    pos = b.mapTo(self.canvas, QPoint(0, 0))
                    rects.append((b.key, (pos.x(), pos.y(), b.width(), b.height())))
            target = pick_target(point.x(), point.y(), rects, self.cfg.display.snap_px)

        update = engine.update(target, now)
        selected = None
        for b in buttons:
            b.set_state(b.key == target, update.progress if b.key == update.target else 0.0)
            if b.key == update.selected:
                selected = b
        if selected is not None:
            self.sounds.click()
            selected.activate()

        self.gaze_dot.set_point(point if self.show_gaze_dot else None)

    # Pages

    def _bar_button(self, key: str, label: str, on_select, icon: str, x: int) -> DwellButton:
        button = DwellButton(key, label, on_select, icon=icon, variant="nav", label_px=40)
        button.setParent(self.canvas)
        button.setGeometry(x, theme.BAR_Y, theme.BAR_BUTTON_W, theme.BAR_H)
        return button

    def _bar_buttons(self):
        """The buttons in the message bar row on the current page."""
        if self.page is self.keyboard_page:
            return [self.speak_button, self.needs_button, self.pause_button]
        return [self.pause_button]

    def show_page(self, page: Page) -> None:
        if page is self.page:
            return
        self.page.hide()
        for b in (*self.page.buttons, *self._bar_buttons()):
            b.set_state(False, 0.0)
        self.page = page
        page.show()
        keyboard = page is self.keyboard_page
        self.speak_button.setVisible(keyboard)
        self.needs_button.setVisible(keyboard)
        self.bar.resize(self._bar_widths["keyboard" if keyboard else "needs"], theme.BAR_H)
        self.gaze_dot.raise_()
        if page is self.keyboard_page:
            self._show_typed()

    def _on_need(self, tile: NeedTile) -> None:
        self.bar.show_message(tile.label, tile.thai)
        self._log(tile.label, tile.thai)
        if tile.action == "alert":
            self.sounds.alert()
            QTimer.singleShot(2200, lambda: self.speaker.speak(tile.thai, "th"))
        else:
            self.speaker.speak(tile.thai, "th")

    def _show_typed(self, note: str = "", warning: bool = False) -> None:
        self.bar.show_typing(self.typed, note, warning)
        self.keyboard_page.set_suggestions(self.predictor.suggest(self.typed, KeyboardPage.SUGGESTIONS))

    def _show_status(self, message: str, note: str = "", warning: bool = False) -> None:
        """A status line such as "Welcome back". On the keyboard page the typed text stays in the box,
        because the next key adds to it, and the status shows as a small note underneath."""
        if self.page is self.keyboard_page:
            self._show_typed(f"{message}. {note}" if note else message, warning)
        else:
            self.bar.show_message(message, note=note, warning=warning)

    def _sentence(self) -> str:
        return " ".join(self.typed.split()).capitalize()

    def _on_answer(self, english: str, thai: str) -> None:
        """Yes or No: spoken at once, and the typed text stays for the next key."""
        self.bar.show_message(english, thai)
        self._log(english, thai)
        self.speaker.speak(thai, "th")

    def _on_letter(self, ch: str) -> None:
        self.typed += ch
        self._show_typed()

    def _on_word(self, word: str) -> None:
        """Replace the word being typed with the chosen one, then a space."""
        if not word:
            return
        stem = self.typed.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.typed = stem + word + " "
        self._show_typed()

    def _on_delete(self) -> None:
        self.typed = self.typed[:-1]
        self._show_typed()

    def _on_clear(self) -> None:
        self.typed = ""
        self._show_typed()

    def _on_speak(self) -> None:
        text = self._sentence()
        if not text:
            return
        self.predictor.learn(text)
        self._request_id += 1
        request = self._request_id
        lang = self.cfg.language
        if lang.speak == "th" and lang.translate and self.translator.enabled:
            self.bar.show_message(text, note="Translating...")

            def work():
                try:
                    self._translated.emit(request, text, self.translator.translate(text), True)
                except TranslationError as exc:
                    log.warning("Translation failed: %s", exc)
                    self._translated.emit(request, text, text, False)

            threading.Thread(target=work, name="translate", daemon=True).start()
        else:
            self._translated.emit(request, text, text, lang.speak != "th")

    def _on_translated(self, request: int, english: str, spoken: str, ok: bool) -> None:
        if request != self._request_id:
            return  # a newer message replaced this one
        thai = ok and spoken != english
        # If the patient kept typing while it translated, speak it but leave their new text in the box.
        if not (self.page is self.keyboard_page and self._sentence() != english):
            if thai:
                self.bar.show_message(english, spoken)
            elif not ok:
                self.bar.show_message(english, note="Translation failed, speaking English", warning=True)
            else:
                self.bar.show_message(english)
        if thai:
            self.speaker.speak(spoken, "th")
        else:
            self.speaker.speak(english, "en")
        self._log(english, spoken if thai else "")

    def _log(self, english: str, thai: str) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().isoformat(timespec="seconds")
            with open(DATA_DIR / "messages.log", "a", encoding="utf-8") as f:
                f.write(f"{stamp}\t{english}\t{thai}\n")
        except OSError:
            log.exception("Could not write the message log")

    # Pause

    @property
    def paused(self) -> bool:
        return self.pause_screen.isVisible()

    def pause(self) -> None:
        if self.paused:
            return
        for b in (*self.page.buttons, *self._bar_buttons()):
            b.set_state(False, 0.0)
        self.resume_dwell.dwell_time_s = self.cfg.pause.resume_dwell_s
        self.resume_dwell.reset()
        self.pause_screen.resume_dwell_s = self.cfg.pause.resume_dwell_s
        self.pause_screen.show()
        self.pause_screen.raise_()
        self.gaze_dot.raise_()

    def resume(self) -> None:
        if not self.paused:
            return
        self.pause_screen.hide()
        self.pause_screen.resume_button.set_state(False, 0.0)
        self.dwell.reset()
        self._show_status("Welcome back", note="Look at a button to choose it")

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    # Calibration

    def open_calibration(self) -> None:
        if not self.source.supports_calibration or self.calibration is not None:
            return
        self.close_settings()
        self.calibration = CalibrationScreen(
            self.source, self.map_to_canvas, self.cfg.calibration.auto_accept_max_error_px,
            self.cfg.calibration.redo_point_px, self.canvas, show_live_gaze=self.cfg.calibration.show_live_gaze,
        )
        self.calibration.finished.connect(self._on_calibration_finished)
        self.calibration.show()
        self.calibration.setFocus()

    def _on_calibration_finished(self, outcome: str) -> None:
        path = self.cfg.calibration.saved_path
        if outcome == "accepted":
            try:
                self.source.save_calibration(path)
            except Exception:
                log.exception("Could not save calibration")
            self._show_status("Calibration done", note="Look at a button to choose it")
        else:
            self._use_saved_calibration()
        self.calibration.hide()
        self.calibration.deleteLater()
        self.calibration = None
        self.dwell.reset()
        self.setFocus()

    def _use_saved_calibration(self) -> None:
        try:
            loaded = self.source.load_calibration(self.cfg.calibration.saved_path)
        except Exception:
            log.exception("Could not load saved calibration")
            loaded = False
        if loaded:
            self._show_status("Using the saved calibration", note="F2 to recalibrate")
        else:
            self._show_status("Not calibrated", note="Press F2 to calibrate", warning=True)

    # Settings

    def open_settings(self) -> None:
        if self.calibration is not None:
            return
        self.settings.load()
        self.settings.show()
        self.settings.raise_()
        self.settings.setFocus()

    def close_settings(self) -> None:
        if self.settings.isVisible():
            self.settings.hide()
            self.dwell.reset()
            self.setFocus()

    def _apply_settings(self) -> None:
        self.dwell.dwell_time_s = self.cfg.dwell.dwell_time_s
        self.needs_page.set_needs(self.cfg.needs)
        self._show_status("Settings saved", note=f"Dwell time {self.cfg.dwell.dwell_time_s:.1f} s")

    # Caregiver keys

    def _toggle_gaze_dot(self) -> None:
        self.show_gaze_dot = not self.show_gaze_dot

    def _toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        try:
            self.source.stop()
        finally:
            self.speaker.close()
        super().closeEvent(event)
