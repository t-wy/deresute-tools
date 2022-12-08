from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional, Union, cast, TYPE_CHECKING

from PyQt5.QtCore import QSize, Qt, QMimeData, QPoint
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget, QWidget, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLineEdit, QPushButton, \
    QApplication, QAbstractItemView

import customlogger as logger
from db import db
from gui.events.state_change_events import UnitStorageUpdatedEvent, CustomCardUpdatedEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.viewmodels.mime_headers import CARD, CALCULATOR_UNIT, UNIT_EDITOR_UNIT, CALCULATOR_GRANDUNIT
from gui.viewmodels.utils import ImageWidget
from logic.card import Card
from logic.profile import unit_storage
from settings import IMAGE_PATH64, IMAGE_PATH32, IMAGE_PATH

if TYPE_CHECKING:
    from gui.viewmodels.simulator.calculator import CalculatorView


class UnitCard(ImageWidget):
    def __init__(self, unit_widget: UnitWidget, card_idx: int, color: str = 'black', size: int = 64, *args, **kwargs):
        super(UnitCard, self).__init__(*args, **kwargs)
        self.set_padding(1)
        self.toggle_border(True, size)
        self.setAcceptDrops(True)
        self.unit_widget = unit_widget
        self.card_idx = card_idx
        self.color = color

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.unit_widget.set_card(self.card_idx, None)
            if type(self.unit_widget.unit_view) == UnitView:
                self.unit_widget.unit_view.post_update_unit(self.unit_widget)
        if event.button() == Qt.LeftButton:
            self.unit_widget.toggle_edit_card(self.card_idx)
            event.ignore()

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        mimetext = e.mimeData().text()
        if mimetext.startswith(CARD):
            card_id = int(mimetext[len(CARD):])
            self.unit_widget.set_card(self.card_idx, card_id)
            if type(self.unit_widget.unit_view) == UnitView:
                self.unit_widget.unit_view.post_update_unit(self.unit_widget)
        else:
            self.unit_widget.handle_lost_mime(mimetext)


class UnitWidget(QWidget):
    unit_view: UnitView
    unit_id: int
    cards: list[UnitCard]
    cards_internal: list[Optional[Card]]
    unit_name: QLineEdit
    icon_size: int
    path: Path

    def __init__(self, unit_view: UnitView, parent: QWidget = None, size: int = 64):
        super(UnitWidget, self).__init__(parent)
        self.unit_view = unit_view
        self.unit_id = 0
        self.cards = list()
        self.cards_internal = [None] * 6
        for idx in range(6):
            if idx == 0:
                color = 'red'
            elif idx == 5:
                color = 'blue'
            else:
                color = 'black'
            card = UnitCard(unit_widget=self, card_idx=idx, size=size, color=color)
            self.cards.append(card)
        self.unit_name = QLineEdit()
        self.unit_name.setMinimumSize(QSize(0, 15))
        self.unit_name.setMaximumSize(QSize(16777215, 25))
        self.unit_name.setMaxLength(80)
        self.icon_size = size
        if self.icon_size == 32:
            self.path = IMAGE_PATH32
        elif self.icon_size == 64:
            self.path = IMAGE_PATH64
        elif self.icon_size == 124:
            self.path = IMAGE_PATH

    def clone_internal(self) -> list[Card]:
        res = list()
        for card_internal in self.cards_internal:
            if card_internal is None:
                res.append(None)
                continue
            res.append(card_internal.clone_card())
        return res

    @property
    def card_ids(self) -> list[Optional[int]]:
        return [card.card_id if card is not None else None for card in self.cards_internal]

    def set_unit_id(self, unit_id: int):
        self.unit_id = unit_id

    def set_unit_name(self, unit_name: str):
        self.unit_name.setText(unit_name)
        self.update_unit()

    def get_unit_name(self) -> str:
        return self.unit_name.text().strip()

    def set_card(self, idx: int, card: Union[int, Card, None]):
        if isinstance(card, Card):
            self.cards_internal[idx] = card
        else:
            if idx == 5 and len(self.cards) != 15:
                custom_pots = (10, 10, 10, 0, 5)
            else:
                custom_pots = None
            self.cards_internal[idx] = Card.from_id(card, custom_pots)
        if card is None:
            self.cards[idx].set_path(None)
        else:
            if isinstance(card, Card):
                card_id = card.card_id
            else:
                card_id = card
            self.cards[idx].set_path(str(self.path / "{:06d}.jpg".format(card_id)))
        self.cards[idx].repaint()
        if type(self) == SmallUnitWidget:
            self.update_unit()

    def set_card_internal(self, idx: int, card: Card):
        self.cards_internal[idx] = card

    def toggle_edit_card(self, idx: int):
        try:
            self.unit_view: CalculatorView
            self.unit_view.main_view.custom_card_model.set_card_object(self.cards_internal[idx])
        except AttributeError:
            return

    def update_unit(self):
        unit_storage.update_unit(unit_id=self.unit_id, unit_name=self.get_unit_name(), cards=self.card_ids, grand=False)

    def delete_unit(self):
        unit_storage.delete_unit(self.unit_id)
        self.unit_view.post_delete_unit(self)

    def handle_lost_mime(self, mime_text: str):
        self.unit_view.handle_lost_mime(mime_text)


