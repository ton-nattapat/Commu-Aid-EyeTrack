# Plan: keep dwell progress through a short wobble off the button

Status: plan only, no code yet. Ton asked to rank the 12 follow-up items before coding starts.

## What Ton saw with the patient

When the gaze wobbles off a button for a moment, the patient has to start the whole dwell
again on the same button.

## What the app does today (`commu_aid/dwell.py`)

- There is already a grace period, `dwell.blink_grace_s: 0.3` in `config.yaml`, but it only
  covers gaze landing on **no** button (a blink, a gap, past the screen edge).
- If the wobble lands on a **neighbouring button**, which is the usual case on the keyboard where
  keys sit close together and `snap_px` gives gaps to the nearest key, the progress on the first
  button is dropped at once (`if target != self._current: ... self._elapsed = 0.0`).
- 0.3 s is shorter than many real wobbles.

## Proposed change

1. New setting `dwell.wobble_grace_s: 0.5` (allowed 0.0 to 1.0 s, 0.5 s default as Ton suggested).
2. During the grace time the first button keeps its progress, whether the gaze is on nothing
   or on another button. The progress ring pauses (does not drain, does not fill).
3. If the gaze comes back within the grace time, dwell continues from where it was.
4. If the gaze stays on the other button longer than the grace time, the first button resets
   and the other button starts its dwell from the moment the gaze arrived there, so a real
   move to a new key costs no extra time.
5. Add the setting to the caregiver Settings page (F3) next to the dwell slider, 0.5 s steps
   to match it (0, 0.5, 1.0).
6. Keep `blink_grace_s` for what it does besides dwell (dropping stale tracker samples and
   resetting the gaze filter after a blink), so changing the wobble grace does not change those.

## Resume (rest screen)

- Resume keeps its longer dwell (`pause.resume_dwell_s: 4.0`).
- Resume keeps the short 0.3 s grace instead of the new wobble grace. That keeps the rule that
  two short looks at Resume never add up to a resume (`test_glance_at_resume_does_not_wake`
  looks away for 1.0 s; with a 1.0 s wobble grace those two looks would join up and wake the
  screen).
- Trade-off: a wobble off Resume still restarts its timer. Resume is one large button with
  nothing next to it, so wobbles land on it far less often than on the keyboard.

## Tests to add (`tests/test_dwell.py`, `tests/test_app.py`)

- Look at A, wobble to neighbour B for 0.4 s, back to A: A selects without restarting.
- Look at A, move to B and stay: B selects after its normal dwell time counted from arrival.
- Gap longer than the grace time still resets A.
- Two short looks at Resume with a 1.0 s gap still do not wake the screen, at any wobble grace.
- Simulator run (`--simulate typical` and `hard`) to compare how often a dwell restarts, before
  and after.

## Open question for Ton

- 0.5 s default, adjustable 0 to 1.0 s in Settings. Is that range right?
