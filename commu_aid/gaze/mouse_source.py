"""Mouse pointer as fake gaze, so the app can be built and tested without the eye tracker."""

from __future__ import annotations

import time
from typing import Callable, List, Optional

from PySide6.QtGui import QCursor, QGuiApplication, QScreen

from .source import GazeSample, GazeSource


class MouseGazeSource(GazeSource):
    name = "mouse"

    def __init__(self, screen_provider: Optional[Callable[[], QScreen]] = None):
        # The app window sets this to its own screen, so the mouse maps the same way gaze does.
        self.screen_provider = screen_provider

    def poll(self) -> List[GazeSample]:
        screen = (self.screen_provider and self.screen_provider()) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        pos = QCursor.pos()
        x = (pos.x() - geo.x()) / max(1, geo.width())
        y = (pos.y() - geo.y()) / max(1, geo.height())
        return [GazeSample(time.monotonic(), x, y, True)]


class MouseDemoCalibrationSource(MouseGazeSource):
    """Mouse gaze plus a pretend calibration, to rehearse the calibration screen without the tracker."""

    supports_calibration = True

    def user_position(self):
        from .source import EyePosition

        return EyePosition(0.42, 0.5, 0.5, True), EyePosition(0.58, 0.5, 0.5, True)

    def enter_calibration(self) -> None:
        pass

    def collect(self, x: float, y: float) -> bool:
        time.sleep(0.3)
        return True

    def discard(self, x: float, y: float) -> None:
        pass

    def compute(self, screen_w: int, screen_h: int):
        from .tobii_source import CalibrationPointResult

        from ..ui.calibration import CALIBRATION_POINTS

        return True, [CalibrationPointResult(x, y, 0.0) for x, y in CALIBRATION_POINTS]

    def leave_calibration(self) -> None:
        pass

    def save_calibration(self, path) -> None:
        pass

    def load_calibration(self, path) -> bool:
        return False
