"""Common interface for anything that reports where the patient is looking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class GazeSample:
    """One gaze point. x and y are 0..1 across the monitor (Tobii's display-area coordinates)."""

    t: float  # seconds, time.monotonic() clock
    x: float = 0.0
    y: float = 0.0
    valid: bool = True


@dataclass
class EyePosition:
    """Where an eye sits in the tracker's view, 0..1 on each axis (z: 0 near, 1 far)."""

    x: float
    y: float
    z: float
    valid: bool


class GazeSource:
    """Base class. Subclasses deliver samples via `poll()`, called from the UI timer."""

    name = "gaze"
    supports_calibration = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def poll(self) -> List[GazeSample]:
        """Return every sample received since the last call, oldest first."""
        return []

    # User position guide, used on the calibration screen to centre the patient.
    def user_position(self) -> Tuple[Optional[EyePosition], Optional[EyePosition]]:
        return None, None
