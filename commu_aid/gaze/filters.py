"""Turn raw per-eye samples into one steady gaze point.

Gaze from a real tracker shakes by tens of pixels even while the patient holds still, and now and
then reports a wild sample. A plain moving average steadies it only a little and makes every jump
to another button arrive late. The filters here are built for how eyes move: they hold still
(fixations) and then jump (saccades). Each one smooths hard while the eyes hold still and lets a
real jump through quickly. All work in screen pixels, so their settings mean the same on any
monitor. None uses Qt; they are unit tested and compared with the gaze simulator.
"""


from __future__ import annotations

import math
from collections import deque
from typing import List, Optional, Sequence, Tuple

from .source import GazeSample


def combine_eyes(
    left: Optional[Sequence[float]], left_valid: bool, right: Optional[Sequence[float]], right_valid: bool
) -> Optional[Tuple[float, float]]:
    """Average both valid eyes, use one if only one is valid, or None if neither is (blink, looking away)."""
    points = []
    for point, valid in ((left, left_valid), (right, right_valid)):
        if valid and point is not None and _finite(point[0]) and _finite(point[1]):
            points.append(point)
    if not points:
        return None
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _finite(v: float) -> bool:
    return v == v and v not in (float("inf"), float("-inf"))


class GazeSmoother:
    """Moving average over the last `window` valid samples.

    An invalid sample passes through as invalid without clearing the window, so the point
    does not jump after a blink; a gap longer than `reset_after_s` starts the average afresh.
    """

    def __init__(self, window: int = 5, reset_after_s: float = 0.3):
        self.window = max(1, int(window))
        self.reset_after_s = reset_after_s
        self._points: deque = deque(maxlen=self.window)
        self._last_valid_t: Optional[float] = None

    def add(self, sample: GazeSample) -> GazeSample:
        if not sample.valid:
            return GazeSample(sample.t, valid=False)
        if self._last_valid_t is not None and sample.t - self._last_valid_t > self.reset_after_s:
            self._points.clear()
        self._last_valid_t = sample.t
        self._points.append((sample.x, sample.y))
        n = len(self._points)
        return GazeSample(
            sample.t, sum(p[0] for p in self._points) / n, sum(p[1] for p in self._points) / n, True
        )


class _Filter:
    """Shared handling of blinks and gaps, in pixels. Subclasses implement `_reset` and `_filter`."""

    def __init__(self, screen_px: Tuple[int, int] = (1920, 1080), reset_after_s: float = 0.3):
        self.w, self.h = max(1, screen_px[0]), max(1, screen_px[1])
        self.reset_after_s = reset_after_s
        self._last_valid_t: Optional[float] = None
        self._reset()

    def add(self, sample: GazeSample) -> GazeSample:
        if not sample.valid:
            return GazeSample(sample.t, valid=False)
        if self._last_valid_t is not None and sample.t - self._last_valid_t > self.reset_after_s:
            self._reset()
        dt = None if self._last_valid_t is None else max(sample.t - self._last_valid_t, 1e-3)
        self._last_valid_t = sample.t
        x, y = self._filter(sample.x * self.w, sample.y * self.h, dt)
        return GazeSample(sample.t, x / self.w, y / self.h, True)

    def _reset(self) -> None:
        raise NotImplementedError

    def _filter(self, x: float, y: float, dt: Optional[float]) -> Tuple[float, float]:
        raise NotImplementedError


