"""Which button the gaze is on. No Qt, unit tested.

Real gaze lands up to a button's width away from where the patient looks, most of all near the
screen edges. A point inside a button picks it; a point in a gap or just past the outer edge of
the layout picks the nearest button within `snap_px`, so gaze that overshoots an edge button
still counts for it instead of resetting the dwell timer. Gaze outside the whole layout, in the
margins along the screen edges, is first pulled straight back onto the layout's edge (up to
`outer_snap_px`), so a miss past an edge button counts for that button, but gaze beside the layout
is not handed to a button further along it.
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


def pick_target(
    x: float, y: float, targets: Iterable[Tuple[Hashable, Rect]], snap_px: float = 0, outer_snap_px: float = 0
) -> Optional[Hashable]:
    """The key of the button under (x, y), or of the nearest one within snap_px, or None.

    With outer_snap_px, a point up to that far outside the box around all the buttons is first
    moved onto the box's edge.
    """
    targets = list(targets)
    if outer_snap_px > 0 and targets:
        rects = [rect for _, rect in targets]
        left, top = min(r[0] for r in rects), min(r[1] for r in rects)
        right, bottom = max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects)
        cx, cy = min(max(x, left), right), min(max(y, top), bottom)
        if (cx, cy) != (x, y):
            if math.hypot(x - cx, y - cy) > max(outer_snap_px, snap_px):
                return None
            x, y = cx, cy
    best_key, best_d = None, math.inf
    for key, rect in targets:
        d = distance_to_rect(x, y, rect)
        if d == 0:
            return key
        if d < best_d:
            best_key, best_d = key, d
    return best_key if best_d <= snap_px else None
