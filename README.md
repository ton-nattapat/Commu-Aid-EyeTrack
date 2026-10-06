# Commu-Aid-EyeTrack

A full-screen communication aid for a person with ALS, driven by a Tobii Pro Spark eye tracker.
The patient looks at a button for a set time (3 seconds by default, adjustable from 1 to 3)
to choose it. The app shows the English text and
speaks it in Thai.

- **Page 1, Needs:** 11 large tiles (Thirsty, Hungry, Pee, Pain, Too hot, Too cold, Turn me,
  Suction, Yes, No, Call caregiver) and a Keyboard tile. Each tile speaks a fixed Thai phrase.
  Call caregiver also plays a loud alarm.
- **Page 2, Keyboard:** QWERTY letters, Space, Delete, Clear, Speak, and Needs to go back.
  Four word buttons above the letters predict the word being typed (or the next word);
  choosing one finishes the word and adds a space. Prediction is offline and learns from
  every message the patient speaks.
  Speak translates the typed English to Thai offline (Meta NLLB-200) and speaks the Thai.
- **Calibration** runs every time the app starts: position check, 5-point calibration (a point
  with bad data is shown once more), validation, then Accept or Retry.
- **Edges:** buttons keep clear of the left, right and bottom screen edges, where the tracker is
  least accurate, and gaze that lands just past a button still counts for it.
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

#### Install the Tobii Pro Spark driver (runtime)

The Tobii SDK can't see the Spark until Tobii's Spark runtime is installed. Eye Tracker
Manager's own driver installer (+ > Tobii Pro Spark > Install) only supports macOS 13 and 14,
so on newer macOS its Install button stays greyed out. Install the runtime directly instead:

