"""Start-up calibration: position check, 5-point calibration, validation, then Accept or Retry.

The caregiver drives this screen with the keyboard or mouse:
  Space  start calibration (from the position check)
  Enter  accept the result
  R      retry
  Esc    skip, and use the last saved calibration instead
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from ..gaze.source import GazeSample
from . import theme

CALIBRATION_POINTS = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)]
VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.7, 0.7)]
SHRINK_S = 1.2  # target shrinks to draw the eye before data is collected
SETTLE_S = 0.8  # validation: ignore gaze while the eye moves to the target
MEASURE_S = 1.0  # validation: average gaze over this long
GOOD_PX = 60  # under this error a point is shown in the accent colour, above it in orange

BUTTON_STYLE = (
    "QPushButton { background: #24324a; color: #f4f6f8; border: 2px solid #3a4652; border-radius: 16px; }"
    "QPushButton:hover { border-color: #f2c94c; }"
)


@dataclass
class PointError:
    x: float
    y: float
    error_px: Optional[float]


class CalibrationScreen(QWidget):
    finished = Signal(str)  # "accepted" | "skipped"
    _worker_done = Signal(object)

    def __init__(self, source, map_to_canvas: Callable[[float, float], QPointF], auto_accept_px: float = 0, parent=None):
        super().__init__(parent)
        self.source = source
        self.map_to_canvas = map_to_canvas
        self.auto_accept_px = auto_accept_px
        self.setGeometry(0, 0, theme.CANVAS_W, theme.CANVAS_H)
        self.setFocusPolicy(Qt.StrongFocus)
        self.stage = "position"
        self.message = ""
        self.point_index = 0
        self.stage_started = 0.0
        self.calibration_ok = False
        self.calibration_errors: List[PointError] = []
        self.validation_errors: List[PointError] = []
        self._samples: List[Tuple[float, float]] = []
        self._worker_done.connect(self._on_worker_done)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self._buttons = {}
        for name, text, slot in (
            ("start", "Start calibration (Space)", self.start_calibration),
            ("accept", "Accept (Enter)", self.accept),
            ("retry", "Retry (R)", self.start_calibration),
            ("skip", "Skip, use saved (Esc)", self.skip),
        ):
            b = QPushButton(text, self)
            b.setFont(theme.font(28, bold=True))
            b.setStyleSheet(BUTTON_STYLE)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(slot)
            self._buttons[name] = b
        self._show_buttons("start", "skip")

    # Gaze from the main window, used for validation.
    def feed(self, sample: GazeSample) -> None:
        if self.stage != "validate" or not sample.valid:
            return
        elapsed = time.monotonic() - self.stage_started
        if SETTLE_S <= elapsed <= SETTLE_S + MEASURE_S:
            pt = self.map_to_canvas(sample.x, sample.y)
            self._samples.append((pt.x(), pt.y()))

    # Flow

    def start_calibration(self) -> None:
        if self.stage in ("calibrate", "computing", "validate"):
            return
        self._show_buttons()
        self.stage = "calibrate"
        self.point_index = 0
        self.message = "Look at the dot"
        self.source.enter_calibration()
        self._begin_point()

    def _begin_point(self) -> None:
        self.stage_started = time.monotonic()
        self._collecting = False

    def _run_in_worker(self, fn) -> None:
        def run():
            try:
                result = fn()
            except Exception as exc:  # reported on screen; caregiver can retry or skip
                result = exc
            self._worker_done.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def _on_worker_done(self, result) -> None:
        if isinstance(result, Exception):
            self._fail(f"Calibration error: {result}")
            return
        if self.stage == "calibrate":
            if not result:
                self._fail("The tracker could not see the eyes at that point.")
                return
            self.point_index += 1
            if self.point_index < len(CALIBRATION_POINTS):
                self._begin_point()
            else:
                self.stage = "computing"
                self.message = "Computing..."
                self._run_in_worker(lambda: self.source.compute(theme.CANVAS_W, theme.CANVAS_H))
        elif self.stage == "computing":
            self.source.leave_calibration()
            ok, points = result
            self.calibration_ok = ok
            self.calibration_errors = [PointError(p.x, p.y, p.mean_error_px) for p in points]
            if not ok:
                self._fail("Calibration failed. Check the patient's position and retry.")
                return
            self.stage = "validate"
            self.point_index = 0
            self.validation_errors = []
            self.message = "Look at the dot"
            self._begin_validation_point()

    def _begin_validation_point(self) -> None:
        self._samples = []
        self.stage_started = time.monotonic()

    def _finish_validation_point(self) -> None:
        x, y = VALIDATION_POINTS[self.point_index]
        target = self.map_to_canvas(x, y)
        if self._samples:
            mx = sum(s[0] for s in self._samples) / len(self._samples)
            my = sum(s[1] for s in self._samples) / len(self._samples)
            err = math.hypot(mx - target.x(), my - target.y())
        else:
            err = None
        self.validation_errors.append(PointError(x, y, err))
        self.point_index += 1
        if self.point_index < len(VALIDATION_POINTS):
            self._begin_validation_point()
        else:
            self._show_result()

    def _show_result(self) -> None:
        self.stage = "result"
        errors = [p.error_px for p in self.validation_errors]
        valid = [e for e in errors if e is not None]
        if valid:
            self.message = f"Average error {sum(valid) / len(valid):.0f} px, worst {max(valid):.0f} px"
        else:
            self.message = "No gaze was measured during validation"
        if len(valid) < len(errors):
            self.message += f" ({len(errors) - len(valid)} point(s) not seen)"
        self._show_buttons("accept", "retry", "skip")
        if self.auto_accept_px > 0 and len(valid) == len(errors) and max(valid) <= self.auto_accept_px:
            self.message += ". Accepting automatically."
            QTimer.singleShot(1500, self.accept)

    def _fail(self, message: str) -> None:
        try:
            self.source.leave_calibration()
        except Exception:
            pass
        self.stage = "result"
        self.message = message
        self.validation_errors = []
        self._show_buttons("retry", "skip")

    def accept(self) -> None:
        if self.stage != "result" or not self.calibration_ok:
            return
        self.finished.emit("accepted")

    def skip(self) -> None:
        if self.stage in ("calibrate", "computing"):
            try:
                self.source.leave_calibration()
            except Exception:
                pass
        self.finished.emit("skipped")

    # Timer

    def _tick(self) -> None:
        now = time.monotonic()
        if self.stage == "calibrate" and not self._collecting and now - self.stage_started >= SHRINK_S:
            self._collecting = True
            x, y = CALIBRATION_POINTS[self.point_index]
            self._run_in_worker(lambda: self.source.collect(x, y))
        elif self.stage == "validate" and now - self.stage_started >= SETTLE_S + MEASURE_S:
            self._finish_validation_point()
        self.update()

    # Keys

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Space and self.stage == "position":
            self.start_calibration()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        elif key == Qt.Key_R and self.stage == "result":
            self.start_calibration()
        elif key == Qt.Key_Escape:
            self.skip()
        else:
            super().keyPressEvent(event)

    # Drawing

    def _show_buttons(self, *names: str) -> None:
        x = theme.CANVAS_W - theme.MARGIN
        for name in reversed(list(self._buttons)):
            b = self._buttons[name]
            b.setVisible(name in names)
        for name in reversed(names):
            b = self._buttons[name]
            w = 420
            x -= w
            b.setGeometry(x, theme.CANVAS_H - 120, w, 72)
            x -= 24

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), theme.BACKGROUND)
        if self.stage == "position":
            self._paint_position(p)
        elif self.stage == "calibrate":
            self._paint_target(p, CALIBRATION_POINTS[self.point_index], shrink=True)
        elif self.stage == "validate":
            self._paint_target(p, VALIDATION_POINTS[self.point_index], shrink=False)
        elif self.stage == "computing":
            self._paint_text(p, self.message, theme.CANVAS_H / 2)
        elif self.stage == "result":
            self._paint_result(p)
        p.end()

    def _paint_text(self, p: QPainter, text: str, y: float, px: int = 40, color=None) -> None:
        p.setPen(color or theme.TEXT)
        p.setFont(theme.font(px, bold=True))
        p.drawText(QRectF(0, y - px, theme.CANVAS_W, px * 2), Qt.AlignCenter, text)

    def _paint_position(self, p: QPainter) -> None:
        self._paint_text(p, "Calibration", 120, 64)
        self._paint_text(
            p, "Caregiver: move the screen or bed until both eyes sit inside the box, then press Space.", 220, 32, theme.TEXT_QUIET
        )
        box = QRectF(theme.CANVAS_W / 2 - 400, 320, 800, 500)
        zone = box.adjusted(200, 125, -200, -125)
        p.setPen(QPen(theme.BORDER, 3))
        p.drawRoundedRect(box, 24, 24)
        p.setPen(QPen(theme.HOVER, 3, Qt.DashLine))
        p.drawRoundedRect(zone, 16, 16)
        left, right = self.source.user_position()
        status = "Eyes not found"
        if left is not None and right is not None:
            seen = [e for e in (left, right) if e.valid]
            for e in seen:
                # The tracker looks at the patient, so x is mirrored to match what the caregiver sees.
                pt = QPointF(box.left() + (1 - e.x) * box.width(), box.top() + e.y * box.height())
                radius = 18 + (1 - e.z) * 30  # bigger when closer
                p.setPen(Qt.NoPen)
                p.setBrush(theme.HOVER if zone.contains(pt) else theme.WARNING)
                p.drawEllipse(pt, radius, radius)
            if seen:
                z = sum(e.z for e in seen) / len(seen)
                status = "Move closer" if z > 0.7 else "Move further away" if z < 0.3 else "Distance OK"
        self._paint_text(p, status, 880, 36)

    def _paint_target(self, p: QPainter, point, shrink: bool) -> None:
        center = self.map_to_canvas(*point)
        elapsed = time.monotonic() - self.stage_started
        if shrink:
            t = min(1.0, elapsed / SHRINK_S)
            radius = 48 - 34 * t
        else:
            radius = 20
        p.setPen(Qt.NoPen)
        p.setBrush(theme.HOVER)
        p.drawEllipse(center, radius, radius)
        p.setBrush(theme.BACKGROUND)
        p.drawEllipse(center, 5, 5)

    def _paint_result(self, p: QPainter) -> None:
        self._paint_text(p, "Calibration result", 100, 56)
        self._paint_text(p, self.message, 180, 34, theme.TEXT_QUIET)
        p.setFont(theme.font(26, bold=True))
        for pe in self.calibration_errors:
            self._paint_error(p, pe, theme.TEXT_QUIET)
        for pe in self.validation_errors:
            color = theme.WARNING if pe.error_px is None or pe.error_px > GOOD_PX else theme.HOVER
            self._paint_error(p, pe, color)

    def _paint_error(self, p: QPainter, pe: PointError, color) -> None:
        center = self.map_to_canvas(pe.x, pe.y)
        p.setPen(QPen(color, 3))
        p.setBrush(Qt.NoBrush)
        radius = max(10.0, min(pe.error_px if pe.error_px is not None else 40.0, 200.0))
        p.drawEllipse(center, radius, radius)
        p.drawLine(center + QPointF(-8, 0), center + QPointF(8, 0))
        p.drawLine(center + QPointF(0, -8), center + QPointF(0, 8))
        label = "not seen" if pe.error_px is None else f"{pe.error_px:.0f} px"
        p.drawText(QRectF(center.x() - 100, center.y() + radius + 4, 200, 34), Qt.AlignCenter, label)
