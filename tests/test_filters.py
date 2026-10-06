import math
import random

from commu_aid.config import GazeFilterConfig
from commu_aid.gaze.filters import FixationFilter, GazeSmoother, OneEuroFilter, combine_eyes, make_gaze_filter
from commu_aid.gaze.simulated_source import PROFILES, GazeSimulator
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


# Fixation and One Euro filters work in pixels on a 1920x1080 screen.

W, H = 1920, 1080


def px(x, y, t):
    return GazeSample(t, x / W, y / H)


def out_px(sample):
    return round(sample.x * W, 6), round(sample.y * H, 6)


def test_fixation_filter_holds_still_through_shake():
    f = FixationFilter(radius_px=80, confirm_samples=3, screen_px=(W, H))
    rng = random.Random(0)
    outs = [out_px(f.add(px(500 + rng.gauss(0, 20), 500 + rng.gauss(0, 20), i / 60))) for i in range(120)]
    assert max(math.hypot(x - 500, y - 500) for x, y in outs[60:]) < 15


def test_fixation_filter_ignores_a_single_wild_sample():
    f = FixationFilter(radius_px=80, confirm_samples=3, screen_px=(W, H))
    for i in range(30):
        f.add(px(500, 500, i / 60))
    assert out_px(f.add(px(800, 500, 0.5))) == (500, 500)
    assert out_px(f.add(px(500, 500, 0.52))) == (500, 500)


def test_fixation_filter_jumps_after_confirm_samples():
    f = FixationFilter(radius_px=80, confirm_samples=3, screen_px=(W, H))
    for i in range(30):
        f.add(px(500, 500, i / 60))
    assert out_px(f.add(px(800, 500, 0.50))) == (500, 500)
    assert out_px(f.add(px(800, 500, 0.52))) == (500, 500)
    assert out_px(f.add(px(800, 500, 0.53))) == (800, 500)


def test_fixation_filter_passes_invalid_and_resets_after_long_gap():
    f = FixationFilter(radius_px=80, screen_px=(W, H), reset_after_s=0.3)
    f.add(px(500, 500, 0.0))
    assert not f.add(GazeSample(0.1, valid=False)).valid
    assert out_px(f.add(px(900, 900, 1.0))) == (900, 900)


def test_one_euro_removes_a_single_spike_and_follows_a_jump():
    f = OneEuroFilter(screen_px=(W, H))
    for i in range(30):
        f.add(px(500, 500, i / 60))
    assert abs(out_px(f.add(px(900, 500, 0.50)))[0] - 500) < 1
    assert abs(out_px(f.add(px(500, 500, 0.52)))[0] - 500) < 1
    for i in range(20):
        last = f.add(px(900, 500, 0.53 + i / 60))
    assert abs(out_px(last)[0] - 900) < 40


def test_make_gaze_filter_picks_method():
    assert isinstance(make_gaze_filter(GazeFilterConfig(method="fixation")), FixationFilter)
    assert isinstance(make_gaze_filter(GazeFilterConfig(method="one_euro")), OneEuroFilter)
    assert isinstance(make_gaze_filter(GazeFilterConfig(method="average")), GazeSmoother)


def _shake_and_lag(make, profile="typical", seed=1, fixations=40, fix_s=1.5):
    """RMS error while the eyes hold still, and median samples until the point reaches a new target."""
    rng = random.Random(seed)
    sim = GazeSimulator(PROFILES[profile], (W, H), seed=seed)
    f = make()
    errors, lags, t = [], [], 0.0
    for _ in range(fixations):
        tx, ty = rng.uniform(0.15, 0.85), rng.uniform(0.15, 0.85)
        t0, lag = t, None
        while t - t0 < fix_s:
            out = f.add(sim.sample(t, tx, ty))
            if out.valid:
                # Where the simulated gaze sits without shake or spikes: target plus calibration error.
                truth_x = sim._fixation[0] + sim.p.offset_px[0] + sim._drift[0]
                truth_y = sim._fixation[1] + sim.p.offset_px[1] + sim._drift[1]
                e = math.hypot(out.x * W - truth_x, out.y * H - truth_y)
                if lag is None and e < 50:
                    lag = round((t - t0) * 60)
                if t - t0 > 0.4:
                    errors.append(e)
            t += 1 / 60
        if lag is not None:
            lags.append(lag)
    return math.sqrt(sum(e * e for e in errors) / len(errors)), sorted(lags)[len(lags) // 2]


def test_fixation_filter_beats_moving_average_on_simulated_gaze():
    old_shake, old_lag = _shake_and_lag(lambda: GazeSmoother(5))
    new_shake, new_lag = _shake_and_lag(lambda: make_gaze_filter(GazeFilterConfig(), (W, H)))
    assert new_shake < 0.7 * old_shake
    assert new_lag < old_lag
