# The Mac app and installer

This page is in two parts: [building the installer](#build-the-installer) on your own Mac, and
[installing it on another Mac](#install-on-another-mac) to test there. The Tobii Pro Spark
driver is not part of the installer; it is [its own step](#4-install-the-tobii-pro-spark-driver),
downloaded from Tobii on each Mac.

## Build the installer

On the Mac you develop on, with the environment from the [README](../README.md#setup-macos):

```bash
conda activate commu-aid
packaging/mac/build_mac.sh
```

It installs PyInstaller (`requirements-build.txt`), builds `dist/Communication Aid.app`, signs it
ad hoc, and packs it into `dist/CommunicationAid-0.1.0-arm64.dmg` with an Applications shortcut
and a [Read Me First](../packaging/mac/Read%20Me%20First.txt) for the person installing it.
Send that `.dmg` (AirDrop, a USB stick or a shared drive).

| Option | What it does |
| --- | --- |
| `--version 0.2.0` | Version shown in Finder and in the file name |
| `--no-translate` | Leaves out PyTorch and the translation code, several hundred MB smaller. Speak then says the typed English. Needs tiles still speak Thai. |

Things to know:

- **Same chip type.** The app runs on Macs with the same kind of chip as the Mac that built it.
  Built on Apple silicon (M1 to M4), it runs on Apple silicon Macs; for an Intel Mac, build it
  on an Intel Mac.
- **The translation model is not inside.** The NLLB-200 model (about 2.5 GB) downloads on the
  app's first start and is cached in `~/.cache/huggingface`, as when running from source. That
  keeps the installer small enough to send, and a Mac that already has the model reuses it.
- **Not signed by Apple.** Without an Apple Developer ID, macOS asks once before opening the app
  on another Mac (step 2 below). With a Developer ID you can sign it instead:
  `COMMU_AID_SIGN_ID="Developer ID Application: ..." packaging/mac/build_mac.sh`
  (notarizing is a further step not covered here).
- The recipe is [`packaging/mac/commu_aid.spec`](../packaging/mac/commu_aid.spec).

## Install on another Mac

### 1. Install the app

Open the `.dmg` and drag **Communication Aid** onto **Applications**.

### 2. Open it the first time

macOS blocks apps that are not signed by Apple the first time:

1. Double-click **Communication Aid** in Applications. macOS says it can't be opened; click
   **Done**.
2. Open **System Settings > Privacy & Security**, scroll down to "Communication Aid was blocked"
   and click **Open Anyway**. Enter the Mac password if asked.
3. Open the app again and click **Open Anyway**.

This is needed once. If there is no Open Anyway button, run this in Terminal instead:

```bash
xattr -dr com.apple.quarantine "/Applications/Communication Aid.app"
```

### 3. Add the Thai voice

System Settings > Accessibility > Spoken Content > System Voice > Manage Voices, and add
**Kanya** (Thai).

### 4. Install the Tobii Pro Spark driver

The app finds the Spark only after Tobii's Spark runtime is installed. This is Tobii's software,
so it is downloaded from Tobii on each Mac rather than put in the installer. Follow
[Install the Tobii Pro Spark driver](../README.md#install-the-tobii-pro-spark-driver-runtime)
in the README (Tobii Connect download, `install-driver`, Mac password, replug the tracker).
On an Apple silicon Mac the runtime is an Intel build, so Rosetta must be installed:

```bash
softwareupdate --install-rosetta --agree-to-license
```

Then, once only, run Display Setup in **Tobii Pro Eye Tracker Manager** (also from Tobii) so
the tracker knows the screen's size and position.

To check the tracker without starting the app:

```bash
"/Applications/Communication Aid.app/Contents/MacOS/Communication Aid" --check-tracker
```

### 5. Start the app

Open **Communication Aid**. Calibration runs first. On the first start the translation model
downloads (about 2.5 GB), so keep the Mac online for a few minutes; the first Speak waits for
it, and with no internet Speak says the English instead.

If the tracker isn't found, the app says why (**Show Details** has the full tracker check) and
offers **Use the mouse** to try everything without it. Other start options work from Terminal:

```bash
open -a "Communication Aid" --args --mouse --windowed
open -a "Communication Aid" --args --simulate
```

### Where the app keeps its files

Everything is in the hidden folder `~/.commu_aid` (Finder: Go > Go to Folder, `~/.commu_aid`):

| File | What it is |
| --- | --- |
| `config.yaml` | Settings. Copied from the app on first start; the Settings page (F3) saves here. Delete it to go back to the defaults. |
| `app.log` | Log of the last run. Send it with any problem report. |
| `calibration.bin` | Last accepted calibration |
| `messages.log`, `words.json` | Messages spoken, and the words learned for prediction |

### Uninstall

Drag **Communication Aid** from Applications to the Bin, and delete `~/.commu_aid` and
`~/.cache/huggingface/hub/models--facebook--nllb-200-distilled-600M` if you want the settings
and the model gone too.
