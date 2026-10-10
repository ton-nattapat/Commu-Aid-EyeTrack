# Plan: caregiver typing from the physical keyboard

Status: built in PR #15, on top of the new keyboard layout (PR #21).

## Problem

Noisy gaze sometimes picks the wrong letter or word. Today the only way to fix the
message box is for the patient to dwell on Delete or Clear, which is slow and tiring.
A caregiver sitting next to the patient should be able to correct the text with the
Mac's own keyboard.

## Proposed behaviour

Keys act on the message box only while the main screen is showing (not during
calibration, Settings or the rest screen, which keep their own key handling).

| Key | Action |
| --- | --- |
| A–Z, 0–9 | Add the letter or number (uppercase, same as the on-screen keys) |
| Space | Add a space |
| Backspace | Delete one character (same as Delete) |
| Shift+Backspace | Clear the whole box (same as Clear) |
| Return / Enter | Speak (same as the Speak button) |

- Typing a letter while the Needs page is open switches to the keyboard page first,
  so the caregiver sees what they type.
- Word suggestions refresh after every key, exactly as with gaze typing, by routing
  keys through the existing `_on_letter`, `_on_delete`, `_on_clear` and `_on_speak`
  handlers in `commu_aid/ui/main_window.py`.
- Existing shortcuts stay as they are: F2 Calibration, F3 Settings, F4 Pause,
  Ctrl+G gaze dot, F11 full screen, Ctrl+Q quit. Esc stays reserved for closing
  Settings and skipping calibration.
- Number keys (top row and keypad) type into the number row added by the new layout.
- Ctrl, Alt and Cmd combinations are left alone so they never type by accident.

## Defaults chosen (Ton had not answered yet)

1. Enter speaks straight away.
2. Word prediction learns from caregiver typing too, the same as gaze typing, since
   `_on_speak` already calls `predictor.learn`.

## Tests

Unit tests in `tests/` that send `QKeyEvent`s to the main window with a fake gaze
source and check `typed`, the page shown, and that keys are ignored while Settings,
calibration or the rest screen is open.
