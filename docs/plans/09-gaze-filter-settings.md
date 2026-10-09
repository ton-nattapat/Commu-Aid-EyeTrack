# Plan: gaze filter controls on the Settings page (item 9)

Status: plan only, no code yet. Waiting for Ton to rank this against the other items.

## What Ton asked for

The current noise filter works well, but the caregiver should be able to change it from the
Settings page (F3) instead of editing `config.yaml` by hand.

## What exists today

- `gaze_filter` section in `config.yaml` (PR #7): `method` is `fixation` (default), `one_euro`
  or `average`, each with its own numbers. `fixation_radius_px` defaults to 120 and must stay
  under 146 px (the distance between button centres).
- `make_gaze_filter()` in `commu_aid/gaze/filters.py` builds the filter once, in
  `MainWindow.__init__`. Saving Settings does not rebuild it, so a change today needs a restart.
- The Settings page only has the dwell slider (big yellow slider, 110 px -/+ buttons, PR #11)
  and the Needs tiles table.

## Proposed change

1. **Filter type**: three large toggle buttons in one row, same style as the dwell -/+ buttons:
   - "Steady" = `fixation` (recommended, selected by default)
   - "Smooth" = `one_euro`
   - "Simple" = `average`
2. **Steadiness**: one slider with -/+ buttons, styled like the dwell slider, with 5 steps from
   "Light" to "Strong". Each step sets the main number of the chosen filter, so the caregiver
   never sees raw parameters:
   - Steady: `fixation_radius_px` 60 / 80 / 100 / 120 / 140 (120 = today's default)
   - Smooth: `min_cutoff_hz` 2.0 / 1.0 / 0.5 / 0.3 / 0.15 (0.5 = default)
   - Simple: `average_samples` 3 / 5 / 8 / 12 / 16 (5 = default)
   A value from a hand-edited config snaps to the nearest step, as dwell does.
3. **"Reset to recommended"** button: Steady, radius 120.
4. **Apply on Save without restart**: `_apply_settings()` rebuilds `self.smoother` with
   `make_gaze_filter()`, and the "Settings saved" note says which filter is on.
5. **Room on the page**: the Needs table shrinks a little to fit the two new rows at 1920x1080.
   If it gets too tight, Needs tiles move to a second Settings tab.

Other numbers (`confirm_samples`, `hold_s`, `beta`, `d_cutoff_hz`) stay in `config.yaml` only.

## Tests

- Config round trip: each method and step survives Save and load.
- Snapping: an off-step value loads to the nearest step; radius never goes above 140.
- Main window: after Save, `smoother` is the new filter type with the new number.
- Screenshot of the Settings page at 1920x1080 for Ton to check.

## Questions for Ton

- Are the three filter types worth showing, or only the Steadiness slider for the Steady filter?
  (Simpler for the caregiver; recommended if the other two are never used.)
- Would a small "try it" area on the Settings page, showing the gaze dot live, help the
  caregiver judge a change before saving?
