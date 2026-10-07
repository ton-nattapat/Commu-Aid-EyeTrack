"""Caregiver Settings page (F3): dwell time and the Needs tiles, saved to config.yaml."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import DWELL_MAX_S, DWELL_MIN_S, DWELL_STEP_S, NEEDS_TILE_COUNT, AppConfig, NeedTile, clamp_dwell
from . import theme

STYLE = """
QWidget#settings { background: #101418; }
QLabel { color: #f4f6f8; }
QTableWidget { background: #1e252d; color: #f4f6f8; gridline-color: #3a4652; font-size: 26px; }
QHeaderView::section { background: #24324a; color: #f4f6f8; font-size: 24px; padding: 8px; border: none; }
QComboBox { font-size: 24px; background: #24324a; color: #f4f6f8; border: none; padding: 4px 12px; }
QComboBox QAbstractItemView { background: #24324a; color: #f4f6f8; selection-background-color: #3a4652; }
QPushButton { font-size: 28px; font-weight: bold; padding: 14px 40px;
              background: #24324a; color: #f4f6f8; border: 2px solid #3a4652; border-radius: 16px; }
QPushButton:hover { border-color: #f2c94c; }
QPushButton#dwellStep { font-size: 56px; padding: 0; border: 3px solid #f2c94c; border-radius: 20px; }
QPushButton#dwellStep:disabled { color: #5c6875; border-color: #3a4652; }
QSlider::groove:horizontal { height: 20px; background: #3a4652; border-radius: 10px; }
QSlider::sub-page:horizontal { background: #f2c94c; border-radius: 10px; }
QSlider::handle:horizontal { width: 44px; height: 44px; margin: -18px 0; border-radius: 28px;
                             background: #f4f6f8; border: 6px solid #f2c94c; }
"""

SLIDER_HANDLE = 56  # px, QSlider::handle width plus its border above
STEP_BUTTON = 110  # theme.MIN_TARGET


def _steps(seconds: float) -> int:
    """Slider position (number of DWELL_STEP_S steps) nearest to the given dwell time."""
    return round(clamp_dwell(seconds) / DWELL_STEP_S)


class SliderTicks(QWidget):
    """Labels under the dwell slider, one at each step, lined up with the handle's centre."""

    def __init__(self, slider: QSlider, parent=None):
        super().__init__(parent)
        self.slider = slider
        self.setFont(theme.font(26))
        self.setMinimumHeight(36)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        lo, hi = self.slider.minimum(), self.slider.maximum()
        span = self.width() - SLIDER_HANDLE
        for v in range(lo, hi + 1):
            x = SLIDER_HANDLE / 2 + span * (v - lo) / max(hi - lo, 1)
            p.setPen(theme.HOVER if v == self.slider.value() else theme.TEXT_QUIET)
            p.drawText(int(x) - 60, 0, 120, self.height(), Qt.AlignCenter, f"{v * DWELL_STEP_S:.1f}")


class SettingsPage(QWidget):
    def __init__(self, cfg: AppConfig, on_saved: Callable[[], None], on_closed: Callable[[], None], parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.on_saved = on_saved
        self.on_closed = on_closed
        self.setObjectName("settings")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(STYLE)
        self.setGeometry(0, 0, theme.CANVAS_W, theme.CANVAS_H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.MARGIN, 24, theme.MARGIN, 24)
        layout.setSpacing(16)

        title = QLabel("Caregiver settings")
        title.setFont(theme.font(56, bold=True))
        layout.addWidget(title)

        dwell_row = QHBoxLayout()
        dwell_row.setSpacing(theme.GAP)
        dwell_label = QLabel("Dwell time")
        dwell_label.setFont(theme.font(32, bold=True))
        self.dwell_value = QLabel()
        self.dwell_value.setFont(theme.font(40, bold=True))
        self.dwell_value.setMinimumWidth(160)
        self.dwell_slider = QSlider(Qt.Horizontal)
        self.dwell_slider.setRange(_steps(DWELL_MIN_S), _steps(DWELL_MAX_S))
        self.dwell_slider.setSingleStep(1)
        self.dwell_slider.setPageStep(1)
        self.dwell_slider.setMinimumHeight(64)
        self.dwell_less = self._step_button("\u2212", -1)
        self.dwell_more = self._step_button("+", 1)
        slider_column = QVBoxLayout()
        slider_column.setSpacing(4)
        slider_column.addWidget(self.dwell_slider)
        self.dwell_ticks = SliderTicks(self.dwell_slider)
        slider_column.addWidget(self.dwell_ticks)
        self.dwell_slider.valueChanged.connect(self._show_dwell)
        dwell_row.addWidget(dwell_label)
        dwell_row.addWidget(self.dwell_less)
        dwell_row.addLayout(slider_column, 1)
        dwell_row.addWidget(self.dwell_more)
        dwell_row.addWidget(self.dwell_value)
        layout.addLayout(dwell_row)

        tiles_label = QLabel("Needs tiles (the 12th tile always opens the keyboard)")
        tiles_label.setFont(theme.font(32, bold=True))
        layout.addWidget(tiles_label)

        self.table = QTableWidget(NEEDS_TILE_COUNT, 4)
        self.table.setHorizontalHeaderLabels(["Icon", "English label", "Thai phrase (spoken)", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(3, 220)
        self.table.verticalHeader().setDefaultSectionSize(54)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel (Esc)")
        cancel.clicked.connect(self.cancel)
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def load(self) -> None:
        self.dwell_slider.setValue(_steps(self.cfg.dwell.dwell_time_s))
        self._show_dwell(self.dwell_slider.value())
        for row in range(NEEDS_TILE_COUNT):
            tile = self.cfg.needs[row] if row < len(self.cfg.needs) else NeedTile("", "")
            for col, value in enumerate((tile.icon, tile.label, tile.thai)):
                self.table.setItem(row, col, QTableWidgetItem(value))
            action = QComboBox()
            action.addItems(["speak", "alert"])
            action.setCurrentText(tile.action if tile.action in ("speak", "alert") else "speak")
            self.table.setCellWidget(row, 3, action)

    def save(self) -> None:
        self.cfg.dwell.dwell_time_s = clamp_dwell(self.dwell_slider.value() * DWELL_STEP_S)
        needs = []
        for row in range(NEEDS_TILE_COUNT):
            icon, label, thai = (self._text(row, c) for c in range(3))
            if not label and not thai:
                continue
            needs.append(NeedTile(label=label, thai=thai, icon=icon, action=self.table.cellWidget(row, 3).currentText()))
        self.cfg.needs = needs
        if self.cfg.path is not None:
            self.cfg.save()
        self.on_saved()
        self.on_closed()

    def _step_button(self, text: str, direction: int) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("dwellStep")
        button.setFixedSize(STEP_BUTTON, STEP_BUTTON)
        button.clicked.connect(lambda: self.dwell_slider.setValue(self.dwell_slider.value() + direction))
        return button

    def _show_dwell(self, steps: int) -> None:
        self.dwell_value.setText(f"{steps * DWELL_STEP_S:.1f} s")
        self.dwell_less.setEnabled(steps > self.dwell_slider.minimum())
        self.dwell_more.setEnabled(steps < self.dwell_slider.maximum())
        self.dwell_ticks.update()

    def cancel(self) -> None:
        self.on_closed()

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)
