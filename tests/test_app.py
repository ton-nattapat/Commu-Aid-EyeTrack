"""Drive the real window with a scripted gaze source and a fake clock (no tracker, no audio)."""

import threading
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from commu_aid.config import load_config  # noqa: E402
from commu_aid.gaze.source import GazeSample, GazeSource  # noqa: E402
from commu_aid.translate import TranslationError  # noqa: E402
from commu_aid.ui import main_window, theme  # noqa: E402
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
    centre = button.mapTo(window.canvas, button.rect().center())
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
    look_at(w, source, w.speak_button)
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
    look_at(w, source, w.speak_button)
    dwell(w, clock, app, 3.2)
    for _ in range(50):
        app.processEvents()
        if speaker.spoken:
            break
    assert speaker.spoken == [("Water please", "en")]
    assert w.bar.note_is_warning


class HangingTranslator:
    """Never answers until released, like a model stuck on a sentence."""

    enabled = True

    def __init__(self):
        self.release = threading.Event()

    def translate(self, text):
        self.release.wait(5)
        return f"TH:{text}"


def test_stuck_translation_times_out_and_speaks_english(setup, app):
    make, clock, source, speaker, _ = setup
    translator = HangingTranslator()
    w = make(translator)
    w.show_page(w.keyboard_page)
    w.typed = "water please"
    w._on_speak()
    assert w.bar.note == "Translating..." and speaker.spoken == []
    w._on_translation_timeout(w._request_id, "Water please")  # what the backstop timer calls
    assert speaker.spoken == [("Water please", "en")]
    assert w.bar.note_is_warning
    translator.release.set()  # the late answer must not be spoken as well
    for _ in range(50):
        app.processEvents()
        time.sleep(0.01)
    assert speaker.spoken == [("Water please", "en")]


