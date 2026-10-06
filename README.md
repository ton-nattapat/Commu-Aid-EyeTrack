# Commu-Aid-EyeTrack

A full-screen communication aid for a person with ALS, driven by a Tobii Pro Spark eye tracker.
The patient looks at a button for 3 seconds to choose it. The app shows the English text and
speaks it in Thai.

- **Page 1, Needs:** 11 large tiles (Thirsty, Hungry, Pee, Pain, Too hot, Too cold, Turn me,
  Suction, Yes, No, Call caregiver) and a Keyboard tile. Each tile speaks a fixed Thai phrase.
  Call caregiver also plays a loud alarm.
- **Page 2, Keyboard:** QWERTY letters, Space, Delete, Clear, Speak, and Needs to go back.
  Speak translates the typed English to Thai offline (Meta NLLB-200) and speaks the Thai.
- **Calibration** runs every time the app starts: position check, 5-point calibration,
  validation, then Accept or Retry.
- **Settings (F3)** let the caregiver change the dwell time (2 to 5 s) and the Needs tiles.

| Needs | Keyboard |
| --- | --- |
| ![Needs page](docs/screenshots/3-needs.png) | ![Keyboard page](docs/screenshots/4-keyboard.png) |
| **Calibration** | **Settings** |
| ![Calibration result](docs/screenshots/2-calibration-result.png) | ![Settings](docs/screenshots/5-settings.png) |

The design and decisions are in the
[design proposal](https://claude.ai/code/artifact/2b4e4611-b66c-4974-8125-2c922de159a4).

## Setup (macOS)

`tobii-research` only ships wheels for **Python 3.10**, so use exactly that version.

```bash
# Python 3.10, e.g. with uv (or pyenv / python.org installer)
uv venv -p 3.10 .venv
source .venv/bin/activate

uv pip install -r requirements.txt          # app
uv pip install -r requirements-tobii.txt    # eye tracker
uv pip install -r requirements-translate.txt  # offline translation (large: torch + 2.5 GB model)
```

Once only, in **Tobii Pro Eye Tracker Manager**, run Display Setup so the tracker knows the
monitor's size and position. The app's layout is fixed at 1920x1080.

For the Thai voice: System Settings > Accessibility > Spoken Content > System Voice >
Manage Voices, and add **Kanya** (Thai).

The first time Speak is used, the translation model downloads from Hugging Face
(about 2.5 GB) and is cached after that, so the first run needs internet.

## Run

```bash
python -m commu_aid                      # Tobii Pro Spark, calibration at start-up
python -m commu_aid --mouse --windowed   # no tracker: the mouse stands in for gaze
python -m commu_aid --mouse --calibration-demo   # rehearse the calibration screen with the mouse
python -m commu_aid --skip-calibration   # use the last saved calibration
```

Caregiver keys:

| Key | Action |
| --- | --- |
| F2 | Calibrate again |
| F3 | Settings (dwell time, Needs tiles) |
| Ctrl+G | Show or hide the gaze dot |
| F11 | Full screen on or off |
| Ctrl+Q | Quit |

On the calibration screen: **Space** starts, **Enter** accepts, **R** retries, **Esc** skips and
uses the saved calibration.

## Settings

Everything is in [`config.yaml`](config.yaml): dwell time, blink grace, cooldown, the Needs
tiles and their Thai phrases, translation, voices, and calibration options (for example
`auto_accept_max_error_px` to accept a good calibration without pressing Enter).
The Thai phrases should be checked by a Thai speaker; they use the male form (ผม ... ครับ).

The app writes to `~/.commu_aid/`: the saved calibration, generated sounds, and
`messages.log` (every message with a time stamp).

## How it works

```text
Tobii Pro Spark ─▶ Gaze source ─▶ Gaze filter ─▶ Dwell engine ─▶ UI pages ─▶ Speech
 (tobii_research    (or mouse)    (combine eyes,  (3 s timer,     (Needs,
  60 Hz)                           smooth, blinks) grace, cooldown) Keyboard)
```

| File | Role |
| --- | --- |
| `commu_aid/gaze/tobii_source.py` | Tobii SDK: gaze stream, user position, calibration |
| `commu_aid/gaze/mouse_source.py` | Mouse as fake gaze for development |
| `commu_aid/gaze/filters.py` | Combine both eyes, moving-average smoothing |
| `commu_aid/dwell.py` | Dwell state machine (no UI code, unit tested) |
| `commu_aid/ui/main_window.py` | Full-screen window, gaze loop, page switching |
| `commu_aid/ui/pages.py` | Needs and Keyboard layouts |
| `commu_aid/ui/calibration.py` | Start-up calibration screen |
| `commu_aid/ui/settings.py` | Caregiver settings |
| `commu_aid/speech.py` | Offline text-to-speech (`say` on macOS, pyttsx3 elsewhere) |
| `commu_aid/translate.py` | Offline English to Thai with NLLB-200 |

Dwell rules: a selection fires after the dwell time on one button; a blink or glance away
shorter than 0.3 s does not reset the timer; after a selection, nothing can be selected for
1 s and the same button stays inert until the patient looks away, so one long stare never
types "AAAA" or bounces between pages.

## Tests

```bash
uv pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest
```

The tests cover the dwell engine with scripted gaze streams, the gaze filters, config
loading and saving, and the whole window driven by a scripted gaze source (choosing a need,
the alarm, typing and speaking, translation failure, page switching, and settings).
