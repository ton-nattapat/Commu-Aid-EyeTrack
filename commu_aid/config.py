"""Load and save config.yaml as typed settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

import yaml

NEEDS_TILE_COUNT = 11
DWELL_MIN_S = 1.0
DWELL_MAX_S = 3.0


@dataclass
class DwellConfig:
    dwell_time_s: float = 3.0
    blink_grace_s: float = 0.3
    cooldown_s: float = 1.0


GAZE_FILTER_METHODS = ("fixation", "one_euro", "average")


@dataclass
class GazeFilterConfig:
    method: str = "fixation"  # fixation | one_euro | average
    # fixation: hold one point per fixation, jump only when the eyes really move
    fixation_radius_px: float = 120  # shake within this distance stays on the same point
    confirm_samples: int = 3  # this many samples in a row at a new spot make a jump (3 = 50 ms at 60 Hz)
    hold_s: float = 0.3  # the point averages this much recent gaze, so it still follows slow drift
    # one_euro: speed-adaptive low-pass filter
    min_cutoff_hz: float = 0.5
    beta: float = 0.01
    d_cutoff_hz: float = 1.0
    # average: the old moving average
    average_samples: int = 5


@dataclass
class DisplayConfig:
    width: int = 1920
    height: int = 1080
    show_gaze_dot: bool = True
    side_margin_px: int = 120  # buttons keep this far from the left and right screen edges
    bottom_margin_px: int = 100  # and this far from the bottom edge, nearest the tracker
    snap_px: int = 40  # gaze in a gap or just past the edge counts for the nearest button this close


@dataclass
class LanguageConfig:
    screen: str = "en"
    speak: str = "th"
    translate: bool = True


@dataclass
class TranslationConfig:
    engine: str = "nllb"
    model: str = "facebook/nllb-200-distilled-600M"
    source_code: str = "eng_Latn"
    target_code: str = "tha_Thai"


@dataclass
class SpeechConfig:
    engine: str = "auto"
    voice_th: str = "Kanya"
    voice_en: str = "Samantha"
    rate: int = 170


@dataclass
class CalibrationConfig:
    on_startup: bool = True
    saved_file: str = "~/.commu_aid/calibration.bin"
    auto_accept_max_error_px: float = 0
    redo_point_px: float = 150  # recollect a calibration point once when its error is above this (0 = never)
    show_live_gaze: bool = True  # draw the gaze live on the calibration screen (G toggles it there)

    @property
    def saved_path(self) -> Path:
        return Path(self.saved_file).expanduser()


@dataclass
class NeedTile:
    label: str
    thai: str
    icon: str = ""
    action: str = "speak"  # speak | alert


@dataclass
class AppConfig:
    dwell: DwellConfig = field(default_factory=DwellConfig)
    gaze_filter: GazeFilterConfig = field(default_factory=GazeFilterConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    needs: List[NeedTile] = field(default_factory=list)
    path: Path | None = None

    def save(self, path: Path | None = None) -> None:
        target = path or self.path
        if target is None:
            raise ValueError("No path to save the config to")
        data = asdict(self)
        data.pop("path")
        text = (
            "# Communication Aid settings.\n"
            "# The caregiver Settings page (F3) rewrites this file; edit by hand only while the app is closed.\n\n"
            + yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        )
        Path(target).write_text(text, encoding="utf-8")


def _section(cls, raw):
    """Build a dataclass from a dict, ignoring unknown keys and keeping defaults for missing ones."""
    raw = raw or {}
    names = cls.__dataclass_fields__.keys()
    return cls(**{k: v for k, v in raw.items() if k in names})


def load_config(path: Path | str) -> AppConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    needs = [
        NeedTile(
            label=str(t.get("label", "")),
            thai=str(t.get("thai", "")),
            icon=str(t.get("icon", "")),
            action=str(t.get("action", "speak")),
        )
        for t in raw.get("needs") or []
    ][:NEEDS_TILE_COUNT]
    cfg = AppConfig(
        dwell=_section(DwellConfig, raw.get("dwell")),
        gaze_filter=_gaze_filter(raw),
        display=_section(DisplayConfig, raw.get("display")),
        language=_section(LanguageConfig, raw.get("language")),
        translation=_section(TranslationConfig, raw.get("translation")),
        speech=_section(SpeechConfig, raw.get("speech")),
        calibration=_section(CalibrationConfig, raw.get("calibration")),
        needs=needs,
        path=path,
    )
    cfg.dwell.dwell_time_s = clamp_dwell(cfg.dwell.dwell_time_s)
    return cfg


def _gaze_filter(raw) -> GazeFilterConfig:
    cfg = _section(GazeFilterConfig, raw.get("gaze_filter"))
    if "gaze_filter" not in raw:
        # Config files from before the gaze filter kept the moving-average window under dwell.
        old = (raw.get("dwell") or {}).get("smoothing_samples")
        if old is not None:
            cfg.average_samples = int(old)
    if cfg.method not in GAZE_FILTER_METHODS:
        cfg.method = GazeFilterConfig.method
    return cfg


def clamp_dwell(seconds: float) -> float:
    return max(DWELL_MIN_S, min(DWELL_MAX_S, float(seconds)))
