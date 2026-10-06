from commu_aid.gaze.filters import GazeSmoother, combine_eyes
from commu_aid.gaze.source import GazeSample


def test_combine_both_eyes_averages():
    assert combine_eyes((0.2, 0.4), True, (0.4, 0.6), True) == (0.30000000000000004, 0.5)


def test_combine_uses_the_valid_eye():
    assert combine_eyes((0.2, 0.4), False, (0.4, 0.6), True) == (0.4, 0.6)


def test_combine_none_valid_is_blink():
    assert combine_eyes((0.2, 0.4), False, (0.4, 0.6), False) is None


def test_combine_ignores_nan():
    nan = float("nan")
    assert combine_eyes((nan, nan), True, (0.4, 0.6), True) == (0.4, 0.6)


def test_smoother_averages_window():
    s = GazeSmoother(window=2)
    s.add(GazeSample(0.0, 0.0, 0.0))
    out = s.add(GazeSample(0.016, 1.0, 1.0))
    assert (out.x, out.y) == (0.5, 0.5)


def test_smoother_passes_invalid_and_keeps_window_after_blink():
    s = GazeSmoother(window=3, reset_after_s=0.3)
    s.add(GazeSample(0.0, 0.5, 0.5))
    assert not s.add(GazeSample(0.1, valid=False)).valid
    out = s.add(GazeSample(0.2, 0.5, 0.5))
    assert (out.x, out.y) == (0.5, 0.5)


def test_smoother_resets_after_long_gap():
    s = GazeSmoother(window=3, reset_after_s=0.3)
    s.add(GazeSample(0.0, 0.0, 0.0))
    out = s.add(GazeSample(1.0, 1.0, 1.0))
    assert (out.x, out.y) == (1.0, 1.0)
