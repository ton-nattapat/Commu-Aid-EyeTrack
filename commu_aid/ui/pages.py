"""Page 1 (Needs) and page 2 (Keyboard).

Both pages sit under the message bar and keep their page-switch button in the same
bottom-right corner, so the patient always knows where it is.
"""

from __future__ import annotations

from typing import Callable, List

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from ..config import NeedTile
from . import theme
from .dwell_button import DwellButton

AREA_W = theme.CANVAS_W - 2 * theme.MARGIN
AREA_H = theme.GRID_BOTTOM - theme.GRID_TOP


class Page(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setGeometry(theme.MARGIN, theme.GRID_TOP, AREA_W, AREA_H)
        self.buttons: List[DwellButton] = []

    def clear_buttons(self) -> None:
        for b in self.buttons:
            b.deleteLater()
        self.buttons = []

    def add(self, button: DwellButton, rect: QRect) -> DwellButton:
        button.setParent(self)
        button.setGeometry(rect)
        button.show()
        self.buttons.append(button)
        return button


class NeedsPage(Page):
    COLS = 4
    ROWS = 3

    def __init__(self, needs: List[NeedTile], on_need: Callable[[NeedTile], None], on_keyboard: Callable[[], None], parent=None):
        super().__init__(parent)
        self.on_need = on_need
        self.on_keyboard = on_keyboard
        self.set_needs(needs)

    def set_needs(self, needs: List[NeedTile]) -> None:
        self.clear_buttons()
        w = (AREA_W - (self.COLS - 1) * theme.GAP) // self.COLS
        h = (AREA_H - (self.ROWS - 1) * theme.GAP) // self.ROWS

        def cell(i: int) -> QRect:
            row, col = divmod(i, self.COLS)
            return QRect(col * (w + theme.GAP), row * (h + theme.GAP), w, h)

        slots = self.COLS * self.ROWS - 1  # the last cell is the keyboard button
        for i, tile in enumerate(needs[:slots]):
            variant = "alert" if tile.action == "alert" else "normal"
            self.add(
                DwellButton(("need", i), tile.label, lambda t=tile: self.on_need(t), icon=tile.icon, variant=variant),
                cell(i),
            )
        self.add(DwellButton("nav", "Keyboard", self.on_keyboard, icon="⌨️", variant="nav"), cell(slots))


class KeyboardPage(Page):
    ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
    UNITS = 10  # keys per full row

    def __init__(
        self,
        on_letter: Callable[[str], None],
        on_delete: Callable[[], None],
        on_clear: Callable[[], None],
        on_speak: Callable[[], None],
        on_needs: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        unit_w = (AREA_W - (self.UNITS - 1) * theme.GAP) / self.UNITS
        row_h = (AREA_H - 3 * theme.GAP) / 4

        def rect(col: float, row: int, span: float = 1) -> QRect:
            x = col * (unit_w + theme.GAP)
            w = span * unit_w + (span - 1) * theme.GAP
            return QRect(round(x), round(row * (row_h + theme.GAP)), round(w), round(row_h))

        offsets = [0, 0.5, 0]
        for r, letters in enumerate(self.ROWS):
            for c, ch in enumerate(letters):
                self.add(DwellButton(("key", ch), ch, lambda ch=ch: on_letter(ch), label_px=64), rect(offsets[r] + c, r))
        self.add(DwellButton("delete", "Delete", on_delete, label_px=44), rect(7, 2, 3))
        self.add(DwellButton("space", "Space", lambda: on_letter(" "), label_px=44), rect(0, 3, 4))
        self.add(DwellButton("clear", "Clear", on_clear, label_px=44), rect(4, 3, 2))
        self.add(DwellButton("speak", "Speak", on_speak, icon="🔊", label_px=44, variant="nav"), rect(6, 3, 2))
        self.add(DwellButton("nav", "Needs", on_needs, icon="🏠", label_px=44, variant="nav"), rect(8, 3, 2))
