"""Turn raw per-eye samples into one steady gaze point."""

from __future__ import annotations

from collections import deque
from typing import Optional, Sequence, Tuple

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
