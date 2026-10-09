"""Dwell engine against scripted gaze streams at 60 Hz."""

from commu_aid.dwell import DwellEngine

FRAME = 1 / 60


def run(engine, script, start=0.0):
    """script: list of (target, seconds). Returns [(time, selected)] for every selection."""
    t = start
    selections = []
    for target, seconds in script:
        for _ in range(round(seconds / FRAME)):
            t += FRAME
            u = engine.update(target, t)
            if u.selected is not None:
                selections.append((round(t, 3), u.selected))
    return selections, t


def test_steady_look_selects_after_dwell_time():
    sel, _ = run(DwellEngine(3.0), [("A", 3.5)])
    assert len(sel) == 1
    assert sel[0][1] == "A"
    assert 3.0 <= sel[0][0] <= 3.05


def test_short_look_selects_nothing():
    sel, _ = run(DwellEngine(3.0), [("A", 2.9), (None, 1.0)])
    assert sel == []


def test_blink_mid_dwell_does_not_reset():
    sel, _ = run(DwellEngine(3.0, blink_grace_s=0.3), [("A", 1.5), (None, 0.2), ("A", 1.6)])
    assert [s[1] for s in sel] == ["A"]


def test_progress_is_held_during_blink():
    e = DwellEngine(3.0, blink_grace_s=0.3)
    run(e, [("A", 1.5)])
    u = e.update(None, 1.5 + 0.1)
    assert u.target == "A"
    assert abs(u.progress - 0.5) < 0.02


def test_long_look_away_resets():
    sel, _ = run(DwellEngine(3.0, blink_grace_s=0.3), [("A", 2.0), (None, 0.5), ("A", 2.0)])
    assert sel == []


def test_moving_to_another_button_restarts_timer():
    sel, _ = run(DwellEngine(3.0), [("A", 2.0), ("B", 2.0)])
    assert sel == []


def test_long_stare_selects_only_once():
    sel, _ = run(DwellEngine(3.0, cooldown_s=1.0), [("A", 10.0)])
    assert [s[1] for s in sel] == ["A"]


def test_look_away_then_back_selects_again():
    sel, _ = run(DwellEngine(3.0, cooldown_s=1.0), [("A", 3.2), (None, 0.5), ("A", 3.5)])
    assert [s[1] for s in sel] == ["A", "A"]


def test_cooldown_blocks_other_buttons():
    e = DwellEngine(2.0, cooldown_s=1.0)
    sel, t = run(e, [("A", 2.05)])
    assert len(sel) == 1
    # Straight to B: the first second is cooldown, so B needs cooldown + dwell.
    sel_b, t2 = run(e, [("B", 2.5)], start=t)
    assert sel_b == []
    sel_b, _ = run(e, [("B", 0.6)], start=t2)
    assert [s[1] for s in sel_b] == ["B"]


def test_stalled_frame_does_not_count_as_dwell():
    e = DwellEngine(3.0)
    e.update("A", 0.0)
    u = e.update("A", 5.0)  # the app froze for 5 s
    assert u.selected is None
    assert u.progress < 0.1


def test_changing_dwell_time_applies_immediately():
    e = DwellEngine(3.0)
    e.dwell_time_s = 2.0
    sel, _ = run(e, [("A", 2.2)])
    assert len(sel) == 1


def test_wobble_onto_neighbour_keeps_progress():
    e = DwellEngine(3.0, blink_grace_s=0.3, wobble_grace_s=0.5)
    sel, _ = run(e, [("A", 1.5), ("B", 0.4), ("A", 1.6)])
    assert [s[1] for s in sel] == ["A"]
    assert 3.4 <= sel[0][0] <= 3.6  # 1.5 s + 0.4 s wobble (not counted) + 1.5 s


def test_progress_is_held_on_neighbour_during_wobble():
    e = DwellEngine(3.0, wobble_grace_s=0.5)
    run(e, [("A", 1.5)])
    u = e.update("B", 1.5 + 0.2)
    assert u.target == "A"
    assert abs(u.progress - 0.5) < 0.02


def test_real_move_to_neighbour_counts_from_arrival():
    e = DwellEngine(3.0, wobble_grace_s=0.5)
    sel, _ = run(e, [("A", 1.5), ("B", 3.5)])
    assert [s[1] for s in sel] == ["B"]
    assert 4.45 <= sel[0][0] <= 4.6  # B selects 3 s after the gaze arrived, not 3 s after the grace


def test_wobble_longer_than_grace_resets():
    sel, _ = run(DwellEngine(3.0, wobble_grace_s=0.5), [("A", 2.0), ("B", 0.7), ("A", 2.0)])
    assert sel == []


def test_wobble_grace_also_covers_gaps():
    sel, _ = run(DwellEngine(3.0, blink_grace_s=0.3, wobble_grace_s=1.0), [("A", 1.5), (None, 0.8), ("A", 1.6)])
    assert [s[1] for s in sel] == ["A"]


def test_wobble_off_switches_at_once():
    e = DwellEngine(3.0, wobble_grace_s=0.0)
    run(e, [("A", 1.5)])
    assert e.update("B", 1.5 + 1 / 60).target == "B"
