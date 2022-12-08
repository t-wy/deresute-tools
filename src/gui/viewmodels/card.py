from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import cast, Any, Optional

from PyQt5.QtCore import QSize, QMimeData, Qt, QPoint
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QComboBox, QAbstractItemView, QApplication, QWidget, \
    QHeaderView

import customlogger as logger
from db import db
from gui.events.calculator_view_events import PushCardEvent
from gui.events.quicksearch_events import PushCardIndexEvent
from gui.events.state_change_events import PotentialUpdatedEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.viewmodels.mime_headers import CARD
from gui.viewmodels.utils import ImageWidget, NumericalTableWidgetItem
from logic.live import Live
from logic.profile import card_storage
from network import meta_updater
from settings import IMAGE_PATH64, IMAGE_PATH, IMAGE_PATH32
from static.color import CARD_GUI_COLORS
from static.skill import SKILL_COLOR_BY_NAME


class CustomCardTable(QTableWidget):
    drag_start_position: QPoint
    selected: list[QTableWidgetItem]

    def __init__(self, *args):
        super().__init__(*args)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            self.selected = self.selectedItems()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        if self.selectedItems():
            self.selected = self.selectedItems()
        if not self.selected:
            return
        drag = QDrag(self)
        card_row = self.row(self.selected[0])
        card_id = self.item(card_row, 2).text()
        card_img = cast(ImageWidget, self.cellWidget(card_row, 1)).picture
        mimedata = QMimeData()
        mimedata.setText(CARD + card_id)
        pixmap = QPixmap(card_img.size())
        painter = QPainter(pixmap)
        painter.drawPixmap(0, 0, card_img)
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(card_img.size().width() / 2, card_img.size().height() / 2))
        drag.setMimeData(mimedata)
        drag.exec_(Qt.CopyAction | Qt.MoveAction)


class CardView:
    widget: CustomCardTable
    model: CardModel
    size: int

    def __init__(self, main: QWidget):
        self.widget = CustomCardTable(main)
        self.widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.widget.setDragEnabled(True)
        self.widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.widget.setSortingEnabled(True)
        self.widget.verticalHeader().setVisible(False)
        self.size = 20

    def set_model(self, model: CardModel):
        self.model = model

    def connect_cell_change(self):
        self.widget.cellChanged.connect(lambda r, c: self.model.handle_cell_change(r, c))

    def disconnect_cell_change(self):
        self.widget.cellChanged.disconnect()

    def initialize_pics(self):
        for r_idx in range(self.widget.rowCount()):
            image = ImageWidget(None, self.widget)
            self.widget.setCellWidget(r_idx, 1, image)
        self.connect_cell_change()

    def toggle_auto_resize(self, on: bool = False):
        if on:
            self.widget.horizontalHeader().setSectionResizeMode(cast(QHeaderView.ResizeMode, 4))  # Auto fit
            self.widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # Auto fit
        else:
            name_col_width = self.widget.columnWidth(4)
            self.widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)  # Resize
            self.widget.setColumnWidth(4, name_col_width)

    def load_data(self, data: list[OrderedDict[str, Any]], card_list: list[int] = None):
        if card_list is None:
            self.widget.setColumnCount(len(data[0]) + 2)
            self.widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)  # Fix icon column size
            self.widget.setRowCount(len(data))
            self.widget.setHorizontalHeaderLabels(['#', ''] + list(data[0].keys()))
            rows = range(len(data))
        else:
            data_dict = {int(_['ID']): _ for _ in data}
            rows = dict()
            for r_idx in range(self.widget.rowCount()):
                card_id = int(self.widget.item(r_idx, 2).text())
                if card_id not in data_dict:
                    continue
                else:
                    rows[card_id] = r_idx
            rows = [rows[card_id] for card_id in map(int, card_list)]
            data = [data_dict[card_id] for card_id in map(int, card_list)]

        # Turn off sorting to avoid indices changing mid-update
        self.widget.setSortingEnabled(False)
        for r_idx, card_data in zip(rows, data):
            row_count_item = NumericalTableWidgetItem(r_idx + 1)
            row_count_item.setFlags(row_count_item.flags() & ~Qt.ItemIsEditable)
            self.widget.setItem(r_idx, 0, row_count_item)
            for c_idx, (key, value) in enumerate(card_data.items()):
                if isinstance(value, int):
                    item = NumericalTableWidgetItem(value)
                elif value is None:
                    item = QTableWidgetItem("")
                else:
                    item = QTableWidgetItem(str(value))
                if c_idx != 1:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item = QTableWidgetItem()
                    item.setData(Qt.EditRole, value)
                if key == 'Skill' and value is not None:
                    item.setBackground(QColor(*SKILL_COLOR_BY_NAME[value], 135))
                if key == 'Color' and value is not None:
                    item.setBackground(QColor(*CARD_GUI_COLORS[value], 100))
                self.widget.setItem(r_idx, c_idx + 2, item)
        logger.info("Loaded {} cards".format(len(data)))
        self.widget.setSortingEnabled(True)
        # Turn on auto-fit once to make it look better than turn it off to render faster during resize
        self.toggle_auto_resize(card_list is None)

    def show_only_ids(self, card_ids: list[int]):
        if not card_ids:
            card_ids = set()
        else:
            card_ids = set(card_ids)
        count = 1
        for r_idx in range(self.widget.rowCount()):
            if int(self.widget.item(r_idx, 2).text()) in card_ids:
                self.widget.setRowHidden(r_idx, False)
                self.widget.item(r_idx, 0).setData(2, str(count))
                count += 1
            else:
                self.widget.setRowHidden(r_idx, True)
        self.refresh_spacing()

    def draw_icons(self, icons: Optional[dict[str, Path]], size: Optional[int]):
        if size is None:
            self.size = 20
        else:
            self.size = size
        for r_idx in range(self.widget.rowCount()):
            if icons:
                card_id = self.widget.item(r_idx, 2).text()
                cast(ImageWidget, self.widget.cellWidget(r_idx, 1)).set_path(icons[card_id])
            else:
                cast(ImageWidget, self.widget.cellWidget(r_idx, 1)).set_path(None)
        self.refresh_spacing()

    def refresh_spacing(self):
        self.widget.verticalHeader().setDefaultSectionSize(self.size + 10)
        self.widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.widget.setColumnWidth(1, self.size + 10)


