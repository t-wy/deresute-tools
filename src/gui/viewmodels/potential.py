from __future__ import annotations

from typing import Any, List, Dict

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QTableWidgetItem, QHeaderView

import customlogger as logger
from db import db
from gui.events.state_change_events import PotentialUpdatedEvent
from gui.events.utils import eventbus
from gui.viewmodels.utils import NumericalTableWidgetItem, ImageWidget
from logic.profile import potential
from settings import IMAGE_PATH64


class PotentialView:
    parent: QtWidgets.QWidget
    layout: QtWidgets.QVBoxLayout
    widget: QtWidgets.QTableWidget
    model: PotentialModel

    def __init__(self):
        self.parent = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.parent)
        self.widget = QtWidgets.QTableWidget(self.parent)
        self.layout.addWidget(self.widget)
        self.widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.widget.setSortingEnabled(True)
        self.widget.verticalHeader().setVisible(False)
        self.widget.verticalHeader().setDefaultSectionSize(75)

    def set_model(self, model: PotentialModel):
        self.model = model

    def load_data(self, data: List[Dict[str, Any]]):
        self.widget.setColumnCount(len(data[0]))
        self.widget.setRowCount(len(data))
        self.widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.widget.setColumnWidth(1, 75)
        self.widget.setColumnWidth(2, 75)
        for i in range(3, len(data[0])):
            self.widget.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

        keys = list(data[0].keys())
        keys[1] = ""
        self.widget.setHorizontalHeaderLabels(keys)
        for r_idx, character in enumerate(data):
            for c_idx, (key, value) in enumerate(character.items()):
                if c_idx == 1:
                    item = ImageWidget(None, self.widget)
                    item.set_path(str(IMAGE_PATH64 / "{:06d}.jpg".format(value)))
                    self.widget.setCellWidget(r_idx, c_idx, item)
                    continue
                elif isinstance(value, int):
                    item = NumericalTableWidgetItem(value)
                elif value is None:
                    item = QTableWidgetItem("")
                else:
                    item = QTableWidgetItem(str(value))

                if c_idx in {0, 2, 8}:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item = QTableWidgetItem()
                    item.setData(Qt.EditRole, value)
                self.widget.setItem(r_idx, c_idx, item)
        self.connect_cell_changed()

    def connect_cell_changed(self):
        self.widget.cellChanged.connect(lambda r, c: self.model.handle_cell_change(r, c))

    def disconnect_cell_changed(self):
        self.widget.cellChanged.disconnect()

    def update_total(self, r_idx: int, total: int):
        self.widget.item(r_idx, 8).setData(2, total)


class PotentialModel:
    view: PotentialView

    def __init__(self, view: PotentialView):
        self.view = view
        self.potentials = dict()

    def initialize_data(self):
        data = db.cachedb.execute_and_fetchall("""
            SELECT
                potential_cache.chara_id as ID,
                card_data_cache.id as _card_id,
                chara_cache.full_name as Name,
                potential_cache.vo as Vocal,
                potential_cache.da as Dance,
                potential_cache.vi as Visual,
                potential_cache.li as Life,
                potential_cache.sk as Skill,
                potential_cache.vo+potential_cache.da+potential_cache.vi+potential_cache.li+potential_cache.sk as Total
            FROM (SELECT * FROM potential_cache ORDER BY random()) AS potential_cache
            INNER JOIN chara_cache ON potential_cache.chara_id = chara_cache.chara_id
            INNER JOIN card_data_cache ON card_data_cache.chara_id = potential_cache.chara_id
            GROUP BY card_data_cache.chara_id
        """, out_dict=True)
        for chara in data:
            self.potentials[int(chara['ID'])] = [
                int(chara['Vocal']),
                int(chara['Dance']),
                int(chara['Visual']),
                int(chara['Life']),
                int(chara['Skill'])
            ]
        self.view.load_data(data)

    def handle_cell_change(self, r_idx: int, c_idx: int):
        if 3 > c_idx or 7 < c_idx:
            return
        chara_id = int(self.view.widget.item(r_idx, 0).text())
        new_value = self.view.widget.item(r_idx, c_idx).text()
        try:
            new_value = int(new_value)
            assert 0 <= new_value <= 10
        except Exception:
            logger.error("Potential {} invalid for character ID {}".format(new_value, chara_id))
            # Revert value
            self.view.disconnect_cell_changed()
            self.view.widget.item(r_idx, c_idx).setData(2, self.potentials[chara_id][c_idx - 3])
            self.view.connect_cell_changed()
            return
        self.potentials[chara_id][c_idx - 3] = new_value
        # Update
        pots = self.potentials[chara_id].copy()
        # Swap dance / visual
        pots[1] = self.potentials[chara_id][2]
        pots[2] = self.potentials[chara_id][1]
        potential.update_potential(chara_id=chara_id, pots=pots)
        card_ids = db.cachedb.execute_and_fetchall("SELECT id FROM card_data_cache WHERE chara_id = ?", [chara_id])
        card_ids = [_[0] for _ in card_ids]
        eventbus.eventbus.post(PotentialUpdatedEvent(card_ids))
        self.view.update_total(r_idx, sum(pots))
