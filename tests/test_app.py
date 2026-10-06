"""Drive the real window with a scripted gaze source and a fake clock (no tracker, no audio)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from commu_aid.config import load_config  # noqa: E402
from commu_aid.gaze.source import GazeSample, GazeSource  # noqa: E402
from commu_aid.translate import TranslationError  # noqa: E402
from commu_aid.ui import main_window  # noqa: E402
from tests.test_config import ROOT  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class ScriptedGaze(GazeSource):
    def __init__(self, clock):
        self.clock = clock
        self.point = None  # (x, y) normalised, or None for no valid gaze

    def poll(self):
        if self.point is None:
            return [GazeSample(self.clock(), valid=False)]
        return [GazeSample(self.clock(), *self.point)]


class FakeSpeaker:
    def __init__(self):
        self.spoken = []

    def speak(self, text, lang):
        self.spoken.append((text, lang))

    def close(self):
        pass


class FakeSounds:
    def __init__(self):
        self.alerts = 0

    def click(self):
        pass

    def alert(self):
        self.alerts += 1


class FakeTranslator:
    enabled = True

    def __init__(self, fail=False):
        self.fail = fail

    def translate(self, text):
        if self.fail:
            raise TranslationError("offline")
        return f"TH:{text}"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def setup(app, monkeypatch, tmp_path):
    clock = Clock()
    monkeypatch.setattr(main_window.time, "monotonic", clock)
    monkeypatch.setattr(main_window, "DATA_DIR", tmp_path)
    cfg = load_config(ROOT / "config.yaml")
    source = ScriptedGaze(clock)
    speaker, sounds = FakeSpeaker(), FakeSounds()

    def make(translator=None):
        w = main_window.MainWindow(cfg, source, speaker, translator or FakeTranslator(), sounds)
        w.resize(1920, 1080)
        w.show()
        app.processEvents()
        w._timer.stop()  # the test drives ticks itself
        return w

    return make, clock, source, speaker, sounds


def look_at(window, source, button):
    """Point the scripted gaze at the centre of a button."""
    centre = button.geometry().center() + button.parentWidget().pos()
    view_pt = window.mapFromScene(QPointF(centre))
    global_pt = window.mapToGlobal(view_pt)
    geo = window.screen().geometry()
    source.point = ((global_pt.x() - geo.x()) / geo.width(), (global_pt.y() - geo.y()) / geo.height())


def dwell(window, clock, app, seconds):
    for _ in range(round(seconds * 60)):
        clock.t += 1 / 60
        window._tick()
    app.processEvents()


def button(page, key):
    return next(b for b in page.buttons if b.key == key)


def test_needs_tile_speaks_thai_after_three_seconds(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    look_at(w, source, button(w.needs_page, ("need", 0)))
    dwell(w, clock, app, 2.8)
    assert speaker.spoken == []
    dwell(w, clock, app, 0.4)
    assert speaker.spoken == [("ผมหิวน้ำครับ", "th")]
    assert w.bar.english == "Thirsty" and w.bar.thai == "ผมหิวน้ำครับ"


def test_call_caregiver_plays_alarm(setup, app):
    make, clock, source, _, sounds = setup
    w = make()
    look_at(w, source, button(w.needs_page, ("need", 10)))
    dwell(w, clock, app, 3.2)
    assert sounds.alerts == 1


def test_type_and_speak_translates_to_thai(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    look_at(w, source, button(w.needs_page, "nav"))
    dwell(w, clock, app, 3.2)
    assert w.page is w.keyboard_page
    source.point = None
    dwell(w, clock, app, 1.2)  # rest through the cooldown
    for key in [("key", "H"), ("key", "I")]:
        look_at(w, source, button(w.keyboard_page, key))
        dwell(w, clock, app, 3.2)
        source.point = None
        dwell(w, clock, app, 1.2)
    assert w.typed == "HI"
    look_at(w, source, button(w.keyboard_page, "speak"))
    dwell(w, clock, app, 3.2)
    for _ in range(50):
        app.processEvents()
        if speaker.spoken:
            break
    assert speaker.spoken == [("TH:Hi", "th")]
    assert w.bar.thai == "TH:Hi"


def test_translation_failure_speaks_english(setup, app):
    make, clock, source, speaker, _ = setup
    w = make(FakeTranslator(fail=True))
    w.show_page(w.keyboard_page)
    w.typed = "water please"
    look_at(w, source, button(w.keyboard_page, "speak"))
    dwell(w, clock, app, 3.2)
    for _ in range(50):
        app.processEvents()
        if speaker.spoken:
            break
    assert speaker.spoken == [("Water please", "en")]
    assert w.bar.note_is_warning


def test_page_switch_does_not_bounce_back(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    look_at(w, source, button(w.needs_page, "nav"))
    dwell(w, clock, app, 3.2)
    assert w.page is w.keyboard_page
    # The Needs button sits in the same corner; a continued stare must not switch straight back.
    look_at(w, source, button(w.keyboard_page, "nav"))
    dwell(w, clock, app, 5.0)
    assert w.page is w.keyboard_page


def test_settings_slider_range_is_one_to_three_seconds(setup, tmp_path):
    make = setup[0]
    w = make()
    w.cfg.path = tmp_path / "config.yaml"
    w.open_settings()
    assert (w.settings.dwell_slider.minimum(), w.settings.dwell_slider.maximum()) == (10, 30)
    w.settings.dwell_slider.setValue(10)
    w.settings.save()
    assert w.dwell.dwell_time_s == 1.0


def test_settings_save_changes_dwell_and_tiles(setup, app, tmp_path):
    make, clock, source, speaker, _ = setup
    w = make()
    w.cfg.path = tmp_path / "config.yaml"
    w.open_settings()
    w.settings.dwell_slider.setValue(20)
    w.settings.table.item(0, 1).setText("Water")
    w.settings.save()
    assert w.dwell.dwell_time_s == 2.0
    assert not w.settings.isVisible()
    look_at(w, source, button(w.needs_page, ("need", 0)))
    dwell(w, clock, app, 2.2)
    assert w.bar.english == "Water"
    assert "Water" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_needs_tile_still_selected_with_simulated_gaze(app, monkeypatch, tmp_path):
    """Typical jitter, offset, blinks and dropouts must not stop a steady look from selecting a tile."""
    from commu_aid.gaze.simulated_source import PROFILES, SimulatedGazeSource

    clock = Clock()
    monkeypatch.setattr(main_window.time, "monotonic", clock)
    monkeypatch.setattr(main_window, "DATA_DIR", tmp_path)
    cfg = load_config(ROOT / "config.yaml")
    target = ScriptedGaze(clock)
    source = SimulatedGazeSource(target, PROFILES["typical"], (1920, 1080), seed=3, clock=clock)
    speaker = FakeSpeaker()
    w = main_window.MainWindow(cfg, source, speaker, FakeTranslator(), FakeSounds())
    w.resize(1920, 1080)
    w.show()
    app.processEvents()
    w._timer.stop()
    look_at(w, target, button(w.needs_page, ("need", 0)))
    dwell(w, clock, app, 8.0)
    assert speaker.spoken and speaker.spoken[0] == ("ผมหิวน้ำครับ", "th")


def test_word_prediction_finishes_the_word(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    for key in [("key", "W"), ("key", "A"), ("key", "T")]:
        look_at(w, source, button(w.keyboard_page, key))
        dwell(w, clock, app, 3.2)
        source.point = None
        dwell(w, clock, app, 1.2)
    first = button(w.keyboard_page, ("word", 0))
    assert first.label == "WATER"
    look_at(w, source, first)
    dwell(w, clock, app, 3.2)
    assert w.typed == "WATER "
    assert w.bar.english == "WATER "


def test_empty_suggestion_cannot_be_chosen(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    w.keyboard_page.set_suggestions(["YES"])
    hidden = button(w.keyboard_page, ("word", 1))
    assert hidden.isHidden()
    look_at(w, source, hidden)
    dwell(w, clock, app, 3.2)
    assert w.typed == ""


def test_keyboard_targets_stay_large(setup):
    w = setup[0]()
    for b in w.keyboard_page.buttons:
        assert min(b.width(), b.height()) >= 110, b.key


def test_buttons_stay_clear_of_the_screen_edges(setup):
    w = setup[0]()
    d = w.cfg.display
    for page in (w.needs_page, w.keyboard_page):
        for b in page.buttons:
            left = page.x() + b.x()
            assert left >= d.side_margin_px and left + b.width() <= 1920 - d.side_margin_px, b.key
            assert page.y() + b.y() + b.height() <= 1080 - d.bottom_margin_px, b.key


def test_gaze_just_past_the_bottom_edge_still_selects(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    w.typed = "HI"
    space = button(w.keyboard_page, "space")
    look_at(w, source, space)
    x, y = source.point
    source.point = (x, y + (space.height() / 2 + 25) / 1080)  # 25 px below the key, towards the tracker
    dwell(w, clock, app, 3.2)
    assert w.typed == "HI "
