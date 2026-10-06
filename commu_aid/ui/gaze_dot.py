"""A translucent dot showing where the tracker thinks the patient is looking."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter

from . import theme


class GazeDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.point: Optional[QPointF] = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def set_point(self, point: Optional[QPointF]) -> None:
        if point != self.point:
            self.point = point
            self.update()

    def paintEvent(self, _event) -> None:
        if self.point is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.GAZE_DOT)
        p.drawEllipse(self.point, 22, 22)
        p.end()
