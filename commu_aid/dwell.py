"""Dwell selection state machine.

Pure logic with no UI or hardware code: feed it which button (if any) the gaze is on,
with a timestamp, and it reports progress and fires selections.

States, per the design:
  Idle      gaze on no button
  Dwelling  gaze on a button; its timer runs and progress fills
  Grace     gaze left (blink or off-button); progress is held for `blink_grace_s`,
            then reset if gaze has not come back
  Selected  timer reached `dwell_time_s`; a selection is returned once
  Locked    the selected button ignores gaze until gaze leaves it, and nothing can be
            selected until `cooldown_s` has passed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Optional

# A single frame longer than this (e.g. the app stalled) never counts as more dwell time.
MAX_FRAME_S = 0.1


@dataclass
class DwellUpdate:
    target: Optional[Hashable]  # the button currently accumulating dwell, if any
    progress: float  # 0.0 to 1.0 for `target`
    selected: Optional[Hashable] = None  # set on the one update where a selection fires


class DwellEngine:
    def __init__(self, dwell_time_s: float = 3.0, blink_grace_s: float = 0.3, cooldown_s: float = 1.0):
        self.dwell_time_s = dwell_time_s
        self.blink_grace_s = blink_grace_s
        self.cooldown_s = cooldown_s
        self.reset()

    def reset(self) -> None:
        self._current: Optional[Hashable] = None
        self._elapsed = 0.0
        self._last_now: Optional[float] = None
        self._last_on_current: Optional[float] = None
        self._locked: Optional[Hashable] = None
        self._cooldown_until = float("-inf")

    @property
    def locked_target(self) -> Optional[Hashable]:
        return self._locked

    def update(self, target: Optional[Hashable], now: float) -> DwellUpdate:
        dt = 0.0 if self._last_now is None else max(0.0, min(now - self._last_now, MAX_FRAME_S))
        self._last_now = now

        # Locked: the just-selected button stays inert until gaze leaves it.
        if self._locked is not None and target != self._locked:
            self._locked = None
        if target is not None and target == self._locked:
            target = None

        cooling = now < self._cooldown_until

        if target is None:
            # Grace: hold progress briefly so a blink or a jitter off the edge does not reset it.
            if self._current is not None and self._last_on_current is not None:
                if now - self._last_on_current > self.blink_grace_s:
                    self._clear_current()
            return DwellUpdate(self._current, self._progress())

        if target != self._current:
            self._current = target
            self._elapsed = 0.0
            dt = 0.0
        self._last_on_current = now

        if cooling:
            return DwellUpdate(self._current, 0.0)

        self._elapsed += dt
        if self._elapsed >= self.dwell_time_s:
            selected = self._current
            self._locked = selected
            self._cooldown_until = now + self.cooldown_s
            self._clear_current()
            return DwellUpdate(None, 0.0, selected=selected)
        return DwellUpdate(self._current, self._progress())

    def _progress(self) -> float:
        if self._current is None or self.dwell_time_s <= 0:
            return 0.0
        return min(1.0, self._elapsed / self.dwell_time_s)

    def _clear_current(self) -> None:
        self._current = None
        self._elapsed = 0.0
        self._last_on_current = None
