"""Start-up calibration: position check, 5-point calibration, validation, then Accept or Retry.

A calibration point whose data came out much worse than the rest (typically a bottom corner, where
the eyelids cover the eyes from the tracker's view) is shown once more and collected again before
validation. The result screen draws a line from each dot to where the gaze actually landed, and
says so when every point misses in the same outward or inward direction, which points at a wrong
screen size in Tobii Pro Eye Tracker Manager's Display Setup rather than at the patient. It also
plots every gaze sample behind each result: per eye (blue left, pink right) where the tracker
reports eyes separately, hollow for samples the tracker left out of the calibration.

The live gaze is drawn on every stage of this screen, unfiltered, so the caregiver can see what the
tracker sees. The patient may follow the dot instead of the target; G hides it.

The caregiver drives this screen with the keyboard or mouse:
  Space  start calibration (from the position check)
  Enter  accept the result
  R      retry
  Esc    skip, and use the last saved calibration instead
  G      show or hide the live gaze
  S      show or hide the gaze samples on the result screen
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from ..gaze.source import GazeSample
from . import theme

CALIBRATION_POINTS = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)]
VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.7, 0.7)]
SHRINK_S = 1.2  # target shrinks to draw the eye before data is collected
SETTLE_S = 0.8  # validation: ignore gaze while the eye moves to the target
MEASURE_S = 1.0  # validation: average gaze over this long
GOOD_PX = 60  # under this error a point is shown in the accent colour, above it in orange
FACE_W_PX = 300  # position check: width of the face mask at a good distance (z = 0.5)
LIVE_TRAIL_S = 0.3  # live gaze: recent samples drawn as a fading trail behind the current one
LIVE_STALE_S = 0.3  # live gaze: hide it when no valid sample came for this long (blink, eyes lost)
DISPLAY_SETUP_HINT = "check the screen size in Eye Tracker Manager > Display Setup"

BUTTON_STYLE = (
    "QPushButton { background: #24324a; color: #f4f6f8; border: 2px solid #3a4652; border-radius: 16px; }"
    "QPushButton:hover { border-color: #f2c94c; }"
)


@dataclass
class PointError:
    x: float  # target, 0..1
    y: float
    error_px: Optional[float]
    gaze: Optional[QPointF] = None  # where the gaze landed on average, canvas coordinates
    samples: List["Sample"] = field(default_factory=list)  # every gaze sample behind the result


@dataclass
class Sample:
    """One gaze sample to plot, canvas coordinates."""

    eye: str  # "left" | "right" | "both" (no per-eye data)
    pos: QPointF
    used: bool = True  # False: the tracker left it out of the calibration


def eye_samples(sample: GazeSample, map_to_canvas) -> List[Sample]:
    """A live gaze sample as one point per eye, or one combined point when the source has no per-eye data."""
    if sample.left is None and sample.right is None:
        return [Sample("both", map_to_canvas(sample.x, sample.y))]
    return [
        Sample(eye, map_to_canvas(*pt))
        for eye, pt in (("left", sample.left), ("right", sample.right))
        if pt is not None
    ]


def radial_pattern(points: List[Tuple[float, float, float, float]], centre: Tuple[float, float]) -> Optional[str]:
    """'outward' or 'inward' when every off-centre miss points away from or towards the screen centre.

    Each point is (target x, target y, gaze x, gaze y) in pixels. A display area set up for a bigger
    or smaller screen than the real one scales gaze around the centre like this; a patient or head
    position problem does not. Needs at least 3 off-centre points that each miss by more than GOOD_PX.
    """
    signs = []
    for tx, ty, gx, gy in points:
        rx, ry = tx - centre[0], ty - centre[1]
        r = math.hypot(rx, ry)
        ex, ey = gx - tx, gy - ty
        err = math.hypot(ex, ey)
        if r < 1:
            continue  # the centre point has no outward direction
        if err <= GOOD_PX:
            return None
        radial = (ex * rx + ey * ry) / r
        if abs(radial) < 0.7 * err:
            return None  # mostly sideways: not a scale error
        signs.append(radial > 0)
    if len(signs) < 3 or len(set(signs)) != 1:
        return None
    return "outward" if signs[0] else "inward"


class CalibrationScreen(QWidget):
    finished = Signal(str)  # "accepted" | "skipped"
    _worker_done = Signal(object)

    def __init__(
        self, source, map_to_canvas: Callable[[float, float], QPointF], auto_accept_px: float = 0,
        redo_px: float = 0, parent=None, show_live_gaze: bool = True,
    ):
        super().__init__(parent)
        self.source = source
        self.map_to_canvas = map_to_canvas
        self.auto_accept_px = auto_accept_px
        self.redo_px = redo_px
        self.points: List[Tuple[float, float]] = list(CALIBRATION_POINTS)  # being collected in this pass
        self._redone = False
        self.setGeometry(0, 0, theme.CANVAS_W, theme.CANVAS_H)
        self.setFocusPolicy(Qt.StrongFocus)
        self.stage = "position"
        self.message = ""
        self.hint = ""
        self.point_index = 0
        self.stage_started = 0.0
        self.calibration_ok = False
        self.calibration_errors: List[PointError] = []
        self.validation_errors: List[PointError] = []
        self._samples: List[Tuple[float, float]] = []
        self._raw_samples: List[Sample] = []  # validation: every sample measured at the current point
        self.show_live_gaze = show_live_gaze
        self.show_samples = True
        self._live: "deque[Tuple[float, QPointF, List[Sample]]]" = deque()  # (time, combined, per eye)
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

    # Unfiltered gaze from the main window: drawn live, and measured during validation.
    def feed(self, sample: GazeSample) -> None:
        if not sample.valid:
            return
        pt = self.map_to_canvas(sample.x, sample.y)
        eyes = eye_samples(sample, self.map_to_canvas)
        self._live.append((sample.t, pt, eyes))
        while self._live and self._live[0][0] < sample.t - LIVE_TRAIL_S:
            self._live.popleft()
        if self.stage != "validate":
            return
        elapsed = time.monotonic() - self.stage_started
        if SETTLE_S <= elapsed <= SETTLE_S + MEASURE_S:
            self._samples.append((pt.x(), pt.y()))
            self._raw_samples.extend(eyes)

    # Flow

    def start_calibration(self) -> None:
        if self.stage in ("calibrate", "computing", "validate"):
            return
        self._show_buttons()
        self.stage = "calibrate"
        self.points = list(CALIBRATION_POINTS)
        self._redone = False
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
            if self.point_index < len(self.points):
                self._begin_point()
            else:
                self.stage = "computing"
                self.message = "Computing..."
                self._run_in_worker(lambda: self.source.compute(theme.CANVAS_W, theme.CANVAS_H))
        elif self.stage == "computing":
            ok, points = result
            if ok and self._redo_bad_points(points):
                return
            self.source.leave_calibration()
            self.calibration_ok = ok
            self.calibration_errors = [
                PointError(
                    p.x, p.y, p.mean_error_px,
                    self.map_to_canvas(p.gaze_x, p.gaze_y) if p.gaze_x is not None else None,
                    [Sample(s.eye, self.map_to_canvas(s.x, s.y), s.used) for s in getattr(p, "samples", [])],
                )
                for p in points
            ]
            if not ok:
                self._fail("Calibration failed. Check the patient's position and retry.")
                return
            self.stage = "validate"
            self.point_index = 0
            self.validation_errors = []
            self.message = "Look at the dot"
            self._begin_validation_point()

    def _redo_bad_points(self, points) -> bool:
        """Once per calibration, collect again the points that came out far worse than redo_px. True if started."""
        if self._redone or self.redo_px <= 0:
            return False
        # The tracker reports points back as float32; use our own coordinates when discarding and recollecting.
        bad = [
            min(CALIBRATION_POINTS, key=lambda c: math.hypot(c[0] - p.x, c[1] - p.y))
            for p in points
            if p.mean_error_px is None or p.mean_error_px > self.redo_px
        ]
        if not bad or len(bad) == len(points):
            return False  # nothing to fix, or everything is bad: a full retry is the better answer
        self._redone = True
        for x, y in bad:
            self.source.discard(x, y)
        self.points = bad
        self.point_index = 0
        self.stage = "calibrate"
        self.message = "Once more: look at the dot"
        self._begin_point()
        return True

    def _begin_validation_point(self) -> None:
        self._samples = []
        self._raw_samples = []
        self.stage_started = time.monotonic()

    def _finish_validation_point(self) -> None:
        x, y = VALIDATION_POINTS[self.point_index]
        target = self.map_to_canvas(x, y)
        if self._samples:
            mx = sum(s[0] for s in self._samples) / len(self._samples)
            my = sum(s[1] for s in self._samples) / len(self._samples)
            err = math.hypot(mx - target.x(), my - target.y())
            gaze = QPointF(mx, my)
        else:
            err, gaze = None, None
        self.validation_errors.append(PointError(x, y, err, gaze, self._raw_samples))
        self.point_index += 1
        if self.point_index < len(VALIDATION_POINTS):
            self._begin_validation_point()
        else:
            self._show_result()

    def _show_result(self) -> None:
        self.stage = "result"
        self.hint = ""
        errors = [p.error_px for p in self.validation_errors]
        valid = [e for e in errors if e is not None]
        if valid:
            self.message = f"Average error {sum(valid) / len(valid):.0f} px, worst {max(valid):.0f} px"
        else:
            self.message = "No gaze was measured during validation"
        if len(valid) < len(errors):
            self.message += f" ({len(errors) - len(valid)} point(s) not seen)"
        centre = self.map_to_canvas(0.5, 0.5)
        pattern = radial_pattern(
            [
                (t.x(), t.y(), pe.gaze.x(), pe.gaze.y())
                for pe in self.validation_errors
                if pe.gaze is not None
                for t in (self.map_to_canvas(pe.x, pe.y),)
            ],
            (centre.x(), centre.y()),
        )
        if pattern:
            where = "outside" if pattern == "outward" else "inside"
            self.hint = f"Gaze lands {where} every dot: {DISPLAY_SETUP_HINT}"
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
        self.hint = ""
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
            x, y = self.points[self.point_index]
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
        elif key == Qt.Key_G:
            self.show_live_gaze = not self.show_live_gaze
        elif key == Qt.Key_S and self.stage == "result":
            self.show_samples = not self.show_samples
        else:
            super().keyPressEvent(event)

    # Drawing

    def _show_buttons(self, *names: str) -> None:
        # Centred, so the bottom corner calibration points and their samples stay in view.
        w, gap = 380, 24
        x = (theme.CANVAS_W - len(names) * w - (len(names) - 1) * gap) // 2
        for name, b in self._buttons.items():
            b.setVisible(name in names)
        for name in names:
            self._buttons[name].setGeometry(x, theme.CANVAS_H - 120, w, 72)
            x += w + gap

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), theme.BACKGROUND)
        if self.stage == "position":
            self._paint_position(p)
        elif self.stage == "calibrate":
            self._paint_target(p, self.points[self.point_index], shrink=True)
        elif self.stage == "validate":
            self._paint_target(p, VALIDATION_POINTS[self.point_index], shrink=False)
        elif self.stage == "computing":
            self._paint_text(p, self.message, theme.CANVAS_H / 2)
        elif self.stage == "result":
            self._paint_result(p)
        if self.show_live_gaze:
            self._paint_live(p)
        p.end()

    def _paint_live(self, p: QPainter) -> None:
        if not self._live or time.monotonic() - self._live[-1][0] > LIVE_STALE_S:
            return
        p.setPen(Qt.NoPen)
        newest = self._live[-1][0]
        for t, pt, _eyes in self._live:
            color = QColor(theme.GAZE_DOT)
            color.setAlphaF(0.5 * max(0.0, 1 - (newest - t) / LIVE_TRAIL_S))
            p.setBrush(color)
            p.drawEllipse(pt, 6, 6)
        _t, pt, eyes = self._live[-1]
        p.setPen(QPen(theme.TEXT, 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(pt, 14, 14)
        p.setPen(Qt.NoPen)
        for s in eyes:
            p.setBrush(_eye_color(s.eye))
            p.drawEllipse(s.pos, 5, 5)

    def _paint_text(self, p: QPainter, text: str, y: float, px: int = 40, color=None) -> None:
        p.setPen(color or theme.TEXT)
        p.setFont(theme.font(px, bold=True))
        p.drawText(QRectF(0, y - px, theme.CANVAS_W, px * 2), Qt.AlignCenter, text)

    def _paint_position(self, p: QPainter) -> None:
        self._paint_text(p, "Calibration", 120, 64)
        self._paint_text(
            p, "Caregiver: move the screen or bed until the face fits the dashed outline, then press Space.", 220, 32,
            theme.TEXT_QUIET,
        )
        box = QRectF(theme.CANVAS_W / 2 - 400, 320, 800, 500)
        zone = box.adjusted(200, 125, -200, -125)
        p.setPen(QPen(theme.BORDER, 3))
        p.drawRoundedRect(box, 24, 24)
        p.setPen(QPen(theme.HOVER, 3, Qt.DashLine))
        p.drawRoundedRect(zone, 16, 16)
        left, right = self.source.user_position()
        status = "Eyes not found"
        p.save()
        p.setClipRect(box)
        # Where the face should be: centred in the box at a good distance.
        self._paint_face(p, zone.center(), 0.5, 0.0, theme.TEXT_QUIET, dashed=True)
        if left is not None and right is not None:
            seen = [e for e in (left, right) if e.valid]
            # The tracker looks at the patient, so x is mirrored to match what the caregiver sees.
            pts = [QPointF(box.left() + (1 - e.x) * box.width(), box.top() + e.y * box.height()) for e in seen]
            if seen:
                z = sum(e.z for e in seen) / len(seen)
                status = "Move closer" if z > 0.7 else "Move further away" if z < 0.3 else "Distance OK"
            if len(seen) == 2:
                # The face mask follows the head: centred between the eyes, tilted with them, bigger when closer.
                good = status == "Distance OK" and all(zone.contains(pt) for pt in pts)
                a, b = sorted(pts, key=lambda q: q.x())
                angle = math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))
                self._paint_face(p, (a + b) / 2, z, angle, theme.HOVER if good else theme.WARNING)
            for pt, e in zip(pts, seen):
                radius = 18 + (1 - e.z) * 30  # bigger when closer
                p.setPen(Qt.NoPen)
                p.setBrush(theme.HOVER if zone.contains(pt) else theme.WARNING)
                p.drawEllipse(pt, radius, radius)
        p.restore()
        self._paint_text(p, status, 880, 36)

    def _paint_face(self, p: QPainter, eyes: QPointF, z: float, angle: float, color, dashed: bool = False) -> None:
        """A head outline with its eye line at `eyes`, sized by distance z (0 near, 1 far) and rotated by angle."""
        w = FACE_W_PX * (1.5 - min(max(z, 0.0), 1.0))
        h = 1.3 * w
        p.save()
        p.translate(eyes)
        p.rotate(angle)
        p.setPen(QPen(color, 3, Qt.DashLine if dashed else Qt.SolidLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0.12 * h), w / 2, h / 2)
        p.drawArc(QRectF(-0.18 * w, 0.28 * h, 0.36 * w, 0.14 * h), 200 * 16, 140 * 16)  # mouth
        p.restore()

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
        if self.show_samples:
            for pe in self.calibration_errors + self.validation_errors:
                self._paint_samples(p, pe.samples)
            self._paint_legend(p)
        p.setFont(theme.font(26, bold=True))
        for pe in self.calibration_errors:
            self._paint_error(p, pe, theme.TEXT_QUIET, label_above=True)  # the centre has both kinds of point
        for pe in self.validation_errors:
            color = theme.WARNING if pe.error_px is None or pe.error_px > GOOD_PX else theme.HOVER
            self._paint_error(p, pe, color)
        self._paint_text(p, "Calibration result", 100, 56)
        self._paint_text(p, self.message, 180, 34, theme.TEXT_QUIET)
        if self.hint:
            # On a backing box: the hint sits over the top validation circles.
            p.setFont(theme.font(30, bold=True))
            w = p.fontMetrics().horizontalAdvance(self.hint) + 48
            p.setPen(QPen(theme.WARNING, 2))
            p.setBrush(theme.SURFACE)
            p.drawRoundedRect(QRectF((theme.CANVAS_W - w) / 2, 210, w, 56), 14, 14)
            self._paint_text(p, self.hint, 238, 30, theme.WARNING)

    def _paint_error(self, p: QPainter, pe: PointError, color, label_above: bool = False) -> None:
        center = self.map_to_canvas(pe.x, pe.y)
        p.setPen(QPen(color, 3))
        p.setBrush(Qt.NoBrush)
        radius = max(10.0, min(pe.error_px if pe.error_px is not None else 40.0, 200.0))
        p.drawEllipse(center, radius, radius)
        if pe.gaze is not None:
            # Which way the gaze missed: all outward or all inward means a Display Setup problem.
            p.drawLine(center, pe.gaze)
            p.drawEllipse(pe.gaze, 5, 5)
        p.drawLine(center + QPointF(-8, 0), center + QPointF(8, 0))
        p.drawLine(center + QPointF(0, -8), center + QPointF(0, 8))
        label = "not seen" if pe.error_px is None else f"{pe.error_px:.0f} px"
        y = center.y() - radius - 38 if label_above else center.y() + radius + 4
        p.drawText(QRectF(center.x() - 100, y, 200, 34), Qt.AlignCenter, label)

    def _paint_samples(self, p: QPainter, samples: List[Sample]) -> None:
        for s in samples:
            color = QColor(_eye_color(s.eye))
            color.setAlpha(200)
            if s.used:
                p.setPen(Qt.NoPen)
                p.setBrush(color)
            else:
                p.setPen(QPen(color, 1.5))
                p.setBrush(Qt.NoBrush)
            p.drawEllipse(s.pos, 3, 3)

    def _paint_legend(self, p: QPainter) -> None:
        eyes = {s.eye for pe in self.calibration_errors + self.validation_errors for s in pe.samples}
        if not eyes:
            return
        items = [(e, label) for e, label in (("left", "left eye"), ("right", "right eye"), ("both", "gaze"))
                 if e in eyes]
        if any(not s.used for pe in self.calibration_errors for s in pe.samples):
            items.append(("unused", "not used"))
        # A column at the middle of the left edge, the one place clear of every point and button.
        p.setFont(theme.font(22))
        x, y = float(theme.MARGIN), theme.CANVAS_H / 2 - 18 * len(items)
        for kind, label in items:
            if kind == "unused":
                p.setPen(QPen(theme.TEXT_QUIET, 2))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(_eye_color(kind))
            p.drawEllipse(QPointF(x + 8, y), 7, 7)
            p.setPen(theme.TEXT_QUIET)
            p.drawText(QRectF(x + 24, y - 18, 280, 36), Qt.AlignVCenter | Qt.AlignLeft, label)
            y += 36
        p.setPen(theme.TEXT_QUIET)
        p.drawText(QRectF(x, y, 300, 36), Qt.AlignVCenter | Qt.AlignLeft, "S samples, G live gaze")


def _eye_color(eye: str) -> QColor:
    return {"left": theme.LEFT_EYE, "right": theme.RIGHT_EYE}.get(eye, theme.BOTH_EYES)
