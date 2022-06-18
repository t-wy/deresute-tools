import math

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QFont, QFontMetrics, QIntValidator
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QStackedWidget, QLineEdit, QHBoxLayout, QGridLayout, \
    QRadioButton, QButtonGroup, QSizePolicy, QTreeWidget, QTreeWidgetItem, QCheckBox, QPushButton, QSpinBox, QTextEdit, \
    QSpacerItem, QCheckBox

from chart_pic_generator import BaseChartPicGenerator, WINDOW_WIDTH, SCROLL_WIDTH, MAX_LABEL_Y
from db import db
from gui.events.calculator_view_events import CacheSimulationEvent, CustomSimulationEvent, CustomSimulationResultEvent
from gui.events.chart_viewer_events import SendMusicEvent, HookAbuseToChartViewerEvent, HookUnitToChartViewerEvent, \
    ToggleMirrorEvent, HookSimResultToChartViewerEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.value_accessor_events import GetMirrorFlagEvent
from static.judgement import Judgement
from static.skill import SKILL_BASE, SKILL_INACTIVATION_REASON, get_skill_description

class ChartViewer:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.generator = None
        
        self.chart_mode = 0
        self.song_id = 0
        self.difficulty = 0
        self.mirror = False
        
        self.cards = None
        self.skill_probability = None
        self.perfect_detail = None
        
        self.custom_offset_cache = {}
        self.custom_group_cache = None
        self.custom_abuse = -1
        
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
        self.info_widget.custom_abuse_button.setDisabled(True)
        self.custom_abuse = -1
    
    @subscribe(HookAbuseToChartViewerEvent)
    def hook_abuse(self, event: HookAbuseToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_abuse(event.cards, event.abuse_df)
        self.info_widget.mode_abuse_button.setCheckable(True)
        
        self.info_widget.custom_abuse_button.setDisabled(False)
        self.custom_abuse = 0
    
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
        self.info_widget.custom_theoretic_line.setText(str(int(event.result[2])))
        self.info_widget.custom_skill_prob_line.setText("{:.2%}".format(event.result[4]))
        
        self.perfect_detail = event.result[1]
        self._handle_simulation_result()
        
        idx = self.generator.selected_note
        self._show_detail_note_score_info(idx)
        
        self.generator.hook_abuse(self.cards, event.result[3])
        
        self.generator.draw_perfect_chart()
        if self.custom_abuse == 1:
            self.generator.draw_abuse_chart()
    
    def _handle_simulation_result(self):
        numbers = self.perfect_detail.note_number
        length = len(self.perfect_detail.note_number)
        self.skill_probability = self.perfect_detail.skill_probability
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
        self.cards = event.cards
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
        if idx == 0:
            widget.hide()
        else:
            widget.show()
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
        self.set_stacked_widget_index(self.info_widget.detail_widget, 1)
        self.info_widget.note_number_line.setText(num)
        self.info_widget.note_second_line.setText(time)
        self.info_widget.note_type_line.setText(note_type)
        
        if self.chart_mode in (1, 3) and note_type != "DAMAGE" and self.perfect_detail != None:
            self.set_stacked_widget_index(self.info_widget.note_score_info_widget, 1)
            idx = int(num) - 1
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
                                                         "{:+}%".format(skill[2])))
                if skill[2] <= 0:
                    continue
                item_skill_child = QTreeWidgetItem(item_skill)
                total_boost = (sum([_[2]  for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
                item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                             "{:+}%".format(math.floor(skill[2] / total_boost))))
                for boost in skill[3]:
                    item_boost = QTreeWidgetItem(item_skill)
                    item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                                "{:+}%".format(round((boost[2] - 1000) / 10))))
        elif self.perfect_detail.judgement[idx] == Judgement.GREAT:
            for skill in self.perfect_detail.score_great_bonus_skill[idx]:
                item_skill = QTreeWidgetItem(self.info_widget.note_score_skill)
                item_skill.setText(0, "[{}] {} : {}".format(skill[0] + 1, SKILL_BASE[skill[1]]["name"],
                                                         "{:+}%".format(skill[2])))
                if skill[2] <= 0:
                    continue
                item_skill_child = QTreeWidgetItem(item_skill)
                total_boost = (sum([_[2]  for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
                item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                             "{:+}%".format(math.floor(skill[2] / total_boost))))
                for boost in skill[3]:
                    item_boost = QTreeWidgetItem(item_skill)
                    item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                                "{:+}%".format(round((boost[2] - 1000) / 10))))
        
        self.info_widget.note_combo_skill.clear()
        for skill in self.perfect_detail.combo_bonus_skill[idx]:
            item_skill = QTreeWidgetItem(self.info_widget.note_combo_skill)
            item_skill.setText(0, "[{}] {} : {}".format(skill[0] + 1, SKILL_BASE[skill[1]]["name"],
                                                     "{:+}%".format(skill[2])))
            if skill[2] <= 0:
                continue
            item_skill_child = QTreeWidgetItem(item_skill)
            total_boost = (sum([_[2] for _ in skill[3]]) - 1000 * (len(skill[3]) - 1)) / 1000
            item_skill_child.setText(0, "{} : {}".format(SKILL_BASE[skill[1]]["name"],
                                                         "{:+}%".format(math.floor(skill[2] / total_boost))))
            for boost in skill[3]:
                item_boost = QTreeWidgetItem(item_skill)
                item_boost.setText(0, "[{}] {} : ({})".format(boost[0] + 1, SKILL_BASE[boost[1]]["name"],
                                                            "{:+}%".format(round((boost[2] - 1000) / 10))))
    
    def show_detail_skill_info(self, skill_type, time):
        card_idx, idx = self.generator.selected_skill
        self.set_stacked_widget_index(self.info_widget.detail_widget, 2)
        self.info_widget.skill_type_line.setText(SKILL_BASE[skill_type]['name'])
        self.info_widget.skill_time_line.setText(time)
        self.info_widget.skill_prob_line.setText("{:.2%}".format(self.skill_probability[card_idx]))
        card_id = (self.cards[card_idx].card_id + 1) // 2 * 2 - 1
        if str(card_id)[0] == "5":
            self.info_widget.skill_description_line.setText("")
        else:
            self.info_widget.skill_description_line.setText(get_skill_description(card_id))
        
        if self.perfect_detail == None:
            return
        
        if card_idx in self.perfect_detail.skill_inactivation_reason and \
            idx in self.perfect_detail.skill_inactivation_reason[card_idx]:
            self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 0)
            self.set_stacked_widget_index(self.info_widget.skill_inactivation_widget, 1)
            self.info_widget.skill_prob_line.setText("-")
            self.info_widget.skill_inactivation_detail_line.setText(
                SKILL_INACTIVATION_REASON[self.perfect_detail.skill_inactivation_reason[card_idx][idx]])
        else:
            self.set_stacked_widget_index(self.info_widget.skill_inactivation_widget, 0)
            
            if skill_type == 16: #encore
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 1)
                if card_idx in self.perfect_detail.encore_skill and idx in self.perfect_detail.encore_skill[card_idx]:
                    encore_skill = self.perfect_detail.encore_skill[card_idx][idx]
                    self.info_widget.skill_detail_encore_line.setText("[{}] {}".format(encore_skill[0] + 1,
                                                                                       SKILL_BASE[encore_skill[1]]["name"]))
                    self.info_widget.skill_detail_encore_line_.setText("{:.1f}".format(encore_skill[2]))
                else:
                    self.info_widget.skill_detail_encore_line.setText("")
                    self.info_widget.skill_detail_encore_line_.setText("")
            elif skill_type == 25: #life sparkle
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 2)
                t = float(time.split(" ~ ")[0])
                if self.cache_simulation.left_inclusive:
                    last_note = self.generator.notes.index[self.generator.notes['sec'] < t].tolist()[-1]
                else:
                    last_note = self.generator.notes.index[self.generator.notes['sec'] <= t].tolist()[-1]
                self.info_widget.skill_detail_sparkle_life_line.setText(str(self.perfect_detail.life[last_note]))
                self.update_sparkle_value()
            elif skill_type in (35, 36, 37): #motif
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 3)
                _ = card_idx // 5 * 5
                if skill_type == 35:
                    appeal = sum([_.vo for _ in self.cards[_:_+5]])
                    self.info_widget.skill_detail_motif_appeal_line.setText(str(appeal))
                elif skill_type == 36:
                    appeal = sum([_.da for _ in self.cards[_:_+5]])
                    self.info_widget.skill_detail_motif_appeal_line.setText(str(appeal))
                elif skill_type == 37:
                    appeal = sum([_.vi for _ in self.cards[_:_+5]])
                    self.info_widget.skill_detail_motif_appeal_line.setText(str(appeal))
                self.update_motif_value()
            elif skill_type == 39: #alternate
                if card_idx in self.perfect_detail.amr_bonus and idx in self.perfect_detail.amr_bonus[card_idx]:
                    alt_bonus = self.perfect_detail.amr_bonus[card_idx][idx]
                else:
                    alt_bonus = [0, 0, 0, 0, 0]
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 4)
                self.info_widget.skill_detail_alt_tap_line.setText("{:+}%".format(alt_bonus[0]))
                self.info_widget.skill_detail_alt_long_line.setText("{:+}%".format(alt_bonus[1]))
                self.info_widget.skill_detail_alt_flick_line.setText("{:+}%".format(alt_bonus[2]))
                self.info_widget.skill_detail_alt_slide_line.setText("{:+}%".format(alt_bonus[3]))
                self.info_widget.skill_detail_alt_great_line.setText("{:+}%".format(alt_bonus[4]))
            elif skill_type == 40: #refrain
                if card_idx in self.perfect_detail.amr_bonus and idx in self.perfect_detail.amr_bonus[card_idx]:
                    ref_bonus = self.perfect_detail.amr_bonus[card_idx][idx]
                else:
                    ref_bonus = [0, 0, 0, 0, 0, 0]    
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 5)
                self.info_widget.skill_detail_ref_tap_line.setText("{:+}%".format(ref_bonus[0]))
                self.info_widget.skill_detail_ref_long_line.setText("{:+}%".format(ref_bonus[1]))
                self.info_widget.skill_detail_ref_flick_line.setText("{:+}%".format(ref_bonus[2]))
                self.info_widget.skill_detail_ref_slide_line.setText("{:+}%".format(ref_bonus[3]))
                self.info_widget.skill_detail_ref_great_line.setText("{:+}%".format(ref_bonus[4]))
                self.info_widget.skill_detail_ref_combo_line.setText("{:+}%".format(ref_bonus[5]))
            elif skill_type == 41: #magic
                if card_idx in self.perfect_detail.magic_bonus and idx in self.perfect_detail.magic_bonus[card_idx]:
                    magic_bonus = self.perfect_detail.magic_bonus[card_idx][idx]
                else:
                    magic_bonus = {"tap" : 0, "long" : 0, "flick" : 0, "slide" : 0, "great" : 0, "combo" : 0,
                         "sparkle" : 0, "life" : 0, "psupport" : 0, "csupport" : 0,
                         "cu_score" : 0, "cu_combo" : 0, "cu_life" : 0, "cu_support" : 0,
                         "co_score" : 0, "co_combo" : 0, "co_life" : 0, "co_support" : 0,
                         "pa_score" : 0, "pa_combo" : 0, "pa_life" : 0, "pa_support" : 0,
                         "guard" : False, "overload" : 0, "concentration" : False}
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 6)
                self.info_widget.skill_detail_magic_tap_line.setText("{:+}%".format(magic_bonus["tap"]))
                self.info_widget.skill_detail_magic_long_line.setText("{:+}%".format(magic_bonus["long"]))
                self.info_widget.skill_detail_magic_flick_line.setText("{:+}%".format(magic_bonus["flick"]))
                self.info_widget.skill_detail_magic_slide_line.setText("{:+}%".format(magic_bonus["slide"]))
                self.info_widget.skill_detail_magic_great_line.setText("{:+}%".format(magic_bonus["great"]))
                if magic_bonus["sparkle"] != 0:
                    combo_text = "({:+}%)".format(max(magic_bonus["combo"], magic_bonus["sparkle"]))
                    self.info_widget.skill_detail_magic_combo_line.setToolTip("COMBO BONUS value from Life Sparkle can change while the skill is active.")
                else:
                    combo_text = "{:+}%".format(max(magic_bonus["combo"], magic_bonus["sparkle"]))
                    self.info_widget.skill_detail_magic_combo_line.setToolTip("")
                self.info_widget.skill_detail_magic_combo_line.setText(combo_text)
                self.info_widget.skill_detail_magic_life_line.setText("-{} / {:+}".format(magic_bonus["overload"], magic_bonus["life"]))
                self.info_widget.skill_detail_magic_life_line.setToolTip("Life consumed on skill activation / Life recovered on PERFECT note")
                psupport_text = ["-", "GREAT", "NICE", "BAD", "MISS"]
                csupport_text = ["-", "NICE", "BAD", "MISS"]
                self.info_widget.skill_detail_magic_psupport_line.setText(psupport_text[magic_bonus["psupport"]])
                self.info_widget.skill_detail_magic_csupport_line.setText(csupport_text[magic_bonus["csupport"]])
                self.info_widget.skill_detail_magic_boost_score_cute_line.setText("{:+}%".format(magic_bonus["cu_score"]))
                self.info_widget.skill_detail_magic_boost_combo_cute_line.setText("{:+}%".format(magic_bonus["cu_combo"]))
                self.info_widget.skill_detail_magic_boost_life_cute_line.setText("{:+}%".format(magic_bonus["cu_life"]))
                self.info_widget.skill_detail_magic_boost_support_cute_line.setText("{:+}".format(magic_bonus["cu_support"]))
                self.info_widget.skill_detail_magic_boost_score_cool_line.setText("{:+}%".format(magic_bonus["co_score"]))
                self.info_widget.skill_detail_magic_boost_combo_cool_line.setText("{:+}%".format(magic_bonus["co_combo"]))
                self.info_widget.skill_detail_magic_boost_life_cool_line.setText("{:+}%".format(magic_bonus["co_life"]))
                self.info_widget.skill_detail_magic_boost_support_cool_line.setText("{:+}".format(magic_bonus["co_support"]))
                self.info_widget.skill_detail_magic_boost_score_passion_line.setText("{:+}%".format(magic_bonus["pa_score"]))
                self.info_widget.skill_detail_magic_boost_combo_passion_line.setText("{:+}%".format(magic_bonus["pa_combo"]))
                self.info_widget.skill_detail_magic_boost_life_passion_line.setText("{:+}%".format(magic_bonus["pa_life"]))
                self.info_widget.skill_detail_magic_boost_support_passion_line.setText("{:+}".format(magic_bonus["pa_support"]))
                self.info_widget.skill_detail_magic_guard_checkbox.setChecked(magic_bonus["guard"])
                self.info_widget.skill_detail_magic_concentration_checkbox.setChecked(magic_bonus["concentration"])
            elif skill_type == 42: #mutual
                if card_idx in self.perfect_detail.amr_bonus and idx in self.perfect_detail.amr_bonus[card_idx]:
                    mut_bonus = self.perfect_detail.amr_bonus[card_idx][idx][5]
                else:
                    mut_bonus = 0
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 7)
                self.info_widget.skill_detail_mut_combo_line.setText("{:+}%".format(mut_bonus))
            else:
                self.set_stacked_widget_index(self.info_widget.skill_detail_widget, 0)
        
        if self.chart_mode == 3:
            self.set_stacked_widget_index(self.info_widget.custom_detail_widget, 1)
            idx = self.generator.selected_skill[0]
            num = self.generator.selected_skill[1]
            if idx in self.perfect_detail.skill_inactivation_reason and \
                num in self.perfect_detail.skill_inactivation_reason[idx]:
                self.info_widget.custom_skill_active_button.setDisabled(True)
                self.info_widget.custom_skill_active_line.setText("-")
            else:
                self.info_widget.custom_skill_active_button.setDisabled(False)
                if num in self.generator.skill_inactive_list[idx]:
                    self.info_widget.custom_skill_active_line.setText("Not Activated")
                else:
                    self.info_widget.custom_skill_active_line.setText("Activated")
    
    def update_sparkle_value(self):
        life = int(self.info_widget.skill_detail_sparkle_life_line.text())
        rarity_ssr = self.cards[self.generator.selected_skill[0]].sk.values[0] == 1
        
        life_trimmed = life // 10
        
        if rarity_ssr:
            sparkle_values = [_[0] for _ in db.masterdb.execute_and_fetchall("SELECT type_01_value FROM skill_life_value")]
        else:
            sparkle_values = [_[0] for _ in db.masterdb.execute_and_fetchall("SELECT type_02_value FROM skill_life_value")]
        
        if life_trimmed >= len(sparkle_values):
            life_trimmed = len(sparkle_values) - 1
        
        value = sparkle_values[int(life_trimmed)]
        self.info_widget.skill_detail_sparkle_combo_line.setText("{:+}%".format(value - 100))
    
    def update_motif_value(self):
        appeal = int(self.info_widget.skill_detail_motif_appeal_line.text())
        grand = len(self.cards) == 15
        
        appeal_trimmed = appeal // 1000
        
        if grand:
            motif_values = [_[0] for _ in db.masterdb.execute_and_fetchall("SELECT type_01_value FROM skill_motif_value_grand")]
        else:
            motif_values = [_[0] for _ in db.masterdb.execute_and_fetchall("SELECT type_01_value FROM skill_motif_value")]
        
        if appeal_trimmed >= len(motif_values):
            appeal_trimmed = len(motif_values) - 1
        
        value = motif_values[int(appeal_trimmed)]
        self.info_widget.skill_detail_motif_score_line.setText("{:+}%".format(value - 100))
    
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
        self.generator.draw_perfect_chart_skill_part(idx, num)
        self.generator.draw_selected_skill(idx, num)

    def reset_all_custom_settings(self):
        self.generator.skill_inactive_list = [[] for _ in range(15)]
        self.simulate_custom()
        self.generator.draw_perfect_chart()
        if self.custom_abuse == 1:
            self.generator.draw_abuse_chart()
        self.show_detail_nothing()
    
    def simulate_custom(self):
        eventbus.eventbus.post(CustomSimulationEvent(self.cache_simulation, self.generator.skill_inactive_list))
    
    def toggle_custom_abuse(self):
        if self.custom_abuse == 0:
            self.generator.draw_nothing_selected()
            self.generator.draw_abuse_chart()
            self.show_detail_nothing()
            self.custom_abuse = 1
        elif self.custom_abuse == 1:
            self.generator.draw_perfect_chart()
            self.custom_abuse = 0
    
    def setup_info_widget(self):
        self.info_widget.layout = QVBoxLayout(self.info_widget)
        self.info_widget.layout.setSpacing(0)
        
        self._setup_song_info()
        self.info_widget.song_info_layout.setSpacing(6)
        self.info_widget.layout.addSpacing(12)
        
        self._setup_chart_mode()
        self.info_widget.mode_button_layout.setSpacing(6)
        
        self.info_widget.detail_widget = QStackedWidget()
        self.info_widget.detail_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.detail_widget.addWidget(QWidget())
        
        self._setup_note_info()
        self._setup_note_score_info()
        self.info_widget.note_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.note_score_layout.setContentsMargins(0, 6, 0, 0)
        
        self._setup_skill_info()
        self.info_widget.skill_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_encore_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_sparkle_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_motif_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_alt_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_ref_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_magic_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_detail_mut_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.skill_inactivation_detail_layout.setContentsMargins(0, 6, 0, 0)
        
        self.info_widget.custom_widget = QStackedWidget()
        self.info_widget.custom_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.custom_widget.addWidget(QWidget())
        
        self._setup_custom()
        self.info_widget.custom_setting_layout.setContentsMargins(0, 6, 0, 0)
        self.info_widget.custom_skill_layout.setContentsMargins(0, 6, 0, 0)
        
        self.info_widget.layout.addWidget(self.info_widget.custom_widget)
        self.info_widget.layout.addWidget(self.info_widget.detail_widget)
        
        self._resize_stacked_widget(self.info_widget.detail_widget, 0)
        self._resize_stacked_widget(self.info_widget.custom_widget, 0)
        self._resize_stacked_widget(self.info_widget.note_score_info_widget, 0)
        self._resize_stacked_widget(self.info_widget.custom_detail_widget, 0)
        self._resize_stacked_widget(self.info_widget.skill_detail_widget, 0)
        self._resize_stacked_widget(self.info_widget.skill_inactivation_widget, 0)
    
    '''
    self.info_widget
        self.info_widget.song_info_layout
            self.info_widget.title_layout
            self.info_widget.difficulty_layout
            self.info_widget.level_layout
            self.info_widget.total_layout
            self.info_widget.save
        self.info_widget.mode_button_layout
            self.info_widget.mode_label
            self.info_widget.mode_default_button
            self.info_widget.mode_perfect_button
            self.info_widget.mode_abuse_button
            self.info_widget.mode_custom_button
        self.info_widget.custom_widget
            QWidget()
            self.info_widget.custom_setting_widget
                self.info_widget.custom_general_layout
                    self.info_widget.custom_score_layout
                    self.info_widget.custom_button_layout
                self.info_widget.custom_detail_widget
                    QWidget()
                    self.info_widget.custom_skill_widget
        self.info_widget.detail_widget
            QWidget()
            self.info_widget.note_widget
                self.info_widget.note_info_layout
                    self.info_widget.note_number_layout
                    self.info_widget.note_second_layout
                    self.info_widget.note_type_layout
                self.info_widget.note_score_info_widget
                    QWidget()
                    self.info_widget.note_score_widget
                        self.info_widget.note_score_general_layout
                        self.info_widget.note_skills_layout
            self.info_widget.skill_widget
                self.info_widget.skill_info_layout
                    self.info_widget.skill_type_layout
                    self.info_widget.skill_time_layout
                    self.info_widget.skill_prob_layout
                self.info_widget.skill_description_layout
                self.info_widget.skill_detail_widget
                    QWidget()    
                    self.info_widget.skill_detail_encore_widget
                    self.info_widget.skill_detail_sparkle_widget
                    self.info_widget.skill_detail_motif_widget
                    self.info_widget.skill_detail_alt_widget
                    self.info_widget.skill_detail_ref_widget
                    self.info_widget.skill_detail_magic_widget
                    self.info_widget.skill_detail_mut_widget
                self.info_widget.skill_inactivation_widget
                    QWidget()
                    self.info_widget.skill_inactivation_detail_widget
    '''
        
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
        
        self.info_widget.save = QPushButton("Save")
        self.info_widget.save.clicked.connect(lambda: self.save_chart())
        self.info_widget.save.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        self.info_widget.song_info_layout = QHBoxLayout()
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
        
        self.info_widget.note_info_layout = QHBoxLayout()
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_number_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_second_layout)
        self.info_widget.note_info_layout.addLayout(self.info_widget.note_type_layout)
        self.info_widget.note_layout.addSpacing(6)
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
        
        self.info_widget.skill_prob_layout = QVBoxLayout()
        self.info_widget.skill_prob_label = QLabel("Probability")
        self.info_widget.skill_prob_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_line = QLineEdit()
        self.info_widget.skill_prob_line.setReadOnly(True)
        self.info_widget.skill_prob_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_label)
        self.info_widget.skill_prob_layout.addWidget(self.info_widget.skill_prob_line)
        
        self.info_widget.skill_description_label = QLabel("Effect")
        self.info_widget.skill_description_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_description_line = QTextEdit()
        fm = QFontMetrics(self.info_widget.skill_description_line.font())
        self.info_widget.skill_description_line.setMaximumHeight(fm.height() * 2 + fm.leading() + 10)
        self.info_widget.skill_description_line.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.info_widget.skill_description_line.setReadOnly(True)
        self.info_widget.skill_description_line.setAlignment(Qt.AlignCenter)
        
        self.info_widget.skill_description_layout = QVBoxLayout()
        self.info_widget.skill_description_layout.addWidget(self.info_widget.skill_description_label)
        self.info_widget.skill_description_layout.addWidget(self.info_widget.skill_description_line)
        
        self.info_widget.skill_detail_widget = QStackedWidget()
        self.info_widget.skill_detail_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.skill_detail_widget.addWidget(QWidget())
        self.info_widget.skill_detail_widget.setCurrentIndex(0)
        
        self.info_widget.skill_detail_encore_widget = QWidget()
        self.info_widget.skill_detail_encore_layout = QVBoxLayout(self.info_widget.skill_detail_encore_widget)
        
        self.info_widget.skill_detail_encore_label = QLabel("Encored skill : ")
        self.info_widget.skill_detail_encore_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_encore_line = QLineEdit()
        self.info_widget.skill_detail_encore_line.setReadOnly(True)
        self.info_widget.skill_detail_encore_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_encore_label_ = QLabel("which was activated at")
        self.info_widget.skill_detail_encore_label_.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_encore_line_ = QLineEdit()
        self.info_widget.skill_detail_encore_line_.setReadOnly(True)
        self.info_widget.skill_detail_encore_line_.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_encore_top_layout = QHBoxLayout()
        self.info_widget.skill_detail_encore_top_layout.addWidget(self.info_widget.skill_detail_encore_label, 2)
        self.info_widget.skill_detail_encore_top_layout.addWidget(self.info_widget.skill_detail_encore_line, 2)
        self.info_widget.skill_detail_encore_top_layout.addWidget(self.info_widget.skill_detail_encore_label_, 2)
        self.info_widget.skill_detail_encore_top_layout.addWidget(self.info_widget.skill_detail_encore_line_, 1)
        self.info_widget.skill_detail_encore_layout.addLayout(self.info_widget.skill_detail_encore_top_layout)
        
        self.info_widget.skill_detail_sparkle_widget = QWidget()
        self.info_widget.skill_detail_sparkle_layout = QHBoxLayout(self.info_widget.skill_detail_sparkle_widget)
        
        self.info_widget.skill_detail_sparkle_life_layout = QHBoxLayout()
        self.info_widget.skill_detail_sparkle_life_label = QLabel("Current life :")
        self.info_widget.skill_detail_sparkle_life_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_sparkle_life_line = QLineEdit()
        self.info_widget.skill_detail_sparkle_life_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_sparkle_life_line.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.info_widget.skill_detail_sparkle_life_line.setToolTip("Life Sparkle COMBO BONUS UP value can change while the skill is active.\n" + 
                                                                     "The default value shown here is the life value at the moment of skill activation.")
        self.info_widget.skill_detail_sparkle_life_line.setValidator(QIntValidator(1, 9999, None))
        self.info_widget.skill_detail_sparkle_life_line.editingFinished.connect(lambda: self.update_sparkle_value())
        self.info_widget.skill_detail_sparkle_combo_layout = QHBoxLayout()
        self.info_widget.skill_detail_sparkle_combo_label = QLabel("Life Sparkle COMBO BONUS :")
        self.info_widget.skill_detail_sparkle_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_sparkle_combo_line = QLineEdit()
        self.info_widget.skill_detail_sparkle_combo_line.setReadOnly(True)
        self.info_widget.skill_detail_sparkle_combo_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_sparkle_combo_line.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.info_widget.skill_detail_sparkle_life_layout.addWidget(self.info_widget.skill_detail_sparkle_life_label)
        self.info_widget.skill_detail_sparkle_life_layout.addWidget(self.info_widget.skill_detail_sparkle_life_line)
        self.info_widget.skill_detail_sparkle_combo_layout.addWidget(self.info_widget.skill_detail_sparkle_combo_label)
        self.info_widget.skill_detail_sparkle_combo_layout.addWidget(self.info_widget.skill_detail_sparkle_combo_line)
        self.info_widget.skill_detail_sparkle_layout.addLayout(self.info_widget.skill_detail_sparkle_life_layout)
        self.info_widget.skill_detail_sparkle_layout.addSpacing(12)
        self.info_widget.skill_detail_sparkle_layout.addLayout(self.info_widget.skill_detail_sparkle_combo_layout)
        
        self.info_widget.skill_detail_motif_widget = QWidget()
        self.info_widget.skill_detail_motif_layout = QHBoxLayout(self.info_widget.skill_detail_motif_widget)
        
        self.info_widget.skill_detail_motif_appeal_layout = QHBoxLayout()
        self.info_widget.skill_detail_motif_appeal_label = QLabel("Appeal of the unit :")
        self.info_widget.skill_detail_motif_appeal_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_motif_appeal_line = QLineEdit()
        self.info_widget.skill_detail_motif_appeal_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_motif_appeal_line.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.info_widget.skill_detail_motif_appeal_line.setValidator(QIntValidator(0, 99999, None))
        self.info_widget.skill_detail_motif_appeal_line.editingFinished.connect(lambda: self.update_motif_value())
        self.info_widget.skill_detail_motif_score_layout = QHBoxLayout()
        self.info_widget.skill_detail_motif_score_label = QLabel("Motif SCORE UP :")
        self.info_widget.skill_detail_motif_score_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_motif_score_line = QLineEdit()
        self.info_widget.skill_detail_motif_score_line.setReadOnly(True)
        self.info_widget.skill_detail_motif_score_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_motif_score_line.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.info_widget.skill_detail_motif_appeal_layout.addWidget(self.info_widget.skill_detail_motif_appeal_label)
        self.info_widget.skill_detail_motif_appeal_layout.addWidget(self.info_widget.skill_detail_motif_appeal_line)
        self.info_widget.skill_detail_motif_score_layout.addWidget(self.info_widget.skill_detail_motif_score_label)
        self.info_widget.skill_detail_motif_score_layout.addWidget(self.info_widget.skill_detail_motif_score_line)
        self.info_widget.skill_detail_motif_layout.addLayout(self.info_widget.skill_detail_motif_appeal_layout)
        self.info_widget.skill_detail_motif_layout.addSpacing(12)
        self.info_widget.skill_detail_motif_layout.addLayout(self.info_widget.skill_detail_motif_score_layout)
        
        self.info_widget.skill_detail_alt_widget = QWidget()
        self.info_widget.skill_detail_alt_layout = QHBoxLayout(self.info_widget.skill_detail_alt_widget)
        
        self.info_widget.skill_detail_alt_tap_layout = QVBoxLayout()
        self.info_widget.skill_detail_alt_tap_label = QLabel("TAP")
        self.info_widget.skill_detail_alt_tap_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_tap_line = QLineEdit()
        self.info_widget.skill_detail_alt_tap_line.setReadOnly(True)
        self.info_widget.skill_detail_alt_tap_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_tap_layout.addWidget(self.info_widget.skill_detail_alt_tap_label)
        self.info_widget.skill_detail_alt_tap_layout.addWidget(self.info_widget.skill_detail_alt_tap_line)
        self.info_widget.skill_detail_alt_long_layout = QVBoxLayout()
        self.info_widget.skill_detail_alt_long_label = QLabel("LONG")
        self.info_widget.skill_detail_alt_long_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_long_line = QLineEdit()
        self.info_widget.skill_detail_alt_long_line.setReadOnly(True)
        self.info_widget.skill_detail_alt_long_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_long_layout.addWidget(self.info_widget.skill_detail_alt_long_label)
        self.info_widget.skill_detail_alt_long_layout.addWidget(self.info_widget.skill_detail_alt_long_line)
        self.info_widget.skill_detail_alt_flick_layout = QVBoxLayout()
        self.info_widget.skill_detail_alt_flick_label = QLabel("FLICK")
        self.info_widget.skill_detail_alt_flick_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_flick_line = QLineEdit()
        self.info_widget.skill_detail_alt_flick_line.setReadOnly(True)
        self.info_widget.skill_detail_alt_flick_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_flick_layout.addWidget(self.info_widget.skill_detail_alt_flick_label)
        self.info_widget.skill_detail_alt_flick_layout.addWidget(self.info_widget.skill_detail_alt_flick_line)
        self.info_widget.skill_detail_alt_slide_layout = QVBoxLayout()
        self.info_widget.skill_detail_alt_slide_label = QLabel("SLIDE")
        self.info_widget.skill_detail_alt_slide_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_slide_line = QLineEdit()
        self.info_widget.skill_detail_alt_slide_line.setReadOnly(True)
        self.info_widget.skill_detail_alt_slide_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_slide_layout.addWidget(self.info_widget.skill_detail_alt_slide_label)
        self.info_widget.skill_detail_alt_slide_layout.addWidget(self.info_widget.skill_detail_alt_slide_line)
        self.info_widget.skill_detail_alt_great_layout = QVBoxLayout()
        self.info_widget.skill_detail_alt_great_label = QLabel("GREAT")
        self.info_widget.skill_detail_alt_great_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_great_line = QLineEdit()
        self.info_widget.skill_detail_alt_great_line.setReadOnly(True)
        self.info_widget.skill_detail_alt_great_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_alt_great_layout.addWidget(self.info_widget.skill_detail_alt_great_label)
        self.info_widget.skill_detail_alt_great_layout.addWidget(self.info_widget.skill_detail_alt_great_line)
        self.info_widget.skill_detail_alt_layout.addLayout(self.info_widget.skill_detail_alt_tap_layout)
        self.info_widget.skill_detail_alt_layout.addLayout(self.info_widget.skill_detail_alt_long_layout)
        self.info_widget.skill_detail_alt_layout.addLayout(self.info_widget.skill_detail_alt_flick_layout)
        self.info_widget.skill_detail_alt_layout.addLayout(self.info_widget.skill_detail_alt_slide_layout)
        self.info_widget.skill_detail_alt_layout.addLayout(self.info_widget.skill_detail_alt_great_layout)
        
        self.info_widget.skill_detail_ref_widget = QWidget()
        self.info_widget.skill_detail_ref_layout = QHBoxLayout(self.info_widget.skill_detail_ref_widget)
        
        self.info_widget.skill_detail_ref_tap_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_tap_label = QLabel("TAP")
        self.info_widget.skill_detail_ref_tap_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_tap_line = QLineEdit()
        self.info_widget.skill_detail_ref_tap_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_tap_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_tap_layout.addWidget(self.info_widget.skill_detail_ref_tap_label)
        self.info_widget.skill_detail_ref_tap_layout.addWidget(self.info_widget.skill_detail_ref_tap_line)
        self.info_widget.skill_detail_ref_long_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_long_label = QLabel("LONG")
        self.info_widget.skill_detail_ref_long_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_long_line = QLineEdit()
        self.info_widget.skill_detail_ref_long_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_long_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_long_layout.addWidget(self.info_widget.skill_detail_ref_long_label)
        self.info_widget.skill_detail_ref_long_layout.addWidget(self.info_widget.skill_detail_ref_long_line)
        self.info_widget.skill_detail_ref_flick_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_flick_label = QLabel("FLICK")
        self.info_widget.skill_detail_ref_flick_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_flick_line = QLineEdit()
        self.info_widget.skill_detail_ref_flick_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_flick_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_flick_layout.addWidget(self.info_widget.skill_detail_ref_flick_label)
        self.info_widget.skill_detail_ref_flick_layout.addWidget(self.info_widget.skill_detail_ref_flick_line)
        self.info_widget.skill_detail_ref_slide_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_slide_label = QLabel("SLIDE")
        self.info_widget.skill_detail_ref_slide_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_slide_line = QLineEdit()
        self.info_widget.skill_detail_ref_slide_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_slide_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_slide_layout.addWidget(self.info_widget.skill_detail_ref_slide_label)
        self.info_widget.skill_detail_ref_slide_layout.addWidget(self.info_widget.skill_detail_ref_slide_line)
        self.info_widget.skill_detail_ref_great_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_great_label = QLabel("GREAT")
        self.info_widget.skill_detail_ref_great_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_great_line = QLineEdit()
        self.info_widget.skill_detail_ref_great_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_great_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_great_layout.addWidget(self.info_widget.skill_detail_ref_great_label)
        self.info_widget.skill_detail_ref_great_layout.addWidget(self.info_widget.skill_detail_ref_great_line)
        self.info_widget.skill_detail_ref_combo_layout = QVBoxLayout()
        self.info_widget.skill_detail_ref_combo_label = QLabel("COMBO")
        self.info_widget.skill_detail_ref_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_combo_line = QLineEdit()
        self.info_widget.skill_detail_ref_combo_line.setReadOnly(True)
        self.info_widget.skill_detail_ref_combo_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_ref_combo_layout.addWidget(self.info_widget.skill_detail_ref_combo_label)
        self.info_widget.skill_detail_ref_combo_layout.addWidget(self.info_widget.skill_detail_ref_combo_line)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_tap_layout)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_long_layout)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_flick_layout)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_slide_layout)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_great_layout)
        self.info_widget.skill_detail_ref_layout.addLayout(self.info_widget.skill_detail_ref_combo_layout)
        
        self.info_widget.skill_detail_magic_widget = QWidget()
        self.info_widget.skill_detail_magic_layout = QVBoxLayout(self.info_widget.skill_detail_magic_widget)
        self.info_widget.skill_detail_magic_note_layout = QHBoxLayout()
        
        self.info_widget.skill_detail_magic_tap_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_tap_label = QLabel("TAP")
        self.info_widget.skill_detail_magic_tap_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_tap_line = QLineEdit()
        self.info_widget.skill_detail_magic_tap_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_tap_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_tap_layout.addWidget(self.info_widget.skill_detail_magic_tap_label)
        self.info_widget.skill_detail_magic_tap_layout.addWidget(self.info_widget.skill_detail_magic_tap_line)
        self.info_widget.skill_detail_magic_long_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_long_label = QLabel("LONG")
        self.info_widget.skill_detail_magic_long_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_long_line = QLineEdit()
        self.info_widget.skill_detail_magic_long_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_long_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_long_layout.addWidget(self.info_widget.skill_detail_magic_long_label)
        self.info_widget.skill_detail_magic_long_layout.addWidget(self.info_widget.skill_detail_magic_long_line)
        self.info_widget.skill_detail_magic_flick_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_flick_label = QLabel("FLICK")
        self.info_widget.skill_detail_magic_flick_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_flick_line = QLineEdit()
        self.info_widget.skill_detail_magic_flick_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_flick_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_flick_layout.addWidget(self.info_widget.skill_detail_magic_flick_label)
        self.info_widget.skill_detail_magic_flick_layout.addWidget(self.info_widget.skill_detail_magic_flick_line)
        self.info_widget.skill_detail_magic_slide_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_slide_label = QLabel("SLIDE")
        self.info_widget.skill_detail_magic_slide_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_slide_line = QLineEdit()
        self.info_widget.skill_detail_magic_slide_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_slide_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_slide_layout.addWidget(self.info_widget.skill_detail_magic_slide_label)
        self.info_widget.skill_detail_magic_slide_layout.addWidget(self.info_widget.skill_detail_magic_slide_line)
        self.info_widget.skill_detail_magic_great_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_great_label = QLabel("GREAT")
        self.info_widget.skill_detail_magic_great_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_great_line = QLineEdit()
        self.info_widget.skill_detail_magic_great_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_great_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_great_layout.addWidget(self.info_widget.skill_detail_magic_great_label)
        self.info_widget.skill_detail_magic_great_layout.addWidget(self.info_widget.skill_detail_magic_great_line)
        self.info_widget.skill_detail_magic_combo_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_combo_label = QLabel("COMBO")
        self.info_widget.skill_detail_magic_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_combo_line = QLineEdit()
        self.info_widget.skill_detail_magic_combo_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_combo_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_combo_layout.addWidget(self.info_widget.skill_detail_magic_combo_label)
        self.info_widget.skill_detail_magic_combo_layout.addWidget(self.info_widget.skill_detail_magic_combo_line)
        self.info_widget.skill_detail_magic_life_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_life_label = QLabel("LIFE")
        self.info_widget.skill_detail_magic_life_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_life_line = QLineEdit()
        self.info_widget.skill_detail_magic_life_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_life_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_life_layout.addWidget(self.info_widget.skill_detail_magic_life_label)
        self.info_widget.skill_detail_magic_life_layout.addWidget(self.info_widget.skill_detail_magic_life_line)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_tap_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_long_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_flick_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_slide_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_great_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_combo_layout)
        self.info_widget.skill_detail_magic_note_layout.addLayout(self.info_widget.skill_detail_magic_life_layout)
        
        self.info_widget.skill_detail_magic_support_boost_layout = QHBoxLayout()
        self.info_widget.skill_detail_magic_support_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_psupport_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_psupport_label = QLabel("PERFECT SUPPORT")
        self.info_widget.skill_detail_magic_psupport_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_psupport_line = QLineEdit()
        self.info_widget.skill_detail_magic_psupport_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_psupport_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_psupport_layout.addWidget(self.info_widget.skill_detail_magic_psupport_label)
        self.info_widget.skill_detail_magic_psupport_layout.addWidget(self.info_widget.skill_detail_magic_psupport_line)
        self.info_widget.skill_detail_magic_csupport_layout = QVBoxLayout()
        self.info_widget.skill_detail_magic_csupport_label = QLabel("COMBO SUPPORT")
        self.info_widget.skill_detail_magic_csupport_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_csupport_line = QLineEdit()
        self.info_widget.skill_detail_magic_csupport_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_csupport_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_csupport_layout.addWidget(self.info_widget.skill_detail_magic_csupport_label)
        self.info_widget.skill_detail_magic_csupport_layout.addWidget(self.info_widget.skill_detail_magic_csupport_line)
        self.info_widget.skill_detail_magic_support_layout.addLayout(self.info_widget.skill_detail_magic_psupport_layout)
        self.info_widget.skill_detail_magic_support_layout.addSpacing(4)
        self.info_widget.skill_detail_magic_support_layout.addLayout(self.info_widget.skill_detail_magic_csupport_layout)
        
        self.info_widget.skill_detail_magic_boost_layout = QGridLayout()
        self.info_widget.skill_detail_magic_boost_score_label = QLabel("SCORE")
        self.info_widget.skill_detail_magic_boost_score_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_combo_label = QLabel("COMBO")
        self.info_widget.skill_detail_magic_boost_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_life_label = QLabel("LIFE")
        self.info_widget.skill_detail_magic_boost_life_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_support_label = QLabel("SUPPORT")
        self.info_widget.skill_detail_magic_boost_support_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_cute_label = QLabel("CUTE")
        self.info_widget.skill_detail_magic_boost_cute_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_cool_label = QLabel("COOL")
        self.info_widget.skill_detail_magic_boost_cool_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_passion_label = QLabel("PASSION")
        self.info_widget.skill_detail_magic_boost_passion_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_score_cute_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_score_cute_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_score_cute_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_score_cool_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_score_cool_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_score_cool_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_score_passion_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_score_passion_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_score_passion_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_combo_cute_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_combo_cute_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_combo_cute_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_combo_cool_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_combo_cool_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_combo_cool_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_combo_passion_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_combo_passion_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_combo_passion_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_life_cute_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_life_cute_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_life_cute_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_life_cool_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_life_cool_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_life_cool_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_life_passion_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_life_passion_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_life_passion_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_support_cute_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_support_cute_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_support_cute_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_support_cool_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_support_cool_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_support_cool_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_support_passion_line = QLineEdit()
        self.info_widget.skill_detail_magic_boost_support_passion_line.setReadOnly(True)
        self.info_widget.skill_detail_magic_boost_support_passion_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_score_label, 0, 1, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_combo_label, 0, 2, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_life_label, 0, 3, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_support_label, 0, 4, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_cute_label, 1, 0, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_cool_label, 2, 0, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_passion_label, 3, 0, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_score_cute_line, 1, 1, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_score_cool_line, 2, 1, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_score_passion_line, 3, 1, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_combo_cute_line, 1, 2, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_combo_cool_line, 2, 2, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_combo_passion_line, 3, 2, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_life_cute_line, 1, 3, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_life_cool_line, 2, 3, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_life_passion_line, 3, 3, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_support_cute_line, 1, 4, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_support_cool_line, 2, 4, 1, 1)
        self.info_widget.skill_detail_magic_boost_layout.addWidget(self.info_widget.skill_detail_magic_boost_support_passion_line, 3, 4, 1, 1)
        self.info_widget.skill_detail_magic_support_boost_layout.addLayout(self.info_widget.skill_detail_magic_support_layout)
        self.info_widget.skill_detail_magic_support_boost_layout.addSpacing(8)
        self.info_widget.skill_detail_magic_support_boost_layout.addLayout(self.info_widget.skill_detail_magic_boost_layout)

        self.info_widget.skill_detail_magic_misc_layout = QHBoxLayout()
        self.info_widget.skill_detail_magic_guard_checkbox = QCheckBox("Prevent life decrease")
        self.info_widget.skill_detail_magic_guard_checkbox.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.info_widget.skill_detail_magic_guard_checkbox.setFocusPolicy(Qt.NoFocus)
        self.info_widget.skill_detail_magic_guard_checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
        self.info_widget.skill_detail_magic_concentration_checkbox = QCheckBox("Halve PERFECT timing window")
        self.info_widget.skill_detail_magic_concentration_checkbox.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.info_widget.skill_detail_magic_concentration_checkbox.setFocusPolicy(Qt.NoFocus)
        self.info_widget.skill_detail_magic_concentration_checkbox.setStyleSheet("margin-left:10%; margin-right:10%;")
        self.info_widget.skill_detail_magic_misc_layout.addWidget(self.info_widget.skill_detail_magic_guard_checkbox)
        self.info_widget.skill_detail_magic_misc_layout.addWidget(self.info_widget.skill_detail_magic_concentration_checkbox)
        self.info_widget.skill_detail_magic_layout.addLayout(self.info_widget.skill_detail_magic_note_layout)
        self.info_widget.skill_detail_magic_layout.addSpacing(8)
        self.info_widget.skill_detail_magic_layout.addLayout(self.info_widget.skill_detail_magic_support_boost_layout)
        self.info_widget.skill_detail_magic_layout.addSpacing(8)
        self.info_widget.skill_detail_magic_layout.addLayout(self.info_widget.skill_detail_magic_misc_layout)
        
        self.info_widget.skill_detail_mut_widget = QWidget()
        self.info_widget.skill_detail_mut_layout = QHBoxLayout(self.info_widget.skill_detail_mut_widget)
        self.info_widget.skill_detail_mut_combo_label = QLabel("COMBO BONUS")
        self.info_widget.skill_detail_mut_combo_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_mut_combo_line = QLineEdit()
        self.info_widget.skill_detail_mut_combo_line.setReadOnly(True)
        self.info_widget.skill_detail_mut_combo_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_detail_mut_combo_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.info_widget.skill_detail_mut_layout.addWidget(self.info_widget.skill_detail_mut_combo_label)
        self.info_widget.skill_detail_mut_layout.addWidget(self.info_widget.skill_detail_mut_combo_line)
        
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_encore_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_sparkle_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_motif_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_alt_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_ref_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_magic_widget)
        self.info_widget.skill_detail_widget.addWidget(self.info_widget.skill_detail_mut_widget)
        
        self.info_widget.skill_inactivation_widget = QStackedWidget()
        self.info_widget.skill_inactivation_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.info_widget.skill_inactivation_widget.addWidget(QWidget())
        self.info_widget.skill_inactivation_widget.setCurrentIndex(0)
        self.info_widget.skill_inactivation_detail_widget = QWidget()
        self.info_widget.skill_inactivation_detail_layout = QVBoxLayout(self.info_widget.skill_inactivation_detail_widget)
        
        self.info_widget.skill_inactivation_detail_label = QLabel("[！] This skill does not activate because of the following reason:")
        self.info_widget.skill_inactivation_detail_label.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_inactivation_detail_line = QLineEdit()
        self.info_widget.skill_inactivation_detail_line.setReadOnly(True)
        self.info_widget.skill_inactivation_detail_line.setAlignment(Qt.AlignCenter)
        self.info_widget.skill_inactivation_detail_layout.addWidget(self.info_widget.skill_inactivation_detail_label)
        self.info_widget.skill_inactivation_detail_layout.addWidget(self.info_widget.skill_inactivation_detail_line)
        self.info_widget.skill_inactivation_widget.addWidget(self.info_widget.skill_inactivation_detail_widget)
        
        self.info_widget.skill_widget = QWidget()
        self.info_widget.skill_layout = QVBoxLayout(self.info_widget.skill_widget)
        
        self.info_widget.skill_info_layout = QHBoxLayout()
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_type_layout)
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_time_layout)
        self.info_widget.skill_info_layout.addLayout(self.info_widget.skill_prob_layout)
        
        self.info_widget.skill_layout.addSpacing(6)
        self.info_widget.skill_layout.addLayout(self.info_widget.skill_info_layout)
        self.info_widget.skill_layout.addSpacing(6)
        self.info_widget.skill_layout.addLayout(self.info_widget.skill_description_layout)
        self.info_widget.skill_layout.addWidget(self.info_widget.skill_detail_widget)
        self.info_widget.skill_layout.addWidget(self.info_widget.skill_inactivation_widget)
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
        
        self.info_widget.custom_theoretic_layout = QVBoxLayout()
        self.info_widget.custom_theoretic_label = QLabel("Theoretical Score")
        self.info_widget.custom_theoretic_label.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_theoretic_line = QLineEdit()
        self.info_widget.custom_theoretic_line.setReadOnly(True)
        self.info_widget.custom_theoretic_line.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_theoretic_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.info_widget.custom_theoretic_layout.addWidget(self.info_widget.custom_theoretic_label)
        self.info_widget.custom_theoretic_layout.addWidget(self.info_widget.custom_theoretic_line)
        self.info_widget.custom_score_layout = QHBoxLayout()
        
        self.info_widget.custom_skill_prob_layout = QVBoxLayout()
        self.info_widget.custom_skill_prob_label = QLabel("Probability")
        self.info_widget.custom_skill_prob_label.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_skill_prob_line = QLineEdit()
        self.info_widget.custom_skill_prob_line.setReadOnly(True)
        self.info_widget.custom_skill_prob_line.setAlignment(Qt.AlignCenter)
        self.info_widget.custom_skill_prob_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.info_widget.custom_skill_prob_layout.addWidget(self.info_widget.custom_skill_prob_label)
        self.info_widget.custom_skill_prob_layout.addWidget(self.info_widget.custom_skill_prob_line)
        self.info_widget.custom_score_layout = QHBoxLayout()
        self.info_widget.custom_score_layout.addLayout(self.info_widget.custom_total_layout)
        self.info_widget.custom_score_layout.addLayout(self.info_widget.custom_theoretic_layout)
        self.info_widget.custom_score_layout.addLayout(self.info_widget.custom_skill_prob_layout)
        
        self.info_widget.custom_button_layout = QVBoxLayout()
        self.info_widget.custom_update_button = QPushButton("Update")
        self.info_widget.custom_update_button.clicked.connect(lambda: self.simulate_custom())
        self.info_widget.custom_button_bottom_layout = QHBoxLayout()
        self.info_widget.custom_reset_button = QPushButton("Reset All")
        self.info_widget.custom_reset_button.clicked.connect(lambda: self.reset_all_custom_settings())
        self.info_widget.custom_abuse_button = QPushButton("Toggle abuse")
        self.info_widget.custom_abuse_button.clicked.connect(lambda: self.toggle_custom_abuse())
        self.info_widget.custom_button_layout.addWidget(self.info_widget.custom_update_button)
        self.info_widget.custom_button_bottom_layout.addWidget(self.info_widget.custom_reset_button)
        self.info_widget.custom_button_bottom_layout.addWidget(self.info_widget.custom_abuse_button)
        self.info_widget.custom_button_layout.addLayout(self.info_widget.custom_button_bottom_layout)
        
        self.info_widget.custom_general_layout = QHBoxLayout()
        self.info_widget.custom_general_layout.addLayout(self.info_widget.custom_score_layout)
        self.info_widget.custom_general_layout.addLayout(self.info_widget.custom_button_layout)
        
        self.info_widget.custom_skill_widget = QWidget()
        self.info_widget.custom_skill_layout = QHBoxLayout(self.info_widget.custom_skill_widget)
        
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
        
        self.info_widget.custom_setting_layout.addSpacing(6)
        self.info_widget.custom_setting_layout.addLayout(self.info_widget.custom_general_layout)
        self.info_widget.custom_setting_layout.addWidget(self.info_widget.custom_detail_widget)
        
        self.info_widget.custom_widget.addWidget(self.info_widget.custom_setting_widget)
        self.info_widget.custom_widget.setCurrentIndex(0)
