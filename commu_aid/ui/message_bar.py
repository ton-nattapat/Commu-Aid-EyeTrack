"""The bar across the top: the English text, and under it the Thai that is spoken."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class MessageBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.english = ""
        self.thai = ""
        self.note = ""
        self.note_is_warning = False
        self.typing = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def show_message(self, english: str, thai: str = "", note: str = "", warning: bool = False) -> None:
        self.english, self.thai, self.note, self.note_is_warning = english, thai, note, warning
        self.typing = False
        self.update()

    def show_typing(self, text: str) -> None:
        self.english, self.thai, self.note, self.note_is_warning = text, "", "", False
        self.typing = True
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(r, 20, 20)
        p.fillPath(path, theme.SURFACE)
        p.setPen(QPen(theme.BORDER, 2))
        p.drawPath(path)

        inner = r.adjusted(40, 16, -40, -16)
        english = self.english + ("|" if self.typing else "")
        p.setPen(theme.TEXT)
        p.setFont(theme.font(72, bold=True))
        top = QRectF(inner.left(), inner.top(), inner.width(), inner.height() * 0.55)
        p.drawText(top, Qt.AlignLeft | Qt.AlignVCenter, _elide_left(p, english, top.width()))

        bottom = QRectF(inner.left(), inner.top() + inner.height() * 0.55, inner.width(), inner.height() * 0.45)
        if self.thai:
            p.setFont(theme.font(56))
            p.setPen(theme.TEXT)
            p.drawText(bottom, Qt.AlignLeft | Qt.AlignVCenter, self.thai)
        if self.note:
            p.setFont(theme.font(32))
            p.setPen(theme.WARNING if self.note_is_warning else theme.TEXT_QUIET)
            p.drawText(bottom, Qt.AlignRight | Qt.AlignVCenter, self.note)
        p.end()


def _elide_left(p: QPainter, text: str, width: float) -> str:
    """Keep the end of a long typed message visible."""
    return p.fontMetrics().elidedText(text, Qt.ElideLeft, int(width))
