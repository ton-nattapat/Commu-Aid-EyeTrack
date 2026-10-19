# Communication Aid on Windows

Windows 10 or 11, 64-bit. Everything the Mac version does works the same: the Tobii Pro Spark,
calibration, dwell, offline English-to-Thai translation and Thai speech. The differences are the
Thai voice (Microsoft Pattara instead of Kanya) and the installer (a Setup.exe instead of a .dmg).

## 1. Get the installer

GitHub builds it on a Windows machine for every change:

1. Open the repository on GitHub > **Actions** > **Windows**, and click the newest green run
   (for `main`, or for the pull request you want to try).
2. Under **Artifacts**, download **CommunicationAid-Windows-Setup** (a zip; you must be signed in
   to GitHub). Unzip it: inside is `CommunicationAid-<version>-Windows-Setup.exe`.

To build it yourself on a Windows PC instead, see [Build on Windows](#build-on-windows).

## 2. One-time setup on the PC

Do these in order, once per PC.

1. **Tobii Pro Spark runtime.** Sign in at <https://connect.tobii.com/s/spark-downloads>, download
   the Windows runtime for the Spark and install it. Plug the Spark's USB cable straight into the
   PC (not a hub or monitor port).
2. **Tobii Pro Eye Tracker Manager** for Windows, from
   <https://www.tobii.com/products/software/applications-and-developer-kits/tobii-pro-eye-tracker-manager>.
   Open it: the Spark should be listed (if it offers to install a driver or update firmware, accept).
   Click the Spark > **Display Setup**: enter this monitor's size in mm and where the Spark sits,
   and save. Close Eye Tracker Manager before starting the app.
3. **Thai voice.** Settings > Time & language > Language & region > **Add a language** > Thai.
   In the optional features tick **Text-to-speech** (the other Thai features are not needed, and
   Thai does not have to become the display language). Restart the PC. Check it under
   Settings > Time & language > Speech > Manage voices: **Microsoft Pattara** is listed.
4. **Display scale.** The app fills the screen at any scale, so the Windows "Scale" setting
   (Settings > System > Display) can stay as it is.

## 3. Install and start

1. Double-click `CommunicationAid-<version>-Windows-Setup.exe`. Windows may say
   **"Windows protected your PC"** because the installer is not signed: click **More info**, then
   **Run anyway**. It installs for this Windows user only, so no administrator password is needed.
2. Start **Communication Aid** from the Start menu or the desktop icon. The first start downloads
   the translation model (about 2.5 GB), so keep the PC on the internet for the first few minutes;
   after that it runs offline.
3. Calibration runs first. Then press **F3** and check **Thai voice** shows *Automatic* or
   *Microsoft Pattara*; press **Try voice** to hear it.

No tracker? The app says so, and **Show Details** explains why. **Use the mouse** tries the app
without it; the Start menu also has *Communication Aid (mouse, no eye tracker)*.

Keys: F2 calibrate again, F3 settings, F4 pause / resume, Ctrl+G gaze dot, F11 full screen,
Ctrl+Q quit. On laptops whose F keys change volume or brightness, hold **Fn**. The caregiver can
type on the keyboard (letters, numbers, Space, Backspace, Enter to Speak) even with the Thai
keyboard layout on.

Settings, calibration and `app.log` are kept in `%USERPROFILE%\.commu_aid` (type that into the
File Explorer address bar). Send `app.log` when reporting a problem. Uninstall from Settings > Apps;
that folder stays.

## Updating

Run the newer Setup.exe over the old one. Settings and calibration are kept.

## Run from source (for development)

```powershell
conda env create -f environment.yml   # Python 3.10, the Tobii SDK, translation, pytest
conda activate commu-aid
python -m commu_aid --mouse --windowed    # try it with the mouse
python -m commu_aid                       # with the Spark
python -m commu_aid.check_tracker         # why the Spark is or isn't found
python -m pytest
```

Use Anaconda Prompt (or Miniconda). `environment.yml` installs `pywin32`, which the app uses to
reach the Windows voices.

## Build on Windows

```powershell
conda activate commu-aid
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
```

With [Inno Setup 6](https://jrsoftware.org/isdl.php) installed this makes
`dist\CommunicationAid-<version>-Windows-Setup.exe`; without it, a zip of the app folder.
`-NoTranslate` leaves out offline translation (much smaller; Speak then says the English) and
`-Version 0.2.0` sets the version.

## If something is wrong

- **"No Tobii eye tracker found"**: run *Show Details* (or `python -m commu_aid.check_tracker`).
  If Windows does not see a Tobii device on USB, replug the cable straight into the PC. If it
  does but the SDK finds no tracker, reinstall the Spark runtime and restart the PC.
- **Speaks in English, or silent, for Thai**: the Thai voice is not installed (step 2.3). The log
  lists the voices the app found ("Windows voices: ...").
- **Gaze misses towards the edges**: Display Setup in Eye Tracker Manager does not match this
  monitor; fix it and recalibrate (F2).