class SmallUnitWidget(UnitWidget):
    def __init__(self, unit_view: UnitView, parent: QWidget = None):
        super(SmallUnitWidget, self).__init__(unit_view, parent)

        self.vertical_layout = QVBoxLayout()
        self.unit_management_layout = QHBoxLayout()

        self.unit_name.textEdited.connect(lambda: self.unit_view.post_update_unit(self))

        self.unit_management_layout.addWidget(self.unit_name)

        self.delete_button = QPushButton()
        self.delete_button.setText("Delete unit")
        self.delete_button.clicked.connect(lambda: self.delete_unit())
        self.unit_management_layout.addWidget(self.delete_button)

        self.vertical_layout.addLayout(self.unit_management_layout)
        self.card_layout = QHBoxLayout()

        for card in self.cards:
            card.setMinimumSize(QSize(self.icon_size + 2, self.icon_size + 2))
            self.card_layout.addWidget(card)

        self.vertical_layout.addLayout(self.card_layout)
        self.setLayout(self.vertical_layout)


class DraggableUnitList(QListWidget):
    unit_view: UnitView
    drag_start_position: QPoint
    selected: list[QListWidgetItem]

    def __init__(self, parent: QWidget, unit_view: UnitView):
        super().__init__(parent)
        self.unit_view = unit_view
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

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
        mimedata = QMimeData()
        card_ids = cast(UnitWidget, self.itemWidget(self.selected[0])).card_ids
        mimedata.setText(UNIT_EDITOR_UNIT + str(card_ids))
        drag.setMimeData(mimedata)
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        mimetext = e.mimeData().text()
        if mimetext.startswith(CALCULATOR_UNIT):
            logger.debug("Dragged {} into unit storage".format(mimetext[len(CALCULATOR_UNIT):]))
            self.unit_view.add_unit(mimetext[len(CALCULATOR_UNIT):], create_new=True)
        elif mimetext.startswith(CALCULATOR_GRANDUNIT):
            logger.debug("Dragged {} into unit storage".format(mimetext[len(CALCULATOR_GRANDUNIT):]))
            self.unit_view.add_units(mimetext[len(CALCULATOR_UNIT):], create_new=True)
        e.ignore()


