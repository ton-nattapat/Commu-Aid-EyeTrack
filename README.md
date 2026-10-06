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
- **Settings (F3)** let the caregiver change the dwell time (1 to 3 s) and the Needs tiles.

| Needs | Keyboard |
| --- | --- |
| ![Needs page](docs/screenshots/3-needs.png) | ![Keyboard page](docs/screenshots/4-keyboard.png) |
| **Calibration** | **Settings** |
| ![Calibration result](docs/screenshots/2-calibration-result.png) | ![Settings](docs/screenshots/5-settings.png) |

The design and decisions are in the
[design proposal](https://claude.ai/code/artifact/2b4e4611-b66c-4974-8125-2c922de159a4).

## Setup (macOS)

`tobii-research` only ships wheels for **Python 3.10**, so the environment must use exactly
that version.

### With conda (terminal)

From the project folder:

```bash
conda env create -f environment.yml   # Python 3.10 + every requirement, including Tobii and translation
conda activate commu-aid
```

[`environment.yml`](environment.yml) installs the app, the Tobii SDK, the offline translation
packages (PyTorch is large, so this step takes a while) and pytest. After you pull new code
that changes a `requirements*.txt` file, update the environment with:

```bash
conda env update -f environment.yml --prune
```

To start again from scratch: `conda env remove -n commu-aid`, then create it again.

### With conda in VS Code

1. Install the **Python** extension (it includes the debugger).
2. Open the project folder in VS Code.
3. Press Cmd+Shift+P, choose **Python: Select Interpreter**, and pick **commu-aid**
   (create the environment in a terminal first, as above).
4. Open a new terminal (Terminal > New Terminal): it activates `commu-aid` for you.
   Run the app there with the commands under [Run](#run).
5. Or open **Run and Debug** (Cmd+Shift+D), pick one of the configurations in
   [`.vscode/launch.json`](.vscode/launch.json), and press F5:
   - Communication Aid (mouse, windowed)
   - Communication Aid (Tobii Pro Spark)
   - Communication Aid (calibration demo with mouse)
   - Communication Aid (simulated eye tracker)
6. The tests show up in the **Testing** panel (the flask icon).

If VS Code's terminal still shows `(base)`, run `conda activate commu-aid` in it once.

### Without conda (uv or venv)

```bash
uv venv -p 3.10 .venv
source .venv/bin/activate

uv pip install -r requirements.txt          # app
uv pip install -r requirements-tobii.txt    # eye tracker
uv pip install -r requirements-translate.txt  # offline translation (large: torch + 2.5 GB model)
```

### One-time setup on the Mac

Once only, in **Tobii Pro Eye Tracker Manager**, run Display Setup so the tracker knows the
monitor's size and position. The app's layout is fixed at 1920x1080.

For the Thai voice: System Settings > Accessibility > Spoken Content > System Voice >
Manage Voices, and add **Kanya** (Thai).

The first time Speak is used, the translation model downloads from Hugging Face
(about 2.5 GB) and is cached after that, so the first run needs internet.

## Run

From the project folder, with the environment active (`conda activate commu-aid`):

```bash
python -m commu_aid                      # Tobii Pro Spark, calibration at start-up
python -m commu_aid --mouse --windowed   # no tracker: the mouse stands in for gaze
python -m commu_aid --mouse --calibration-demo   # rehearse the calibration screen with the mouse
python -m commu_aid --simulate --windowed        # simulated eye tracker (see below)
python -m commu_aid --skip-calibration   # use the last saved calibration
```

### Simulated eye tracker

`--simulate` still follows the mouse, but makes it behave like real gaze from the Pro Spark:
the point shakes all the time, sits a little off target and slowly drifts, holds still on small
movements and jumps on large ones, drops out on blinks (about 15 a minute) and on short losses
of tracking, and now and then gives a wild sample. Use it to try dwell time, blink grace and
cooldown settings before the tracker is available.

```bash
python -m commu_aid --simulate --windowed          # typical bedside conditions
python -m commu_aid --simulate mild --windowed     # close to the tracker's specification
python -m commu_aid --simulate hard --windowed     # tired patient, glasses, poor light
python -m commu_aid --simulate --sim-seed 1        # repeat the same jitter and blinks every run
python -m commu_aid --simulate --calibration-demo  # with the pretend calibration screen
```

Press Ctrl+G to see the gaze dot. The levels are defined in
[`commu_aid/gaze/simulated_source.py`](commu_aid/gaze/simulated_source.py).

Caregiver keys:

| Key | Action |
| --- | --- |
| F2 | Calibrate again |
| F3 | Settings (dwell time, Needs tiles) |
| Ctrl+G (Cmd+G on a Mac) | Show or hide the gaze dot |
| F11 | Full screen on or off |
| Ctrl+Q (Cmd+Q on a Mac) | Quit |

On a Mac keyboard, hold **fn** to use F2, F3 and F11.

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
| `commu_aid/gaze/simulated_source.py` | Simulated tracker: mouse plus jitter, offset, blinks, dropouts |
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
python -m pytest        # in the activated commu-aid environment (pytest comes with environment.yml)
```

The tests cover the dwell engine with scripted gaze streams, the gaze filters, config
loading and saving, and the whole window driven by a scripted gaze source (choosing a need,
the alarm, typing and speaking, translation failure, page switching, and settings).
