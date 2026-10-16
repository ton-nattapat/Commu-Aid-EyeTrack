"""The letter-group keyboard: a second keyboard page for testing, beside the QWERTY one.

The patient first picks one of 7 big groups (A B C D, E F G H, ... U V W X, Y Z . ?), then one of
the 4 big keys in that group, and the page goes back to the groups. The 8th big button is Space,
typed in one look because it is used most. Each choice is a far bigger target than a QWERTY key,
at the cost of two looks per letter.

Yes and No sit down the left, a small Clear above a tall Delete on the right, and the word
suggestions across the top, as on the QWERTY page. F5 switches between the two keyboards.
"""

from __future__ import annotations

from typing import Callable, List

from PySide6.QtCore import QRect
from PySide6.QtGui import QFontMetrics

from . import theme
from .dwell_button import DwellButton
from .pages import KeyboardPage, Page

GROUPS = ["ABCD", "EFGH", "IJKL", "MNOP", "QRST", "UVWX", "YZ.?"]
GROUP_COLS = 4  # 2 rows of 4: the 7 groups, then Space


class GroupKeyboardPage(Page):
    SUGGESTIONS = KeyboardPage.SUGGESTIONS
    WORD_PX = KeyboardPage.WORD_PX
    ANSWERS = KeyboardPage.ANSWERS
    WORD_ROWS = 5  # the word row is as tall as on the QWERTY page (one of its 5 rows)

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
        self.on_letter = on_letter
        self.on_word = on_word
        area_w, area_h = self.width(), self.height()
        gap, col_w = theme.KEY_GAP, theme.KEY_COLUMN_W

        def edges(x: float, y: float, w: float, h: float) -> QRect:
            """Round the edges, not the sizes, so touching keys never overlap by a pixel."""
            left, top = round(x), round(y)
            return QRect(left, top, round(x + w) - left, round(y + h) - top)

        answer_h = (area_h - gap) / 2
        for i, (key, label, thai) in enumerate(self.ANSWERS):
            b = DwellButton(key, label.upper(), lambda e=label, t=thai: on_answer(e, t), variant=key, label_px=60)
            self.add(b, edges(0, i * (answer_h + gap), col_w, answer_h))

        keys_x = col_w + gap
        keys_w = area_w - 2 * keys_x
        word_h = (area_h - (self.WORD_ROWS - 1) * gap) / self.WORD_ROWS

        right_x = area_w - col_w
        self.add(DwellButton("clear", "Clear", on_clear, label_px=44), edges(right_x, 0, col_w, word_h))
        delete_y = round(word_h + gap)
        self.add(
            DwellButton("delete", "Delete", on_delete, icon="⌫", variant="nav", label_px=44),
            QRect(right_x, delete_y, col_w, area_h - delete_y),
        )

        word_w = (keys_w - (self.SUGGESTIONS - 1) * gap) / self.SUGGESTIONS
        self.suggestion_buttons: List[DwellButton] = []
        for i in range(self.SUGGESTIONS):
            b = DwellButton(("word", i), "", lambda i=i: self._word(i), label_px=self.WORD_PX, variant="word")
            self.suggestion_buttons.append(self.add(b, edges(keys_x + i * (word_w + gap), 0, word_w, word_h)))

        # Below the words: the 8 groups in 2 rows of 4, or the 4 keys of the open group and Back.
        top = word_h + gap
        body_h = area_h - top
        cell_w = (keys_w - (GROUP_COLS - 1) * gap) / GROUP_COLS
        group_h = (body_h - gap) / 2

        self.group_buttons: List[DwellButton] = []
        def cell(i: int) -> QRect:
            row, col = divmod(i, GROUP_COLS)
            return edges(keys_x + col * (cell_w + gap), top + row * (group_h + gap), cell_w, group_h)

        for i, chars in enumerate(GROUPS):
            b = DwellButton(("group", i), "  ".join(chars), lambda i=i: self.open_group(i), label_px=64)
            self.group_buttons.append(self.add(b, cell(i)))
        space = DwellButton("space", "Space", lambda: on_letter(" "), label_px=64)
        self.group_buttons.append(self.add(space, cell(len(GROUPS))))

        # The letters are taller than a group; Back fills the strip below them.
        letter_h = round((body_h - gap) * 0.65)
        self.letter_buttons: List[DwellButton] = []
        for i in range(GROUP_COLS):
            b = DwellButton(("letter", i), "", lambda i=i: self._letter(i), label_px=110)
            self.letter_buttons.append(self.add(b, edges(keys_x + i * (cell_w + gap), top, cell_w, letter_h)))
        back_y = top + letter_h + gap
        self.back_button = self.add(
            DwellButton("back", "Back to groups", self.show_groups, icon="↩", variant="nav", label_px=40),
            edges(keys_x, back_y, keys_w, area_h - back_y),
        )
        self.open_index = -1  # the group whose keys are showing, or -1 for the groups
        self.show_groups()

    # Stages

    def open_group(self, i: int) -> None:
        self.open_index = i
        for b, ch in zip(self.letter_buttons, GROUPS[i]):
            b.label = ch
            b.update()
        self._show_stage(groups=False)

    def show_groups(self) -> None:
        self.open_index = -1
        self._show_stage(groups=True)

    def _show_stage(self, groups: bool) -> None:
        for b in self.group_buttons:
            b.set_state(False, 0.0)
            b.setVisible(groups)
        for b in (*self.letter_buttons, self.back_button):
            b.set_state(False, 0.0)
            b.setVisible(not groups)

    def _letter(self, i: int) -> None:
        if self.open_index < 0:
            return
        ch = GROUPS[self.open_index][i]
        self.show_groups()
        self.on_letter(ch)

    def _word(self, i: int) -> None:
        word = self.suggestion_buttons[i].label
        self.show_groups()
        self.on_word(word)

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
