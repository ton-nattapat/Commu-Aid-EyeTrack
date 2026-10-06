"""Tobii Pro Spark through Tobii's `tobii_research` package (Tobii Pro SDK).

`tobii_research` only ships wheels for Python 3.10, so the app pins Python 3.10.
The SDK calls our callbacks on its own thread; they only push into thread-safe queues,
and the UI drains them on its timer through `poll()`.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .filters import combine_eyes
from .source import EyePosition, GazeSample, GazeSource


class TrackerNotFound(RuntimeError):
    pass


@dataclass
class EyeSample:
    """One eye's gaze in one calibration sample, 0..1 across the monitor."""

    eye: str  # "left" | "right"
    x: float
    y: float
    used: bool = True  # False: valid, but the tracker left it out of the calibration


@dataclass
class CalibrationPointResult:
    x: float  # target, 0..1
    y: float
    mean_error_px: Optional[float]  # None when the tracker kept no valid samples for the point
    gaze_x: Optional[float] = None  # where the gaze landed on average, 0..1 (None with no valid samples)
    gaze_y: Optional[float] = None
    samples: List[EyeSample] = field(default_factory=list)  # every valid eye sample collected at the point


def _eye(d: dict, side: str) -> Optional[Tuple[float, float]]:
    """One eye's gaze point from a gaze data dict, or None when the tracker marks it invalid."""
    if not d[f"{side}_gaze_point_validity"]:
        return None
    x, y = d[f"{side}_gaze_point_on_display_area"][:2]
    if x != x or y != y:  # NaN
        return None
    return (x, y)


def _tr():
    import tobii_research  # imported lazily so the mouse mode works without the SDK installed

    return tobii_research


class TobiiGazeSource(GazeSource):
    name = "tobii"
    supports_calibration = True

    def __init__(self, eyetracker=None):
        tr = _tr()
        if eyetracker is None:
            trackers = tr.find_all_eyetrackers()
            if not trackers:
                raise TrackerNotFound(
                    "No Tobii eye tracker found.\n\n"
                    "1. Plug the tracker's USB-A cable straight into the Mac (Tobii's USB-C adapter is fine, "
                    "a hub or monitor port often is not), then unplug and replug it.\n"
                    "2. Open Tobii Pro Eye Tracker Manager. If the Spark is not listed, press + to install its driver, "
                    "or install the Spark runtime from connect.tobii.com/s/spark-downloads.\n"
                    "3. Run python -m commu_aid.check_tracker in Terminal for details."
                )
            eyetracker = trackers[0]
        self.eyetracker = eyetracker
        self._samples: "queue.SimpleQueue[GazeSample]" = queue.SimpleQueue()
        self._position_lock = threading.Lock()
        self._position: Tuple[Optional[EyePosition], Optional[EyePosition]] = (None, None)
        self._calibration = None
        self._running = False

    @property
    def description(self) -> str:
        et = self.eyetracker
        return f"{et.model} ({et.serial_number})"

    # Streaming

    def start(self) -> None:
        if self._running:
            return
        tr = _tr()
        self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._on_gaze, as_dictionary=True)
        self.eyetracker.subscribe_to(tr.EYETRACKER_USER_POSITION_GUIDE, self._on_position, as_dictionary=True)
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        tr = _tr()
        self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._on_gaze)
        self.eyetracker.unsubscribe_from(tr.EYETRACKER_USER_POSITION_GUIDE, self._on_position)
        self._running = False

    def poll(self) -> List[GazeSample]:
        out = []
        while True:
            try:
                out.append(self._samples.get_nowait())
            except queue.Empty:
                return out

    def user_position(self):
        with self._position_lock:
            return self._position

    def _on_gaze(self, d: dict) -> None:
        left, right = _eye(d, "left"), _eye(d, "right")
        point = combine_eyes(left, left is not None, right, right is not None)
        now = time.monotonic()
        if point is None:
            self._samples.put(GazeSample(now, valid=False))
        else:
            self._samples.put(GazeSample(now, point[0], point[1], True, left, right))

    def _on_position(self, d: dict) -> None:
        def eye(side: str) -> Optional[EyePosition]:
            pos: Sequence[float] = d[f"{side}_user_position"]
            valid = bool(d[f"{side}_user_position_validity"])
            if not valid:
                return EyePosition(0.5, 0.5, 0.5, False)
            return EyePosition(pos[0], pos[1], pos[2], True)

        with self._position_lock:
            self._position = (eye("left"), eye("right"))

    # Calibration (screen-based, run from the calibration screen)

    def enter_calibration(self) -> None:
        tr = _tr()
        self._calibration = tr.ScreenBasedCalibration(self.eyetracker)
        self._calibration.enter_calibration_mode()

    def collect(self, x: float, y: float) -> bool:
        """Blocking (a few hundred ms). Collects data while the patient looks at (x, y). Retries once."""
        tr = _tr()
        if self._calibration.collect_data(x, y) == tr.CALIBRATION_STATUS_SUCCESS:
            return True
        return self._calibration.collect_data(x, y) == tr.CALIBRATION_STATUS_SUCCESS

    def discard(self, x: float, y: float) -> None:
        """Drop the data collected at (x, y) so the point can be collected again before the next compute."""
        self._calibration.discard_data(x, y)

    def compute(self, screen_w: int, screen_h: int) -> Tuple[bool, List[CalibrationPointResult]]:
        tr = _tr()
        result = self._calibration.compute_and_apply()
        ok = result.status != tr.CALIBRATION_STATUS_FAILURE
        points = []
        for cp in result.calibration_points:
            tx, ty = cp.position_on_display_area
            errors, xs, ys, samples = [], [], [], []
            for sample in cp.calibration_samples:
                for side, eye in (("left", sample.left_eye), ("right", sample.right_eye)):
                    if eye.validity == tr.VALIDITY_INVALID_AND_NOT_USED:
                        continue
                    ex, ey = eye.position_on_display_area
                    used = eye.validity == tr.VALIDITY_VALID_AND_USED
                    samples.append(EyeSample(side, ex, ey, used))
                    if used:
                        errors.append((((ex - tx) * screen_w) ** 2 + ((ey - ty) * screen_h) ** 2) ** 0.5)
                        xs.append(ex)
                        ys.append(ey)
            if errors:
                points.append(
                    CalibrationPointResult(
                        tx, ty, sum(errors) / len(errors), sum(xs) / len(xs), sum(ys) / len(ys), samples
                    )
                )
            else:
                points.append(CalibrationPointResult(tx, ty, None, samples=samples))
        return ok, points

    def leave_calibration(self) -> None:
        if self._calibration is not None:
            self._calibration.leave_calibration_mode()
            self._calibration = None

    def save_calibration(self, path: Path) -> None:
        data = self.eyetracker.retrieve_calibration_data()
        if data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def load_calibration(self, path: Path) -> bool:
        if not path.exists():
            return False
        self.eyetracker.apply_calibration_data(path.read_bytes())
        return True
