"""A large button that fills with progress while the patient looks at it."""

from __future__ import annotations

from typing import Callable, Hashable, Optional

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class DwellButton(QWidget):
    def __init__(
        self,
        key: Hashable,
        label: str,
        on_select: Callable[[], None],
        icon: str = "",
        variant: str = "normal",  # normal | nav | alert | word
        label_px: int = 48,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.icon = icon
        self.variant = variant
        self.label_px = label_px
        self.on_select = on_select
        self.progress = 0.0
        self.gazed = False
        self._flash = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_state(self, gazed: bool, progress: float) -> None:
        if gazed != self.gazed or abs(progress - self.progress) > 0.001:
            self.gazed = gazed
            self.progress = progress
            self.update()

    def activate(self) -> None:
        self._flash = True
        self.progress = 0.0
        self.update()
        QTimer.singleShot(300, self._end_flash)
        self.on_select()

    def _end_flash(self) -> None:
        self._flash = False
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        radius = 24
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)

        fill = {"nav": theme.SURFACE_NAV, "alert": theme.SURFACE_ALERT, "word": theme.SURFACE_WORD}.get(self.variant, theme.SURFACE)
        p.fillPath(path, theme.FLASH if self._flash else fill)

        if self.progress > 0 and not self._flash:
            # Progress fills from the bottom up, easy to see from the corner of the eye.
            p.save()
            p.setClipPath(path)
            h = r.height() * self.progress
            p.fillRect(QRectF(r.left(), r.bottom() - h, r.width(), h), theme.PROGRESS)
            p.restore()

        pen = QPen(theme.HOVER if self.gazed else theme.BORDER, 8 if self.gazed else 3)
        p.setPen(pen)
        p.drawPath(path)

        text_color = QColor("#101418") if self._flash else theme.TEXT
        p.setPen(text_color)
        if self.icon:
            icon_px = int(min(r.height() * 0.38, 110))
            p.setFont(theme.font(icon_px))
            icon_rect = QRectF(r.left(), r.top() + r.height() * 0.08, r.width(), r.height() * 0.5)
            p.drawText(icon_rect, Qt.AlignCenter, self.icon)
            p.setFont(theme.font(self.label_px, bold=True))
            label_rect = QRectF(r.left() + 8, r.top() + r.height() * 0.55, r.width() - 16, r.height() * 0.4)
            p.drawText(label_rect, Qt.AlignCenter | Qt.TextWordWrap, self.label)
        else:
            p.setFont(theme.font(self.label_px, bold=True))
            p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, self.label)
        p.end()
