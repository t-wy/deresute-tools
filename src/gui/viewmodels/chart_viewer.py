import math

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QFont, QFontMetrics
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QStackedWidget, QLineEdit, QHBoxLayout, \
    QRadioButton, QButtonGroup, QSizePolicy, QTreeWidget, QTreeWidgetItem, QCheckBox, QPushButton, QSpinBox

from chart_pic_generator import BaseChartPicGenerator, WINDOW_WIDTH, SCROLL_WIDTH, MAX_LABEL_Y
from db import db
from gui.events.calculator_view_events import CacheSimulationEvent, CustomSimulationEvent, CustomSimulationResultEvent
from gui.events.chart_viewer_events import SendMusicEvent, HookAbuseToChartViewerEvent, HookUnitToChartViewerEvent, \
    ToggleMirrorEvent, HookSimResultToChartViewerEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.value_accessor_events import GetMirrorFlagEvent
from static.judgement import Judgement
from static.skill import SKILL_BASE

class ChartViewer:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.generator = None
        
        self.chart_mode = 0
        self.song_id = 0
        self.difficulty = 0
        self.mirror = False
        
        self.perfect_detail = None
        
        self.custom_offset_cache = {}
        self.custom_group_cache = None
        
        self.widget = QWidget(parent)
        self.widget.layout = QVBoxLayout(self.widget)
        self.info_widget = QWidget()
        self.chart_widget = QScrollArea()
        self.info_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)
        self.chart_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)
        self.widget.layout.addWidget(self.info_widget)
        self.widget.layout.addWidget(self.chart_widget)
        self.setup_info_widget()
        
        label = QLabel()
        canvas = QPixmap(WINDOW_WIDTH, MAX_LABEL_Y)
        label.setPixmap(canvas)
        painter = QPainter(label.pixmap())
        painter.fillRect(0, 0, canvas.width(), canvas.height(), Qt.black)
        label.repaint()
        self.chart_widget.setWidget(label)
        vbar = self.chart_widget.verticalScrollBar()
        vbar.setValue(vbar.maximum())
        
        eventbus.eventbus.register(self)

    @subscribe(SendMusicEvent)
    def hook_music(self, event: SendMusicEvent):
        self.song_id = event.song_id
        self.difficulty = event.difficulty
        self.mirrored = eventbus.eventbus.post_and_get_first(GetMirrorFlagEvent())
        
        self.generator = BaseChartPicGenerator.get_generator(self.song_id, self.difficulty, self, reset_main=False,
                                                             mirrored=self.mirrored)
        
        self.perfect_detail = None
        
        title, difficulty, level, total = self.get_song_info_from_id(self.song_id, self.difficulty)
        self.info_widget.title_line.setText(title)
        self.info_widget.difficulty_line.setText(difficulty)
        self.info_widget.difficulty_line.setCursorPosition(0)
        self.info_widget.level_line.setText(str(level))
        self.info_widget.total_notes_line.setText(str(total))
        
        self.info_widget.mode_default_button.setChecked(True)
        self.info_widget.mode_perfect_button.setCheckable(False)
        self.info_widget.mode_abuse_button.setCheckable(False)
        self.info_widget.mode_custom_button.setCheckable(False)
    
    @subscribe(HookAbuseToChartViewerEvent)
    def hook_abuse(self, event: HookAbuseToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_abuse(event.cards, event.abuse_df)
        self.info_widget.mode_abuse_button.setCheckable(True)
    
    @subscribe(CacheSimulationEvent)
    def cache_simulation_event(self, event: CacheSimulationEvent):
        self.cache_simulation = event.event
    
    @subscribe(HookSimResultToChartViewerEvent)
    def hook_simulation_result(self, event: HookSimResultToChartViewerEvent):
        if self.generator is None:
            return
        
        self.perfect_detail = event.perfect_detail
        self._handle_simulation_result()
        
        self.info_widget.mode_custom_button.setCheckable(True)
    
    @subscribe(CustomSimulationResultEvent)
    def display_custom_simulation_result(self, event: CustomSimulationResultEvent):
        self.info_widget.custom_total_line.setText(str(event.result[0]))
        
        self.perfect_detail = event.result[1]
        self._handle_simulation_result()
        
        idx = self.generator.selected_note
        self._show_detail_note_score_info(idx)
    
    def _handle_simulation_result(self):
        numbers = self.perfect_detail.note_number
        length = len(self.perfect_detail.note_number)
        self.perfect_detail.judgement = [self.perfect_detail.judgement[numbers.index(_ + 1)] for _ in range(length)]
        self.perfect_detail.life = [int(self.perfect_detail.life[numbers.index(_ + 1)]) for _ in range(length)]
        self.perfect_detail.score_bonus_skill = [self.perfect_detail.score_bonus_skill[numbers.index(_ + 1)]
                                                 for _ in range(length)]
        self.perfect_detail.score_great_bonus_skill = [self.perfect_detail.score_great_bonus_skill[numbers.index(_ + 1)]
                                                        for _ in range(length)]
        self.perfect_detail.combo_bonus_skill = [self.perfect_detail.combo_bonus_skill[numbers.index(_ + 1)]
                                                 for _ in range(length)]
        self.perfect_detail.note_score_list = [int(self.perfect_detail.note_score_list[numbers.index(_ + 1)])
                                                 for _ in range(length)]
        total_score = 0
        self.perfect_detail.cumulative_score_list = [total_score := total_score + score
                                                     for score in self.perfect_detail.note_score_list]
        for note in self.perfect_detail.score_bonus_skill:
            note.sort(key = lambda _: _[0])
            for skill in note:
                if skill[3] is not None and len(skill[3]) > 0:
                    skill[3].sort(key = lambda _: _[0])
        for note in self.perfect_detail.combo_bonus_skill:
            note.sort(key = lambda _: _[0])
            for skill in note:
                if skill[3] is not None and len(skill[3]) > 0:
                    skill[3].sort(key = lambda _: _[0])
        self.perfect_detail.score_bonus_list = [round(1 + sum([skill[2] for skill in note]) / 100, 2)
                                                for note in self.perfect_detail.score_bonus_skill]
        self.perfect_detail.combo_bonus_list = [round(1 + sum([skill[2] for skill in note]) / 100, 2)
                                                for note in self.perfect_detail.combo_bonus_skill]
    
    @subscribe(HookUnitToChartViewerEvent)
    def hook_unit(self, event: HookUnitToChartViewerEvent):
        if self.generator is None:
            return
        unit_changed = self.generator.hook_cards(event.cards)
        self.info_widget.mode_perfect_button.setCheckable(True)
        self.perfect_detail = None
        if self.chart_mode == 1 and unit_changed:
            self.generator.draw_perfect_chart()

    @subscribe(ToggleMirrorEvent)
    def toggle_mirror(self, event: ToggleMirrorEvent):
        if self.generator is None:
            return
        self.generator = self.generator.mirror_generator(event.mirrored)

    def set_chart_mode(self):
        mode = self.info_widget.mode_button_group.checkedId()
        if self.chart_mode == mode:
            return
        else:
            self.chart_mode = mode
            if mode == 0:
                self.generator.draw_default_chart()
            elif mode == 1:
                self.generator.draw_perfect_chart()
            elif mode == 2:
                self.generator.draw_perfect_chart()
                self.generator.draw_abuse_chart()
            elif mode == 3:
                self.generator.draw_perfect_chart()
                self.set_stacked_widget_index(self.info_widget.custom_widget, 1)
                self.simulate_custom()
            
            if mode != 3:
                self.set_stacked_widget_index(self.info_widget.custom_widget, 0)
                self.set_stacked_widget_index(self.info_widget.custom_detail_widget, 0)
                
            self.show_detail_nothing()
            self.generator.pixmap_cache = [None] * self.generator.n_label

    def set_stacked_widget_index(self, widget, idx):
        h = self.info_widget.height()
        self._resize_stacked_widget(widget, idx)
        widget.setCurrentIndex(idx)
        delta = self.info_widget.height() - h
        self.chart_widget.verticalScrollBar().setValue(self.chart_widget.verticalScrollBar().value() + delta)

    def _resize_stacked_widget(self, widget, idx):
        for i in range(widget.count()):
            if i == idx:
                widget.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                widget.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def show_detail_nothing(self):
        self.set_stacked_widget_index(self.info_widget.detail_widget, 0)
        
        if self.chart_mode == 3:
            self.set_stacked_widget_index(self.info_widget.custom_detail_widget, 0)
    
    def show_detail_note_info(self, num, time, note_type):
        idx = int(num) - 1
        self.set_stacked_widget_index(self.info_widget.detail_widget, 1)
        self.info_widget.note_number_line.setText(num)
        self.info_widget.note_second_line.setText(time)
        self.info_widget.note_type_line.setText(note_type)
        
        if self.chart_mode in (1, 3) and self.perfect_detail != None:
            self.set_stacked_widget_index(self.info_widget.note_score_info_widget, 1)
            self._show_detail_note_score_info(idx)
        else:
            self.set_stacked_widget_index(self.info_widget.note_score_info_widget, 0)
    
    def _show_detail_note_score_info(self, idx):
        self.info_widget.note_life_line.setText(str(self.perfect_detail.life[idx]))
        self.info_widget.note_combo_line.setText("{} ({})".format(self.perfect_detail.combo[idx], self.perfect_detail.weight[idx]))
        self.info_widget.note_score_bonus_line.setText(str(self.perfect_detail.score_bonus_list[idx]))
        self.info_widget.note_combo_bonus_line.setText(str(self.perfect_detail.combo_bonus_list[idx]))
        self.info_widget.note_note_score_line.setText(str(self.perfect_detail.note_score_list[idx]))
        self.info_widget.note_current_score_line.setText(str(self.perfect_detail.cumulative_score_list[idx]))
        
        self.info_widget.note_score_skill.clear()
        if self.perfect_detail.judgement[idx] == Judgement.PERFECT:
            for skill in self.perfect_detail.score_bonus_skill[idx]:
                item_skill = QTreeWidgetItem(self.info_widget.note_score_skill)
                item_skill.setText(0, "[{}] {} : {}".format(skill[0] + 1, SKILL_BASE[skill[1]]["name"],
                                                         "{}{}%".format("+" if skill[2] >= 0 else "", str(skill[2]))))
                if skill[2] <= 0:
                    continue
                item_skill_child = QTreeWidgetItem(item_skill)
                total_boost = (sum([_[2]  for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
                item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                             "{}{}%".format("+" if skill[2] >= 0 else "", str(math.floor(skill[2] / total_boost)))))
                for boost in skill[3]:
                    item_boost = QTreeWidgetItem(item_skill)
                    item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                                "{}{}%".format("+" if boost[2] >= 0 else "", str(round((boost[2] - 1000) / 10)))))
        elif self.perfect_detail.judgement[idx] == Judgement.GREAT:
            for skill in self.perfect_detail.score_great_bonus_skill[idx]:
                item_skill = QTreeWidgetItem(self.info_widget.note_score_skill)
                item_skill.setText(0, "[{}] {} : {}".format(skill[0] + 1, SKILL_BASE[skill[1]]["name"],
                                                         "{}{}%".format("+" if skill[2] >= 0 else "", str(skill[2]))))
                if skill[2] <= 0:
                    continue
                item_skill_child = QTreeWidgetItem(item_skill)
                total_boost = (sum([_[2]  for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
                item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                             "{}{}%".format("+" if skill[2] >= 0 else "", str(math.floor(skill[2] / total_boost)))))
                for boost in skill[3]:
                    item_boost = QTreeWidgetItem(item_skill)
                    item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                                "{}{}%".format("+" if boost[2] >= 0 else "", str(round((boost[2] - 1000) / 10)))))
        
        self.info_widget.note_combo_skill.clear()
        for skill in self.perfect_detail.combo_bonus_skill[idx]:
            item_skill = QTreeWidgetItem(self.info_widget.note_combo_skill)
            item_skill.setText(0, "[{}] {} : {}".format(skill[0] + 1, SKILL_BASE[skill[1]]["name"],
                                                     "{}{}%".format("+" if skill[2] >= 0 else "", str(skill[2]))))
            if skill[2] <= 0:
                continue
            item_skill_child = QTreeWidgetItem(item_skill)
            total_boost = (sum([_[2] for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
            item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                         "{}{}%".format("+" if skill[2] >= 0 else "", str(math.floor(skill[2] / total_boost)))))
            for boost in skill[3]:
                item_boost = QTreeWidgetItem(item_skill)
                item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                            "{}{}%".format("+" if boost[2] >= 0 else "", str(round((boost[2] - 1000) / 10)))))
    
    def show_detail_skill_info(self, skill_type, time, prob):
        self.set_stacked_widget_index(self.info_widget.detail_widget, 2)
        self.info_widget.skill_type_line.setText(skill_type)
        self.info_widget.skill_time_line.setText(time)
        #self.info_widget.skill_prob_line.setText(prob)

        if self.chart_mode == 3:
            self.set_stacked_widget_index(self.info_widget.custom_detail_widget, 1)
            idx = self.generator.selected_skill[0]
            num = self.generator.selected_skill[1]
            if num in self.generator.skill_inactive_list[idx]:
                self.info_widget.custom_skill_active_line.setText("Not Activated")
            else:
                self.info_widget.custom_skill_active_line.setText("Activated")
    
    def save_chart(self):
        self.generator.save_image()

    def get_song_info_from_id(self, song_id, diff):
        data = db.cachedb.execute_and_fetchone("""
                    SELECT  name,
                            level,
                            CAST(Tap + Long + Flick + Slide AS INTEGER)
                    FROM live_detail_cache WHERE live_id = ? AND difficulty = ?
                """, [song_id, diff])
        diff_text = db.cachedb.execute_and_fetchone("SELECT text FROM difficulty_text WHERE id = ?", [diff])
        return data[0], diff_text[0], data[1], data[2]

    def change_skill_activation(self):
        idx = self.generator.selected_skill[0]
        num = self.generator.selected_skill[1]
        if num in self.generator.skill_inactive_list[idx]:
            self.generator.skill_inactive_list[idx].remove(num)
            self.info_widget.custom_skill_active_line.setText("Activated")
        else:
            self.generator.skill_inactive_list[idx].append(num)
            self.info_widget.custom_skill_active_line.setText("Not Activated")
        self.generator.draw_perfect_chart() #TODO : Optimize by redrawing partially
        self.generator.draw_selected_skill(idx, num)
    
    def update_custom_chart(self):
        self.generator.draw_perfect_chart()
    
    def simulate_custom(self):
        eventbus.eventbus.post(CustomSimulationEvent(self.cache_simulation, self.generator.skill_inactive_list))
    
    def setup_info_widget(self):
        self.info_widget.layout = QVBoxLayout(self.info_widget)
        
        self._setup_song_info()
        self.info_widget.layout.addSpacing(12)
        self._setup_chart_mode()
        
        self.info_widget.detail_widget = QStackedWidget()
        self.info_widget.detail_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.detail_widget.addWidget(QWidget())
        
        self._setup_note_info()
        self._setup_note_score_info()
        
        self._setup_skill_info()
        
        self.info_widget.custom_widget = QStackedWidget()
        self.info_widget.custom_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.custom_widget.addWidget(QWidget())
        
        self._setup_custom()
        
        self.info_widget.layout.addWidget(self.info_widget.custom_widget)
        self.info_widget.layout.addWidget(self.info_widget.detail_widget)
        self.info_widget.layout.setSpacing(0)
        
        self._resize_stacked_widget(self.info_widget.detail_widget, 0)
        self._resize_stacked_widget(self.info_widget.custom_widget, 0)
        self._resize_stacked_widget(self.info_widget.note_score_info_widget, 0)
        self._resize_stacked_widget(self.info_widget.custom_detail_widget, 0)
        
    def _setup_song_info(self):
        self.info_widget.title_layout = QVBoxLayout()
        self.info_widget.title_label = QLabel("Title")
        self.info_widget.title_label.setAlignment(Qt.AlignCenter)
        self.info_widget.title_line = QLineEdit()
        self.info_widget.title_line.setReadOnly(True)
        self.info_widget.title_line.setCursorPosition(0)
        self.info_widget.title_layout.addWidget(self.info_widget.title_label)
        self.info_widget.title_layout.addWidget(self.info_widget.title_line)
        
        self.info_widget.difficulty_layout = QVBoxLayout()
        self.info_widget.difficulty_label = QLabel("Difficulty")
        self.info_widget.difficulty_label.setAlignment(Qt.AlignCenter)
        self.info_widget.difficulty_line = QLineEdit()
        self.info_widget.difficulty_line.setReadOnly(True)
        self.info_widget.difficulty_line.setAlignment(Qt.AlignCenter)
        self.info_widget.difficulty_layout.addWidget(self.info_widget.difficulty_label)
        self.info_widget.difficulty_layout.addWidget(self.info_widget.difficulty_line)
        
        self.info_widget.level_layout = QVBoxLayout()
        self.info_widget.level_label = QLabel("Level")
        self.info_widget.level_label.setAlignment(Qt.AlignCenter)
        self.info_widget.level_line = QLineEdit()
        self.info_widget.level_line.setReadOnly(True)
        self.info_widget.level_line.setAlignment(Qt.AlignCenter)
        self.info_widget.level_layout.addWidget(self.info_widget.level_label)
        self.info_widget.level_layout.addWidget(self.info_widget.level_line)
        
        self.info_widget.save = QPushButton("Save")
        self.info_widget.save.clicked.connect(lambda: self.save_chart())
        
        self.info_widget.total_notes_layout = QVBoxLayout()
        self.info_widget.total_notes_label = QLabel("Notes")
        self.info_widget.total_notes_label.setAlignment(Qt.AlignCenter)
        self.info_widget.total_notes_line = QLineEdit()
        self.info_widget.total_notes_line.setReadOnly(True)
        self.info_widget.total_notes_line.setAlignment(Qt.AlignCenter)
        self.info_widget.total_notes_layout.addWidget(self.info_widget.total_notes_label)
        self.info_widget.total_notes_layout.addWidget(self.info_widget.total_notes_line)
        
        self.info_widget.song_info_layout = QHBoxLayout()
        self.info_widget.song_info_layout.setSpacing(6)
        self.info_widget.song_info_layout.addLayout(self.info_widget.title_layout, 9)
        self.info_widget.song_info_layout.addLayout(self.info_widget.difficulty_layout, 2)
        self.info_widget.song_info_layout.addLayout(self.info_widget.level_layout, 2)
        self.info_widget.song_info_layout.addLayout(self.info_widget.total_notes_layout, 2)
        self.info_widget.song_info_layout.addWidget(self.info_widget.save, 2)
        self.info_widget.layout.addLayout(self.info_widget.song_info_layout)
    
    def _setup_chart_mode(self):
        self.info_widget.mode_button_group = QButtonGroup(self.info_widget)
        
        self.info_widget.mode_label = QLabel('Chart Mode')
        
        self.info_widget.mode_default_button = QRadioButton('Default')
        self.info_widget.mode_default_button.setChecked(True)
        self.info_widget.mode_default_button.toggled.connect(self.set_chart_mode)
        self.info_widget.mode_button_group.addButton(self.info_widget.mode_default_button, 0)
        
        self.info_widget.mode_perfect_button = QRadioButton('Perfect')
        self.info_widget.mode_perfect_button.setCheckable(False)
        self.info_widget.mode_perfect_button.toggled.connect(self.set_chart_mode)
        self.info_widget.mode_button_group.addButton(self.info_widget.mode_perfect_button, 1)
        
        self.info_widget.mode_abuse_button = QRadioButton('Abuse')
        self.info_widget.mode_abuse_button.setCheckable(False)
        self.info_widget.mode_abuse_button.toggled.connect(self.set_chart_mode)
        self.info_widget.mode_button_group.addButton(self.info_widget.mode_abuse_button, 2)
        
        self.info_widget.mode_custom_button = QRadioButton('Custom')
        self.info_widget.mode_custom_button.setCheckable(False)
        self.info_widget.mode_custom_button.toggled.connect(self.set_chart_mode)
        self.info_widget.mode_button_group.addButton(self.info_widget.mode_custom_button, 3)
        
        self.info_widget.mode_button_layout = QHBoxLayout()
        self.info_widget.mode_button_layout.setSpacing(6)
        self.info_widget.mode_button_layout.addStretch(1)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_label, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_default_button, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_perfect_button, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_abuse_button, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_custom_button, 2)
        self.info_widget.layout.addLayout(self.info_widget.mode_button_layout)
    
    def _setup_note_info(self):
        self.info_widget.note_number_layout = QVBoxLayout()
        self.info_widget.note_number_label = QLabel("Note Number")
        self.info_widget.note_number_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_number_line = QLineEdit()
        self.info_widget.note_number_line.setReadOnly(True)
        self.info_widget.note_number_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_number_layout.addWidget(self.info_widget.note_number_label)
        self.info_widget.note_number_layout.addWidget(self.info_widget.note_number_line)
        
        self.info_widget.note_second_layout = QVBoxLayout()
        self.info_widget.note_second_label = QLabel("Note Time")
        self.info_widget.note_second_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_second_line = QLineEdit()
        self.info_widget.note_second_line.setReadOnly(True)
        self.info_widget.note_second_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_second_layout.addWidget(self.info_widget.note_second_label)
        self.info_widget.note_second_layout.addWidget(self.info_widget.note_second_line)
        
        self.info_widget.note_type_layout = QVBoxLayout()
        self.info_widget.note_type_label = QLabel("Note Type")
        self.info_widget.note_type_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_type_line = QLineEdit()
        self.info_widget.note_type_line.setReadOnly(True)
        self.info_widget.note_type_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_type_layout.addWidget(self.info_widget.note_type_label)
        self.info_widget.note_type_layout.addWidget(self.info_widget.note_type_line)
        
        self.info_widget.note_widget = QWidget()
        self.info_widget.note_layout = QVBoxLayout(self.info_widget.note_widget)
        margin = self.info_widget.note_layout.contentsMargins()
        self.info_widget.note_layout.setContentsMargins(0, margin.top(), 0, 0)
        self.info_widget.note_layout.setSpacing(0)
        self.info_widget.note_info_layout = QHBoxLayout()
        self.info_widget.note_info_layout.setSpacing(6)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_number_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_second_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_type_layout)
        self.info_widget.note_layout.addLayout(self.info_widget.note_info_layout)
        
    def _setup_note_score_info(self):
        self.info_widget.note_life_layout = QVBoxLayout()
        self.info_widget.note_life_label = QLabel("Life")
        self.info_widget.note_life_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_life_line = QLineEdit()
        self.info_widget.note_life_line.setReadOnly(True)
        self.info_widget.note_life_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_life_layout.addWidget(self.info_widget.note_life_label)
        self.info_widget.note_life_layout.addWidget(self.info_widget.note_life_line)
        
        self.info_widget.note_combo_layout = QVBoxLayout()
        self.info_widget.note_combo_label = QLabel("Combo")
        self.info_widget.note_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_combo_line = QLineEdit()
        self.info_widget.note_combo_line.setReadOnly(True)
        self.info_widget.note_combo_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_combo_layout.addWidget(self.info_widget.note_combo_label)
        self.info_widget.note_combo_layout.addWidget(self.info_widget.note_combo_line)
        
        self.info_widget.note_score_bonus_layout = QVBoxLayout()
        self.info_widget.note_score_bonus_label = QLabel("Score bonus")
        self.info_widget.note_score_bonus_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_score_bonus_line = QLineEdit()
        self.info_widget.note_score_bonus_line.setReadOnly(True)
        self.info_widget.note_score_bonus_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_score_bonus_layout.addWidget(self.info_widget.note_score_bonus_label)
        self.info_widget.note_score_bonus_layout.addWidget(self.info_widget.note_score_bonus_line)
        
        self.info_widget.note_combo_bonus_layout = QVBoxLayout()
        self.info_widget.note_combo_bonus_label = QLabel("Combo bonus")
        self.info_widget.note_combo_bonus_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_combo_bonus_line = QLineEdit()
        self.info_widget.note_combo_bonus_line.setReadOnly(True)
        self.info_widget.note_combo_bonus_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_combo_bonus_layout.addWidget(self.info_widget.note_combo_bonus_label)
        self.info_widget.note_combo_bonus_layout.addWidget(self.info_widget.note_combo_bonus_line)
        
        self.info_widget.note_note_score_layout = QVBoxLayout()
        self.info_widget.note_note_score_label = QLabel("Note Score")
        self.info_widget.note_note_score_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_note_score_line = QLineEdit()
        self.info_widget.note_note_score_line.setReadOnly(True)
        self.info_widget.note_note_score_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_note_score_layout.addWidget(self.info_widget.note_note_score_label)
        self.info_widget.note_note_score_layout.addWidget(self.info_widget.note_note_score_line)
        
        self.info_widget.note_current_score_layout = QVBoxLayout()
        self.info_widget.note_current_score_label = QLabel("Current Score")
        self.info_widget.note_current_score_label.setAlignment(Qt.AlignCenter)
        self.info_widget.note_current_score_line = QLineEdit()
        self.info_widget.note_current_score_line.setReadOnly(True)
        self.info_widget.note_current_score_line.setAlignment(Qt.AlignCenter)
        self.info_widget.note_current_score_layout.addWidget(self.info_widget.note_current_score_label)
        self.info_widget.note_current_score_layout.addWidget(self.info_widget.note_current_score_line)
        
        self.info_widget.note_score_general_layout = QHBoxLayout()
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_life_layout)
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_combo_layout)
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_score_bonus_layout)
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_combo_bonus_layout)
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_note_score_layout)
        self.info_widget.note_score_general_layout.addLayout(self.info_widget.note_current_score_layout)
        
        self.info_widget.note_score_skill = QTreeWidget()
        self.info_widget.note_score_skill.header().setVisible(False)
        self.info_widget.note_score_skill.setFixedHeight(70)
        self.info_widget.note_combo_skill = QTreeWidget()
        self.info_widget.note_combo_skill.header().setVisible(False)
        self.info_widget.note_combo_skill.setFixedHeight(70)
        
        self.info_widget.note_skills_layout = QHBoxLayout()
        self.info_widget.note_skills_layout.addWidget(self.info_widget.note_score_skill)
        self.info_widget.note_skills_layout.addWidget(self.info_widget.note_combo_skill)
        
        self.info_widget.note_score_widget = QWidget()
        self.info_widget.note_score_layout = QVBoxLayout(self.info_widget.note_score_widget)
        margin = self.info_widget.note_score_layout.contentsMargins()
        self.info_widget.note_score_layout.setContentsMargins(0, margin.top(), 0, 0)
        self.info_widget.note_score_layout.addLayout(self.info_widget.note_score_general_layout)
        self.info_widget.note_score_layout.addLayout(self.info_widget.note_skills_layout)
        
        self.info_widget.note_score_info_widget = QStackedWidget()
        self.info_widget.note_score_info_widget.addWidget(QWidget())
        self.info_widget.note_score_info_widget.addWidget(self.info_widget.note_score_widget)
        self.info_widget.note_score_info_widget.setCurrentIndex(0)
        
        self.info_widget.note_layout.addWidget(self.info_widget.note_score_info_widget)
        self.info_widget.detail_widget.addWidget(self.info_widget.note_widget)

    def _setup_skill_info(self):
        self.info_widget.skill_type_layout = QVBoxLayout()
        self.info_widget.skill_type_label = QLabel("Skill Type")
        self.info_widget.skill_type_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_type_line = QLineEdit()
        self.info_widget.skill_type_line.setReadOnly(True)
        self.info_widget.skill_type_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_type_layout.addWidget(self.info_widget.skill_type_label)
        self.info_widget.skill_type_layout.addWidget(self.info_widget.skill_type_line)
        
        self.info_widget.skill_time_layout = QVBoxLayout()
        self.info_widget.skill_time_label = QLabel("Skill Time")
        self.info_widget.skill_time_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_time_line = QLineEdit()
        self.info_widget.skill_time_line.setReadOnly(True)
        self.info_widget.skill_time_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_time_layout.addWidget(self.info_widget.skill_time_label)
        self.info_widget.skill_time_layout.addWidget(self.info_widget.skill_time_line)
        
        '''
        self.info_widget.skill_prob_layout = QVBoxLayout()
        self.info_widget.skill_prob_label = QLabel("Probability")
        self.info_widget.skill_prob_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_line = QLineEdit()
        self.info_widget.skill_prob_line.setReadOnly(True)
        self.info_widget.skill_prob_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_label)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_line)
        
        self.info_widget.skill_detail_widget = QStackedWidget()
        self.info_widget.skill_detail_widget.addWidget(QWidget())
        self._setup_skill_detail_widget()
        '''
        
        self.info_widget.skill_widget = QWidget()
        self.info_widget.skill_layout = QVBoxLayout(self.info_widget.skill_widget)
        margin = self.info_widget.skill_layout.contentsMargins()
        self.info_widget.skill_layout.setContentsMargins(0, margin.top(), 0, 0)
        self.info_widget.skill_info_layout = QHBoxLayout()
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_type_layout)
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_time_layout)
        #self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_prob_layout)
        self.info_widget.skill_layout.addLayout(self.info_widget.skill_info_layout)
        self.info_widget.detail_widget.addWidget(self.info_widget.skill_widget)

    def _setup_custom(self):
        self.info_widget.custom_total_layout = QVBoxLayout()
        self.info_widget.custom_total_label = QLabel("Total Score")
        self.info_widget.custom_total_label.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_total_line = QLineEdit()
        self.info_widget.custom_total_line.setReadOnly(True)
        self.info_widget.custom_total_line.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_total_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.info_widget.custom_total_layout.addWidget(self.info_widget.custom_total_label)
        self.info_widget.custom_total_layout.addWidget(self.info_widget.custom_total_line)
        
        self.info_widget.custom_button_layout = QVBoxLayout()
        self.info_widget.custom_update_button = QPushButton("Update")
        self.info_widget.custom_update_button.clicked.connect(lambda: self.simulate_custom())
        self.info_widget.custom_reset_button = QPushButton("Reset All")
        self.info_widget.custom_reset_button.setDisabled(True)
        self.info_widget.custom_button_layout.addWidget(self.info_widget.custom_update_button)
        self.info_widget.custom_button_layout.addWidget(self.info_widget.custom_reset_button)
        
        self.info_widget.custom_general_layout = QHBoxLayout()
        self.info_widget.custom_general_layout.setSpacing(6)
        self.info_widget.custom_general_layout.addLayout(self.info_widget.custom_total_layout)
        self.info_widget.custom_general_layout.addLayout(self.info_widget.custom_button_layout)
        
        self.info_widget.custom_skill_widget = QWidget()
        self.info_widget.custom_skill_layout = QHBoxLayout(self.info_widget.custom_skill_widget)
        margin = self.info_widget.custom_skill_layout.contentsMargins()
        self.info_widget.custom_skill_layout.setContentsMargins(0, margin.top(), 0, 0)
        self.info_widget.custom_skill_layout.setSpacing(6)
        self.info_widget.custom_skill_active_line = QLineEdit()
        self.info_widget.custom_skill_active_line.setReadOnly(True)
        self.info_widget.custom_skill_active_line.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_skill_active_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.info_widget.custom_skill_active_button = QPushButton("Change Activation")
        self.info_widget.custom_skill_active_button.clicked.connect(lambda: self.change_skill_activation())
        self.info_widget.custom_skill_layout.addWidget(self.info_widget.custom_skill_active_line)
        self.info_widget.custom_skill_layout.addWidget(self.info_widget.custom_skill_active_button)
        
        self.info_widget.custom_detail_widget = QStackedWidget()
        self.info_widget.custom_detail_widget.addWidget(QWidget())
        self.info_widget.custom_detail_widget.addWidget(self.info_widget.custom_skill_widget)
        
        self.info_widget.custom_setting_widget = QWidget()
        self.info_widget.custom_setting_layout = QVBoxLayout(self.info_widget.custom_setting_widget)
        margin = self.info_widget.custom_setting_layout.contentsMargins()
        self.info_widget.custom_setting_layout.setContentsMargins(0, margin.top(), 0, 0)
        self.info_widget.custom_setting_layout.setSpacing(0)
        self.info_widget.custom_setting_layout.addLayout(self.info_widget.custom_general_layout)
        self.info_widget.custom_setting_layout.addWidget(self.info_widget.custom_detail_widget)
        
        self.info_widget.custom_widget.addWidget(self.info_widget.custom_setting_widget)
        self.info_widget.custom_widget.setCurrentIndex(0)
