"""The rest screen: every button is off except one large Resume button at the top centre.

Resume sits away from where the patient looks while resting (the TV, a visitor) and needs a
longer look than other buttons, so a passing glance does not wake the screen.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import theme
from .dwell_button import DwellButton

RESUME_W = 520
RESUME_H = 320


class PauseScreen(QWidget):
    def __init__(self, on_resume: Callable[[], None], resume_dwell_s: float, parent=None):
        super().__init__(parent)
        self.setGeometry(0, 0, theme.CANVAS_W, theme.CANVAS_H)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.resume_dwell_s = resume_dwell_s
        self.resume_button = DwellButton("resume", "Resume", on_resume, icon="▶️", variant="resume", label_px=56)
        self.resume_button.setParent(self)
        self.resume_button.setGeometry(QRect((theme.CANVAS_W - RESUME_W) // 2, theme.BAR_Y, RESUME_W, RESUME_H))
        self.buttons = [self.resume_button]

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), theme.BACKGROUND)
        top = theme.BAR_Y + RESUME_H + 120
        p.setPen(theme.TEXT_QUIET)
        p.setFont(theme.font(96, bold=True))
        p.drawText(QRectF(0, top, theme.CANVAS_W, 140), Qt.AlignCenter, "Resting")
        p.setFont(theme.font(40))
        p.drawText(
            QRectF(0, top + 160, theme.CANVAS_W, 80), Qt.AlignCenter,
            f"Look at Resume for {self.resume_dwell_s:g} seconds to come back",
        )
        p.end()
