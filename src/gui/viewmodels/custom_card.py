from __future__ import annotations

import os
from collections import OrderedDict
from typing import Any, cast, Optional, Union

from PIL import Image
from PyQt5.QtCore import Qt, QPoint, QMimeData
from PyQt5.QtGui import QBrush, QColor, QDrag, QImage, QIntValidator, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, \
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QGridLayout, \
    QHeaderView

from db import db
from gui.events.calculator_view_events import PushCardEvent
from gui.events.state_change_events import YoinkCustomCardEvent, CustomCardUpdatedEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.viewmodels.mime_headers import CARD
from gui.viewmodels.utils import NumericalTableWidgetItem
from network import meta_updater
from settings import IMAGE_PATH, MY_IMAGE_PATH, IMAGE_PATH32, IMAGE_PATH64
from static.color import CARD_GUI_COLORS
from static.skill import SKILL_COLOR_BY_NAME

INTERVAL_LIST = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18]
DURATION_LIST = [(3, "一瞬の間 "), (4.5, "わずかな間"), (6, "少しの間"), (7.5, "しばらくの間"), (9, "かなりの間")]
PROBABILITY_LIST = ["High probability", "Middle probability", "Low probability"]

frame_list = ["myncu", "mynco", "mynpa", "myr", "mysr", "myssrcu", "myssrco", "myssrpa"]
attr_list = ["mycu", "myco", "mypa"]


def initialize_custom_card_list():
    db.cachedb.execute("DROP TABLE IF EXISTS custom_card")
    db.cachedb.execute("""
        CREATE TABLE custom_card (
            id INTEGER PRIMARY KEY UNIQUE,
            rarity INTEGER,
            image_id INTEGER,
            vocal INTEGER,
            dance INTEGER,
            visual INTEGER,
            life INTEGER,
            use_training_point INTEGER,
            vocal_point INTEGER,
            dance_point INTEGER,
            visual_point INTEGER,
            life_point INTEGER,
            leader_skill_id INTEGER,
            skill_rank INTEGER,
            skill_type INTEGER,
            use_custom_skill INTEGER,
            condition INTEGER,
            available_time_type INTEGER,
            probability_type INTEGER,
            value INTEGER,
            value_2 INTEGER,
            value_3 INTEGER
        )
    """)
    db.cachedb.commit()


def get_stat_from_point(rarity: int, point: int, appeal: int) -> int:
    appeal_text = {0: "hp", 1: "vocal", 2: "dance", 3: "visual"}[appeal]

    value = sum(db.masterdb.execute_and_fetchone(
        "SELECT {}_max, bonus_{} FROM card_data WHERE id = ?".format(appeal_text, appeal_text), [500000 + rarity]))
    if point > 0:
        appeal_text = "life" if appeal == 0 else appeal_text
        value += db.masterdb.execute_and_fetchone(
            "SELECT add_{} FROM card_data_custom_growth_param WHERE point = ?".format(appeal_text), [point])[0]
    return value


def refresh_custom_card_images():
    paths = (IMAGE_PATH, IMAGE_PATH32, IMAGE_PATH64)
    for path in paths:
        images = os.listdir(str(path))
        for image in images:
            try:
                card_id = int(image[:-4])
                if 500000 < card_id < 600000:
                    os.remove(str(path / image))
            except (ValueError, OSError, NotImplementedError):
                pass
    custom_cards = db.cachedb.execute_and_fetchall("SELECT id, rarity, image_id FROM custom_card")
    for card in custom_cards:
        save_custom_card_image(card[0], card[1], card[2])


