# Gaze filter controls on the Settings page (item 9)

Ton wanted the caregiver to change the gaze noise filter from the Settings page (F3) instead of
editing `config.yaml` by hand.

## As built

- A **Gaze steadiness** row under Wobble grace, in the same style: big − / + buttons and the level
  name between them, Light / Low / Medium / High / Strong. The levels set the fixation filter's
  `fixation_radius_px` to 60 / 80 / 100 / 120 / 140 px; 140 stays under the 146 px between
  button centres. High (120 px, today's default) is recommended, and a "Recommended" button
  goes back to it.
- Only the steady (fixation) filter is offered. Ton did not answer whether to show all three
  filter types, so this follows the recommendation: one control, nothing raw for the caregiver.
  `one_euro` and `average` still work from `config.yaml`; changing the level switches back to
  `fixation`, and the hint says so when another filter is set.
- A hand-tuned radius between levels (say 110 px) is kept on Save unless the level is changed.
- Save rebuilds the filter at once, so a change needs no restart.
- Cancel and Save moved up beside the title so all 11 Needs rows still fit at 1920x1080.

The other filter numbers (`confirm_samples`, `hold_s`, the one_euro and average settings) stay in
`config.yaml` only.
