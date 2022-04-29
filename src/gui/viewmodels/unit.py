import ast

from PyQt5.QtCore import QSize, Qt, QMimeData
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget, QWidget, QHBoxLayout, QVBoxLayout, QListWidgetItem, QLineEdit, QPushButton, \
    QApplication

import customlogger as logger
from db import db
from gui.viewmodels.mime_headers import CARD, CALCULATOR_UNIT, UNIT_EDITOR_UNIT, CALCULATOR_GRANDUNIT
from gui.viewmodels.utils import ImageWidget
from logic.card import Card
from logic.profile import unit_storage
from settings import IMAGE_PATH64, IMAGE_PATH32, IMAGE_PATH


class UnitCard(ImageWidget):
    def __init__(self, unit_widget, card_idx, color='black', size=64, *args, **kwargs):
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
            if str(type(self.unit_widget.unit_view)) == "<class 'gui.viewmodels.unit.UnitView'>":
                self.unit_widget.unit_view.copy.copy_unit(self.unit_widget.unit_view)
        elif event.button() == Qt.LeftButton:
            self.unit_widget.toggle_custom_card(self.card_idx)
            event.ignore()

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        mimetext = e.mimeData().text()
        if mimetext.startswith(CARD):
            card_id = int(mimetext[len(CARD):])
            self.unit_widget.set_card(self.card_idx, card_id)
            self.unit_widget.unit_view.copy.copy_unit(self.unit_widget.unit_view)
        else:
            self.unit_widget.handle_lost_mime(mimetext)


class UnitWidget(QWidget):
    def __init__(self, unit_view, parent=None, size=64):
        super(UnitWidget, self).__init__(parent)
        self.unit_view = unit_view
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
        self.unitName = QLineEdit()
        self.unitName.setMinimumSize(QSize(0, 15))
        self.unitName.setMaximumSize(QSize(16777215, 25))
        self.unitName.setMaxLength(80)
        self.icon_size = size
        if self.icon_size == 32:
            self.path = IMAGE_PATH32
        elif self.icon_size == 64:
            self.path = IMAGE_PATH64
        elif self.icon_size == 124:
            self.path = IMAGE_PATH

    def clone_internal(self):
        res = list()
        for card_internal in self.cards_internal:
            if card_internal is None:
                res.append(None)
                continue
            res.append(card_internal.clone_card())
        return res

    @property
    def card_ids(self):
        return [
            card.card_id if card is not None else None for card in self.cards_internal
        ]

    def set_unit_name(self, unit_name):
        self.unitName.setText(unit_name)

    def set_card(self, idx, card):
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
        if type(self) == UnitWidget:
            self.update_unit()

    def set_card_internal(self, idx, card):
        self.cards_internal[idx] = card

    def toggle_custom_card(self, idx):
        try:
            self.unit_view.main_view.custom_card_model.set_card_object(self.cards_internal[idx])
        except AttributeError:
            return

    def set_widget_item(self, widget_item):
        self.widget_item = widget_item

    def update_unit(self):
        unit_name = self.unitName.text().strip()
        card_ids = self.card_ids
        if unit_name != "":
            unit_storage.update_unit(unit_name=unit_name, cards=card_ids, grand=False)
        self.unit_view.copy.copy_unit(self.unit_view)

    def delete_unit(self):
        unit_name = self.unitName.text().strip()
        if unit_name != "":
            unit_storage.delete_unit(unit_name)
        self.unit_view.delete_unit(self.widget_item)

    def handle_lost_mime(self, mime_text):
        if type(self.unit_view) == UnitView:
            self.unit_view.handle_lost_mime(mime_text)


class SmallUnitWidget(UnitWidget):
    def __init__(self, unit_view, parent=None):
        super(SmallUnitWidget, self).__init__(unit_view, parent)

        self.verticalLayout = QVBoxLayout()
        self.unitManagementLayout = QHBoxLayout()

        self.unitName.editingFinished.connect(lambda: self.update_unit())

        self.unitManagementLayout.addWidget(self.unitName)

        self.deleteButton = QPushButton()
        self.deleteButton.setText("Delete unit")
        self.deleteButton.clicked.connect(lambda: self.delete_unit())
        self.unitManagementLayout.addWidget(self.deleteButton)

        self.verticalLayout.addLayout(self.unitManagementLayout)
        self.cardLayout = QHBoxLayout()

        for card in self.cards:
            card.setMinimumSize(QSize(self.icon_size + 2, self.icon_size + 2))
            self.cardLayout.addWidget(card)

        self.verticalLayout.addLayout(self.cardLayout)
        self.setLayout(self.verticalLayout)


