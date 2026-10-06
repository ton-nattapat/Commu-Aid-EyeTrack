import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from commu_aid.gaze.tobii_source import CalibrationPointResult  # noqa: E402
from commu_aid.ui.calibration import CALIBRATION_POINTS, CalibrationScreen, radial_pattern  # noqa: E402

CENTRE = (960, 540)


def test_all_misses_outward_means_display_setup():
    # Targets at 0.3/0.7 on 1920x1080, gaze 100 px further from the centre at each.
    pts = [(576, 324, 496, 264), (1344, 324, 1424, 264), (576, 756, 496, 816), (1344, 756, 1424, 816)]
    assert radial_pattern(pts + [(960, 540, 970, 550)], CENTRE) == "outward"
    inward = [(tx, ty, 2 * tx - gx, 2 * ty - gy) for tx, ty, gx, gy in pts]
    assert radial_pattern(inward, CENTRE) == "inward"


def test_same_offset_everywhere_is_not_display_setup():
    pts = [(tx, ty, tx + 100, ty) for tx, ty in ((576, 324), (1344, 324), (576, 756), (1344, 756))]
    assert radial_pattern(pts, CENTRE) is None


def test_small_misses_are_not_reported():
    pts = [(576, 324, 556, 314), (1344, 324, 1364, 314), (576, 756, 556, 766), (1344, 756, 1364, 766)]
    assert radial_pattern(pts, CENTRE) is None


class FakeTracker:
    """Calibration source whose bottom corners come out bad on the first compute."""

    supports_calibration = True

    def __init__(self, bad=((0.1, 0.9), (0.9, 0.9))):
        self.bad = set(bad)
        self.collected = []
        self.discarded = []
        self.computes = 0
        self.left = False

    def user_position(self):
        return None, None

    def enter_calibration(self):
        pass

    def collect(self, x, y):
        self.collected.append((x, y))
        return True

    def discard(self, x, y):
        self.discarded.append((x, y))

    def compute(self, w, h):
        self.computes += 1
        first = self.computes == 1
        return True, [
            CalibrationPointResult(x, y, 260.0 if first and (x, y) in self.bad else 40.0, x, y)
            for x, y in CALIBRATION_POINTS
        ]

    def leave_calibration(self):
        self.left = True


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def run_calibration(app, source, redo_px):
    screen = CalibrationScreen(source, lambda x, y: QPointF(x * 1920, y * 1080), redo_px=redo_px)
    screen._timer.stop()
    screen._run_in_worker = lambda fn: screen._on_worker_done(fn())  # no threads in tests
    screen.start_calibration()
    for _ in range(20):
        if screen.stage != "calibrate":
            break
        screen.stage_started = time.monotonic() - 5
        screen._tick()
    return screen


def test_bad_points_are_collected_once_more(app):
    source = FakeTracker()
    screen = run_calibration(app, source, redo_px=150)
    assert screen.stage == "validate"
    assert source.discarded == [(0.1, 0.9), (0.9, 0.9)]
    assert source.collected == list(CALIBRATION_POINTS) + [(0.1, 0.9), (0.9, 0.9)]
    assert source.computes == 2 and source.left
    assert all(pe.error_px == 40.0 for pe in screen.calibration_errors)


def test_redo_can_be_turned_off(app):
    source = FakeTracker()
    screen = run_calibration(app, source, redo_px=0)
    assert screen.stage == "validate"
    assert source.discarded == [] and source.computes == 1


def test_everything_bad_is_not_redone(app):
    source = FakeTracker(bad=CALIBRATION_POINTS)
    run_calibration(app, source, redo_px=150)
    assert source.discarded == [] and source.computes == 1
