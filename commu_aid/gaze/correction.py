"""Edge correction: undo the tracker's leftover error near the screen edges. No Qt, unit tested.

Even after a good calibration, Tobii gaze lands off target near the screen edges, worst at the
bottom corners next to the tracker. For a patient who keeps his head still that error stays much
the same from minute to minute, so it can be measured and taken back out. The calibration screen
measures where the gaze lands at a 3x3 grid of validation dots that reach out to the edge buttons;
this class turns those misses into a smooth shift and removes it from every live gaze sample.

Between the dots the shift is interpolated (bilinear); past the outer dots it stays at the value of
the nearest edge. A dot that saw no gaze gets no shift. Each shift is capped, so one bad
measurement cannot throw the gaze across the screen.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .source import GazeSample

MAX_SHIFT_PX = 250  # a measured miss larger than this is capped to it
INVERSE_STEPS = 4  # fixed-point steps to find the target behind a gaze point (the shift varies slowly)

Point = Tuple[float, float]


def _cell(v: float, grid: Sequence[float]) -> Tuple[int, float]:
    """Index of the grid cell holding v and how far across it v is (0..1, clamped outside the grid)."""
    v = min(max(v, grid[0]), grid[-1])
    for i in range(len(grid) - 2):
        if v <= grid[i + 1]:
            break
    else:
        i = len(grid) - 2
    span = grid[i + 1] - grid[i]
    return i, (v - grid[i]) / span if span > 0 else 0.0


@dataclass
class EdgeCorrection:
    """A shift, 0..1 across the monitor, measured at each node of a grid and interpolated between them."""

    xs: List[float]  # grid columns, 0..1, increasing
    ys: List[float]  # grid rows, 0..1, increasing
    dx: List[List[float]]  # dx[row][col]: how far right of the dot the gaze landed, 0..1 of the width
    dy: List[List[float]]  # dy[row][col]: how far below the dot the gaze landed, 0..1 of the height

    @classmethod
    def from_misses(
        cls, misses: Sequence[Tuple[Point, Optional[Point]]], screen_px: Tuple[int, int] = (1920, 1080),
        max_shift_px: float = MAX_SHIFT_PX,
    ) -> "EdgeCorrection":
        """Build from (dot, where the gaze landed or None) pairs whose dots form a full grid, 0..1."""
        xs = sorted({round(d[0], 6) for d, _ in misses})
        ys = sorted({round(d[1], 6) for d, _ in misses})
        if len(xs) < 2 or len(ys) < 2 or len(misses) != len(xs) * len(ys):
            raise ValueError("Edge correction needs dots on a full grid of at least 2 x 2")
        w, h = max(1, screen_px[0]), max(1, screen_px[1])
        dx = [[0.0] * len(xs) for _ in ys]
        dy = [[0.0] * len(xs) for _ in ys]
        for (tx, ty), gaze in misses:
            if gaze is None:
                continue
            ex, ey = (gaze[0] - tx) * w, (gaze[1] - ty) * h
            scale = min(1.0, max_shift_px / max(math.hypot(ex, ey), 1e-9))
            row, col = ys.index(round(ty, 6)), xs.index(round(tx, 6))
            dx[row][col], dy[row][col] = ex * scale / w, ey * scale / h
        return cls(xs, ys, dx, dy)

    def shift_at(self, x: float, y: float) -> Point:
        """The shift the tracker adds to gaze aimed at (x, y)."""
        i, u = _cell(x, self.xs)
        j, v = _cell(y, self.ys)

        def lerp(grid):
            top = grid[j][i] * (1 - u) + grid[j][i + 1] * u
            bottom = grid[j + 1][i] * (1 - u) + grid[j + 1][i + 1] * u
            return top * (1 - v) + bottom * v

        return lerp(self.dx), lerp(self.dy)

    def correct(self, x: float, y: float) -> Point:
        """Where the patient was looking when the tracker reported (x, y)."""
        # The shift is measured at the dots the patient looked at, so find the target t with
        # t + shift(t) = gaze rather than subtracting the shift at the gaze point itself.
        tx, ty = x, y
        for _ in range(INVERSE_STEPS):
            sx, sy = self.shift_at(tx, ty)
            tx, ty = x - sx, y - sy
        return tx, ty

    def apply(self, sample: GazeSample) -> GazeSample:
        if not sample.valid:
            return sample
        x, y = self.correct(sample.x, sample.y)
        left = self.correct(*sample.left) if sample.left is not None else None
        right = self.correct(*sample.right) if sample.right is not None else None
        return replace(sample, x=x, y=y, left=left, right=right)

    def largest_shift_px(self, screen_px: Tuple[int, int] = (1920, 1080)) -> float:
        w, h = screen_px
        return max(
            math.hypot(self.dx[r][c] * w, self.dy[r][c] * h) for r in range(len(self.ys)) for c in range(len(self.xs))
        )

    # Saved next to the tracker's calibration, which it belongs to.

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"xs": self.xs, "ys": self.ys, "dx": self.dx, "dy": self.dy}
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Optional["EdgeCorrection"]:
        """The saved correction, or None when there is none or it cannot be read."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            c = cls([float(v) for v in data["xs"]], [float(v) for v in data["ys"]], data["dx"], data["dy"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        rows, cols = len(c.ys), len(c.xs)
        if rows < 2 or cols < 2 or len(c.dx) != rows or len(c.dy) != rows:
            return None
        if any(len(r) != cols for r in (*c.dx, *c.dy)):
            return None
        return c


def correction_path(calibration_path: Path) -> Path:
    """Where the edge correction for a saved calibration file is kept."""
    return calibration_path.with_name(calibration_path.stem + ".edge.json")