def save_custom_card_image(custom_id: int, rarity: int, image_id: int):
    card_id = 500000 + custom_id
    attribute = int(str(image_id)[0])
    frame_index = (0, 3, 4, 5)[(rarity - 1) // 2]
    if frame_index in (0, 5):
        frame_index += attribute - 1

    image = Image.open(str(IMAGE_PATH / "{}.png".format(image_id)))
    frame = Image.open(str(MY_IMAGE_PATH / (frame_list[frame_index] + ".png")))
    my = Image.open(str(MY_IMAGE_PATH / "my1.png"))
    attr_icon = Image.open(str(MY_IMAGE_PATH / (attr_list[attribute-1] + ".png")))

    frame_positioned = Image.new('RGBA', (124, 124), color=(0, 0, 0, 0))
    frame_positioned.paste(frame, (0, 0))
    my_positioned = Image.new('RGBA', (124, 124), color=(0, 0, 0, 0))
    my_positioned.paste(my, (82, 2))
    attr_icon_positioned = Image.new('RGBA', (124, 124), color=(0, 0, 0, 0))
    attr_icon_positioned.paste(attr_icon, (2, 99))

    custom_image = Image.new('RGBA', (124, 124))
    custom_image.alpha_composite(image)
    custom_image.alpha_composite(frame_positioned)
    custom_image.alpha_composite(my_positioned)
    custom_image.alpha_composite(attr_icon_positioned)
    custom_image.save(str(IMAGE_PATH / "{}.png".format(card_id)), "PNG")

    custom_image_copy = Image.new('RGBA', (124, 124), color=(255, 255, 255, 255))
    custom_image_copy.alpha_composite(custom_image)
    custom_image64 = custom_image_copy.convert('RGB').resize((64, 64))
    custom_image64.save(str(IMAGE_PATH64 / "{}.jpg".format(card_id)), "JPEG")
    custom_image32 = custom_image_copy.convert('RGB').resize((32, 32))
    custom_image32.save(str(IMAGE_PATH32 / "{}.jpg".format(card_id)), "JPEG")


class CustomListWidget(QTableWidget):
    drag_start_position: QPoint
    selected: list[QTableWidgetItem]

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
        card_id = "5" + self.item(card_row, 0).text().zfill(5)

        mimedata = QMimeData()
        mimedata.setText(CARD + card_id)
        drag.setMimeData(mimedata)
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

    def selected_row(self) -> Optional[int]:
        if len(self.selectionModel().selectedRows()) == 0:
            return
        else:
            return self.selectionModel().selectedRows()[0].row()


class CustomView:
    widget: QGroupBox
    layout: QGridLayout
    model: CustomModel

    def __init__(self):
        self.widget = QGroupBox()
        self.layout = QGridLayout(self.widget)
        self._setup_widget()

    def set_model(self, model: CustomModel):
        self.model = model
        self.model.load_data()
        self.update_leader()
        self.update_skill()

    def _setup_widget(self):
        self.widget.setTitle("Custom Cards")

        self._setup_image()
        self._setup_appeal_leader()
        self._setup_skill()
        self._setup_buttons()
        self._setup_list()

        self.update_skill_detail()
        self.reset_settings()

    def _setup_image(self):
        self.image_layout = QVBoxLayout()
        self.layout.addLayout(self.image_layout, 0, 0)
        self.layout.setColumnStretch(0, 3)

        self.rarity_layout = QHBoxLayout()
        self.image_layout.addLayout(self.rarity_layout)

        self.rarity_label = QLabel("Rarity : ")
        self.rarity_layout.addWidget(self.rarity_label)

        self.rarity_box = QComboBox()
        self.rarity_box.addItems(("SSR+", "SSR", "SR+", "SR", "R+", "R", "N+", "N"))
        self.rarity_box.currentIndexChanged.connect(lambda: self.update_image())
        self.rarity_box.currentIndexChanged.connect(lambda: self.update_appeal())
        self.rarity_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rarity_layout.addWidget(self.rarity_box)

        self.card_image = QLabel()
        card_pixmap = QPixmap(124, 124)
        card_pixmap.fill(QColor(255, 255, 255, 255))
        self.card_image.setPixmap(card_pixmap)
        self.card_painter = QPainter(self.card_image.pixmap())
        self.card_painter.end()
        self.image_layout.addWidget(self.card_image)

        self.card_image_setting_layout = QHBoxLayout()
        self.image_layout.addLayout(self.card_image_setting_layout)

        self.card_image_label = QLabel("Image ID : ")
        self.card_image_setting_layout.addWidget(self.card_image_label)

        self.card_image_id_edit = QLineEdit()
        self.card_image_id_edit.setValidator(QIntValidator(100000, 399999, None))
        self.card_image_id_edit.editingFinished.connect(lambda: self.update_image())
        self.card_image_setting_layout.addWidget(self.card_image_id_edit)

    def _setup_appeal_leader(self):
        self.appeal_leader_layout = QVBoxLayout()
        self.appeal_leader_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addLayout(self.appeal_leader_layout, 0, 2)
        self.layout.setColumnStretch(1, 1)
        self.layout.setColumnStretch(2, 9)

        self.appeal_layout = QGridLayout()
        self.appeal_leader_layout.addLayout(self.appeal_layout)

        self.vocal_layout = QVBoxLayout()
        self.appeal_layout.addLayout(self.vocal_layout, 0, 0)

        self.vocal_label = QLabel("Vocal")
        self.vocal_label.setAlignment(Qt.AlignCenter)
        self.vocal_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.vocal_layout.addWidget(self.vocal_label)

        self.vocal_text = QLineEdit(str(3000))
        self.vocal_text.setValidator(QIntValidator(0, 99999, None))
        self.vocal_layout.addWidget(self.vocal_text)

        self.vocal_spinbox = QSpinBox()
        self.vocal_spinbox.setRange(0, 30)
        self.vocal_spinbox.valueChanged.connect(lambda: self.update_appeal(1))
        self.vocal_spinbox.setDisabled(True)
        self.vocal_layout.addWidget(self.vocal_spinbox)

        self.dance_layout = QVBoxLayout()
        self.appeal_layout.addLayout(self.dance_layout, 0, 1)

        self.dance_label = QLabel("Dance")
        self.dance_label.setAlignment(Qt.AlignCenter)
        self.dance_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dance_layout.addWidget(self.dance_label)

        self.dance_text = QLineEdit(str(3000))
        self.dance_text.setValidator(QIntValidator(0, 99999, None))
        self.dance_layout.addWidget(self.dance_text)

        self.dance_spinbox = QSpinBox()
        self.dance_spinbox.setRange(0, 30)
        self.dance_spinbox.valueChanged.connect(lambda: self.update_appeal(2))
        self.dance_spinbox.setDisabled(True)
        self.dance_layout.addWidget(self.dance_spinbox)

        self.visual_layout = QVBoxLayout()
        self.appeal_layout.addLayout(self.visual_layout, 0, 2)

        self.visual_label = QLabel("Visual")
        self.visual_label.setAlignment(Qt.AlignCenter)
        self.visual_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.visual_layout.addWidget(self.visual_label)

        self.visual_text = QLineEdit(str(3000))
        self.visual_text.setValidator(QIntValidator(0, 99999, None))
        self.visual_layout.addWidget(self.visual_text)

        self.visual_spinbox = QSpinBox()
        self.visual_spinbox.setRange(0, 30)
        self.visual_spinbox.valueChanged.connect(lambda: self.update_appeal(3))
        self.visual_spinbox.setDisabled(True)
        self.visual_layout.addWidget(self.visual_spinbox)

        self.life_layout = QVBoxLayout()
        self.appeal_layout.addLayout(self.life_layout, 0, 3)

        self.life_label = QLabel("Life")
        self.life_label.setAlignment(Qt.AlignCenter)
        self.life_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.life_layout.addWidget(self.life_label)

        self.life_text = QLineEdit(str(44))
        self.life_text.setValidator(QIntValidator(0, 999, None))
        self.life_layout.addWidget(self.life_text)

        self.life_spinbox = QSpinBox()
        self.life_spinbox.setRange(0, 30)
        self.life_spinbox.valueChanged.connect(lambda: self.update_appeal(0))
        self.life_spinbox.setDisabled(True)
        self.life_layout.addWidget(self.life_spinbox)

        self.appeal_checkbox = QCheckBox("Use MY Card training point")
        self.appeal_checkbox.stateChanged.connect(lambda: self.change_appeal_mode())
        self.appeal_layout.addWidget(self.appeal_checkbox, 1, 0, 1, 4)

        self.leader_layout = QVBoxLayout()
        self.appeal_leader_layout.addLayout(self.leader_layout)

        self.leader_grade_layout = QHBoxLayout()
        self.leader_layout.addLayout(self.leader_grade_layout)

        self.leader_label = QLabel("Leader Skill")
        self.leader_label.setAlignment(Qt.AlignCenter)
        self.leader_grade_layout.addWidget(self.leader_label)

        self.leader_grade_combobox = QComboBox()
        self.leader_grade_combobox.addItems(["★3 (SSR)", "★2 (SR)", "★1 (R)"])
        self.leader_grade_combobox.currentIndexChanged.connect(lambda: self.update_leader())
        self.leader_grade_layout.addWidget(self.leader_grade_combobox)

        self.leader_id_combobox = QComboBox()
        self.leader_layout.addWidget(self.leader_id_combobox)

    def _setup_skill(self):
        self.skill_layout = QVBoxLayout()
        self.layout.addLayout(self.skill_layout, 0, 4)
        self.layout.setColumnStretch(3, 1)
        self.layout.setColumnStretch(4, 9)

        self.skill_grade_layout = QHBoxLayout()
        self.skill_layout.addLayout(self.skill_grade_layout)

        self.skill_label = QLabel("Skill")
        self.skill_label.setAlignment(Qt.AlignCenter)
        self.skill_grade_layout.addWidget(self.skill_label)

        self.skill_grade_combobox = QComboBox()
        self.skill_grade_combobox.addItems(["★3 (SSR)", "★2 (SR)", "★1 (R)"])
        self.skill_grade_combobox.currentIndexChanged.connect(lambda: self.update_skill())
        self.skill_grade_layout.addWidget(self.skill_grade_combobox)

        self.skill_type_combobox = QComboBox()
        self.skill_type_combobox.currentIndexChanged.connect(lambda: self.update_skill_detail())
        self.skill_type_combobox.currentIndexChanged.connect(lambda: self._handle_skill_selection())
        self.skill_layout.addWidget(self.skill_type_combobox)

        self.skill_detail_combobox = QComboBox()
        self.skill_detail_combobox.currentIndexChanged.connect(lambda: self._sync_custom_to_regular_skill())
        self.skill_detail_combobox.setDisabled(True)
        self.skill_layout.addWidget(self.skill_detail_combobox)

        self.skill_custom_time_layout = QHBoxLayout()
        self.skill_layout.addLayout(self.skill_custom_time_layout)

        self.skill_custom_interval_combobox = QComboBox()
        self.skill_custom_interval_combobox.addItem("-")
        self.skill_custom_interval_combobox.addItems(["{} sec.".format(_) for _ in INTERVAL_LIST])
        self.skill_custom_interval_combobox.setDisabled(True)
        self.skill_custom_time_layout.addWidget(self.skill_custom_interval_combobox, 3)

        self.skill_custom_duration_combobox = QComboBox()
        self.skill_custom_duration_combobox.addItem("-")
        self.skill_custom_duration_combobox.addItems(["{} ({} sec.)".format(_[1], _[0]) for _ in DURATION_LIST])
        self.skill_custom_duration_combobox.setDisabled(True)
        self.skill_custom_time_layout.addWidget(self.skill_custom_duration_combobox, 7)

        self.skill_custom_probability_combobox = QComboBox()
        self.skill_custom_probability_combobox.addItem("-")
        self.skill_custom_probability_combobox.addItems(PROBABILITY_LIST)
        self.skill_custom_probability_combobox.setDisabled(True)
        self.skill_layout.addWidget(self.skill_custom_probability_combobox)

        self.skill_custom_checkbox = QCheckBox("Use custom skill settings")
        self.skill_custom_checkbox.stateChanged.connect(lambda: self.change_skill_mode())
        self.skill_custom_checkbox.setDisabled(True)
        self.skill_layout.addWidget(self.skill_custom_checkbox)

    def _setup_buttons(self):
        self.buttons_layout = QVBoxLayout()
        self.layout.addLayout(self.buttons_layout, 0, 6)
        self.layout.setColumnStretch(5, 1)
        self.layout.setColumnStretch(6, 6)

        self.reset_button = QPushButton("Reset")
        self.reset_button.pressed.connect(lambda: self.reset_settings())
        self.reset_button.setToolTip("Clear all current custom card settings.")
        self.buttons_layout.addWidget(self.reset_button)

        self.load_button = QPushButton("Load")
        self.load_button.pressed.connect(lambda: self.model.load_card())
        self.load_button.setToolTip("Set custom card settings to selected custom card.")
        self.buttons_layout.addWidget(self.load_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.pressed.connect(lambda: self.model.delete_card())
        self.delete_button.setToolTip("Delete selected custom card from the list.")
        self.buttons_layout.addWidget(self.delete_button)

        self.save_button = QPushButton("Save")
        self.save_button.pressed.connect(lambda: self.model.save_card(self._get_current_card_data()))
        self.save_button.setToolTip("Overwrite current custom card settings to selected custom card.")
        self.buttons_layout.addWidget(self.save_button)

        self.create_button = QPushButton("Create")
        self.create_button.pressed.connect(lambda: self.model.create_card(self._get_current_card_data()))
        self.create_button.setToolTip("Add new custom card with current custom card settings.")
        self.buttons_layout.addWidget(self.create_button)

        self.push_layout = QHBoxLayout()
        self.buttons_layout.addLayout(self.push_layout)

        self.push_button = QPushButton("Push")
        self.push_button.pressed.connect(lambda: self.model.push_custom_card())
        self.push_button.setToolTip("Send selected custom card to first empty card space in the calculator.\n"
                                    "Guest slot will be ignored if Guest checkbox is not checked.")
        self.push_layout.addWidget(self.push_button)

        self.push_checkbox = QCheckBox("Guest")
        self.push_layout.addWidget(self.push_checkbox)

    def _setup_list(self):
        self.list_widget = CustomListWidget(self.widget)
        self.list_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Disable edit
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.list_widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)  # Smooth scroll
        self.list_widget.verticalHeader().setVisible(False)
        self.list_widget.setSortingEnabled(True)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layout.addWidget(self.list_widget, 1, 0, 1, 7)

    def load_custom_cards(self, data: OrderedDict):
        data_cols = ["ID", "Name", "Rarity", "Color", "Skill", "Leader",
                     "Interval", "Prob", "Vocal", "Dance", "Visual", "Life"]

        self.list_widget.clear()
        self.list_widget.setColumnCount(len(data_cols))
        self.list_widget.setRowCount(len(data))
        self.list_widget.setHorizontalHeaderLabels(data_cols)
        self.list_widget.horizontalHeader().setSectionResizeMode(cast(QHeaderView.ResizeMode, 4))
        self.list_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        for r_idx, card_data in enumerate(data):
            for c_idx, (key, value) in enumerate(card_data.items()):
                if isinstance(value, int):
                    item = NumericalTableWidgetItem(value)
                else:
                    item = QTableWidgetItem(str(value))
                if key == 'Interval' and value == 0:
                    item = QTableWidgetItem("")
                if key == 'Skill' and value is not None:
                    item.setBackground(QColor(*SKILL_COLOR_BY_NAME[value], 135))
                if key == 'Color' and value is not None:
                    item.setBackground(QColor(*CARD_GUI_COLORS[value], 100))
                self.list_widget.setItem(r_idx, c_idx, item)
        self.list_widget.sortItems(0, Qt.AscendingOrder)

    @property
    def card_rarity(self) -> int:
        return 8 - self.rarity_box.currentIndex()

    @property
    def image_id(self) -> str:
        return self.card_image_id_edit.text()

    @property
    def vocal(self) -> int:
        return int(self.vocal_text.text())

    @property
    def vocal_point(self) -> int:
        return self.vocal_spinbox.value()

    @property
    def dance(self) -> int:
        return int(self.dance_text.text())

    @property
    def dance_point(self) -> int:
        return self.dance_spinbox.value()

    @property
    def visual(self) -> int:
        return int(self.visual_text.text())

    @property
    def visual_point(self) -> int:
        return self.visual_spinbox.value()

    @property
    def life(self) -> int:
        return int(self.life_text.text())

    @property
    def life_point(self) -> int:
        return self.life_spinbox.value()

    @property
    def use_training_point(self) -> bool:
        return self.appeal_checkbox.isChecked()

    @property
    def leader_grade(self) -> int:
        return 3 - self.leader_grade_combobox.currentIndex()

    @property
    def leader_id(self) -> int:
        grade_idx = self.leader_grade_combobox.currentIndex()
        id_idx = self.leader_id_combobox.currentIndex()
        return list(self.model.leader_list[grade_idx].keys())[id_idx]

    @property
    def skill_grade(self) -> int:
        return 3 - self.skill_grade_combobox.currentIndex()

    @property
    def skill_type(self) -> int:
        grade_idx = self.skill_grade_combobox.currentIndex()
        type_idx = self.skill_type_combobox.currentIndex()
        return list(self.model.skill_list[grade_idx].keys())[type_idx]

    @property
    def skill_values(self) -> dict[str, Any]:
        grade_idx = self.skill_grade_combobox.currentIndex()
        type_idx = self.skill_type_combobox.currentIndex()
        value_idx = self.skill_detail_combobox.currentIndex()
        values = cast(tuple[str, list[dict[str, Any]]], list(self.model.skill_list[grade_idx].values())[type_idx])
        return values[1][value_idx]

    @property
    def skill_interval(self) -> int:
        return self.skill_values['condition']

    @property
    def skill_duration(self) -> int:  # 1 ~ 5
        return self.skill_values['available_time_type']

    @property
    def skill_probability(self) -> int:  # 1 ~ 3
        return self.skill_values['probability_type']

    @property
    def use_custom_skill(self) -> bool:
        return self.skill_custom_checkbox.isChecked()

    @property
    def skill_custom_interval(self) -> int:
        return INTERVAL_LIST[self.skill_custom_interval_combobox.currentIndex()]

    @property
    def skill_custom_duration(self) -> int:
        return 1 + self.skill_custom_duration_combobox.currentIndex()

    @property
    def skill_custom_probability(self) -> int:
        return 4 - self.skill_custom_probability_combobox.currentIndex()

    def update_image(self):
        if self.image_id == "" or int(self.image_id) < 100000:
            return
        attribute = int(self.image_id[0])
        if attribute not in (1, 2, 3) or not os.path.exists(str(IMAGE_PATH / (self.image_id + ".png"))):
            return

        frame_index = (0, 3, 4, 5)[(self.card_rarity - 1) // 2]
        if frame_index in (0, 5):
            frame_index += attribute - 1

        image = QImage(str(IMAGE_PATH / (self.image_id + ".png")))
        frame = QImage(str(MY_IMAGE_PATH / (frame_list[frame_index] + ".png")))
        my = QImage(str(MY_IMAGE_PATH / "my1.png"))
        attr_icon = QImage(str(MY_IMAGE_PATH / (attr_list[attribute-1] + ".png")))

        self.card_painter.begin(self.card_image.pixmap())
        self.card_painter.setPen(QPen(Qt.white, 1, Qt.SolidLine))
        self.card_painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        self.card_painter.drawRect(0, 0, 123, 123)
        self.card_painter.drawImage(QPoint(0, 0), image)
        self.card_painter.drawImage(QPoint(0, 0), frame)
        self.card_painter.drawImage(QPoint(82, 2), my)
        self.card_painter.drawImage(QPoint(2, 99), attr_icon)
        self.card_image.repaint()
        self.card_painter.end()

    def change_appeal_mode(self):
        texts = (self.vocal_text, self.dance_text, self.visual_text, self.life_text)
        spinboxes = (self.vocal_spinbox, self.dance_spinbox, self.visual_spinbox, self.life_spinbox)

        for text in texts:
            text.setEnabled(not self.use_training_point)
        for spinbox in spinboxes:
            spinbox.setEnabled(self.use_training_point)
        if self.use_training_point:
            self.update_appeal()

    def update_appeal(self, appeal: int = None):
        if not self.use_training_point:
            return
        if appeal in (None, 1):
            self.vocal_text.setText(str(get_stat_from_point(self.card_rarity, self.vocal_point, 1)))
        if appeal in (None, 2):
            self.dance_text.setText(str(get_stat_from_point(self.card_rarity, self.dance_point, 2)))
        if appeal in (None, 3):
            self.visual_text.setText(str(get_stat_from_point(self.card_rarity, self.visual_point, 3)))
        if appeal in (None, 0):
            self.life_text.setText(str(get_stat_from_point(self.card_rarity, self.life_point, 0)))

    def update_leader(self):
        self.leader_id_combobox.clear()
        self.leader_id_combobox.addItems(self.model.leader_list[self.leader_grade_combobox.currentIndex()].values())

    def change_skill_mode(self):
        self.skill_detail_combobox.setEnabled(not self.use_custom_skill)
        self.skill_custom_interval_combobox.setEnabled(self.use_custom_skill)
        self.skill_custom_duration_combobox.setEnabled(self.use_custom_skill)
        self.skill_custom_probability_combobox.setEnabled(self.use_custom_skill)
        if not self.use_custom_skill:
            self.update_skill_detail()
            self._sync_custom_to_regular_skill()
        else:
            self.skill_detail_combobox.clear()
            self.skill_detail_combobox.addItem("-")

    def update_skill(self):
        self.skill_type_combobox.clear()
        names = [detail[0] for detail in cast(tuple[str, list[dict[str, Any]]],
                 list(self.model.skill_list[self.skill_grade_combobox.currentIndex()].values()))]
        self.skill_type_combobox.addItems(names)
        self.update_skill_detail()

    def update_skill_detail(self):
        self.skill_detail_combobox.clear()
        if self.skill_type_combobox.currentIndex() > 0:
            grade_idx = self.skill_grade_combobox.currentIndex()
            type_idx = self.skill_type_combobox.currentIndex()
            values = cast(tuple[str, list[dict[str, Any]]],
                          list(self.model.skill_list[grade_idx].values())[type_idx])[1]
            prob_text = db.cachedb.execute_and_fetchall("SELECT id, keywords FROM probability_keywords")
            prob_text.sort()
            prob_text = [prob[1] for prob in prob_text]
            self.skill_detail_combobox.addItems([
                "{} seconds, {} probability".format(value['condition'], prob_text[value['probability_type']])
                for value in values])
        else:
            self.skill_detail_combobox.addItem("-")

    def reset_settings(self):
        self.rarity_box.setCurrentIndex(0)

        self.card_painter.begin(self.card_image.pixmap())
        self.card_painter.setPen(QPen(Qt.white, 1, Qt.SolidLine))
        self.card_painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        self.card_painter.drawRect(0, 0, 123, 123)
        self.card_painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
        self.card_painter.drawRoundedRect(0, 0, 123, 123, 10, 10)
        self.card_image.repaint()
        self.card_painter.end()

        self.card_image_id_edit.setText("")

        self.vocal_text.setText(str(3000))
        self.dance_text.setText(str(3000))
        self.visual_text.setText(str(3000))
        self.life_text.setText(str(44))
        self.vocal_spinbox.setValue(0)
        self.dance_spinbox.setValue(0)
        self.visual_spinbox.setValue(0)
        self.life_spinbox.setValue(0)

        self.appeal_checkbox.setChecked(False)

        self.leader_grade_combobox.setCurrentIndex(0)
        self.leader_id_combobox.setCurrentIndex(0)

        self.skill_grade_combobox.setCurrentIndex(0)
        self.skill_type_combobox.setCurrentIndex(0)
        self.skill_detail_combobox.setCurrentIndex(0)
        self.skill_custom_checkbox.setChecked(False)
        self.skill_custom_interval_combobox.setCurrentIndex(0)
        self.skill_custom_duration_combobox.setCurrentIndex(0)
        self.skill_custom_probability_combobox.setCurrentIndex(0)

    def _get_current_card_data(self) -> list[Union[int, str]]:
        if not self.use_custom_skill:
            skill_interval = self.skill_interval
            skill_duration = self.skill_duration
            skill_probability = self.skill_probability
        else:
            skill_interval = self.skill_custom_interval
            skill_duration = self.skill_custom_duration
            skill_probability = self.skill_custom_probability
        return [self.card_rarity, self.image_id, self.vocal, self.dance, self.visual, self.life,
                self.use_training_point, self.vocal_point, self.dance_point, self.visual_point, self.life_point,
                self.leader_id, self.skill_grade, self.skill_type, self.use_custom_skill,
                skill_interval, skill_duration, skill_probability,
                self.skill_values['value'], self.skill_values['value_2'], self.skill_values['value_3']]

    def load_card(self, data: OrderedDict):
        self.rarity_box.setCurrentIndex(8 - data['rarity'])

        self.card_image_id_edit.setText(str(data['image_id']))
        self.update_image()

        if data['use_training_point']:
            self.appeal_checkbox.setChecked(True)
            self.vocal_spinbox.setValue(data['vocal_point'])
            self.dance_spinbox.setValue(data['dance_point'])
            self.visual_spinbox.setValue(data['visual_point'])
            self.life_spinbox.setValue(data['life_point'])
        else:
            self.appeal_checkbox.setChecked(False)
            self.vocal_text.setText(str(data['vocal']))
            self.dance_text.setText(str(data['dance']))
            self.visual_text.setText(str(data['visual']))
            self.life_text.setText(str(data['life']))
            self.vocal_spinbox.setValue(0)
            self.dance_spinbox.setValue(0)
            self.visual_spinbox.setValue(0)
            self.life_spinbox.setValue(0)

        leader_skill_id = data['leader_skill_id'] % 5000
        leader_grade_idx = next(idx for idx, leaders in enumerate(self.model.leader_list)
                                if leader_skill_id in leaders.keys())
        leader_id_idx = list(self.model.leader_list[leader_grade_idx].keys()).index(leader_skill_id)
        self.leader_grade_combobox.setCurrentIndex(leader_grade_idx)
        self.update_leader()
        self.leader_id_combobox.setCurrentIndex(leader_id_idx)

        skill_grade_idx = 3 - data['skill_rank']
        skill_type_idx = list(self.model.skill_list[skill_grade_idx].keys()).index(data['skill_type'])
        self.skill_grade_combobox.setCurrentIndex(skill_grade_idx)
        self.update_skill()
        self.skill_type_combobox.setCurrentIndex(skill_type_idx)
        if data['use_custom_skill']:
            self.skill_custom_checkbox.setChecked(True)
            self.skill_detail_combobox.setCurrentIndex(0)
            self.skill_custom_interval_combobox.setCurrentIndex(INTERVAL_LIST.index(data['condition']))
            self.skill_custom_duration_combobox.setCurrentIndex(data['available_time_type'] - 1)
            self.skill_custom_probability_combobox.setCurrentIndex(4 - data['probability_type'])
        else:
            self.skill_custom_checkbox.setChecked(False)
            skill_detail_list = cast(tuple[str, list[dict[str, Any]]],
                                     list(self.model.skill_list[skill_grade_idx].values())[skill_type_idx])[1]
            skill_detail_idx = next(idx for idx, detail in enumerate(skill_detail_list)
                                    if detail['condition'] == data['condition']
                                    and detail['probability_type'] == data['probability_type'])
            self.skill_detail_combobox.setCurrentIndex(skill_detail_idx)
            self._sync_custom_to_regular_skill()

    def _handle_skill_selection(self):
        self.skill_custom_checkbox.setDisabled(True)
        self.skill_custom_interval_combobox.clear()
        self.skill_custom_duration_combobox.clear()
        self.skill_custom_probability_combobox.clear()
        if self.skill_type_combobox.currentIndex() > 0:
            self.skill_custom_checkbox.setDisabled(False)
            self.skill_custom_interval_combobox.addItems(["{} sec.".format(_) for _ in INTERVAL_LIST])
            self.skill_custom_duration_combobox.addItems(["{} ({} sec.)".format(_[1], _[0]) for _ in DURATION_LIST])
            self.skill_custom_probability_combobox.addItems(PROBABILITY_LIST)
            self.change_skill_mode()
        else:
            self.skill_detail_combobox.setDisabled(True)
            self.skill_custom_interval_combobox.addItem("-")
            self.skill_custom_interval_combobox.setDisabled(True)
            self.skill_custom_duration_combobox.addItem("-")
            self.skill_custom_duration_combobox.setDisabled(True)
            self.skill_custom_probability_combobox.addItem("-")
            self.skill_custom_probability_combobox.setDisabled(True)

    def _sync_custom_to_regular_skill(self):
        if self.skill_type_combobox.currentIndex() > 0 and not self.use_custom_skill:
            self.skill_custom_interval_combobox.setCurrentIndex(INTERVAL_LIST.index(self.skill_interval))
            self.skill_custom_duration_combobox.setCurrentIndex(self.skill_duration - 1)
            self.skill_custom_probability_combobox.setCurrentIndex(4 - self.skill_probability)

    def is_setting_valid(self) -> bool:
        image_id = self.card_image_id_edit.text()
        if db.cachedb.execute_and_fetchone("SELECT 1 FROM card_data_cache WHERE id = ?", [image_id]) is None:
            return False
        if "" in (self.vocal_text.text(), self.dance_text.text(), self.visual_text.text(), self.life_text.text()):
            return False
        return True


class CustomModel:
    view: CustomView

    leader_list: list[OrderedDict[int, str]]
    skill_list: list[OrderedDict[int, tuple[str, list[dict[str, Any]]]]]

    def __init__(self, view: CustomView):
        self.view = view
        eventbus.eventbus.register(self)

    def load_data(self):
        self._fetch_leader()
        self._fetch_skill()
        self.load_custom_cards()

    def _fetch_leader(self):
        rarities = (8, 6, 4)
        self.leader_list = list()

        leader_names = {leader_id: leader_keyword for (leader_id, leader_keyword)
                        in db.cachedb.execute_and_fetchall("SELECT id, keywords FROM leader_keywords")}
        # Some of "Shiny" leader skills present in data but not in actual cards, so add these manually
        shinys = ((62, 63, 64, 65, 66), (39, 40, 41, 42, 43), (16, 17, 18, 19, 20))
        for rarity_idx, rarity in enumerate(rarities):
            leader_ids = [l[0] for l in db.cachedb.execute_and_fetchall(
                "SELECT DISTINCT leader_skill_id FROM card_data_cache WHERE rarity = ?", [rarity]) if l[0] > 0]
            leader_ids.extend(shinys[rarity_idx])
            leader_ids = list(set(leader_ids))
            leader_ids.sort()
            leader_ids.insert(0, 0)
            self.leader_list.append(OrderedDict((leader_id, leader_names[leader_id]) for leader_id in leader_ids))

    def _fetch_skill(self):
        rarities = (8, 6, 4)
        self.skill_list = list()

        skill_types = {skill_id: skill_type for (skill_id, skill_type)
                       in db.masterdb.execute_and_fetchall("SELECT id, skill_type FROM skill_data")}
        skill_names = {skill_type: skill_name for (skill_type, skill_name)
                       in db.cachedb.execute_and_fetchall("SELECT id, skill_name FROM skill_keywords")}
        for rarity in rarities:
            rarity_skills = OrderedDict()
            skill_ids = [s[0] for s in db.cachedb.execute_and_fetchall(
                "SELECT DISTINCT skill_id FROM card_data_cache WHERE rarity = ?", [rarity]) if s[0] > 0]
            rarity_skill_types = list(set([skill_types[skill_id] for skill_id in skill_ids]))
            rarity_skill_types.sort()
            rarity_skills[0] = ("", [OrderedDict([('condition', 0), ('available_time_type', 0), ('probability_type', 0),
                                                 ('value', 0), ('value_2', 0), ('value_3', 0)])])
            for skill_type in rarity_skill_types:
                name = skill_names[skill_type]
                values = db.masterdb.execute_and_fetchall("""
                                                            SELECT DISTINCT
                                                                condition,
                                                                available_time_type,
                                                                probability_type,
                                                                value,
                                                                value_2,
                                                                value_3
                                                            FROM skill_data
                                                            LEFT JOIN card_data on skill_data.id = card_data.id
                                                            WHERE rarity = ? AND skill_type = ?
                                                            """, [rarity-1, skill_type], out_dict=True)
                values.sort(key=lambda x: (x['condition'], -x['probability_type']))
                rarity_skills[skill_type] = (name, values)
            self.skill_list.append(rarity_skills)

    def load_custom_cards(self):
        db.cachedb.execute("""ATTACH DATABASE "{}" AS masterdb""".format(meta_updater.get_masterdb_path()))
        db.cachedb.commit()
        query = """
                SELECT  cu.id as ID,
                        cdc.name as Name,
                        REPLACE(UPPER(rt.text) || "+", "U+", "") as Rarity,
                        ct.text as Color,
                        sk.skill_name as Skill,
                        lk.keywords as Leader,
                        cu.condition as Interval,
                        pk.keywords as Prob,
                        cu.vocal as Vocal,
                        cu.dance as Dance,
                        cu.visual as Visual,
                        cu.life as Life
                FROM custom_card as cu
                INNER JOIN card_data_cache cdc on cu.image_id = cdc.id
                INNER JOIN rarity_text rt on cu.rarity = rt.id
                INNER JOIN color_text ct on cdc.attribute = ct.id
                INNER JOIN probability_keywords pk on cu.probability_type = pk.id
                INNER JOIN skill_keywords sk on cu.skill_type = sk.id
                INNER JOIN leader_keywords lk on cu.leader_skill_id = lk.id
                """
        data = db.cachedb.execute_and_fetchall(query, out_dict=True)
        db.cachedb.execute("DETACH DATABASE masterdb")
        db.cachedb.commit()
        self.view.load_custom_cards(data)

    @subscribe(YoinkCustomCardEvent)
    def _handle_yoink_custom_card(self, event):
        self.load_custom_cards()

    def create_card(self, card_data: list[Union[int, str]]):
        if not self.view.is_setting_valid():
            return
        db.cachedb.execute("""
                INSERT INTO custom_card (
                    "rarity", "image_id", "vocal", "dance", "visual", "life", "use_training_point",
                    "vocal_point", "dance_point", "visual_point", "life_point", "leader_skill_id",
                    "skill_rank", "skill_type", "use_custom_skill", "condition", "available_time_type",
                    "probability_type", "value", "value_2", "value_3")
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, card_data)
        db.cachedb.commit()
        custom_id = db.cachedb.execute_and_fetchone("SELECT last_insert_rowid()")[0]
        save_custom_card_image(int(custom_id), card_data[0], int(card_data[1]))
        self.load_custom_cards()

    def save_card(self, card_data: list[Union[int, str]]):
        selected_row = self.view.list_widget.selected_row()
        if not self.view.is_setting_valid() or selected_row is None:
            return
        custom_id = cast(NumericalTableWidgetItem, self.view.list_widget.item(selected_row, 0)).number
        prev_image_id = db.cachedb.execute_and_fetchone("SELECT image_id FROM custom_card WHERE id = ?", [custom_id])[0]
        db.cachedb.execute("""
                UPDATE custom_card
                SET rarity = ?, image_id = ?, vocal = ?, dance = ?, visual = ?, life = ?, use_training_point = ?,
                    vocal_point = ?, dance_point = ?, visual_point = ?, life_point = ?, leader_skill_id = ?,
                    skill_rank = ?, skill_type = ?, use_custom_skill = ?, condition = ?, available_time_type = ?,
                    probability_type = ?, value = ?, value_2 = ?, value_3 = ?
                WHERE id = ?
                """, card_data + [custom_id])
        db.cachedb.commit()
        save_custom_card_image(int(custom_id), card_data[0], int(card_data[1]))
        self.load_custom_cards()

        card_id = int("5" + str(custom_id).zfill(5))
        eventbus.eventbus.post(CustomCardUpdatedEvent(card_id, image_changed=int(card_data[1]) != prev_image_id))

    def load_card(self):
        selected_row = self.view.list_widget.selected_row()
        if selected_row is None:
            return
        custom_id = cast(NumericalTableWidgetItem, self.view.list_widget.item(selected_row, 0)).number
        data = db.cachedb.execute_and_fetchone("""
            SELECT id, rarity, image_id, vocal, dance, visual, life, use_training_point,
                vocal_point, dance_point, visual_point, life_point, leader_skill_id, skill_rank, skill_type,
                use_custom_skill, condition, available_time_type, probability_type, value, value_2, value_3
            FROM custom_card WHERE id = ?
            """, [custom_id], out_dict=True)
        if data is not None:
            self.view.load_card(data)

    def delete_card(self):
        selected_row = self.view.list_widget.selected_row()
        if selected_row is None:
            return
        custom_id = cast(NumericalTableWidgetItem, self.view.list_widget.item(selected_row, 0)).number
        card_id = int("5" + str(custom_id).zfill(5))
        db.cachedb.execute("DELETE from custom_card WHERE id = ?", [custom_id])
        db.cachedb.commit()
        try:
            os.remove(str(IMAGE_PATH / "{}.png".format(card_id)))
        except OSError:
            pass
        try:
            os.remove(str(IMAGE_PATH32 / "{}.jpg".format(card_id)))
        except OSError:
            pass
        try:
            os.remove(str(IMAGE_PATH64 / "{}.jpg".format(card_id)))
        except OSError:
            pass
        self.load_custom_cards()
        eventbus.eventbus.post(CustomCardUpdatedEvent(card_id, delete=True))

    def push_custom_card(self):
        selected_row = self.view.list_widget.selected_row()
        if selected_row is None:
            return
        custom_id = cast(NumericalTableWidgetItem, self.view.list_widget.item(selected_row, 0)).number
        card_id = int("5" + str(custom_id).zfill(5))
        if 500000 < card_id < 600000:
            eventbus.eventbus.post(PushCardEvent(card_id, not self.view.push_checkbox.isChecked()))
