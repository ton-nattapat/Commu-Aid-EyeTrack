import math
import random

import pytest

from commu_aid.gaze.correction import EdgeCorrection, correction_path
from commu_aid.gaze.simulated_source import PROFILES, GazeSimulator
from commu_aid.gaze.source import GazeSample

W, H = 1920, 1080
XS, YS = (0.08, 0.5, 0.92), (0.12, 0.5, 0.88)
GRID = [(x, y) for y in YS for x in XS]


def misses(miss):
    """(dot, where the gaze landed) for every grid dot, given the miss in pixels at each dot."""
    out = []
    for x, y in GRID:
        m = miss(x, y)
        out.append(((x, y), None if m is None else (x + m[0] / W, y + m[1] / H)))
    return out


def px_error(c, target, gaze_px):
    x, y = c.correct(gaze_px[0] / W, gaze_px[1] / H)
    return math.hypot(x * W - target[0], y * H - target[1])


def test_same_miss_everywhere_is_taken_out():
    c = EdgeCorrection.from_misses(misses(lambda x, y: (80, -40)), (W, H))
    for tx, ty in ((960, 540), (100, 1000), (1800, 120), (40, 40)):
        assert px_error(c, (tx, ty), (tx + 80, ty - 40)) == pytest.approx(0, abs=1e-6)


def test_miss_that_grows_towards_the_edge_is_taken_out_between_the_dots():
    # Gaze lands further out the further the dot is from the centre, as with the Spark.
    edge = lambda x, y: ((x - 0.5) * 400, (y - 0.5) * 400)  # noqa: E731
    c = EdgeCorrection.from_misses(misses(edge), (W, H))
    for tx, ty in ((300, 300), (1500, 800), (960, 900)):
        mx, my = edge(tx / W, ty / H)
        assert px_error(c, (tx, ty), (tx + mx, ty + my)) < 2


def test_past_the_outer_dots_the_edge_shift_holds():
    c = EdgeCorrection.from_misses(misses(lambda x, y: (0, 120) if y > 0.8 else (0, 0)), (W, H))
    assert c.shift_at(0.5, 0.99)[1] * H == pytest.approx(120)
    assert c.shift_at(0.5, 0.5) == (0, 0)


def test_unseen_dot_gets_no_shift_and_big_misses_are_capped():
    c = EdgeCorrection.from_misses(
        misses(lambda x, y: None if (x, y) == (0.08, 0.88) else (900, 0) if (x, y) == (0.92, 0.88) else (0, 0)),
        (W, H), max_shift_px=250,
    )
    assert c.shift_at(0.08, 0.88) == (0, 0)
    assert c.largest_shift_px((W, H)) == pytest.approx(250)


def test_needs_a_full_grid():
    with pytest.raises(ValueError):
        EdgeCorrection.from_misses(misses(lambda x, y: (0, 0))[:-1], (W, H))


def test_apply_corrects_each_eye_and_leaves_invalid_samples():
    c = EdgeCorrection.from_misses(misses(lambda x, y: (96, 0)), (W, H))
    s = c.apply(GazeSample(1.0, 0.55, 0.5, True, left=(0.54, 0.5), right=None))
    assert (s.x, s.left[0], s.right) == (pytest.approx(0.5), pytest.approx(0.49), None)
    blink = GazeSample(1.0, valid=False)
    assert c.apply(blink) is blink


def test_save_and_load(tmp_path):
    c = EdgeCorrection.from_misses(misses(lambda x, y: (x * 100, y * 50)), (W, H))
    path = correction_path(tmp_path / "calibration.bin")
    assert path.name == "calibration.edge.json"
    c.save(path)
    assert EdgeCorrection.load(path) == c
    path.write_text("{broken", encoding="utf-8")
    assert EdgeCorrection.load(path) is None
    assert EdgeCorrection.load(tmp_path / "missing.json") is None


def _median(v):
    v = sorted(v)
    return v[len(v) // 2]


def test_correction_halves_edge_error_on_simulated_gaze():
    """Measure like the validation screen does, then compare errors at random edge targets."""
    sim = GazeSimulator(PROFILES["edges"], (W, H), seed=3)
    t = 0.0

    def landed(x, y, seconds=1.0):
        nonlocal t
        xs, ys = [], []
        t0 = t
        while t - t0 < seconds:
            s = sim.sample(t, x, y)
            if s.valid:
                xs.append(s.x)
                ys.append(s.y)
            t += 1 / 60
        return _median(xs), _median(ys)

    c = EdgeCorrection.from_misses([((x, y), landed(x, y)) for x, y in GRID], (W, H))
    rng = random.Random(5)
    raw, fixed = [], []
    for _ in range(30):
        # A spot in the outer band of the layout, where the edge buttons are.
        x, y = rng.choice([(rng.uniform(0.06, 0.94), rng.choice([0.12, 0.88])), (rng.choice([0.07, 0.93]), rng.uniform(0.12, 0.88))])
        gx, gy = landed(x, y)
        raw.append(math.hypot((gx - x) * W, (gy - y) * H))
        cx, cy = c.correct(gx, gy)
        fixed.append(math.hypot((cx - x) * W, (cy - y) * H))
    assert _median(raw) > 120
    assert _median(fixed) < 0.5 * _median(raw)
