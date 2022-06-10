import os

from PyQt5.QtCore import Qt, QPoint, QMimeData
from PyQt5.QtGui import QBrush, QColor, QDrag, QImage, QIntValidator, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QApplication,QCheckBox,  QComboBox, QGroupBox, QHBoxLayout,\
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout
from PIL import Image

from db import db
from gui.viewmodels.mime_headers import CARD
from gui.viewmodels.utils import NumericalTableWidgetItem
from network import meta_updater
from settings import IMAGE_PATH, MY_IMAGE_PATH, IMAGE_PATH32, IMAGE_PATH64
from static.color import CARD_GUI_COLORS
from static.skill import SKILL_COLOR_BY_NAME
from utils import storage

INTERVAL_LIST = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18]
DURATION_LIST = [(3, "一瞬の間 "), (4.5, "わずかな間"), (6, "少しの間"), (7.5, "しばらくの間"), (9, "かなりの間")]
PROBABILITY_LIST = ["High probability", "Middle probability", "Low probability"]

class CustomView:
    def __init__(self):
        self.widget = QGroupBox()
        self.layout = QVBoxLayout(self.widget)
        self.unit_view = None
    
    def setup(self):
        self.widget.setTitle("Custom Cards")
        
        self.initialize_custom_card_list()
        self._fetch_leader()
        self._fetch_skill()
        
        self.image_layout = QVBoxLayout()
        self._setup_image()
        self.appeal_leader_layout = QVBoxLayout()
        self._setup_appeal_leader()
        self.skill_layout = QVBoxLayout()
        self._setup_skill()
        self.save_layout = QVBoxLayout()
        self._setup_save()
        self.reset_settings()
        
        self.edit_layout = QHBoxLayout()
        self.edit_layout.addLayout(self.image_layout, 3)
        self.edit_layout.addStretch(1)
        self.edit_layout.addLayout(self.appeal_leader_layout, 9)
        self.edit_layout.addStretch(1)
        self.edit_layout.addLayout(self.skill_layout, 9)
        self.edit_layout.addStretch(1)
        self.edit_layout.addLayout(self.save_layout, 6)
        
        self.list_widget = CustomListWidget(self.widget)
        self.list_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Disable edit
        self.list_widget.setVerticalScrollMode(1)  # Smooth scroll
        self.list_widget.setHorizontalScrollMode(1)  # Smooth scroll
        self.list_widget.verticalHeader().setVisible(False)
        self.list_widget.setSortingEnabled(True)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.list_widget.load_custom_cards()
        
        self.layout.addLayout(self.edit_layout)
        self.layout.addWidget(self.list_widget)
        
        self.unit_view = None
        self.calculator_view = None
    
    def set_unit_view(self, unit_view):
        self.unit_view = unit_view
    
    def set_calculator_view(self, calculator_view):
        self.calculator_view = calculator_view
    
    def initialize_custom_card_list(self):
        db.cachedb.execute("""
            CREATE TABLE IF NOT EXISTS custom_card (
                id INTEGER PRIMARY KEY UNIQUE,
                rarity INTEGER,
                image_id INTEGER,
                vocal INTEGER,
                dance INTEGER,
                visual INTEGER,
                life INTEGER,
                leader_skill_id INTEGER,
                skill_type INTEGER,
                condition INTEGER,
                available_time_type INTEGER,
                probability_type INTEGER,
                value INTEGER,
                value_2 INTEGER,
                value_3 INTEGER
            )
        """)
        #FOREIGN KEY (image_id) REFERENCES card_data_cache(id)
    
    def _fetch_leader(self):
        rarity = [8, 6, 4]
        self.leader_list = []
        self.leader_name_list = []
        
        for r in rarity:
            data = db.cachedb.execute_and_fetchall("SELECT DISTINCT leader_skill_id FROM card_data_cache WHERE rarity = ?", [r])
            leader_list_rarity = [l[0] for l in data]
            self.leader_list.append(leader_list_rarity)
        
        # Some of "Shiny" leader skills present in data but not in actual cards, so add these manually
        shiny_list = [[62, 63, 64, 65, 66], [39, 40, 41, 42, 43], [16, 17, 18, 19, 20]]
        for r in range(3):
            for _ in range(len(shiny_list[r])):
                if shiny_list[r][_] not in self.leader_list[r]:
                    self.leader_list[r].append(shiny_list[r][_])
        
        for _ in self.leader_list: _.sort()
        
        leader_name_dict = {leader_id: leader_keyword for (leader_id, leader_keyword)
                               in db.cachedb.execute_and_fetchall("SELECT id, keywords FROM leader_keywords")}
        leader_name_dict[0] = "-"
        
        for _ in self.leader_list:
            self.leader_name_list.append([leader_name_dict[l] for l in _])
    
    def _fetch_skill(self):
        rarity = [8, 6, 4]
        
        self.skill_list = []
        self.skill_name_list = []
        self.skill_value_list = [] #(skill_type, condition(interval), available_time_type, probability_type, value, value_2, value_3)
        
        skill_data = {skill_id: skill_type for (skill_id, skill_type) 
                      in db.masterdb.execute_and_fetchall("SELECT id, skill_type FROM skill_data")}
        skill_data[0] = 0
        
        for r in rarity:
            card_data = db.cachedb.execute_and_fetchall("SELECT skill_id FROM card_data_cache WHERE rarity = ?", [r])
            card_skill_list = [l[0] for l in card_data]
            self.skill_list.append(list(set([skill_data[skill_id] for skill_id in card_skill_list])))
            
            skill_values = [db.masterdb.execute_and_fetchone("""
                                                                SELECT
                                                                    skill_type,
                                                                    condition,
                                                                    available_time_type,
                                                                    probability_type,
                                                                    value,
                                                                    value_2,
                                                                    value_3
                                                                FROM skill_data
                                                                WHERE id = ?
                                                                """, [skill_id]) for skill_id in card_skill_list]
            skill_values = list(set(skill_values))
            skill_values = [i for i in skill_values if i]
            skill_values.sort()
            self.skill_value_list.append(skill_values)
        
        for _ in self.skill_list: _.sort()
        
        skill_name_dict = {skill_id: skill_name for (skill_id, skill_name)
                           in db.cachedb.execute_and_fetchall("SELECT id, skill_name FROM skill_keywords")}
        skill_name_dict[0] = "-"
        
        for _ in self.skill_list:
            self.skill_name_list.append([skill_name_dict[s] for s in _])
    
    def _setup_image(self):
        self.rarity_layout = QHBoxLayout()
        self.rarity_label = QLabel("Rarity : ")
        self.rarity_box = QComboBox()
        self.rarity_box.addItems(["SSR+", "SSR", "SR+", "SR", "R+", "R", "N+", "N"])
        self.rarity_box.currentIndexChanged.connect(lambda: self.update_image())
        self.rarity_box.currentIndexChanged.connect(lambda: self.update_appeal())
        self.rarity_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rarity_layout.addWidget(self.rarity_label)
        self.rarity_layout.addWidget(self.rarity_box)
        
        self.card_image = QLabel()
        card_pixmap = QPixmap(124, 124)
        self.card_image.setPixmap(card_pixmap)
        self.card_painter = QPainter(self.card_image.pixmap())
        
        self.card_image_setting_layout = QHBoxLayout()
        self.card_image_label = QLabel("Image ID : ")
        self.card_image_id_edit = QLineEdit()
        self.card_image_id_edit.setValidator(QIntValidator(100000, 399999, None))
        self.card_image_id_edit.editingFinished.connect(lambda: self.update_image())
        self.card_image_setting_layout.addWidget(self.card_image_label)
        self.card_image_setting_layout.addWidget(self.card_image_id_edit)
        
        self.image_layout.addLayout(self.rarity_layout)
        self.image_layout.addWidget(self.card_image)
        self.image_layout.addLayout(self.card_image_setting_layout)
    
    def _setup_appeal_leader(self):
        self.appeals_label_layout = QHBoxLayout()
        self.vocal_label = QLabel("Vocal")
        self.vocal_label.setAlignment(Qt.AlignCenter)
        self.vocal_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dance_label = QLabel("Dance")
        self.dance_label.setAlignment(Qt.AlignCenter)
        self.dance_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.visual_label = QLabel("Visual")
        self.visual_label.setAlignment(Qt.AlignCenter)
        self.visual_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.life_label = QLabel("Life")
        self.life_label.setAlignment(Qt.AlignCenter)
        self.life_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.appeals_label_layout.addWidget(self.vocal_label)
        self.appeals_label_layout.addWidget(self.dance_label)
        self.appeals_label_layout.addWidget(self.visual_label)
        self.appeals_label_layout.addWidget(self.life_label)
        
        self.appeals_text_layout = QHBoxLayout()
        self.vocal_text = QLineEdit()
        self.vocal_text.setValidator(QIntValidator(0, 99999, None))
        self.dance_text = QLineEdit()
        self.dance_text.setValidator(QIntValidator(0, 99999, None))
        self.visual_text = QLineEdit()
        self.visual_text.setValidator(QIntValidator(0, 99999, None))
        self.life_text = QLineEdit()
        self.life_text.setValidator(QIntValidator(0, 99999, None))
        self.appeals_text_layout.addWidget(self.vocal_text)
        self.appeals_text_layout.addWidget(self.dance_text)
        self.appeals_text_layout.addWidget(self.visual_text)
        self.appeals_text_layout.addWidget(self.life_text)
        
        self.appeals_spinbox_layout = QHBoxLayout()
        self.vocal_spinbox = QSpinBox()
        self.vocal_spinbox.setRange(0, 30)
        self.vocal_spinbox.valueChanged.connect(lambda: self.update_appeal())
        self.vocal_spinbox.setDisabled(True)
        self.dance_spinbox = QSpinBox()
        self.dance_spinbox.setRange(0, 30)
        self.dance_spinbox.valueChanged.connect(lambda: self.update_appeal())
        self.dance_spinbox.setDisabled(True)
        self.visual_spinbox = QSpinBox()
        self.visual_spinbox.setRange(0, 30)
        self.visual_spinbox.valueChanged.connect(lambda: self.update_appeal())
        self.visual_spinbox.setDisabled(True)
        self.life_spinbox = QSpinBox()
        self.life_spinbox.setRange(0, 30)
        self.life_spinbox.valueChanged.connect(lambda: self.update_appeal())
        self.life_spinbox.setDisabled(True)
        self.appeals_spinbox_layout.addWidget(self.vocal_spinbox)
        self.appeals_spinbox_layout.addWidget(self.dance_spinbox)
        self.appeals_spinbox_layout.addWidget(self.visual_spinbox)
        self.appeals_spinbox_layout.addWidget(self.life_spinbox)
        
        self.appeal_checkbox = QCheckBox("Use MY Card training point")
        self.appeal_checkbox.stateChanged.connect(lambda: self.change_appeal_mode())
        
        self.leader_grade_layout = QHBoxLayout()
        self.leader_label = QLabel("Leader Skill")
        self.leader_label.setAlignment(Qt.AlignCenter)
        self.leader_grade = QComboBox()
        self.leader_grade.addItems(["★3 (SSR)", "★2 (SR)", "★1 (R)"])
        self.leader_grade.currentIndexChanged.connect(lambda: self.update_leader())
        self.leader_grade_layout.addWidget(self.leader_label)
        self.leader_grade_layout.addWidget(self.leader_grade)
        
        self.leader_type = QComboBox()
        self.leader_type.addItems(self.leader_name_list[0])
        
        self.appeal_leader_layout.addLayout(self.appeals_label_layout)
        self.appeal_leader_layout.addLayout(self.appeals_text_layout)
        self.appeal_leader_layout.addLayout(self.appeals_spinbox_layout)
        self.appeal_leader_layout.addWidget(self.appeal_checkbox)
        self.appeal_leader_layout.addLayout(self.leader_grade_layout)
        self.appeal_leader_layout.addWidget(self.leader_type)
        
    def _setup_skill(self):
        self.skill_grade_layout = QHBoxLayout()
        self.skill_label = QLabel("Skill")
        self.skill_label.setAlignment(Qt.AlignCenter)
        self.skill_grade = QComboBox()
        self.skill_grade.addItems(["★3 (SSR)", "★2 (SR)", "★1 (R)"])
        self.skill_grade.currentIndexChanged.connect(lambda: self.update_skill())
        self.skill_grade_layout.addWidget(self.skill_label)
        self.skill_grade_layout.addWidget(self.skill_grade)
        
        self.skill_kind = QComboBox()
        self.skill_kind.addItems(self.skill_name_list[0])
        self.skill_kind.currentIndexChanged.connect(lambda: self.update_skill_detail())
        self.skill_kind.currentIndexChanged.connect(lambda: self._handle_skill_selection())
        
        self.skill_detail = QComboBox()
        self.update_skill_detail()
        self.skill_detail.currentIndexChanged.connect(lambda: self._sync_custom())
        self.skill_detail.setDisabled(True)
        
        self.skill_custom_time_layout = QHBoxLayout()
        self.skill_custom_interval = QComboBox()
        self.skill_custom_interval.addItem("-")
        self.skill_custom_interval.addItems(["{} sec.".format(_) for _ in INTERVAL_LIST])
        self.skill_custom_interval.setDisabled(True)
        self.skill_custom_duration = QComboBox()
        self.skill_custom_duration.addItem("-")
        self.skill_custom_duration.addItems(["{} ({} sec.)".format(_[1], _[0]) for _ in DURATION_LIST])
        self.skill_custom_duration.setDisabled(True)
        self.skill_custom_time_layout.addWidget(self.skill_custom_interval)
        self.skill_custom_time_layout.addWidget(self.skill_custom_duration)
        
        self.skill_custom_probability = QComboBox()
        self.skill_custom_probability.addItem("-")
        self.skill_custom_probability.addItems(PROBABILITY_LIST)
        self.skill_custom_probability.setDisabled(True)
        
        self.skill_custom_checkbox = QCheckBox("Use custom skill settings")
        self.skill_custom_checkbox.stateChanged.connect(lambda: self.change_skill_mode())
        self.skill_custom_checkbox.setDisabled(True)
        
        self.skill_layout.addLayout(self.skill_grade_layout)
        self.skill_layout.addWidget(self.skill_kind)
        self.skill_layout.addWidget(self.skill_detail)
        self.skill_layout.addLayout(self.skill_custom_time_layout)
        self.skill_layout.addWidget(self.skill_custom_probability)
        self.skill_layout.addWidget(self.skill_custom_checkbox)
        
    def _setup_save(self):
        self.reset_button = QPushButton("Reset")
        self.reset_button.pressed.connect(lambda: self.reset_settings())
        
        self.load_id_edit = QLineEdit()
        self.load_id_edit.setPlaceholderText("Input custom card ID")
        self.load_id_edit.setValidator(QIntValidator(1, 99999, None))
        
        self.load_button = QPushButton("Load")
        self.load_button.pressed.connect(lambda: self.load_card())
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.pressed.connect(lambda: self.delete_card())
        
        self.save_button = QPushButton("Save")
        self.save_button.pressed.connect(lambda: self.save_card())
        
        self.create_button = QPushButton("Create")
        self.create_button.pressed.connect(lambda: self.create_card())
        
        self.save_layout.addWidget(self.reset_button)
        self.save_layout.addWidget(self.load_id_edit)
        self.save_layout.addWidget(self.load_button)
        self.save_layout.addWidget(self.delete_button)
        self.save_layout.addWidget(self.save_button)
        self.save_layout.addWidget(self.create_button)
        
    def update_image(self):
        frame_list = ["myssrcu", "myssrco", "myssrpa", "mysr", "myr", "myncu", "mynco", "mynpa"]
        attr_list = ["mycu", "myco", "mypa"]
        
        image_id = self.card_image_id_edit.text()
        if image_id == "" or int(image_id) < 100000:
            return
        attribute = int(image_id[0])
        if attribute not in [1, 2, 3] or not os.path.exists(str(IMAGE_PATH / (image_id + ".png"))):
            return
        rarity = self.rarity_box.currentIndex()
        frame_index = [0, 3, 4, 5][rarity // 2]
        if frame_index in [0, 5]:
            frame_index += attribute - 1
        
        image = QImage(str(IMAGE_PATH / (image_id + ".png")))
        frame = QImage(str(MY_IMAGE_PATH / (frame_list[frame_index] + ".png")))
        my = QImage(str(MY_IMAGE_PATH / "my1.png"))
        attr_icon = QImage(str(MY_IMAGE_PATH / (attr_list[attribute-1] + ".png")))
        
        self.card_painter.setPen(QPen(Qt.white, 1, Qt.SolidLine))
        self.card_painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        self.card_painter.drawRect(0, 0, 123, 123)
        self.card_painter.drawImage(QPoint(0, 0), image)
        self.card_painter.drawImage(QPoint(0, 0), frame)
        self.card_painter.drawImage(QPoint(82, 2), my)
        self.card_painter.drawImage(QPoint(2, 99), attr_icon)
        self.card_image.repaint()
    
    def change_appeal_mode(self):
        txt = [self.vocal_text, self.dance_text, self.visual_text, self.life_text]
        sb = [self.vocal_spinbox, self.dance_spinbox, self.visual_spinbox, self.life_spinbox]
        
        if self.appeal_checkbox.isChecked():
            for _ in txt: _.setDisabled(True)
            for _ in sb: _.setDisabled(False)
            self.update_appeal()
        
        else:
            for _ in txt: _.setDisabled(False)
            for _ in sb: _.setDisabled(True)
    
    def update_appeal(self):
        if not self.appeal_checkbox.isChecked():
            return
        
        rarity = self.rarity_box.currentIndex()        
        vocal_point = self.vocal_spinbox.value()
        dance_point = self.dance_spinbox.value()
        visual_point = self.visual_spinbox.value()
        life_point = self.life_spinbox.value()
        
        self.vocal_text.setText(str(self._calculate_appeal_life(rarity, vocal_point, True)))
        self.dance_text.setText(str(self._calculate_appeal_life(rarity, dance_point, True)))
        self.visual_text.setText(str(self._calculate_appeal_life(rarity, visual_point, True)))
        self.life_text.setText(str(self._calculate_appeal_life(rarity, life_point, False)))
    
    def _calculate_appeal_life(self, rarity, point, isAppeal):
        appeal_base = 1600
        appeal_rarity = 200
        appeal_point = [200, 115]
        appeal_point_threshold = 10
        life_base = [21, 22, 27, 29, 37, 39, 42, 44]
        life_point = [4, 2]
        life_point_threshold = 10
        
        if isAppeal:
            value = appeal_base + appeal_rarity * (7 - rarity)
            if point < appeal_point_threshold + 1:
                value += appeal_point[0] * point
            else:
                value += appeal_point[0] * appeal_point_threshold + appeal_point[1] * (point - appeal_point_threshold)
            return value
            
        else:
            value = life_base[7 - rarity]
            if point < life_point_threshold + 1:
                value += life_point[0] * point
            else:
                value += life_point[0] * life_point_threshold + life_point[1] * (point - life_point_threshold)
            return value
    
    def update_leader(self):
        self.leader_type.clear()
        self.leader_type.addItems(self.leader_name_list[self.leader_grade.currentIndex()])
    
    def change_skill_mode(self):
        if self.skill_custom_checkbox.isChecked():
            self.skill_detail.setDisabled(True)
            self.skill_custom_interval.setDisabled(False)
            self.skill_custom_duration.setDisabled(False)
            self.skill_custom_probability.setDisabled(False)
            self.skill_detail.clear()
            self.skill_detail.addItem("-")
    
        else:
            self.skill_detail.setDisabled(False)
            self.skill_custom_interval.setDisabled(True)
            self.skill_custom_duration.setDisabled(True)
            self.skill_custom_probability.setDisabled(True)
            self.update_skill_detail()
            self._sync_custom()
    
    def update_skill(self):
        self.skill_kind.clear()
        self.skill_kind.addItems(self.skill_name_list[self.skill_grade.currentIndex()])
        self.update_skill_detail()
    
    def update_skill_detail(self):
        self.skill_detail.clear()
        
        if self.skill_kind.currentIndex() > 0:
            grade = self.skill_grade.currentIndex()
            skill_text = ["Low", "Middle", "High"]
            self.skill_detail.addItems(["{} seconds, {} probability".format(i[1], skill_text[i[3]-2]) for i in self.skill_value_list[grade]
                                    if len(i) > 0 and i[0] == self.skill_list[grade][self.skill_kind.currentIndex()]])
        
        else:
            self.skill_detail.addItem("-")
    
    def reset_settings(self):
        self.id = 0
        
        self.rarity_box.setCurrentIndex(0)
        
        self.card_painter.setPen(QPen(Qt.white, 1, Qt.SolidLine))
        self.card_painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        self.card_painter.drawRect(0, 0, 123, 123)
        self.card_painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
        self.card_painter.drawRoundedRect(0, 0, 123, 123, 10, 10)
        self.card_image.repaint()
        
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
        
        self.leader_grade.setCurrentIndex(0)
        self.leader_type.setCurrentIndex(0)
        
        self.skill_grade.setCurrentIndex(0)
        self.skill_kind.setCurrentIndex(0)
        self.skill_detail.setCurrentIndex(0)
        self.skill_custom_checkbox.setChecked(False)
        self.skill_custom_interval.setCurrentIndex(0)
        self.skill_custom_duration.setCurrentIndex(0)
        self.skill_custom_probability.setCurrentIndex(0)
        
    def _handle_skill_selection(self):
        if self.skill_kind.currentIndex() > 0:
            self.skill_custom_checkbox.setDisabled(False)
            self.skill_custom_interval.clear()
            self.skill_custom_duration.clear()
            self.skill_custom_probability.clear()
            self.skill_custom_interval.addItems(["{} sec.".format(_) for _ in INTERVAL_LIST])
            self.skill_custom_duration.addItems(["{} ({} sec.)".format(_[1], _[0]) for _ in DURATION_LIST])
            self.skill_custom_probability.addItems(PROBABILITY_LIST)
            self.change_skill_mode()
            
        else:
            self.skill_custom_checkbox.setDisabled(True)
            self.skill_detail.setDisabled(True)
            self.skill_custom_interval.setDisabled(True)
            self.skill_custom_duration.setDisabled(True)
            self.skill_custom_probability.setDisabled(True)
            self.skill_custom_interval.clear()
            self.skill_custom_duration.clear()
            self.skill_custom_probability.clear()
            self.skill_custom_interval.addItem("-")
            self.skill_custom_duration.addItem("-")
            self.skill_custom_probability.addItem("-")
        
    def _sync_custom(self):
        if self.skill_kind.currentIndex() > 0:
            if not self.skill_custom_checkbox.isChecked():
                grade = self.skill_grade.currentIndex()
                _ = [(i[1], i[2], i[3]) for i in self.skill_value_list[grade] 
                     if len(i) > 0 and i[0] == self.skill_list[grade][self.skill_kind.currentIndex()]][self.skill_detail.currentIndex()]
                self.skill_custom_interval.setCurrentIndex(INTERVAL_LIST.index(_[0]))
                self.skill_custom_duration.setCurrentIndex(_[1] - 1)
                self.skill_custom_probability.setCurrentIndex(4 - _[2])
    
    def get_card_attr(self):
        rarity = 8 - self.rarity_box.currentIndex()
        image_id = self.card_image_id_edit.text()
        vocal = self.vocal_text.text()
        dance = self.dance_text.text()
        visual = self.visual_text.text()
        life = self.life_text.text()
        leader_skill_id = self.leader_list[self.leader_grade.currentIndex()][self.leader_type.currentIndex()]
        skill_type = self.skill_list[self.skill_grade.currentIndex()][self.skill_kind.currentIndex()]
        condition = INTERVAL_LIST[self.skill_custom_interval.currentIndex()] if skill_type != 0 else 0
        available_time_type = self.skill_custom_duration.currentIndex() + 1
        probability_type = 0 if skill_type == 0 else 4 - self.skill_custom_probability.currentIndex()
        if self.skill_kind.currentIndex() > 0:
            _ = [i for i in self.skill_value_list[self.skill_grade.currentIndex()] if i[0] == skill_type][0][4:]
        else:
            _ = (0, 0, 0)
        value = _[0]
        value_2 = _[1]
        value_3 = _[2]
        
        return [rarity, image_id, vocal, dance, visual, life, leader_skill_id,
             skill_type, condition, available_time_type, probability_type,
             value, value_2, value_3]
    
    def create_card(self):
        if not self._is_setting_valid():
            return
        query = """
                INSERT INTO custom_card (
                    "rarity", "image_id", "vocal", "dance", "visual", "life",
                    "leader_skill_id", "skill_type", "condition", "available_time_type", "probability_type",
                    "value", "value_2", "value_3")
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """
        _ = self.get_card_attr()
        
        db.cachedb.execute(query, _)
        db.cachedb.commit()
        
        custom_id = db.cachedb.execute_and_fetchone("SELECT last_insert_rowid()")[0]
        
        p = "{}".format("5" + str(custom_id).zfill(5))
        path = IMAGE_PATH / (p + ".png")
        path32 = IMAGE_PATH32 / (p + ".jpg")
        path64 = IMAGE_PATH64 / (p + ".jpg")
        storage.exists(path)
        self.card_image.pixmap().save(str(path))
        img = Image.open(str(path)).convert('RGB')
        img.resize((32, 32), Image.ANTIALIAS).save(str(path32), format='JPEG')
        img.resize((64, 64), Image.ANTIALIAS).save(str(path64), format='JPEG')
        
        self.list_widget.load_custom_cards()
    
    def save_card(self):
        if self.load_id_edit.text() == "":
            return
        
        if not self._is_setting_valid():
            return
        custom_id = self.load_id_edit.text()
        
        query = """
                UPDATE custom_card
                SET rarity = ?, image_id = ?, vocal = ?, dance = ?, visual = ?, life = ?,
                    leader_skill_id = ?, skill_type = ?, condition = ?, available_time_type = ?, probability_type = ?,
                    value = ?, value_2 = ?, value_3 = ?
                WHERE id = {}
                """.format(custom_id)
        _ = self.get_card_attr()
        
        db.cachedb.execute(query, _)
        db.cachedb.commit()
        
        p = "{}".format("5" + str(custom_id).zfill(5))
        path = IMAGE_PATH / (p + ".png")
        path32 = IMAGE_PATH32 / (p + ".jpg")
        path64 = IMAGE_PATH64 / (p + ".jpg")
        storage.exists(path)
        self.card_image.pixmap().save(str(path))
        img = Image.open(str(path)).convert('RGB')
        img.resize((32, 32), Image.ANTIALIAS).save(str(path32), format='JPEG')
        img.resize((64, 64), Image.ANTIALIAS).save(str(path64), format='JPEG')
        
        self.list_widget.load_custom_cards()
    
    def load_card(self):
        if self.load_id_edit.text() == "":
            return
        custom_id = int(self.load_id_edit.text())
        
        data = db.cachedb.execute_and_fetchone("""
                                                SELECT
                                                    id,
                                                    rarity,    
                                                    image_id,
                                                    vocal,
                                                    dance,
                                                    visual,
                                                    life,
                                                    leader_skill_id,
                                                    skill_type,
                                                    condition,
                                                    available_time_type,
                                                    probability_type
                                                FROM custom_card
                                                WHERE id = ?
                                                """, [custom_id])
        if data is not None:
            self.id = data[0]
            
            self.rarity_box.setCurrentIndex(8 - data[1])
            
            self.card_image_id_edit.setText(str(data[2]))
            self.update_image()
            
            self.vocal_text.setText(str(data[3]))
            self.dance_text.setText(str(data[4]))
            self.visual_text.setText(str(data[5]))
            self.life_text.setText(str(data[6]))
            
            self.vocal_spinbox.setValue(0)
            self.dance_spinbox.setValue(0)
            self.visual_spinbox.setValue(0)
            self.life_spinbox.setValue(0)
            
            self.appeal_checkbox.setChecked(False)
            
            _ = self._find_index_from_id(self.leader_list, data[7])
            self.leader_grade.setCurrentIndex(_[0])
            self.update_leader()
            self.leader_type.setCurrentIndex(_[1])
            
            _ = self._find_index_from_id(self.skill_list, data[8])
            self.skill_grade.setCurrentIndex(_[0])
            self.update_skill()
            self.skill_kind.setCurrentIndex(_[1])
            self.skill_detail.setCurrentIndex(0)
            if data[8] != 0:
                self.skill_custom_checkbox.setChecked(True)
                self.skill_custom_interval.setCurrentIndex(INTERVAL_LIST.index(data[9]))
                self.skill_custom_duration.setCurrentIndex(data[10] - 1)
                self.skill_custom_probability.setCurrentIndex(4 - data[11])
            else:
                self.skill_custom_checkbox.setChecked(False)
                self.skill_custom_interval.setCurrentIndex(0)
                self.skill_custom_duration.setCurrentIndex(0)
                self.skill_custom_probability.setCurrentIndex(0)
    
    def delete_card(self):
        if self.load_id_edit.text() == "":
            return
        
        custom_id = int(self.load_id_edit.text())
        card_id = int("5" + str(custom_id).zfill(5))
        
        self.unit_view.remove_deleted_custom_card(card_id)
        self.calculator_view.views[0].remove_unit_with_deleted_custom_card(card_id)
        self.calculator_view.views[1].remove_unit_with_deleted_custom_card(card_id)
        
        db.cachedb.execute("DELETE from custom_card WHERE id = ?", [custom_id])
        db.cachedb.commit()
        
        self.list_widget.load_custom_cards()
    
    def _find_index_from_id(self, skill_list, skill_id):
        for r_idx, l in enumerate(skill_list):
            for s_idx, s in enumerate(l):
                if s == skill_id:
                    return (r_idx, s_idx)
    
    def _is_setting_valid(self):
        image_id = self.card_image_id_edit.text()
        if db.cachedb.execute_and_fetchone("SELECT 1 FROM card_data_cache WHERE id = ?", [image_id]) is None:
            return False
        
        vocal = self.vocal_text.text()
        dance = self.dance_text.text()
        visual = self.visual_text.text()
        life = self.life_text.text()
        if vocal == "" or dance == "" or visual == "" or life == "":
            return False
        
        skill_type = self.skill_list[self.skill_grade.currentIndex()][self.skill_kind.currentIndex()]
        if skill_type != 0:
            condition = INTERVAL_LIST[self.skill_custom_interval.currentIndex()]
            available_time_type = DURATION_LIST[self.skill_custom_duration.currentIndex()][0]
            if condition < available_time_type:
                return False
            
        return True


class CustomListWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super(CustomListWidget, self).__init__(*args, **kwargs)

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
    
    def load_custom_cards(self):
        DATA_COLS = ["ID", "Name", "Rarity", "Color", "Skill", "Leader",
                     "Interval", "Prob", "Vocal", "Dance", "Visual", "Life"]
        
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
        
        self.clear()
        self.setColumnCount(len(DATA_COLS))
        self.setRowCount(len(data))
        self.setHorizontalHeaderLabels(DATA_COLS)
        self.horizontalHeader().setSectionResizeMode(4)
        self.horizontalHeader().setSectionResizeMode(1, 1)
        
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
                self.setItem(r_idx, c_idx, item)
        self.sortItems(0, Qt.AscendingOrder)