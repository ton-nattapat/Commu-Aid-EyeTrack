"""Click and caregiver-alarm sounds, generated as small WAV files on first run."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

RATE = 44100


def _write_tone(path: Path, segments, volume: float) -> None:
    """segments: list of (frequency_hz or 0 for silence, seconds)."""
    frames = bytearray()
    for freq, seconds in segments:
        n = int(RATE * seconds)
        for i in range(n):
            fade = min(1.0, i / 200, (n - i) / 200)  # avoid clicks at the edges
            v = math.sin(2 * math.pi * freq * i / RATE) * volume * fade if freq else 0.0
            frames += struct.pack("<h", int(v * 32767))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class Sounds:
    def __init__(self, folder: Path):
        click = folder / "click.wav"
        alert = folder / "alert.wav"
        if not click.exists():
            _write_tone(click, [(1200, 0.05)], 0.5)
        if not alert.exists():
            # Two-tone alarm, repeated, clearly different from speech.
            _write_tone(alert, [(880, 0.25), (660, 0.25)] * 4, 1.0)
        self._click = self._effect(click, 0.6)
        self._alert = self._effect(alert, 1.0)

    @staticmethod
    def _effect(path: Path, volume: float) -> QSoundEffect:
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(volume)
        return effect

    def click(self) -> None:
        self._click.play()

    def alert(self) -> None:
        self._alert.setLoopCount(2)
        self._alert.play()