class FixationFilter(_Filter):
    """Holds one steady point per fixation and moves it only when the eyes really jump.

    While samples stay within `radius_px` of the current fixation, the point is their running
    average (an exponential one after `hold_s`, so it still follows slow drift). Samples outside
    the radius are held back; once `confirm_samples` of them in a row agree on a new spot, the
    point jumps straight there. A single wild sample, or shake that only briefly leaves the
    radius, never moves the point.
    """

    def __init__(
        self,
        radius_px: float = 70.0,
        confirm_samples: int = 3,
        hold_s: float = 0.3,
        screen_px: Tuple[int, int] = (1920, 1080),
        reset_after_s: float = 0.3,
    ):
        self.radius_px = max(1.0, float(radius_px))
        self.confirm_samples = max(1, int(confirm_samples))
        self.hold_s = max(0.0, float(hold_s))
        super().__init__(screen_px, reset_after_s)

    def _reset(self) -> None:
        self._centre: Optional[Tuple[float, float]] = None
        self._age = 0.0  # seconds of samples in the running average
        self._pending: List[Tuple[float, float]] = []

    def _filter(self, x: float, y: float, dt: Optional[float]) -> Tuple[float, float]:
        dt = dt or 1.0 / 60.0
        if self._centre is None:
            self._start(x, y, dt)
            return self._centre
        cx, cy = self._centre
        if math.hypot(x - cx, y - cy) <= self.radius_px:
            self._pending.clear()
            self._age += dt
            k = dt / max(self._age, self.hold_s) if self.hold_s > 0 else dt / self._age
            self._centre = (cx + (x - cx) * k, cy + (y - cy) * k)
            return self._centre
        # Outside: a candidate new fixation, as long as the outside samples agree with each other.
        if self._pending:
            px, py = _mean(self._pending)
            if math.hypot(x - px, y - py) > self.radius_px:
                self._pending.clear()
        self._pending.append((x, y))
        if len(self._pending) >= self.confirm_samples:
            mx, my = _mean(self._pending)
            n = len(self._pending)
            self._pending.clear()
            self._centre, self._age = (mx, my), n * dt
        return self._centre

    def _start(self, x: float, y: float, dt: float) -> None:
        self._centre, self._age = (x, y), dt
        self._pending.clear()


class OneEuroFilter(_Filter):
    """The One Euro filter (Casiez, Roussel and Vogel, CHI 2012), with a 3-sample median in front.

    A low-pass filter whose cutoff rises with speed: slow movement (shake during a fixation) is
    smoothed hard at `min_cutoff_hz`, fast movement (a jump) gets a higher cutoff and little lag.
    `beta` sets how quickly the cutoff rises with speed in px/s. The median removes single wild
    samples, which would otherwise look like a fast movement and pass straight through.
    """

    def __init__(
        self,
        min_cutoff_hz: float = 0.5,
        beta: float = 0.01,
        d_cutoff_hz: float = 1.0,
        screen_px: Tuple[int, int] = (1920, 1080),
        reset_after_s: float = 0.3,
    ):
        self.min_cutoff_hz = max(1e-3, float(min_cutoff_hz))
        self.beta = max(0.0, float(beta))
        self.d_cutoff_hz = max(1e-3, float(d_cutoff_hz))
        super().__init__(screen_px, reset_after_s)

    def _reset(self) -> None:
        self._recent: deque = deque(maxlen=3)
        self._value: Optional[List[float]] = None
        self._speed = [0.0, 0.0]

    def _filter(self, x: float, y: float, dt: Optional[float]) -> Tuple[float, float]:
        self._recent.append((x, y))
        mx = _median([p[0] for p in self._recent])
        my = _median([p[1] for p in self._recent])
        if self._value is None or dt is None:
            self._value = [mx, my]
            return mx, my
        for i, v in enumerate((mx, my)):
            speed = (v - self._value[i]) / dt
            self._speed[i] += _alpha(self.d_cutoff_hz, dt) * (speed - self._speed[i])
            cutoff = self.min_cutoff_hz + self.beta * abs(self._speed[i])
            self._value[i] += _alpha(cutoff, dt) * (v - self._value[i])
        return self._value[0], self._value[1]


def make_gaze_filter(cfg, screen_px: Tuple[int, int] = (1920, 1080), reset_after_s: float = 0.3):
    """The filter a `GazeFilterConfig` asks for."""
    if cfg.method == "fixation":
        return FixationFilter(cfg.fixation_radius_px, cfg.confirm_samples, cfg.hold_s, screen_px, reset_after_s)
    if cfg.method == "one_euro":
        return OneEuroFilter(cfg.min_cutoff_hz, cfg.beta, cfg.d_cutoff_hz, screen_px, reset_after_s)
    return GazeSmoother(cfg.average_samples, reset_after_s)


def _alpha(cutoff_hz: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / dt)


def _mean(points: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _median(values: List[float]) -> float:
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
