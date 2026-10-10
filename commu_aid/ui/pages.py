"""Page 1 (Needs) and page 2 (Keyboard).

Both pages sit under the message bar and keep their page-switch button in the same
bottom-right corner, so the patient always knows where it is.
"""

from __future__ import annotations

from typing import Callable, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QFontMetrics
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
    """Yes and No down the left, Delete and Clear down the right, and between them the word
    suggestions, a number row and the letters. Speak, Needs and Pause sit beside the message bar."""

    ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
    OFFSETS = [0, 0, 0.5, 0]
    UNITS = 10  # keys per full row
    SUGGESTIONS = 6  # word prediction buttons across the top row
    WORD_PX = 40
    ANSWERS = [("yes", "Yes", "ใช่"), ("no", "No", "ไม่ใช่")]  # key, shown, spoken

    def __init__(
        self,
        on_letter: Callable[[str], None],
        on_word: Callable[[str], None],
        on_delete: Callable[[], None],
        on_clear: Callable[[], None],
        on_answer: Callable[[str, str], None],
        area=None,
        parent=None,
    ):
        super().__init__(area, parent)
        area_w, area_h = self.width(), self.height()
        gap, col_w = theme.KEY_GAP, theme.KEY_COLUMN_W

        def column(x: int, buttons: List[DwellButton]) -> None:
            h = (area_h - (len(buttons) - 1) * gap) / len(buttons)
            for i, b in enumerate(buttons):
                self.add(b, QRect(x, round(i * (h + gap)), col_w, round(h)))

        column(0, [
            DwellButton(key, label.upper(), lambda e=label, t=thai: on_answer(e, t), variant=key, label_px=60)
            for key, label, thai in self.ANSWERS
        ])
        # Delete is used most, so it is tall and away from the corners; Clear sits below it.
        column(area_w - col_w, [
            DwellButton("delete", "Delete", on_delete, icon="⌫", variant="nav", label_px=44),
            DwellButton("clear", "Clear", on_clear, label_px=44),
        ])

        keys_x = col_w + gap
        keys_w = area_w - 2 * keys_x
        unit_w = (keys_w - (self.UNITS - 1) * gap) / self.UNITS
        row_h = (area_h - len(self.ROWS) * gap) / (len(self.ROWS) + 1)

        def rect(col: float, row: int, span: float = 1) -> QRect:
            x = keys_x + col * (unit_w + gap)
            w = span * unit_w + (span - 1) * gap
            return QRect(round(x), round(row * (row_h + gap)), round(w), round(row_h))

        # Row 0: predicted words. Picking one finishes the current word and adds a space.
        word_w = (keys_w - (self.SUGGESTIONS - 1) * gap) / self.SUGGESTIONS
        self.suggestion_buttons: List[DwellButton] = []
        for i in range(self.SUGGESTIONS):
            b = DwellButton(("word", i), "", lambda i=i: on_word(self.suggestion_buttons[i].label), label_px=self.WORD_PX, variant="word")
            self.suggestion_buttons.append(
                self.add(b, QRect(round(keys_x + i * (word_w + gap)), 0, round(word_w), round(row_h)))
            )

        for r, (chars, offset) in enumerate(zip(self.ROWS, self.OFFSETS)):
            for c, ch in enumerate(chars):
                self.add(DwellButton(("key", ch), ch, lambda ch=ch: on_letter(ch), label_px=60), rect(offset + c, r + 1))
        self.add(DwellButton("space", "Space", lambda: on_letter(" "), label_px=44), rect(7, len(self.ROWS), 3))

    def set_suggestions(self, words: List[str]) -> None:
        """Show up to SUGGESTIONS words; unused buttons are hidden so they cannot be chosen."""
        for i, b in enumerate(self.suggestion_buttons):
            word = words[i] if i < len(words) else ""
            if word != b.label:
                b.label = word
                b.label_px = self.WORD_PX
                room = b.width() - 24
                while b.label_px > 24 and QFontMetrics(theme.font(b.label_px, bold=True)).horizontalAdvance(word) > room:
                    b.label_px -= 2  # long words still fit
                b.set_state(False, 0.0)
                b.update()
            b.setVisible(bool(word))
