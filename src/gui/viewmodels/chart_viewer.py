from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QStackedWidget, QLineEdit, QHBoxLayout, \
    QRadioButton, QButtonGroup, QSizePolicy

from chart_pic_generator import BaseChartPicGenerator, WINDOW_WIDTH, SCROLL_WIDTH, MAX_LABEL_Y
from db import db
from gui.events.chart_viewer_events import SendMusicEvent, HookAbuseToChartViewerEvent, HookUnitToChartViewerEvent, \
    ToggleMirrorEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.value_accessor_events import GetMirrorFlagEvent

class ChartViewer:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.generator = None
        
        self.chart_mode = 0
        self.song_id = 0
        self.difficulty = 0
        self.mirror = False
        
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
        
        title, difficulty, level, total = self.get_song_info_from_id(self.song_id, self.difficulty)
        self.info_widget.title_line.setText(title)
        self.info_widget.difficulty_line.setText(difficulty)
        self.info_widget.difficulty_line.setCursorPosition(0)
        self.info_widget.level_line.setText(str(level))
        self.info_widget.total_notes_line.setText(str(total))
        
        self.info_widget.mode_default_button.setChecked(True)
        self.info_widget.mode_perfect_button.setCheckable(False)
        self.info_widget.mode_abuse_button.setCheckable(False)
    
    #TODO: Handle unit and chart desync from using 'lock chart'
    
    @subscribe(HookAbuseToChartViewerEvent)
    def hook_abuse(self, event: HookAbuseToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_abuse(event.cards, event.abuse_df)
        self.info_widget.mode_abuse_button.setCheckable(True)

    @subscribe(HookUnitToChartViewerEvent)
    def hook_unit(self, event: HookUnitToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_cards(event.cards)
        self.info_widget.mode_perfect_button.setCheckable(True)

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
            self.show_detail_nothing()
            self.generator.pixmap_cache = [None] * self.generator.n_label

    def set_detail_widget_index(self, idx):
        h = self.info_widget.height()
        self._resize_detail_widget(idx)
        self.info_widget.detail_widget.setCurrentIndex(idx)
        delta = self.info_widget.height() - h
        self.chart_widget.verticalScrollBar().setValue(self.chart_widget.verticalScrollBar().value() + delta)

    def _resize_detail_widget(self, idx):
        for i in range(self.info_widget.detail_widget.count()):
            if i == idx:
                self.info_widget.detail_widget.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                self.info_widget.detail_widget.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def show_detail_nothing(self):
        self.set_detail_widget_index(0)
    
    def show_detail_note_info(self, num, time, note_type):
        self.set_detail_widget_index(1)
        self.info_widget.note_number_line.setText(num)
        self.info_widget.note_second_line.setText(time)
        self.info_widget.note_type_line.setText(note_type)
    
    def show_detail_skill_info(self, skill_type, time, prob):
        self.set_detail_widget_index(2)
        self.info_widget.skill_type_line.setText(skill_type)
        self.info_widget.skill_time_line.setText(time)
        self.info_widget.skill_prob_line.setText(prob)
    
    '''
    def keyPressEvent(self, event):
        key = event.key()
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_S:
            self.generator.save_image()
    '''
    
    def get_song_info_from_id(self, song_id, diff):
        data = db.cachedb.execute_and_fetchone("""
                    SELECT  name,
                            level,
                            CAST(Tap + Long + Flick + Slide AS INTEGER)
                    FROM live_detail_cache WHERE live_id = ? AND difficulty = ?
                """, [song_id, diff])
        diff_text = db.cachedb.execute_and_fetchone("SELECT text FROM difficulty_text WHERE id = ?", [diff])
        return data[0], diff_text[0], data[1], data[2]

    def setup_info_widget(self):
        self.info_widget.layout = QVBoxLayout(self.info_widget)
        
        self._setup_song_info()
        self.info_widget.layout.addSpacing(12)
        self._setup_chart_mode()
        
        self.info_widget.detail_widget = QStackedWidget()
        self.info_widget.detail_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.detail_widget.addWidget(QWidget())
        
        self._setup_note_info()
        
        self._setup_skill_info()
        
        self._resize_detail_widget(0)
        
        self.info_widget.layout.addWidget(self.info_widget.detail_widget)
    
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
        
        self.info_widget.total_notes_layout = QVBoxLayout()
        self.info_widget.total_notes_label = QLabel("Notes")
        self.info_widget.total_notes_label.setAlignment(Qt.AlignCenter)
        self.info_widget.total_notes_line = QLineEdit()
        self.info_widget.total_notes_line.setReadOnly(True)
        self.info_widget.total_notes_line.setAlignment(Qt.AlignCenter)
        self.info_widget.total_notes_layout.addWidget(self.info_widget.total_notes_label)
        self.info_widget.total_notes_layout.addWidget(self.info_widget.total_notes_line)
        
        self.info_widget.song_info_layout = QHBoxLayout()
        self.info_widget.song_info_layout.addLayout(self.info_widget.title_layout, 9)
        self.info_widget.song_info_layout.addLayout(self.info_widget.difficulty_layout, 2)
        self.info_widget.song_info_layout.addLayout(self.info_widget.level_layout, 2)
        self.info_widget.song_info_layout.addLayout(self.info_widget.total_notes_layout, 2)
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
        
        self.info_widget.mode_button_layout = QHBoxLayout()
        self.info_widget.mode_button_layout.addStretch(1)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_label, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_default_button, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_perfect_button, 2)
        self.info_widget.mode_button_layout.addWidget(self.info_widget.mode_abuse_button, 2)
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
        self.info_widget.note_info_layout = QHBoxLayout()
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_number_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_second_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_type_layout)
        self.info_widget.note_layout.addLayout(self.info_widget.note_info_layout)
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
        
        self.info_widget.skill_prob_layout = QVBoxLayout()
        self.info_widget.skill_prob_label = QLabel("Probability")
        self.info_widget.skill_prob_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_line = QLineEdit()
        self.info_widget.skill_prob_line.setReadOnly(True)
        self.info_widget.skill_prob_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_label)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_line)
        
        self.info_widget.skill_widget = QWidget()
        self.info_widget.skill_layout = QVBoxLayout(self.info_widget.skill_widget)
        self.info_widget.skill_info_layout = QHBoxLayout()
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_type_layout)
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_time_layout)
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_prob_layout)
        self.info_widget.skill_layout.addLayout(self.info_widget.skill_info_layout)
        self.info_widget.detail_widget.addWidget(self.info_widget.skill_widget)