class CardModel:
    view: CardView
    images: dict[str, Path]
    owned: dict[int, int]
    model_id: int
    potential: bool

    def __init__(self, view: CardView, model_id: int):
        assert isinstance(view, CardView)
        self.view = view
        self.images = dict()
        self.owned = dict()
        self.model_id = model_id
        self.potential = False
        eventbus.eventbus.register(self)

    def load_images(self, size: int = None):
        logger.info("Card list thumbnail size: {}".format(size))
        if size is None:
            self.images = dict()
            self.view.draw_icons(None, size)
            return
        if size is not None:
            assert size == 32 or size == 64 or size == 124
            if size == 32:
                path = IMAGE_PATH32
            elif size == 64:
                path = IMAGE_PATH64
            else:
                path = IMAGE_PATH
            for image_path in path.iterdir():
                self.images[image_path.name.split(".")[0]] = image_path
            self.view.draw_icons(self.images, size)

    def set_potential_inclusion(self, potential: bool):
        self.potential = potential

    @subscribe(PotentialUpdatedEvent)
    def initialize_cards_from_event(self, event: PotentialUpdatedEvent):
        if self.potential:
            self.initialize_cards(event.card_list, potential=True)

    def initialize_cards(self, card_list: list[int] = None, potential: bool = False):
        db.cachedb.execute("""ATTACH DATABASE "{}" AS masterdb""".format(meta_updater.get_masterdb_path()))
        db.cachedb.commit()
        query = """
            SELECT  cdc.id as ID,
                    oc.number as Owned,
                    cdc.name as Name,
                    cc.full_name as Character,
                    REPLACE(UPPER(rt.text) || "+", "U+", "") as Rarity,
                    ct.text as Color,
                    sk.skill_name as Skill,
                    lk.keywords as Leader,
                    sd.condition as Interval,
                    pk.keywords as Prob,
        """
        if potential:
            query += """
                    CAST(cdc.vocal_max + cdc.bonus_vocal AS INTEGER) as Vocal,
                    CAST(cdc.dance_max + cdc.bonus_dance AS INTEGER) as Dance,
                    CAST(cdc.visual_max + cdc.bonus_visual AS INTEGER) as Visual,
                    CAST(cdc.hp_max + cdc.bonus_hp AS INTEGER) as Life
            """
        else:
            query += """
                    CAST(cdc.vocal_max + cd.bonus_vocal AS INTEGER) as Vocal,
                    CAST(cdc.dance_max + cd.bonus_dance AS INTEGER) as Dance,
                    CAST(cdc.visual_max + cd.bonus_visual AS INTEGER) as Visual,
                    CAST(cdc.hp_max + cd.bonus_hp AS INTEGER) as Life
            """
        query += """
            FROM card_data_cache as cdc
            INNER JOIN chara_cache cc on cdc.chara_id = cc.chara_id
            INNER JOIN rarity_text rt on cdc.rarity = rt.id
            INNER JOIN color_text ct on cdc.attribute = ct.id
            LEFT JOIN owned_card oc on cdc.id = oc.card_id
            LEFT JOIN masterdb.skill_data sd on cdc.skill_id = sd.id
            LEFT JOIN probability_keywords pk on pk.id = sd.probability_type
            LEFT JOIN skill_keywords sk on sd.skill_type = sk.id
            LEFT JOIN leader_keywords lk on cdc.leader_skill_id = lk.id
            LEFT JOIN masterdb.card_data cd on cdc.id = cd.id
        """
        if card_list is not None:
            query += "WHERE cdc.id IN ({})".format(','.join(['?'] * len(card_list)))
            data = db.cachedb.execute_and_fetchall(query, card_list, out_dict=True)
        else:
            data = db.cachedb.execute_and_fetchall(query, out_dict=True)
        db.cachedb.execute("DETACH DATABASE masterdb")
        db.cachedb.commit()
        for card in data:
            if card['Owned'] is None:
                card['Owned'] = 0
            self.owned[int(card['ID'])] = int(card['Owned'])
        self.view.load_data(data, card_list)

    def handle_cell_change(self, r_idx: int, c_idx: int):
        if c_idx != 3:
            return
        card_id = int(self.view.widget.item(r_idx, 2).text())
        new_value = self.view.widget.item(r_idx, c_idx).text()
        if str(self.owned[card_id]) == new_value:
            return
        try:
            new_value = int(new_value)
            assert new_value >= 0
        except Exception:
            logger.error("Owned value {} invalid for card ID {}".format(new_value, card_id))
            # Revert value
            self.view.disconnect_cell_change()
            self.view.widget.item(r_idx, c_idx).setData(2, self.owned[card_id])
            self.view.connect_cell_change()
            return
        self.owned[card_id] = new_value
        card_storage.update_owned_cards(card_id, new_value)

    @subscribe(PushCardIndexEvent)
    def push_card(self, event: PushCardIndexEvent):
        if event.model_id != self.model_id:
            return
        idx = event.idx
        skip_guest_push = event.skip_guest_push
        count = 0
        cell_widget = None
        for row in range(self.view.widget.rowCount()):
            if self.view.widget.isRowHidden(row):
                continue
            if count == idx:
                cell_widget = self.view.widget.item(row, 2)
                break
            else:
                count += 1
        if cell_widget is None:
            logger.info("No card at index {}".format(idx))
            return
        eventbus.eventbus.post(PushCardEvent(int(cell_widget.text()), skip_guest_push))

    def highlight_event_cards(self, checked: bool):
        highlight_set = Live.static_get_chara_bonus_set(get_name=True)
        for r_idx in range(self.view.widget.rowCount()):
            if self.view.widget.item(r_idx, 5).text() not in highlight_set:
                continue
            for c_idx in range(4, 5):
                item = self.view.widget.item(r_idx, c_idx)
                if checked:
                    item.setBackground(QColor(50, 100, 100, 80))
                else:
                    item.setBackground(QColor(0, 0, 0, 0))


