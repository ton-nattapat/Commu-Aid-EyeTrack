"""Start the Communication Aid.

    python -m commu_aid                  # Tobii Pro Spark, calibration at start-up
    python -m commu_aid --mouse          # no tracker: the mouse pointer stands in for gaze
    python -m commu_aid --mouse --calibration-demo   # rehearse the calibration screen with the mouse
    python -m commu_aid --simulate       # mouse plus realistic gaze jitter, offset, blinks and dropouts
    python -m commu_aid --simulate hard  # mild, typical (default) or hard
    python -m commu_aid --check-tracker  # same as python -m commu_aid.check_tracker
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import shutil
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
USER_DIR = Path("~/.commu_aid").expanduser()

# True inside the packaged Mac app (PyInstaller), where the bundle itself is read-only.
FROZEN = getattr(sys, "frozen", False)


def default_config_path(frozen: bool = FROZEN, bundled: Path = DEFAULT_CONFIG, user_dir: Path = USER_DIR) -> Path:
    """config.yaml in the project folder, or for the packaged app ~/.commu_aid/config.yaml.

    The packaged app can't write inside its own bundle, so on first start it copies the bundled
    config.yaml there and the Settings page (F3) saves to that copy.
    """
    if not frozen:
        return bundled
    path = user_dir / "config.yaml"
    if not path.exists():
        user_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled, path)
    return path


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="commu_aid", description="Eye-tracking communication aid")
    ap.add_argument("--config", type=Path, help="settings file (default: config.yaml; the Mac app uses ~/.commu_aid/config.yaml)")
    ap.add_argument("--mouse", action="store_true", help="use the mouse instead of the eye tracker")
    ap.add_argument(
        "--simulate", nargs="?", const="typical", choices=("mild", "typical", "hard"), metavar="LEVEL",
        help="simulated eye tracker: the mouse with gaze jitter, offset, blinks and dropouts "
        "(LEVEL: mild, typical or hard; default typical). Implies --mouse",
    )
    ap.add_argument("--sim-seed", type=int, help="with --simulate: repeat the same random jitter and blinks")
    ap.add_argument("--calibration-demo", action="store_true", help="with --mouse: show a pretend calibration")
    ap.add_argument("--skip-calibration", action="store_true", help="use the saved calibration instead")
    ap.add_argument("--windowed", action="store_true", help="open in a window instead of full screen")
    ap.add_argument("--check-tracker", action="store_true", help="check the eye tracker set-up and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.check_tracker:
        from .check_tracker import main as check_tracker

        return check_tracker()
    handlers = [logging.StreamHandler()]
    if FROZEN:
        # Opened from Finder there is no terminal, so keep a log next to the other app files.
        USER_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(USER_DIR / "app.log", mode="w", encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )

    from PySide6.QtWidgets import QApplication, QMessageBox

    from .config import load_config
    from .gaze.mouse_source import MouseDemoCalibrationSource, MouseGazeSource
    from .sounds import Sounds
    from .speech import Speaker
    from .translate import Translator
    from .ui.main_window import DATA_DIR, MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Communication Aid")
    cfg = load_config(args.config or default_config_path())

    if args.mouse or args.simulate:
        source = MouseDemoCalibrationSource() if args.calibration_demo else MouseGazeSource()
        if args.simulate:
            from .gaze.simulated_source import PROFILES, SimulatedGazeSource

            source = SimulatedGazeSource(
                source, PROFILES[args.simulate], (cfg.display.width, cfg.display.height), seed=args.sim_seed
            )
            logging.info("Simulated eye tracker (%s)", args.simulate)
    else:
        try:
            from .gaze.tobii_source import TobiiGazeSource

            source = TobiiGazeSource()
            logging.info("Using eye tracker %s", source.description)
        except ImportError:
            logging.exception("Tobii SDK not available")
            problem = (
                "The Tobii Pro SDK (tobii-research) is not installed.\n"
                "Install it with Python 3.10: pip install -r requirements-tobii.txt"
            )
            source = _mouse_instead(QMessageBox, problem)
        except Exception as exc:
            logging.exception("Eye tracker not available")
            source = _mouse_instead(QMessageBox, str(exc))
        if source is None:
            return 1

    translator = Translator(cfg.translation)
    if cfg.language.speak == "th" and cfg.language.translate:
        translator.preload()

    window = MainWindow(
        cfg, source, Speaker(cfg.speech), translator, Sounds(DATA_DIR / "sounds"),
        calibrate_on_start=not args.skip_calibration,
    )
    if args.windowed:
        window.resize(1280, 720)
        window.show()
    else:
        window.showFullScreen()
    return app.exec()


def _mouse_instead(QMessageBox, problem: str):
    """Tell the caregiver the tracker can't be used; offer the mouse instead (None = quit)."""
    box = QMessageBox(QMessageBox.Icon.Critical, "Communication Aid", problem)
    box.setInformativeText("You can try the app with the mouse standing in for gaze.")
    report = _tracker_report()
    if report:
        box.setDetailedText(report)
    use_mouse = box.addButton("Use the mouse", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(use_mouse)
    box.exec()
    if box.clickedButton() is not use_mouse:
        return None
    from .gaze.mouse_source import MouseGazeSource

    logging.info("Using the mouse instead of the eye tracker")
    return MouseGazeSource()


def _tracker_report() -> str:
    """What `python -m commu_aid.check_tracker` prints, for the dialog's Show Details."""
    from .check_tracker import main as check_tracker

    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            check_tracker()
    except Exception:
        logging.exception("Eye tracker check failed")
    report = out.getvalue()
    logging.info("Eye tracker check:\n%s", report)
    return report
