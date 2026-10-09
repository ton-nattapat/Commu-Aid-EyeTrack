"""Colours and sizes shared by every screen. The layout is fixed at 1920x1080."""

from typing import Tuple

from PySide6.QtGui import QColor, QFont

CANVAS_W = 1920
CANVAS_H = 1080
MARGIN = 60
GAP = 36  # at least 1 cm between targets on a 24-inch screen
MIN_TARGET = 110  # at least 3 cm

BAR_Y = 36
BAR_H = 140
BAR_BUTTON_W = 220  # Speak, Needs and Pause beside the message bar
GRID_TOP = BAR_Y + BAR_H + GAP

# The keyboard page: a tall column of big buttons down each side, and between them 5 rows of keys,
# 10 across. Its gaps are narrower so the keys can be bigger; snap_px still gives a look into a gap
# to the nearest key. The side columns are large, so they may sit nearer the screen edge than keys.
KEY_GAP = 24
KEY_COLUMN_W = 180
KEYBOARD_SIDE_MARGIN = MARGIN

# The keyboard is the densest page; this limit keeps its keys >= MIN_TARGET tall.
MAX_SIDE_MARGIN = (CANVAS_W - 9 * GAP - 10 * MIN_TARGET) // 2
MAX_BOTTOM_MARGIN = CANVAS_H - GRID_TOP - 4 * KEY_GAP - 5 * MIN_TARGET


def content_area(side_margin: float = MARGIN, bottom_margin: float = GAP) -> Tuple[int, int, int, int]:
    """Left, top, width, height of the button area, kept clear of the screen edges by the given margins.

    Tobii trackers are least accurate near the edges, worst at the bottom next to the tracker, so
    buttons stay inside this area. Margins are clamped so every target stays at least MIN_TARGET.
    """
    side = int(min(max(side_margin, 0), MAX_SIDE_MARGIN))
    bottom = int(min(max(bottom_margin, 0), MAX_BOTTOM_MARGIN))
    return side, GRID_TOP, CANVAS_W - 2 * side, CANVAS_H - bottom - GRID_TOP

BACKGROUND = QColor("#101418")
SURFACE = QColor("#1e252d")
SURFACE_NAV = QColor("#24324a")
SURFACE_ALERT = QColor("#4a2024")
SURFACE_WORD = QColor("#1d3a3a")  # word prediction buttons
SURFACE_YES = QColor("#1f4a2c")
SURFACE_NO = QColor("#4a2024")
BORDER = QColor("#3a4652")
HOVER = QColor("#f2c94c")
PROGRESS = QColor(242, 201, 76, 110)
FLASH = QColor("#f2c94c")
TEXT = QColor("#f4f6f8")
TEXT_QUIET = QColor("#a8b3bd")
WARNING = QColor("#ff9f6b")
GAZE_DOT = QColor(80, 170, 255, 170)
LEFT_EYE = QColor("#5aa9ff")  # calibration samples and live gaze, per eye
RIGHT_EYE = QColor("#ff6b9a")
BOTH_EYES = QColor("#7ee0a1")  # a sample with no per-eye data (mouse or simulated gaze)


def font(size_px: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(size_px)
    f.setBold(bold)
    return f