def test_page_switch_does_not_bounce_back(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    look_at(w, source, button(w.needs_page, "nav"))
    dwell(w, clock, app, 3.2)
    assert w.page is w.keyboard_page
    # A continued stare at the same spot must not switch straight back.
    dwell(w, clock, app, 5.0)
    assert w.page is w.keyboard_page
    look_at(w, source, w.needs_button)
    dwell(w, clock, app, 3.2)
    assert w.page is w.needs_page


def test_settings_hint_sits_below_the_buttons_and_hides_under_settings(setup):
    make = setup[0]
    w = make()
    hint = w.settings_hint
    assert hint.isVisible() and "F3" in hint.text()
    lowest = max(b.mapTo(w.canvas, b.rect().bottomLeft()).y() for b in w.page.buttons)
    assert hint.geometry().top() > lowest
    w.open_settings()
    assert w.settings.geometry().contains(hint.geometry())


def test_settings_slider_is_one_to_three_seconds_in_half_second_steps(setup, tmp_path):
    make = setup[0]
    w = make()
    w.cfg.path = tmp_path / "config.yaml"
    w.open_settings()
    assert (w.settings.dwell_slider.minimum(), w.settings.dwell_slider.maximum()) == (2, 6)
    w.settings.dwell_slider.setValue(2)
    assert w.settings.dwell_value.text() == "1.0 s"
    assert not w.settings.dwell_less.isEnabled()
    w.settings.dwell_more.click()
    assert w.settings.dwell_value.text() == "1.5 s"
    w.settings.save()
    assert w.dwell.dwell_time_s == 1.5


def test_settings_snaps_an_odd_dwell_time_to_the_nearest_half_second(setup, tmp_path):
    make = setup[0]
    w = make()
    w.cfg.path = tmp_path / "config.yaml"
    w.cfg.dwell.dwell_time_s = 2.3
    w.open_settings()
    assert w.settings.dwell_value.text() == "2.5 s"
    w.settings.dwell_less.click()
    w.settings.save()
    assert w.dwell.dwell_time_s == 2.0


def test_settings_save_changes_dwell_and_tiles(setup, app, tmp_path):
    make, clock, source, speaker, _ = setup
    w = make()
    w.cfg.path = tmp_path / "config.yaml"
    w.open_settings()
    w.settings.dwell_slider.setValue(4)
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


def test_clear_empties_the_text_box(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    for key in [("key", "H"), ("key", "I")]:
        look_at(w, source, button(w.keyboard_page, key))
        dwell(w, clock, app, 3.2)
        source.point = None
        dwell(w, clock, app, 1.2)
    assert w.bar.english == "HI"
    look_at(w, source, button(w.keyboard_page, "clear"))
    dwell(w, clock, app, 3.2)
    assert w.typed == ""
    assert w.bar.english == ""


def type_keys(w, clock, source, app, letters):
    for ch in letters:
        look_at(w, source, button(w.keyboard_page, ("key", ch)))
        dwell(w, clock, app, 3.2)
        source.point = None
        dwell(w, clock, app, 1.2)


def test_resume_keeps_the_typed_text_in_the_box(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    type_keys(w, clock, source, app, "HI")
    w.pause()
    w.resume()
    assert w.typed == "HI"
    assert w.bar.typing and w.bar.english == "HI"  # what the box shows is what the next key adds to
    assert "Welcome back" in w.bar.note
    type_keys(w, clock, source, app, "M")
    assert w.bar.english == "HIM"


def test_clear_after_resume_empties_the_box_for_good(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    type_keys(w, clock, source, app, "HI")
    w.pause()
    w.resume()
    look_at(w, source, button(w.keyboard_page, "clear"))
    dwell(w, clock, app, 3.2)
    source.point = None
    dwell(w, clock, app, 1.2)
    type_keys(w, clock, source, app, "A")
    assert w.typed == "A" and w.bar.english == "A"


def test_status_messages_on_the_keyboard_page_keep_the_typed_text(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    w.typed = "WATER"
    w._show_typed()
    for status in (w._apply_settings, w._use_saved_calibration):
        status()
        assert w.bar.typing and w.bar.english == "WATER", status
        assert w.bar.note


def test_resume_on_the_needs_page_shows_welcome_back(setup):
    w = setup[0]()
    w.pause()
    w.resume()
    assert not w.bar.typing and w.bar.english == "Welcome back"


def test_typing_during_translation_is_not_hidden_by_the_result(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    w.typed = "HI"
    w._on_speak()
    w._on_letter("X")  # the patient starts the next word before the translation is back
    for _ in range(50):
        app.processEvents()
        if speaker.spoken:
            break
    assert speaker.spoken == [("TH:Hi", "th")]
    assert w.bar.typing and w.bar.english == "HIX"


def test_keyboard_targets_stay_large(setup):
    w = setup[0]()
    for b in w.keyboard_page.buttons:
        assert min(b.width(), b.height()) >= 110, b.key


def test_buttons_stay_clear_of_the_screen_edges(setup):
    w = setup[0]()
    d = w.cfg.display
    columns = {"yes", "no", "delete", "clear"}  # big enough to sit nearer the side edges than the keys
    buttons = [
        *w.needs_page.buttons, *w.keyboard_page.buttons,
        w.pause_button, w.speak_button, w.needs_button, w.pause_screen.resume_button,
    ]
    for b in buttons:
        pos = b.mapTo(w.canvas, QPoint(0, 0))
        side = min(d.side_margin_px, theme.KEYBOARD_SIDE_MARGIN) if b.key in columns else d.side_margin_px
        assert pos.x() >= side and pos.x() + b.width() <= 1920 - side, b.key
        assert pos.y() + b.height() <= 1080 - d.bottom_margin_px, b.key


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


def test_pause_turns_off_every_button_until_resume(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    look_at(w, source, w.pause_button)
    dwell(w, clock, app, 3.2)
    assert w.paused
    # A long look at a tile does nothing while resting.
    look_at(w, source, button(w.needs_page, ("need", 0)))
    dwell(w, clock, app, 5.0)
    assert speaker.spoken == []
    # Resume needs the longer resume dwell, not the normal one.
    resume = w.pause_screen.resume_button
    look_at(w, source, resume)
    dwell(w, clock, app, 3.2)
    assert w.paused and resume.progress > 0.7
    dwell(w, clock, app, 1.0)
    assert not w.paused
    # Buttons work again.
    source.point = None
    dwell(w, clock, app, 1.2)
    look_at(w, source, button(w.needs_page, ("need", 0)))
    dwell(w, clock, app, 3.2)
    assert speaker.spoken == [("ผมหิวน้ำครับ", "th")]


def test_glance_at_resume_does_not_wake(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.pause()
    look_at(w, source, w.pause_screen.resume_button)
    dwell(w, clock, app, 2.0)
    source.point = None
    dwell(w, clock, app, 1.0)
    look_at(w, source, w.pause_screen.resume_button)
    dwell(w, clock, app, 2.0)
    assert w.paused  # two short looks never add up to the full resume dwell


def test_caregiver_key_toggles_pause(setup):
    w = setup[0]()
    w.toggle_pause()
    assert w.paused
    w.toggle_pause()
    assert not w.paused


def test_speak_and_needs_sit_beside_pause_on_the_keyboard_page_only(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    assert w.speak_button.isHidden() and w.needs_button.isHidden()
    w.show_page(w.keyboard_page)
    assert w.speak_button.isVisible() and w.needs_button.isVisible()
    assert w.speak_button.y() == w.needs_button.y() == w.pause_button.y()
    assert w.bar.geometry().right() < w.speak_button.x()
    assert w.speak_button.geometry().right() < w.needs_button.x()
    assert w.needs_button.geometry().right() < w.pause_button.x()
    w.show_page(w.needs_page)
    assert w.speak_button.isHidden() and w.needs_button.isHidden()


def test_number_row_sits_above_the_letters(setup, app):
    make, clock, source, _, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    one, q = button(w.keyboard_page, ("key", "1")), button(w.keyboard_page, ("key", "Q"))
    assert one.x() == q.x() and one.geometry().bottom() < q.y()
    for key in [("key", "2"), ("key", "0")]:
        look_at(w, source, button(w.keyboard_page, key))
        dwell(w, clock, app, 3.2)
        source.point = None
        dwell(w, clock, app, 1.2)
    assert w.typed == "20"


def test_yes_and_no_speak_at_once_and_keep_the_typed_text(setup, app):
    make, clock, source, speaker, _ = setup
    w = make()
    w.show_page(w.keyboard_page)
    w.typed = "HEL"
    look_at(w, source, button(w.keyboard_page, "no"))
    dwell(w, clock, app, 3.2)
    assert speaker.spoken == [("ไม่ใช่", "th")]
    assert w.bar.english == "No" and w.typed == "HEL"
    source.point = None
    dwell(w, clock, app, 1.2)
    look_at(w, source, button(w.keyboard_page, "yes"))
    dwell(w, clock, app, 3.2)
    assert speaker.spoken[-1] == ("ใช่", "th")


def test_keyboard_layout_columns_and_word_row(setup):
    w = setup[0]()
    page = w.keyboard_page
    yes, no = button(page, "yes"), button(page, "no")
    delete, clear = button(page, "delete"), button(page, "clear")
    q, p = button(page, ("key", "Q")), button(page, ("key", "P"))
    assert yes.geometry().right() < q.x() and no.x() == yes.x()
    assert delete.x() > p.geometry().right() and clear.x() == delete.x()
    assert delete.y() < clear.y()
    assert delete.height() > 2 * p.height()  # far bigger than one key
    words = [b for b in page.buttons if isinstance(b.key, tuple) and b.key[0] == "word"]
    assert len(words) == 6 and len({b.y() for b in words}) == 1
