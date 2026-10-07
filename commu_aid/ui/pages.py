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


class Page(QWidget):
    """A page of buttons filling `area` (left, top, width, height on the canvas), see theme.content_area."""

    def __init__(self, area=None, parent=None):
        super().__init__(parent)
        self.setGeometry(QRect(*(area or theme.content_area())))
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

    def __init__(
        self, needs: List[NeedTile], on_need: Callable[[NeedTile], None], on_keyboard: Callable[[], None],
        area=None, parent=None,
    ):
        super().__init__(area, parent)
        self.on_need = on_need
        self.on_keyboard = on_keyboard
        self.set_needs(needs)

    def set_needs(self, needs: List[NeedTile]) -> None:
        self.clear_buttons()
        w = (self.width() - (self.COLS - 1) * theme.GAP) // self.COLS
        h = (self.height() - (self.ROWS - 1) * theme.GAP) // self.ROWS

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
    SUGGESTIONS = 4  # word prediction buttons across the top row

    def __init__(
        self,
        on_letter: Callable[[str], None],
        on_word: Callable[[str], None],
        on_delete: Callable[[], None],
        on_clear: Callable[[], None],
        on_needs: Callable[[], None],
        area=None,
        parent=None,
    ):
        super().__init__(area, parent)
        area_w, area_h = self.width(), self.height()
        unit_w = (area_w - (self.UNITS - 1) * theme.GAP) / self.UNITS
        row_h = (area_h - 4 * theme.GAP) / 5

        def rect(col: float, row: int, span: float = 1) -> QRect:
            x = col * (unit_w + theme.GAP)
            w = span * unit_w + (span - 1) * theme.GAP
            return QRect(round(x), round(row * (row_h + theme.GAP)), round(w), round(row_h))

        # Row 0: predicted words. Picking one finishes the current word and adds a space.
        word_w = (area_w - (self.SUGGESTIONS - 1) * theme.GAP) / self.SUGGESTIONS
        self.suggestion_buttons: List[DwellButton] = []
        for i in range(self.SUGGESTIONS):
            b = DwellButton(("word", i), "", lambda i=i: on_word(self.suggestion_buttons[i].label), label_px=48, variant="word")
            self.suggestion_buttons.append(
                self.add(b, QRect(round(i * (word_w + theme.GAP)), 0, round(word_w), round(row_h)))
            )

        offsets = [0, 0.5, 0]
        for r, letters in enumerate(self.ROWS):
            for c, ch in enumerate(letters):
                self.add(DwellButton(("key", ch), ch, lambda ch=ch: on_letter(ch), label_px=64), rect(offsets[r] + c, r + 1))
        self.add(DwellButton("delete", "Delete", on_delete, label_px=44), rect(7, 3, 3))
        # Speak sits in the top row beside Pause (see MainWindow), away from the letters.
        self.add(DwellButton("space", "Space", lambda: on_letter(" "), label_px=44), rect(0, 4, 5))
        self.add(DwellButton("clear", "Clear", on_clear, label_px=44), rect(5, 4, 3))
        self.add(DwellButton("nav", "Needs", on_needs, icon="🏠", label_px=44, variant="nav"), rect(8, 4, 2))

    def set_suggestions(self, words: List[str]) -> None:
        """Show up to SUGGESTIONS words; unused buttons are hidden so they cannot be chosen."""
        for i, b in enumerate(self.suggestion_buttons):
            word = words[i] if i < len(words) else ""
            if word != b.label:
                b.label = word
                b.label_px = 48 if len(word) <= 11 else max(30, 48 * 11 // len(word))  # long words still fit
                b.set_state(False, 0.0)
                b.update()
            b.setVisible(bool(word))
