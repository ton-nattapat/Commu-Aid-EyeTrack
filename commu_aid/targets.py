"""Which button the gaze is on. No Qt, unit tested.

Real gaze lands up to a button's width away from where the patient looks, most of all near the
screen edges. A point inside a button picks it; a point in a gap or just past the outer edge of
the layout picks the nearest button within `snap_px`, so gaze that overshoots an edge button
still counts for it instead of resetting the dwell timer.
"""

from __future__ import annotations

import math
from typing import Hashable, Iterable, Optional, Tuple

Rect = Tuple[float, float, float, float]  # left, top, width, height


def distance_to_rect(x: float, y: float, rect: Rect) -> float:
    """0 inside the rectangle, otherwise the distance to its nearest edge or corner."""
    left, top, w, h = rect
    dx = max(left - x, 0.0, x - (left + w))
    dy = max(top - y, 0.0, y - (top + h))
    return math.hypot(dx, dy)


def pick_target(x: float, y: float, targets: Iterable[Tuple[Hashable, Rect]], snap_px: float = 0) -> Optional[Hashable]:
    """The key of the button under (x, y), or of the nearest one within snap_px, or None."""
    best_key, best_d = None, math.inf
    for key, rect in targets:
        d = distance_to_rect(x, y, rect)
        if d == 0:
            return key
        if d < best_d:
            best_key, best_d = key, d
    return best_key if best_d <= snap_px else None