class IconLoaderView:
    widget: QComboBox
    model: IconLoaderModel

    def __init__(self, main: QWidget):
        self.widget = QComboBox(main)
        self.widget.setMaximumSize(QSize(1000, 25))

        self.widget.addItem("No icon")
        self.widget.addItem("Small icon")
        self.widget.addItem("Medium icon")
        self.widget.addItem("Large icon")

    def set_model(self, model: IconLoaderModel):
        assert isinstance(model, IconLoaderModel)
        self.model = model
        self.widget.currentIndexChanged.connect(lambda x: self.trigger(x))

    def trigger(self, idx: int):
        self.model.load_image(idx)


class IconLoaderModel:
    view: IconLoaderView
    card_model: CardModel

    def __init__(self, view: IconLoaderView, card_model: CardModel):
        self.view = view
        self._card_model = card_model

    def load_image(self, idx: int):
        if idx == 0:
            self._card_model.load_images(size=None)
        elif idx == 1:
            self._card_model.load_images(size=32)
        elif idx == 2:
            self._card_model.load_images(size=64)
        elif idx == 3:
            self._card_model.load_images(size=124)


class CardSmallView(CardView):
    def __init__(self, main: QWidget):
        super().__init__(main)

        self.widget.horizontalHeader().setMinimumSectionSize(0)

    def load_data(self, data: list[OrderedDict[str, Any]], card_list: list[int] = None):
        super().load_data(data, card_list)

        for i in range(1, 4):
            self.widget.setColumnHidden(i, True)


