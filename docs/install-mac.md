# The Mac app and installer

This page is in two parts: [building the installer](#build-the-installer) on your own Mac, and
[installing it on another Mac](#install-on-another-mac). The Tobii Pro Spark driver and Eye
Tracker Manager are not part of the installer; they are downloaded from Tobii on each Mac.

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

The full procedure (app, Gatekeeper, Rosetta, Tobii driver, Eye Tracker Manager, Display Setup,
Thai voice, first start, uninstall) is in the README:
[Install on a Mac (the app)](../README.md#install-on-a-mac-the-app).
