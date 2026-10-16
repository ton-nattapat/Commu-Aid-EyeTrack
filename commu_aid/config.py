"""Load and save config.yaml as typed settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

import yaml

NEEDS_TILE_COUNT = 11
DWELL_MIN_S = 1.0
DWELL_MAX_S = 3.0
DWELL_STEP_S = 0.25  # the Settings slider and its - / + buttons move in these steps
WOBBLE_GRACE_MAX_S = 1.0
SPEECH_RATE_MIN = 120  # words per minute
SPEECH_RATE_MAX = 300
SPEECH_RATE_STEP = 20  # the Settings - / + buttons move in these steps
SYSTEM_VOICE = "system"  # speak with the Mac's System Voice (Accessibility > Spoken Content), e.g. a Siri voice


@dataclass
class DwellConfig:
    dwell_time_s: float = 3.0
    blink_grace_s: float = 0.3
    cooldown_s: float = 1.0
    wobble_grace_s: float = 0.5  # gaze may wobble onto another button this long without losing progress


GAZE_FILTER_METHODS = ("fixation", "one_euro", "average")
# Steadiness levels on the Settings page: fixation radius for each, Light to Strong.
# Buttons are 146 px apart, so the strongest stays below that.
STEADINESS_RADII_PX = (60, 80, 100, 120, 140)
STEADINESS_NAMES = ("Light", "Low", "Medium", "High", "Strong")
STEADINESS_DEFAULT = 3  # High, 120 px


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
    edge_snap_px: int = 150  # gaze outside the whole layout (the edge margins) counts for the nearest button this close


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
    timeout_s: float = 8.0  # give up and speak English if a translation takes longer than this


@dataclass
class SpeechConfig:
    engine: str = "auto"
    voice_th: str = "Kanya"  # a voice name, or "system" for the Mac's System Voice
    voice_en: str = "Samantha"
    rate: int = 200  # words per minute


@dataclass
class CalibrationConfig:
    on_startup: bool = True
    saved_file: str = "~/.commu_aid/calibration.bin"
    auto_accept_max_error_px: float = 0
    redo_point_px: float = 150  # recollect a calibration point once when its error is above this (0 = never)
    show_live_gaze: bool = True  # draw the gaze live on the calibration screen (G toggles it there)
    edge_correction: bool = True  # take the gaze error measured at the validation dots back out of live gaze

    @property
    def saved_path(self) -> Path:
        return Path(self.saved_file).expanduser()


@dataclass
class PauseConfig:
    resume_dwell_s: float = 4.0  # look at Resume this long to come back; longer than dwell so a passing glance does not


KEYBOARD_STYLES = ("qwerty", "groups")


@dataclass
class KeyboardConfig:
    style: str = "qwerty"  # qwerty, or groups: 8 big letter groups, then the 4 keys of the chosen group (F5 switches)


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
    pause: PauseConfig = field(default_factory=PauseConfig)
    keyboard: KeyboardConfig = field(default_factory=KeyboardConfig)
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
        pause=_section(PauseConfig, raw.get("pause")),
        keyboard=_section(KeyboardConfig, raw.get("keyboard")),
        needs=needs,
        path=path,
    )
    cfg.dwell.dwell_time_s = clamp_dwell(cfg.dwell.dwell_time_s)
    cfg.dwell.wobble_grace_s = clamp_wobble_grace(cfg.dwell.wobble_grace_s)
    cfg.speech.rate = clamp_speech_rate(cfg.speech.rate)
    if cfg.keyboard.style not in KEYBOARD_STYLES:
        cfg.keyboard.style = KeyboardConfig.style
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


def clamp_wobble_grace(seconds: float) -> float:
    return max(0.0, min(WOBBLE_GRACE_MAX_S, float(seconds)))


def clamp_speech_rate(rate: float) -> int:
    return max(SPEECH_RATE_MIN, min(SPEECH_RATE_MAX, int(round(float(rate)))))


def steadiness_level(radius_px: float) -> int:
    """Settings level whose fixation radius is nearest the given one."""
    return min(range(len(STEADINESS_RADII_PX)), key=lambda i: abs(STEADINESS_RADII_PX[i] - float(radius_px)))
