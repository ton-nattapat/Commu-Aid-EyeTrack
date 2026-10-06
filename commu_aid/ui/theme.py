"""Colours and sizes shared by every screen. The layout is fixed at 1920x1080."""

from PySide6.QtGui import QColor, QFont

CANVAS_W = 1920
CANVAS_H = 1080
MARGIN = 60
GAP = 36  # at least 1 cm between targets on a 24-inch screen
MIN_TARGET = 110  # at least 3 cm

BAR_Y = 36
BAR_H = 200
GRID_TOP = BAR_Y + BAR_H + GAP
GRID_BOTTOM = CANVAS_H - GAP

BACKGROUND = QColor("#101418")
SURFACE = QColor("#1e252d")
SURFACE_NAV = QColor("#24324a")
SURFACE_ALERT = QColor("#4a2024")
BORDER = QColor("#3a4652")
HOVER = QColor("#f2c94c")
PROGRESS = QColor(242, 201, 76, 110)
FLASH = QColor("#f2c94c")
TEXT = QColor("#f4f6f8")
TEXT_QUIET = QColor("#a8b3bd")
WARNING = QColor("#ff9f6b")
GAZE_DOT = QColor(80, 170, 255, 170)


def font(size_px: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(size_px)
    f.setBold(bold)
    return f