1. Sign in at [connect.tobii.com/s/spark-downloads](https://connect.tobii.com/s/spark-downloads)
   ("Tobii Pro Spark downloads") and click **Download** under **macOS**. You get
   `TobiiProSpark_2.2.3.0_x64.dmg` (version 2.2.3.0 is the one tested here).
2. Open the `.dmg` and double-click **install-driver**. A Terminal window opens.
   If macOS blocks it, go to System Settings > Privacy & Security, scroll down and click
   **Open Anyway**.
3. At `Password:` type your Mac login password (nothing shows while you type) and press Return.
4. Wait for:

   ```text
   I: Installing platform_runtime_IS5LPROENTRY_MAC_x64_service to /Library/Application Support/Tobii/PlatformRuntimes
   I: Installing com.tobii.pdk.runtime.IS5LPROENTRY.plist to /Library/LaunchDaemons
   I: Starting com.tobii.pdk.runtime.IS5LPROENTRY.plist
   Runtime Service 2.2.3.0 Installed
   ```

   then close the Terminal window when it says `[Process completed]`.
5. Plug the Spark straight into the Mac (Tobii's USB-C to USB-A adapter is fine). If it was
   already plugged in, unplug it, wait a few seconds and plug it back in.
6. Check that the SDK finds it:

   ```bash
   conda activate commu-aid
   python -m commu_aid.check_tracker
   ```

   It should print a line like `Tracker     Tobii Pro Spark  serial TPE01-...`.

Don't commit the `.dmg` to this repo: it is Tobii's software, so download it from Tobii Connect
on each Mac.

#### Display, Thai voice and translation

Once only, in **Tobii Pro Eye Tracker Manager**, run Display Setup so the tracker knows the
monitor's size and position. The app's layout is fixed at 1920x1080.

For the Thai voice: System Settings > Accessibility > Spoken Content > System Voice >
Manage Voices, and add **Kanya** (Thai).

The first time Speak is used, the translation model downloads from Hugging Face
(about 2.5 GB) and is cached after that, so the first run needs internet.

### If the app says "No Tobii eye tracker found"

Run the checker in Terminal (with `conda activate commu-aid`):

```bash
python -m commu_aid.check_tracker
```

It shows whether the Mac sees the tracker on USB and whether the Tobii SDK finds it. Then:

1. Plug the Spark's own USB-A cable straight into the Mac, using Tobii's USB-C to USB-A adapter
   if the Mac only has USB-C. Hubs, docks and monitor USB ports often can't supply the power
   spikes the tracker needs. Unplug, wait a few seconds, plug back in.
2. If macOS asks whether to allow the accessory to connect, choose **Allow**.
3. Open **Tobii Pro Eye Tracker Manager**. If the Spark isn't listed, press **+** (top right) to
   install its driver, then unplug and replug the tracker.
4. If Install is greyed out, install the Spark runtime directly as described in
   [Install the Tobii Pro Spark driver](#install-the-tobii-pro-spark-driver-runtime). If the
   tracker still isn't found, restart the Mac. On an Apple silicon Mac, also make sure Rosetta is
   installed (`softwareupdate --install-rosetta --agree-to-license`), since the runtime service
   is an Intel build.
5. Once the driver is installed, the checker should list the Spark.

### If gaze misses near the screen edges

Some error is normal (the gaze dot sits a little off), but if it grows towards the edges, work
through these in order, recalibrating (F2) after each change:

1. **Display Setup.** Run `python -m commu_aid.check_tracker`. It compares the screen size the
   tracker was set up for with the real screen and warns when they differ. If they do, open
   Tobii Pro Eye Tracker Manager > Display Setup, enter this screen's size and where the Spark
   is mounted, and save. A wrong size gives exactly this pattern: good in the middle, worse
   and worse towards the edges. The calibration result screen says so too ("Gaze lands outside
   every dot") when every miss points away from (or towards) the centre.
2. **Distance and angle.** The Spark works from about 45 to 95 cm; aim for 60 to 70 cm, with
   both eyes in the middle of the position box. Tilt the screen so it faces the patient's
   eyes; the tracker must look up at the eyes, not at the chin or forehead. The bottom
   corners are hardest, because the eyelids partly cover the eyes when looking down.
3. **Light and glasses.** Avoid sunlight or a bright lamp behind the patient or shining into
   the tracker. Glasses can reflect the tracker's light; tilt them slightly or try without.
4. **Read the result screen.** Each circle is how far off the gaze was at that dot, and the
   line shows which way it missed. Lines all pointing the same way mean an offset (position);
   lines all pointing outward or inward mean Display Setup.

The layout already helps: `side_margin_px` and `bottom_margin_px` in `config.yaml` keep buttons
away from the edges (the keys stay at least 110 px), and `snap_px` lets gaze in a gap or just
past the edge count for the nearest button. Raising the margins further makes the keys smaller,
so fix Display Setup and position first.

## Run

From the project folder, with the environment active (`conda activate commu-aid`):

```bash
python -m commu_aid                      # Tobii Pro Spark, calibration at start-up
python -m commu_aid --mouse --windowed   # no tracker: the mouse stands in for gaze
python -m commu_aid --mouse --calibration-demo   # rehearse the calibration screen with the mouse
python -m commu_aid --simulate --windowed        # simulated eye tracker (see below)
python -m commu_aid --skip-calibration   # use the last saved calibration
python -m commu_aid --config other.yaml  # use a different settings file
python -m commu_aid -v                   # verbose logging
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
`auto_accept_max_error_px` to accept a good calibration without pressing Enter, and
`redo_point_px` to set when a calibration point is collected again), and the edge margins and
snapping in `display` (see [If gaze misses near the screen edges](#if-gaze-misses-near-the-screen-edges)),
and the gaze filter (see [If the gaze point is shaky](#if-the-gaze-point-is-shaky)).
The Thai phrases should be checked by a Thai speaker; they use the male form (ผม ... ครับ).

### If the gaze point is shaky

Even a well-calibrated tracker reports a point that shakes by tens of pixels while the eyes hold
still. The `gaze_filter` section of `config.yaml` steadies it. The default, `method: fixation`,
works the way eyes move: they hold still on a button, then jump to the next one. While the
samples stay within `fixation_radius_px` of the current point, the point is their average, so
it barely moves; when `confirm_samples` samples in a row land somewhere new, it jumps straight
there. A single wild sample never moves it.

Compared on the simulated tracker (`--simulate`, 60 Hz), with the old 5-sample moving average:

| Level | Shake while looking at a button (RMS) | Time for the point to reach a new button |
| --- | --- | --- |
| mild | 7.7 px → 8.6 px | 67 ms → 33 ms |
| typical | 17.9 px → 12.0 px | 67 ms → 33 ms |
| hard | 37.3 px → 24.4 px | 67 ms → 33 ms |

The default `fixation_radius_px: 120` is set for noisy gaze. Keep it below 146 px, the distance
between neighbouring button centres. With a steady tracker, 80 holds the point closer to slow
drift (6.1 px at mild, 10.2 px at typical, 28.9 px at hard). If the point feels sticky, lower
it or `confirm_samples`.
`method: one_euro` is a speed-adaptive low-pass filter, and `method: average` brings back the
old moving average. Press Ctrl+G to watch the dot while you try them.

The app writes to `~/.commu_aid/`: the saved calibration, generated sounds, and
`messages.log` (every message with a time stamp), and `words.json` (the words and word pairs
the patient has spoken, used to rank predictions; delete it to start fresh).

## How it works

```text
Tobii Pro Spark ─▶ Gaze source ─▶ Gaze filter ─▶ Dwell engine ─▶ UI pages ─▶ Speech
 (tobii_research    (or mouse,    (combine eyes,  (1-3 s timer,   (Needs,
  60 Hz)             simulated)    smooth, blinks) grace, cooldown) Keyboard)
```

| File | Role |
| --- | --- |
| `commu_aid/main.py` | Command-line options, picks the gaze source, starts the app |
| `commu_aid/config.py` | Loads and saves `config.yaml` |
| `commu_aid/gaze/tobii_source.py` | Tobii SDK: gaze stream, user position, calibration |
| `commu_aid/gaze/mouse_source.py` | Mouse as fake gaze for development |
| `commu_aid/gaze/simulated_source.py` | Simulated tracker: mouse plus jitter, offset, blinks, dropouts |
| `commu_aid/gaze/filters.py` | Combine both eyes; gaze filters (fixation, One Euro, moving average) |
| `commu_aid/dwell.py` | Dwell state machine (no UI code, unit tested) |
| `commu_aid/targets.py` | Which button the gaze is on, with snapping to the nearest one |
| `commu_aid/ui/main_window.py` | Full-screen window, gaze loop, page switching |
| `commu_aid/ui/pages.py` | Needs and Keyboard layouts, word prediction row |
| `commu_aid/ui/dwell_button.py` | Button that fills up while it is looked at |
| `commu_aid/ui/message_bar.py` | English and Thai text shown at the top |
| `commu_aid/ui/gaze_dot.py` | Gaze dot overlay (Ctrl+G) |
| `commu_aid/ui/calibration.py` | Start-up calibration screen |
| `commu_aid/ui/settings.py` | Caregiver settings |
| `commu_aid/predict.py` | Offline word prediction (10,000 common words, care words, learning) |
| `commu_aid/data/` | Word lists for prediction (`english_words.txt`, `care_words.txt`) |
| `commu_aid/speech.py` | Offline text-to-speech (`say` on macOS, pyttsx3 elsewhere) |
| `commu_aid/sounds.py` | Click and caregiver-alarm sounds, generated on first run |
| `commu_aid/translate.py` | Offline English to Thai with NLLB-200 |

Dwell rules: a selection fires after the dwell time on one button; a blink or glance away
shorter than 0.3 s does not reset the timer; after a selection, nothing can be selected for
1 s and the same button stays inert until the patient looks away, so one long stare never
types "AAAA" or bounces between pages.

## Tests

```bash
python -m pytest        # in the activated commu-aid environment (pytest comes with environment.yml)
```

The tests cover the dwell engine with scripted gaze streams, the gaze filters, the simulated
eye tracker (jitter, offset, drift, blinks, dropouts, repeatable seeds), word prediction, config loading and saving, and the whole window driven by a scripted gaze source (choosing a need,
the alarm, typing and speaking, word prediction, translation failure, page switching, settings,
edge margins and snapping), and the calibration screen (collecting bad points again, spotting a
Display Setup problem).