class CardSmallModel(CardModel):
    def initialize_cards(self, card_list: list[int] = None, potential: bool = False):
        db.cachedb.execute("""ATTACH DATABASE "{}" AS masterdb""".format(meta_updater.get_masterdb_path()))
        db.cachedb.commit()
        query = """
            SELECT  cdc.id as ID,
                    oc.number as Owned,
                    cdc.name as Name,
                    cc.full_name as Character,
                    REPLACE(UPPER(rt.text) || "+", "U+", "") as Rare,
                    ct.text as Color,
                    sk.skill_name as Skill,
                    lk.keywords as Leader,
                    sd.condition as Int,
                    REPLACE(pk.keywords, "Medium", "Med") as Prob,
        """
        if potential:
            query += """
                    CAST(cdc.vocal_max + cdc.bonus_vocal AS INTEGER) as Vo,
                    CAST(cdc.dance_max + cdc.bonus_dance AS INTEGER) as Da,
                    CAST(cdc.visual_max + cdc.bonus_visual AS INTEGER) as Vi,
                    CAST(cdc.hp_max + cdc.bonus_hp AS INTEGER) as Li
            """
        else:
            query += """
                    CAST(cdc.vocal_max + cd.bonus_vocal AS INTEGER) as Vo,
                    CAST(cdc.dance_max + cd.bonus_dance AS INTEGER) as Da,
                    CAST(cdc.visual_max + cd.bonus_visual AS INTEGER) as Vi,
                    CAST(cdc.hp_max + cd.bonus_hp AS INTEGER) as Li
            """
        query += """
            FROM card_data_cache as cdc
            INNER JOIN chara_cache cc on cdc.chara_id = cc.chara_id
            INNER JOIN rarity_text rt on cdc.rarity = rt.id
            INNER JOIN color_text ct on cdc.attribute = ct.id
            LEFT JOIN owned_card oc on cdc.id = oc.card_id
            LEFT JOIN masterdb.skill_data sd on cdc.skill_id = sd.id
            LEFT JOIN probability_keywords pk on pk.id = sd.probability_type
            LEFT JOIN skill_keywords sk on sd.skill_type = sk.id
            LEFT JOIN leader_keywords lk on cdc.leader_skill_id = lk.id
            LEFT JOIN masterdb.card_data cd on cdc.id = cd.id
        """
        if card_list is not None:
            query += "WHERE cdc.id IN ({})".format(','.join(['?'] * len(card_list)))
            data = db.cachedb.execute_and_fetchall(query, card_list, out_dict=True)
        else:
            data = db.cachedb.execute_and_fetchall(query, out_dict=True)
        db.cachedb.execute("DETACH DATABASE masterdb")
        db.cachedb.commit()
        self.view.load_data(data, card_list)