class UnitView:
    def __init__(self, main: QWidget, view_id: int):
        self.widget = DraggableUnitList(main, self)
        self.widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.view_id = view_id
        self.model = None
        self.pics = None
        eventbus.eventbus.register(self)

    def set_model(self, model: UnitModel):
        self.model = model

    def load_data(self, data: list[tuple[int, str, str]]):
        for unit_id, unit_name, unit_cards in data:
            self.add_unit(unit_cards, unit_name, unit_id=unit_id)

    def add_unit(self, card_ids: str, name: str = "", post_event: bool = True,
                 create_new: bool = False, unit_id: int = 0) -> UnitWidget:
        unit_widget = SmallUnitWidget(self, self.widget)
        if create_new:
            unit_id = unit_storage.add_empty_unit()
        unit_widget.set_unit_id(unit_id)
        unit_widget.set_unit_name(name)
        self.set_cards_from_ids(unit_widget, card_ids)
        unit_widget_item = QListWidgetItem(self.widget)
        unit_widget_item.setSizeHint(unit_widget.sizeHint())
        self.widget.addItem(unit_widget_item)
        self.widget.setItemWidget(unit_widget_item, unit_widget)
        if post_event:
            eventbus.eventbus.post(UnitStorageUpdatedEvent(self.view_id, "add",
                                                           unit_id=unit_id, card_ids=card_ids, name=name))
        return unit_widget

    @staticmethod
    def set_cards_from_ids(unit_widget: UnitWidget, card_ids: str):
        try:
            cards = ast.literal_eval(card_ids)
        except SyntaxError:
            cards = card_ids.split(",")
        for idx, card in enumerate(cards):
            if card is None or card == "":
                unit_widget.set_card(idx, None)
                continue
            unit_widget.set_card(idx, int(card))

    def add_units(self, card_ids: str, create_new: bool = False):
        card_ids = ast.literal_eval(card_ids)
        for i in range(3):
            cards = card_ids[i * 5: (i + 1) * 5]
            if cards != [None] * 5:
                self.add_unit(str(cards), create_new=create_new)

    def add_empty_widget(self):
        unit_widget = SmallUnitWidget(self, self.widget)
        unit_id = unit_storage.add_empty_unit()
        unit_widget.set_unit_id(unit_id)
        unit_widget_item = QListWidgetItem(self.widget)
        unit_widget_item.setSizeHint(unit_widget.sizeHint())
        self.widget.addItem(unit_widget_item)
        self.widget.setItemWidget(unit_widget_item, unit_widget)
        eventbus.eventbus.post(UnitStorageUpdatedEvent(self.view_id, "add", unit_id=unit_id, card_ids=""))

    def post_update_unit(self, unit_widget: UnitWidget):
        for item_idx in range(self.widget.count()):
            if self.widget.itemWidget(self.widget.item(item_idx)) == unit_widget:
                eventbus.eventbus.post(UnitStorageUpdatedEvent(self.view_id, "update", index=item_idx,
                                                               card_ids=str(unit_widget.card_ids),
                                                               name=unit_widget.get_unit_name()))

    def post_delete_unit(self, unit_widget: UnitWidget):
        for item_idx in range(self.widget.count()):
            if self.widget.itemWidget(self.widget.item(item_idx)) == unit_widget:
                self.widget.takeItem(item_idx)
                eventbus.eventbus.post(UnitStorageUpdatedEvent(self.view_id, "delete", index=item_idx))
                break

    def handle_lost_mime(self, mime_text: str):
        if mime_text.startswith(CALCULATOR_UNIT):
            logger.debug("Dragged {} into unit storage".format(mime_text[len(CALCULATOR_UNIT):]))
            self.add_unit(mime_text[len(CALCULATOR_UNIT):], create_new=True)
        elif mime_text.startswith(CALCULATOR_GRANDUNIT):
            logger.debug("Dragged {} into unit storage".format(mime_text[len(CALCULATOR_GRANDUNIT):]))
            self.add_units(mime_text[len(CALCULATOR_UNIT):], create_new=True)

    @subscribe(UnitStorageUpdatedEvent)
    def update_from_event(self, event: UnitStorageUpdatedEvent):
        if event.view_id == self.view_id:
            return
        if event.mode == "add":
            assert event.card_ids is not None
            name = event.name if event.name is not None else ""
            self.add_unit(str(event.card_ids), name=name, post_event=False, unit_id=event.unit_id)
        elif event.mode == "update":
            assert all(_ is not None for _ in (event.index, event.card_ids, event.name))
            unit_widget = cast(UnitWidget, self.widget.itemWidget(self.widget.item(event.index)))
            self.set_cards_from_ids(unit_widget, event.card_ids)
            unit_widget.set_unit_name(event.name)
        elif event.mode == "delete":
            assert event.index is not None
            self.widget.takeItem(event.index)

    @subscribe(CustomCardUpdatedEvent)
    def update_custom_card(self, event: CustomCardUpdatedEvent):
        for row in range(self.widget.count()):
            unit_item = self.widget.item(row)
            unit_widget = cast(UnitWidget, self.widget.itemWidget(unit_item))
            for idx, card in enumerate(unit_widget.cards_internal):
                if card is not None and card.card_id == event.card_id:
                    unit_widget.set_card(idx, event.card_id if not event.delete else None)

    def __del__(self):
        unit_storage.clean_all_units(grand=False)
        for r_idx in range(self.widget.count()):
            widget = cast(UnitWidget, self.widget.itemWidget(self.widget.item(r_idx)))
            widget.update_unit()


class UnitModel:
    def __init__(self, view: UnitView):
        self.view = view

    def initialize_units(self):
        data = db.cachedb.execute_and_fetchall("SELECT unit_id, unit_name, cards FROM personal_units WHERE grand = 0")
        self.view.load_data(data)
