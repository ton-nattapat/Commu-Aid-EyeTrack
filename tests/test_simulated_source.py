import math
import statistics
from dataclasses import replace

from commu_aid.gaze.simulated_source import PROFILES, GazeSimulator, SimulatedGazeSource, SimulationProfile
from commu_aid.gaze.source import EyePosition, GazeSample, GazeSource

W, H = 1920, 1080
QUIET = SimulationProfile(
    jitter_px=0.0, offset_px=(0.0, 0.0), drift_px=0.0, blinks_per_min=0.0, dropouts_per_min=0.0, spike_chance=0.0
)


def run(profile, seconds, target=(0.5, 0.5), seed=1):
    sim = GazeSimulator(profile, (W, H), seed=seed)
    return [sim.sample(i / 60, *target) for i in range(round(seconds * 60))]


def errors_px(samples, target=(0.5, 0.5)):
    return [((s.x - target[0]) * W, (s.y - target[1]) * H) for s in samples if s.valid]


def test_quiet_profile_reports_the_target():
    for s in run(QUIET, 1):
        assert s.valid and math.isclose(s.x, 0.5) and math.isclose(s.y, 0.5)


def test_same_seed_repeats_exactly():
    assert run(PROFILES["typical"], 5, seed=7) == run(PROFILES["typical"], 5, seed=7)
    assert run(PROFILES["typical"], 5, seed=7) != run(PROFILES["typical"], 5, seed=8)


def test_jitter_has_the_requested_spread():
    errs = errors_px(run(replace(QUIET, jitter_px=20.0), 120))
    assert 17 < statistics.pstdev(e[0] for e in errs) < 23
    assert 17 < statistics.pstdev(e[1] for e in errs) < 23
    assert abs(statistics.fmean(e[0] for e in errs)) < 3


def test_offset_shifts_the_gaze():
    errs = errors_px(run(replace(QUIET, offset_px=(40.0, -25.0)), 1))
    assert all(math.isclose(ex, 40.0, abs_tol=1e-6) and math.isclose(ey, -25.0, abs_tol=1e-6) for ex, ey in errs)


def test_drift_wanders_but_stays_bounded():
    errs = errors_px(run(replace(QUIET, drift_px=20.0, drift_time_s=5.0), 600))
    spread = statistics.pstdev(e[0] for e in errs)
    assert 10 < spread < 35
    assert max(abs(e[0]) for e in errs) < 120


def test_blinks_and_dropouts_make_invalid_gaps():
    samples = run(PROFILES["typical"], 600)
    invalid = sum(not s.valid for s in samples) / len(samples)
    # 15 blinks/min of 0.1-0.3 s plus 1 dropout/min of 0.4-1.2 s: about 6 % of the time.
    assert 0.03 < invalid < 0.12
    gaps, run_len = [], 0
    for s in samples:
        if not s.valid:
            run_len += 1
        elif run_len:
            gaps.append(run_len / 60)
            run_len = 0
    assert min(gaps) >= 0.08 and max(gaps) <= 1.3
    assert sum(g < 0.35 for g in gaps) > 100  # mostly short blinks the dwell grace should forgive


def test_eyes_hold_a_fixation_and_jump_on_large_moves():
    sim = GazeSimulator(replace(QUIET, fixation_radius_px=30.0), (W, H))
    first = sim.sample(0.0, 0.5, 0.5)
    nudged = sim.sample(1 / 60, 0.5 + 20 / W, 0.5)  # 20 px: still the same fixation
    assert (nudged.x, nudged.y) == (first.x, first.y)
    jumped = sim.sample(2 / 60, 0.5 + 100 / W, 0.5)
    assert math.isclose(jumped.x, 0.5 + 100 / W)


def test_spikes_are_rare_and_large():
    errs = errors_px(run(replace(QUIET, spike_chance=0.01, spike_px=150.0), 600))
    spikes = [e for e in errs if math.hypot(*e) > 100]
    assert 200 < len(spikes) < 520  # about 1 % of 36 000 samples
    assert all(math.isclose(math.hypot(*e), 150.0) for e in spikes)


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Target(GazeSource):
    supports_calibration = True

    def __init__(self):
        self.point = (0.25, 0.75)
        self.screen_provider = None
        self.started = False

    def start(self):
        self.started = True

    def poll(self):
        return [GazeSample(0.0, *self.point, True)] if self.point else [GazeSample(0.0, valid=False)]

    def user_position(self):
        return EyePosition(0.4, 0.5, 0.5, True), EyePosition(0.6, 0.5, 0.5, True)

    def collect(self, x, y):
        return (x, y)


def test_source_emits_samples_at_tracker_rate():
    clock, target = Clock(), Target()
    src = SimulatedGazeSource(target, QUIET, (W, H), seed=1, clock=clock)
    assert len(src.poll()) == 1
    clock.t += 0.1
    out = src.poll()
    assert len(out) == 6
    assert all(b.t - a.t == 1 / 60 or math.isclose(b.t - a.t, 1 / 60) for a, b in zip(out, out[1:]))
    assert all(math.isclose(s.x, 0.25) and math.isclose(s.y, 0.75) for s in out)


def test_source_restarts_clock_after_a_stall():
    clock, target = Clock(), Target()
    src = SimulatedGazeSource(target, QUIET, (W, H), clock=clock)
    src.poll()
    clock.t += 5.0
    assert len(src.poll()) == 1


def test_source_reports_invalid_when_target_is_lost():
    clock, target = Clock(), Target()
    src = SimulatedGazeSource(target, QUIET, (W, H), clock=clock)
    target.point = None
    assert [s.valid for s in src.poll()] == [False]


def test_source_passes_calibration_and_screen_through():
    target = Target()
    src = SimulatedGazeSource(target, QUIET, (W, H))
    assert src.supports_calibration
    assert src.collect(0.1, 0.9) == (0.1, 0.9)
    assert src.user_position()[0].valid
    src.screen_provider = "screen"
    assert target.screen_provider == "screen"
    src.start()
    assert target.started
