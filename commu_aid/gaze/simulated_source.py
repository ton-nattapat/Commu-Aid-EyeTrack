"""Simulated eye tracker: the mouse pointer (or any other source) as a target, made to behave like real gaze.

Real gaze is not a mouse pointer. It shakes a little all the time, sits slightly off where the
patient is looking (calibration error that also drifts), jumps from one fixation to the next
instead of gliding, drops out on every blink, sometimes loses the eyes for a moment, and now and
then reports a wild sample. This source adds all of that to the target point at the tracker's
60 Hz, so the smoothing, blink grace, dwell timer and cooldown are tested more like they will be
with the Tobii Pro Spark.

Distances are in screen pixels on the fixed 1920x1080 layout. As a guide, at 65 cm from a 24"
monitor, 1 degree of visual angle is about 40 px; Tobii quotes the Spark at about 0.45 degrees
accuracy and 0.25 degrees precision in good conditions, and real patients are usually worse.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .source import GazeSample, GazeSource


@dataclass(frozen=True)
class SimulationProfile:
    rate_hz: float = 60.0  # samples per second, like the Pro Spark
    jitter_px: float = 18.0  # standard deviation of the sample-to-sample shake
    jitter_correlation: float = 0.5  # 0 = white noise; closer to 1 = slower, wavier shake
    offset_px: Tuple[float, float] = (25.0, -15.0)  # fixed calibration error (x right, y down)
    drift_px: float = 20.0  # typical size of the slow wander on top of the offset
    drift_time_s: float = 10.0  # how quickly the wander changes
    fixation_radius_px: float = 30.0  # target moves less than this: the eyes stay put; more: they jump
    blinks_per_min: float = 15.0
    blink_s: Tuple[float, float] = (0.1, 0.3)  # shortest and longest blink
    dropouts_per_min: float = 1.0  # tracker loses the eyes (head turned, eyelids drooping)
    dropout_s: Tuple[float, float] = (0.4, 1.2)
    spike_chance: float = 0.005  # chance per sample of one wild reading
    spike_px: float = 150.0


PROFILES: Dict[str, SimulationProfile] = {
    # Close to the tracker's specification: a still, well-positioned user.
    "mild": SimulationProfile(
        jitter_px=8.0, offset_px=(10.0, -5.0), drift_px=8.0, blinks_per_min=12.0,
        dropouts_per_min=0.3, spike_chance=0.001,
    ),
    # What to expect day to day at the bedside.
    "typical": SimulationProfile(),
    # A tired patient, glasses, poor light or a hurried calibration.
    "hard": SimulationProfile(
        jitter_px=32.0, jitter_correlation=0.6, offset_px=(55.0, -40.0), drift_px=45.0,
        blinks_per_min=22.0, blink_s=(0.15, 0.5), dropouts_per_min=3.0, dropout_s=(0.5, 2.0),
        spike_chance=0.02, spike_px=250.0,
    ),
}


class GazeSimulator:
    """Turns a target point into realistic gaze samples, one call per tracker sample. No Qt, unit tested."""

    def __init__(
        self, profile: SimulationProfile, screen_px: Tuple[int, int] = (1920, 1080), seed: Optional[int] = None
    ):
        self.p = profile
        self.w, self.h = max(1, screen_px[0]), max(1, screen_px[1])
        self.rng = random.Random(seed)
        self._noise = [0.0, 0.0]
        self._drift = [0.0, 0.0]
        self._fixation: Optional[Tuple[float, float]] = None
        self._last_t: Optional[float] = None
        self._blank_until = -math.inf
        self._next_blink: Optional[float] = None
        self._next_dropout: Optional[float] = None

    def sample(self, t: float, target_x: float, target_y: float) -> GazeSample:
        """Gaze at time t while the patient looks at (target_x, target_y), both 0..1 across the monitor."""
        p = self.p
        dt = 1.0 / p.rate_hz if self._last_t is None else max(0.0, t - self._last_t)
        self._last_t = t
        if self._next_blink is None:
            self._next_blink = t + self._wait(p.blinks_per_min)
            self._next_dropout = t + self._wait(p.dropouts_per_min)

        self._update_drift(dt)

        # Blinks and lost tracking: invalid samples, like the Pro Spark reports them.
        if t >= self._next_blink:
            self._blank_until = max(self._blank_until, t + self.rng.uniform(*p.blink_s))
            self._next_blink = self._blank_until + self._wait(p.blinks_per_min)
        if t >= self._next_dropout:
            self._blank_until = max(self._blank_until, t + self.rng.uniform(*p.dropout_s))
            self._next_dropout = self._blank_until + self._wait(p.dropouts_per_min)
        if t < self._blank_until:
            return GazeSample(t, valid=False)

        # Fixations: the eyes hold still on small target movements and jump on large ones.
        tx, ty = target_x * self.w, target_y * self.h
        if self._fixation is None or math.hypot(tx - self._fixation[0], ty - self._fixation[1]) > p.fixation_radius_px:
            self._fixation = (tx, ty)
        fx, fy = self._fixation

        a = min(max(p.jitter_correlation, 0.0), 0.99)
        scale = p.jitter_px * math.sqrt(1.0 - a * a)
        for i in range(2):
            self._noise[i] = a * self._noise[i] + self.rng.gauss(0.0, scale)

        x = fx + p.offset_px[0] + self._drift[0] + self._noise[0]
        y = fy + p.offset_px[1] + self._drift[1] + self._noise[1]
        if self.rng.random() < p.spike_chance:
            angle = self.rng.uniform(0.0, 2.0 * math.pi)
            x += p.spike_px * math.cos(angle)
            y += p.spike_px * math.sin(angle)
        return GazeSample(t, x / self.w, y / self.h, True)

    def _wait(self, per_min: float) -> float:
        return self.rng.expovariate(per_min / 60.0) if per_min > 0 else math.inf

    def _update_drift(self, dt: float) -> None:
        # Ornstein-Uhlenbeck: wanders around zero with a standard deviation of about drift_px.
        tau = max(self.p.drift_time_s, 1e-3)
        sigma = self.p.drift_px * math.sqrt(2.0 / tau)
        for i in range(2):
            self._drift[i] += -self._drift[i] * dt / tau + sigma * math.sqrt(dt) * self.rng.gauss(0.0, 1.0)


class SimulatedGazeSource(GazeSource):
    """Wraps another source (normally the mouse) and reports simulated gaze at the tracker's rate.

    Calibration, user position and the screen provider are passed through to the wrapped source,
    so `--calibration-demo` works the same with simulation on.
    """

    name = "simulated"

    def __init__(
        self,
        target: GazeSource,
        profile: SimulationProfile = PROFILES["typical"],
        screen_px: Tuple[int, int] = (1920, 1080),
        seed: Optional[int] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.target = target
        self.simulator = GazeSimulator(profile, screen_px, seed)
        self.clock = clock
        self._period = 1.0 / profile.rate_hz
        self._next_t: Optional[float] = None
        self._target_point: Optional[Tuple[float, float]] = None

    @property
    def supports_calibration(self) -> bool:  # type: ignore[override]
        return self.target.supports_calibration

    @property
    def screen_provider(self):
        return getattr(self.target, "screen_provider", None)

    @screen_provider.setter
    def screen_provider(self, provider) -> None:
        if hasattr(self.target, "screen_provider"):
            self.target.screen_provider = provider

    def __getattr__(self, name):
        # Only reached for attributes not defined here: calibration calls, description, ...
        if name == "target":
            raise AttributeError(name)
        return getattr(self.target, name)

    def start(self) -> None:
        self.target.start()

    def stop(self) -> None:
        self.target.stop()

    def user_position(self):
        return self.target.user_position()

    def poll(self) -> List[GazeSample]:
        for s in self.target.poll():
            self._target_point = (s.x, s.y) if s.valid else None
        now = self.clock()
        # First call, or the UI stalled (calibration worker, window dragged): restart the sample clock.
        if self._next_t is None or now - self._next_t > 0.5:
            self._next_t = now
        out = []
        while self._next_t <= now:
            t = self._next_t
            self._next_t += self._period
            if self._target_point is None:
                out.append(GazeSample(t, valid=False))
            else:
                out.append(self.simulator.sample(t, *self._target_point))
        return out
