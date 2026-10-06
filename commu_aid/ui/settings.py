"""Caregiver Settings page (F3): dwell time and the Needs tiles, saved to config.yaml."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
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

from ..config import DWELL_MAX_S, DWELL_MIN_S, NEEDS_TILE_COUNT, AppConfig, NeedTile, clamp_dwell
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
"""


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
        layout.setContentsMargins(theme.MARGIN, 40, theme.MARGIN, 40)
        layout.setSpacing(24)

        title = QLabel("Caregiver settings")
        title.setFont(theme.font(56, bold=True))
        layout.addWidget(title)

        dwell_row = QHBoxLayout()
        dwell_label = QLabel("Dwell time")
        dwell_label.setFont(theme.font(32, bold=True))
        self.dwell_value = QLabel()
        self.dwell_value.setFont(theme.font(32))
        self.dwell_value.setMinimumWidth(160)
        self.dwell_slider = QSlider(Qt.Horizontal)
        self.dwell_slider.setRange(int(DWELL_MIN_S * 10), int(DWELL_MAX_S * 10))
        self.dwell_slider.setSingleStep(1)
        self.dwell_slider.setPageStep(5)
        self.dwell_slider.setMinimumHeight(48)
        self.dwell_slider.valueChanged.connect(lambda v: self.dwell_value.setText(f"{v / 10:.1f} s"))
        dwell_row.addWidget(dwell_label)
        dwell_row.addWidget(self.dwell_slider, 1)
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
        self.dwell_slider.setValue(round(self.cfg.dwell.dwell_time_s * 10))
        self.dwell_value.setText(f"{self.cfg.dwell.dwell_time_s:.1f} s")
        for row in range(NEEDS_TILE_COUNT):
            tile = self.cfg.needs[row] if row < len(self.cfg.needs) else NeedTile("", "")
            for col, value in enumerate((tile.icon, tile.label, tile.thai)):
                self.table.setItem(row, col, QTableWidgetItem(value))
            action = QComboBox()
            action.addItems(["speak", "alert"])
            action.setCurrentText(tile.action if tile.action in ("speak", "alert") else "speak")
            self.table.setCellWidget(row, 3, action)

    def save(self) -> None:
        self.cfg.dwell.dwell_time_s = clamp_dwell(self.dwell_slider.value() / 10)
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
