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


def finish_validation(screen, samples_per_point):
    """Feed gaze at each validation point inside its measuring window, then finish it."""
    from commu_aid.ui.calibration import SETTLE_S, VALIDATION_POINTS

    for x, y in VALIDATION_POINTS:
        screen.stage_started = time.monotonic() - SETTLE_S - 0.1
        for sample in samples_per_point(x, y):
            screen.feed(sample)
        screen._finish_validation_point()


def test_result_keeps_every_sample_per_eye(app):
    from commu_aid.gaze.source import GazeSample
    from commu_aid.gaze.tobii_source import EyeSample

    class SampledTracker(FakeTracker):
        def compute(self, w, h):
            ok, points = super().compute(w, h)
            for p in points:
                p.samples = [EyeSample("left", p.x, p.y), EyeSample("right", p.x, p.y, used=False)]
            return ok, points

    screen = run_calibration(app, SampledTracker(bad=()), redo_px=0)
    assert [len(pe.samples) for pe in screen.calibration_errors] == [2] * 5
    assert screen.calibration_errors[0].samples[1].used is False

    def gaze(x, y):
        now = time.monotonic()
        return [
            GazeSample(now, x, y, True, left=(x - 0.01, y), right=(x + 0.01, y)),
            GazeSample(now, x, y, True, left=(x - 0.01, y), right=None),
            GazeSample(now, valid=False),
        ]

    finish_validation(screen, gaze)
    assert screen.stage == "result"
    first = screen.validation_errors[0]
    assert [s.eye for s in first.samples] == ["left", "right", "left"]
    assert first.samples[0].pos.x() == pytest.approx((0.3 - 0.01) * 1920)
    assert first.error_px == pytest.approx(0.0)
    screen.grab()  # paints the samples and legend without errors


def test_live_gaze_follows_unfiltered_samples(app):
    from commu_aid.gaze.source import GazeSample

    screen = CalibrationScreen(FakeTracker(), lambda x, y: QPointF(x * 1920, y * 1080))
    screen._timer.stop()
    now = time.monotonic()
    screen.feed(GazeSample(now - 1.0, 0.1, 0.1, True))
    screen.feed(GazeSample(now, 0.5, 0.5, True))
    screen.feed(GazeSample(now, valid=False))
    assert len(screen._live) == 1  # older than the trail, dropped; invalid, ignored
    assert screen._live[-1][1] == QPointF(960, 540)
    assert screen._live[-1][2][0].eye == "both"
    screen.grab()
    assert screen.stage == "position" and screen._samples == []  # not measured outside validation


def test_tobii_reports_each_eye(monkeypatch):
    from types import SimpleNamespace as NS

    from commu_aid.gaze import tobii_source

    tr = NS(
        CALIBRATION_STATUS_FAILURE=0, VALIDITY_INVALID_AND_NOT_USED=-1, VALIDITY_VALID_BUT_NOT_USED=0,
        VALIDITY_VALID_AND_USED=1,
    )
    monkeypatch.setattr(tobii_source, "_tr", lambda: tr)
    source = tobii_source.TobiiGazeSource.__new__(tobii_source.TobiiGazeSource)
    eye = lambda x, v: NS(position_on_display_area=(x, 0.5), validity=v)  # noqa: E731
    result = NS(status=1, calibration_points=[NS(position_on_display_area=(0.5, 0.5), calibration_samples=[
        NS(left_eye=eye(0.49, 1), right_eye=eye(0.51, 1)),
        NS(left_eye=eye(0.40, 0), right_eye=eye(float("nan"), -1)),
    ])])
    source._calibration = NS(compute_and_apply=lambda: result)
    ok, (point,) = source.compute(1000, 1000)
    assert ok
    assert [(s.eye, s.x, s.used) for s in point.samples] == [("left", 0.49, True), ("right", 0.51, True), ("left", 0.40, False)]
    assert point.mean_error_px == pytest.approx(10.0) and point.gaze_x == pytest.approx(0.5)

    import queue

    source._samples = queue.SimpleQueue()
    source._on_gaze({
        "left_gaze_point_on_display_area": (0.4, 0.5), "left_gaze_point_validity": 1,
        "right_gaze_point_on_display_area": (float("nan"), float("nan")), "right_gaze_point_validity": 0,
    })
    s = source.poll()[0]
    assert s.valid and (s.x, s.y) == (0.4, 0.5) and s.left == (0.4, 0.5) and s.right is None
