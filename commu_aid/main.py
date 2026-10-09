"""Start the Communication Aid.

    python -m commu_aid                  # Tobii Pro Spark, calibration at start-up
    python -m commu_aid --mouse          # no tracker: the mouse pointer stands in for gaze
    python -m commu_aid --mouse --calibration-demo   # rehearse the calibration screen with the mouse
    python -m commu_aid --simulate       # mouse plus realistic gaze jitter, offset, blinks and dropouts
    python -m commu_aid --simulate hard  # mild, typical (default), hard or edges
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="commu_aid", description="Eye-tracking communication aid")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="settings file (default: config.yaml)")
    ap.add_argument("--mouse", action="store_true", help="use the mouse instead of the eye tracker")
    ap.add_argument(
        "--simulate", nargs="?", const="typical", choices=("mild", "typical", "hard", "edges"), metavar="LEVEL",
        help="simulated eye tracker: the mouse with gaze jitter, offset, blinks and dropouts "
        "(LEVEL: mild, typical, hard or edges; default typical). Implies --mouse",
    )
    ap.add_argument("--sim-seed", type=int, help="with --simulate: repeat the same random jitter and blinks")
    ap.add_argument("--calibration-demo", action="store_true", help="with --mouse: show a pretend calibration")
    ap.add_argument("--skip-calibration", action="store_true", help="use the saved calibration instead")
    ap.add_argument("--windowed", action="store_true", help="open in a window instead of full screen")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
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
    cfg = load_config(args.config)

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
        except ImportError:
            QMessageBox.critical(
                None, "Communication Aid",
                "The Tobii Pro SDK (tobii-research) is not installed.\n"
                "Install it with Python 3.10: pip install -r requirements-tobii.txt\n"
                "or start with --mouse to try the app without the tracker.",
            )
            return 1
        except Exception as exc:
            QMessageBox.critical(None, "Communication Aid", f"{exc}\n\nStart with --mouse to try the app without it.")
            return 1
        logging.info("Using eye tracker %s", source.description)

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