class DragableUnitList(QListWidget):
    def __init__(self, parent, unit_view, *args):
        super().__init__(parent, *args)
        self.unit_view = unit_view
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.unit_view_copy = None

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
        mimedata.setText(UNIT_EDITOR_UNIT + str(self.itemWidget(self.selected[0]).card_ids))
        drag.setMimeData(mimedata)
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        mimetext = e.mimeData().text()
        if mimetext.startswith(CALCULATOR_UNIT):
            logger.debug("Dragged {} into unit editor".format(mimetext[len(CALCULATOR_UNIT):]))
            self.unit_view.add_unit(mimetext[len(CALCULATOR_UNIT):])
            if self.unit_view_copy != None:
                self.unit_view_copy.add_unit(mimetext[len(CALCULATOR_UNIT):])
        elif mimetext.startswith(CALCULATOR_GRANDUNIT):
            logger.debug("Dragged {} into unit editor".format(mimetext[len(CALCULATOR_GRANDUNIT):]))
            self.unit_view.add_units(mimetext[len(CALCULATOR_UNIT):])
            if self.unit_view_copy != None:
                self.unit_view_copy.add_units(mimetext[len(CALCULATOR_UNIT):])
        e.ignore()


class UnitView:
    def __init__(self, main):
        self.widget = DragableUnitList(main, self)
        self.widget.setVerticalScrollMode(1)  # Smooth scroll
        self.pics = None
        self.copy = None

    def set_copy(self, view_copy):
        self.copy = view_copy
        self.widget.unit_view_copy = self.copy
    
    def set_model(self, model):
        self.model = model

    def load_data(self, data):
        for unit_name, unit_cards in data:
            unit_widget = self.add_unit(unit_cards)
            unit_widget.set_unit_name(unit_name)

    def copy_unit(self, unit_view):
        self.widget.clear()
        unit_widgets = [unit_view.widget.itemWidget(unit_view.widget.item(x)) for x in range(unit_view.widget.count())]
        for origin in unit_widgets:
            unit_widget = SmallUnitWidget(self, self.widget)
            unit_widget.set_unit_name(origin.unitName.text())
            for idx in range(6):
                unit_widget.set_card(idx, origin.cards_internal[idx])
            unit_widget_item = QListWidgetItem(self.widget)
            unit_widget.set_widget_item(unit_widget_item)
            unit_widget_item.setSizeHint(unit_widget.sizeHint())
            self.widget.addItem(unit_widget_item)
            self.widget.setItemWidget(unit_widget_item, unit_widget)
    
    def add_unit(self, card_ids):
        unit_widget = SmallUnitWidget(self, self.widget)
        unit_widget.set_unit_name("")
        try:
            cards = ast.literal_eval(card_ids)
        except SyntaxError:
            cards = card_ids.split(",")
        for idx, card in enumerate(cards):
            if card is None or card == "":
                continue
            unit_widget.set_card(idx, int(card))
        unit_widget_item = QListWidgetItem(self.widget)
        unit_widget.set_widget_item(unit_widget_item)
        unit_widget_item.setSizeHint(unit_widget.sizeHint())
        self.widget.addItem(unit_widget_item)
        self.widget.setItemWidget(unit_widget_item, unit_widget)
        
        return unit_widget

    def add_units(self, card_ids):
        card_ids = ast.literal_eval(card_ids)
        for i in range(3):
            cards = card_ids[i * 5: (i + 1) * 5]
            if cards != [None] * 5:
                self.add_unit(str(cards))

    def add_empty_widget(self):
        unit_widget = SmallUnitWidget(self, self.widget)
        unit_widget_item = QListWidgetItem(self.widget)
        unit_widget.set_widget_item(unit_widget_item)
        unit_widget_item.setSizeHint(unit_widget.sizeHint())
        self.widget.addItem(unit_widget_item)
        self.widget.setItemWidget(unit_widget_item, unit_widget)

    def delete_unit(self, unit_widget):
        row = self.widget.row(unit_widget)
        self.widget.takeItem(row)
        self.copy.widget.takeItem(row)

    def remove_deleted_custom_card(self, custom_card_id):
        for row in range(self.widget.count()):
            unit_item = self.widget.item(row)
            unit_widget = self.widget.itemWidget(unit_item)
            for idx, card in enumerate(unit_widget.cards_internal):
                if card is not None and card.card_id == custom_card_id:
                    unit_widget.set_card(idx, None)
                    self.copy.copy_unit(self)

    def handle_lost_mime(self, mime_text):
        if mime_text.startswith(CALCULATOR_UNIT):
            logger.debug("Dragged {} into unit editor".format(mime_text[len(CALCULATOR_UNIT):]))
            self.add_unit(mime_text[len(CALCULATOR_UNIT):])
            if self.copy != None:
                self.copy.add_unit(mime_text[len(CALCULATOR_UNIT):])
        elif mime_text.startswith(CALCULATOR_GRANDUNIT):
            logger.debug("Dragged {} into unit editor".format(mime_text[len(CALCULATOR_GRANDUNIT):]))
            self.add_units(mime_text[len(CALCULATOR_UNIT):])
            if self.copy != None:
                self.copy.add_units(mime_text[len(CALCULATOR_UNIT):])

    def __del__(self):
        unit_storage.clean_all_units(grand=False)
        for r_idx in range(self.widget.count()):
            widget = self.widget.itemWidget(self.widget.item(r_idx))
            widget.update_unit()


class UnitModel:

    def __init__(self, view1, view2):
        self.view1 = view1
        self.view2 = view2
        self.images = dict()

    def initialize_units(self):
        data = db.cachedb.execute_and_fetchall("SELECT unit_name, cards FROM personal_units WHERE grand = 0")
        self.view1.load_data(data)
        self.view2.load_data(data)