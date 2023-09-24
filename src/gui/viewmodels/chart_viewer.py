import operator
from collections import defaultdict
from enum import Enum
from typing import Optional, Union, Any, Dict, List, DefaultDict, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics, QIntValidator
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QStackedWidget, QLineEdit, QHBoxLayout, \
    QGridLayout, QRadioButton, QButtonGroup, QSizePolicy, QTreeWidget, QTreeWidgetItem, QCheckBox, QPushButton, \
    QSpinBox, QTextEdit

from chart_pic_generator import BaseChartPicGenerator, WINDOW_WIDTH, SCROLL_WIDTH
from db import db
from gui.events.calculator_view_events import SimulationEvent, CacheSimulationEvent, CustomSimulationEvent, \
    CustomSimulationResultEvent
from gui.events.chart_viewer_events import SendMusicEvent, HookAbuseToChartViewerEvent, HookUnitToChartViewerEvent, \
    ToggleMirrorEvent, HookSimResultToChartViewerEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.value_accessor_events import GetMirrorFlagEvent
from logic.card import Card
from simulator import LiveDetail
from statemachine import NoteDetailSkill, get_note_detail
from static.judgement import Judgement
from static.note_type import NoteType
from static.skill import SKILL_BASE, SKILL_INACTIVATION_REASON
from static.song_difficulty import Difficulty, BAD_TAP_RANGE

BAD_NON_TAP_RANGE = 200000
MISS_OFFSET = 450


class ChartMode(Enum):
    DEFAULT = 0
    PERFECT = 1
    ABUSE = 2
    CUSTOM = 3


class ChartViewer:
    generator: Optional[BaseChartPicGenerator]

    chart_mode: ChartMode
    song_id: int
    difficulty: Difficulty
    mirrored: bool

    cards: List[Card]
    perfect_detail: Optional[LiveDetail]

    simulation_cache: Optional[SimulationEvent]

    custom_offset_cache: DefaultDict[int, int]
    custom_abuse_enabled: bool
    draw_custom_abuse: bool

    def __init__(self, parent):
        self.parent = parent

        self.widget = None
        self.layout = None
        self.info_widget = None
        self.chart_widget = None

        self.generator = None

        self.chart_mode = ChartMode.DEFAULT
        self.song_id = 0
        self.difficulty = Difficulty.DEBUT
        self.mirrored = False

        self.cards = list()
        self.skill_probability = list()
        self.perfect_detail = None

        self.simulation_cache = None

        self.custom_offset_cache = defaultdict(int)
        self.custom_abuse_enabled = False
        self.draw_custom_abuse = False

        self._setup_widget()

        eventbus.eventbus.register(self)

    def _setup_widget(self):
        self.widget = QWidget(self.parent)
        self.layout = QVBoxLayout(self.widget)

        self.info_widget = ChartViewerInfoWidget(self)
        self.info_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)
        self.layout.addWidget(self.info_widget)

        self.chart_widget = QScrollArea()
        self.chart_widget.setStyleSheet("background-color: #000000")
        self.chart_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)
        self.layout.addWidget(self.chart_widget)

    @subscribe(SendMusicEvent)
    def hook_music(self, event: SendMusicEvent):
        self.song_id = event.song_id
        self.difficulty = event.difficulty
        self.mirrored = eventbus.eventbus.post_and_get_first(GetMirrorFlagEvent())

        self.generator = BaseChartPicGenerator.get_generator(self.song_id, self.difficulty, self,
                                                             mirrored=self.mirrored)

        self.perfect_detail = None

        title, difficulty, level, total = get_song_info_from_id(self.song_id, self.difficulty)

        self.info_widget.subwidgets['song_title'].textbox[0].setText(title)
        self.info_widget.subwidgets['song_difficulty'].textbox[0].setText(difficulty)
        self.info_widget.subwidgets['song_difficulty'].textbox[0].setCursorPosition(0)
        self.info_widget.subwidgets['song_level'].textbox[0].setText(str(level))
        self.info_widget.subwidgets['song_notes'].textbox[0].setText(str(total))

        self.info_widget.subwidgets['mode_default'].setChecked(True)
        self.info_widget.subwidgets['mode_perfect'].setCheckable(False)
        self.info_widget.subwidgets['mode_abuse'].setCheckable(False)
        self.info_widget.subwidgets['mode_custom'].setCheckable(False)

        self.info_widget.subwidgets['custom_general_button_abuse'].setDisabled(True)
        self.custom_abuse_enabled = False

    @subscribe(HookAbuseToChartViewerEvent)
    def hook_abuse(self, event: HookAbuseToChartViewerEvent):
        if self.generator is None:
            return

        self.generator.hook_abuse(event.cards, event.abuse_df)
        self.info_widget.subwidgets['mode_abuse'].setCheckable(True)

        if dict_have_nonzero(self.custom_offset_cache) and dict_have_nonzero(self.generator.note_offsets):
            self.info_widget.subwidgets['custom_general_button_abuse'].setDisabled(False)
        self.custom_abuse_enabled = True

    @subscribe(CacheSimulationEvent)
    def cache_simulation_event(self, event: CacheSimulationEvent):
        self.simulation_cache = event.event

    @subscribe(HookSimResultToChartViewerEvent)
    def hook_simulation_result(self, event: HookSimResultToChartViewerEvent):
        if self.generator is None:
            return
        if self.song_id != event.song_id or self.difficulty != event.difficulty:
            return

        self.perfect_detail = event.perfect_detail
        self.set_skill_pics_inact_deact()

        if self.info_widget.subwidgets['mode_perfect'].isCheckable():
            self.info_widget.subwidgets['mode_custom'].setCheckable(True)

        if self.chart_mode != ChartMode.DEFAULT:
            self.generator.draw_chart(paint_skill=True)

    @subscribe(CustomSimulationResultEvent)
    def display_custom_simulation_result(self, event: CustomSimulationResultEvent):
        if self.song_id != event.live.score_id or self.difficulty != event.live.difficulty:
            return

        self.info_widget.subwidgets['custom_general_score_total'].textbox[0].setText(str(event.result.perfect_score))
        self.info_widget.subwidgets['custom_general_score_theoretic'].textbox[0].setText(
            str(int(event.result.abuse_score)))
        self.info_widget.subwidgets['custom_general_score_prob'].textbox[0].setText(
            "{:.2%}".format(event.result.full_roll_chance))

        self.perfect_detail = event.result.perfect_detail
        self.set_skill_pics_inact_deact()

        self.generator.hook_abuse(self.cards, event.result.abuse_data)

        self.generator.draw_chart(paint_skill=True)
        if self.draw_custom_abuse:
            self.generator.draw_chart(draw_abuse=True)
        set_stacked_widget_index(self.info_widget.subwidgets['detail'], 0)
        set_stacked_widget_index(self.info_widget.subwidgets['custom_detail'], 0)

        if dict_have_nonzero(self.custom_offset_cache) and dict_have_nonzero(self.generator.note_offsets):
            self.info_widget.subwidgets['custom_general_button_abuse'].setDisabled(False)

    def set_skill_pics_inact_deact(self):
        for card_num, skill_details in self.perfect_detail.skill_details.items():
            for act_idx, skill_detail in enumerate(skill_details):
                skills = self.generator.get_all_skills_of_index(card_num - 1, act_idx)
                for skill in skills:
                    skill.inact = skill_detail.inact
                    skill.deact = skill_detail.deact

    @subscribe(HookUnitToChartViewerEvent)
    def hook_unit(self, event: HookUnitToChartViewerEvent):
        if self.generator is None:
            return

        self.cards = event.cards
        unit_changed = self.generator.hook_cards(event.cards)

        self.info_widget.subwidgets['mode_perfect'].setCheckable(True)
        self.info_widget.subwidgets['mode_custom'].setCheckable(False)
        self.perfect_detail = None

        if unit_changed:
            if self.chart_mode == ChartMode.PERFECT:
                self.generator.draw_chart(paint_skill=True)
            elif self.chart_mode != ChartMode.DEFAULT:
                self.chart_mode = ChartMode.PERFECT
                self.info_widget.subwidgets['mode_perfect'].setChecked(True)

    @subscribe(ToggleMirrorEvent)
    def toggle_mirror(self, event: ToggleMirrorEvent):
        if self.generator is None:
            return

        self.generator = self.generator.mirror_generator(event.mirrored)

    def set_chart_mode(self):
        mode_id = self.info_widget.subwidgetgroups['mode_button'].checkedId()
        if self.chart_mode == ChartMode(mode_id):
            return
        else:
            self.reset_custom_setting()

            self.chart_mode = ChartMode(mode_id)
            if self.chart_mode == ChartMode.DEFAULT:
                self.generator.draw_chart()
            elif self.chart_mode == ChartMode.PERFECT:
                self.generator.draw_chart(paint_skill=True)
            elif self.chart_mode == ChartMode.ABUSE:
                self.generator.draw_chart(draw_abuse=True)
            elif self.chart_mode == ChartMode.CUSTOM:
                self.generator.draw_chart(paint_skill=True)
                self.simulate_custom()
                set_stacked_widget_index(self.info_widget.subwidgets['custom'], 1)

            self.show_detail_nothing()
            self.generator.pixmap_caches = [None] * self.generator.label_total

    def reset_custom_setting(self):
        set_stacked_widget_index(self.info_widget.subwidgets['custom'], 0)
        set_stacked_widget_index(self.info_widget.subwidgets['custom_detail'], 0)

        self.generator.deact_skills = {card_num: [] for card_num in range(1, 16)}
        self.generator.note_offsets = defaultdict(int)
        self.custom_offset_cache = defaultdict(int)

    def show_detail_nothing(self):
        set_stacked_widget_index(self.info_widget.subwidgets['detail'], 0)
        set_stacked_widget_index(self.info_widget.subwidgets['detail_note_score'], 0)
        set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 0)
        set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_inactivation'], 0)

        if self.chart_mode == ChartMode.CUSTOM:
            set_stacked_widget_index(self.info_widget.subwidgets['custom_detail'], 0)

    def show_detail_note_info(self, number: int):
        if self.perfect_detail is None:
            return

        note_detail = get_note_detail(self.perfect_detail.note_details, number)

        set_stacked_widget_index(self.info_widget.subwidgets['detail'], 1)

        self.info_widget.subwidgets['detail_note_general_number'].textbox[0].setText(str(number))
        self.info_widget.subwidgets['detail_note_general_time'].textbox[0].setText("{:.3f}".format(note_detail.time))
        self.info_widget.subwidgets['detail_note_general_type'].textbox[0].setText(str(note_detail.note_type))

        if self.chart_mode in (ChartMode.PERFECT, ChartMode.CUSTOM) \
                and note_detail.note_type != NoteType.DAMAGE and self.perfect_detail is not None:
            set_stacked_widget_index(self.info_widget.subwidgets['detail_note_score'], 1)
            self._show_detail_note_score_info(number)

            if self.chart_mode == ChartMode.CUSTOM:
                self._show_detail_note_custom_info(number)
        else:
            set_stacked_widget_index(self.info_widget.subwidgets['detail_note_score'], 0)

    def _show_detail_note_score_info(self, number: int):
        note_detail = get_note_detail(self.perfect_detail.note_details, number)

        self.info_widget.subwidgets['detail_note_score_general_life'].textbox[0].setText(str(note_detail.life))
        self.info_widget.subwidgets['detail_note_score_general_combo'].textbox[0].setText(
            "{} ({})".format(note_detail.combo, note_detail.weight))

        if note_detail.judgement == Judgement.PERFECT:
            score_bonus = note_detail.score_bonus
        else:
            score_bonus = note_detail.score_great_bonus
        self._show_detail_note_bonus_info("score", score_bonus)

        combo_bonus = note_detail.combo_bonus
        self._show_detail_note_bonus_info("combo", combo_bonus)

        self.info_widget.subwidgets['detail_note_score_general_note-score'].textbox[0].setText(str(note_detail.score))
        self.info_widget.subwidgets['detail_note_score_general_current-score'].textbox[0].setText(
            str(note_detail.cumulative_score))

    def _show_detail_note_bonus_info(self, widget_text: str, bonus: List[NoteDetailSkill]):
        bonus.sort(key=lambda skill: skill.lane)

        widget_name = 'detail_note_score_general_{}-bonus'.format(widget_text)
        sum_bonus = 1 + sum([skill.value / 100 for skill in bonus])
        self.info_widget.subwidgets[widget_name].textbox[0].setText("{:.2f}".format(sum_bonus))

        widget_name = 'detail_note_score_skill_{}'.format(widget_text)
        self.info_widget.subwidgets[widget_name].clear()
        for skill in bonus:
            item_skill = QTreeWidgetItem(self.info_widget.subwidgets[widget_name])
            skill_type_text = SKILL_BASE[skill.skill_type]['name']
            item_skill.setText(0, "[{}] {} : {}".format(skill.lane, skill_type_text, "{:+}%".format(skill.value)))

            if len(skill.boost) == 0:
                continue

            item_skill_child = QTreeWidgetItem(item_skill)
            item_skill_child.setText(0, "{} : {}".format(skill_type_text, "{:+}%".format(skill.pre_boost_value)))
            for boost in skill.boost:
                item_boost = QTreeWidgetItem(item_skill)
                item_boost.setText(0, "[{}] {} : ({})".format(boost.lane, SKILL_BASE[boost.skill_type]['name'],
                                                              "{:+}%".format(boost.value)))

    def _show_detail_note_custom_info(self, number: int):
        note_detail = get_note_detail(self.perfect_detail.note_details, number)

        set_stacked_widget_index(self.info_widget.subwidgets['custom_detail'], 2)

        self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].valueChanged.disconnect()
        left, right = 0, 0
        if note_detail.note_type == NoteType.TAP:
            left = -BAD_TAP_RANGE[Difficulty(self.difficulty)] // 1000
            right = -left + MISS_OFFSET
        elif note_detail.note_type in (NoteType.LONG, NoteType.FLICK):
            left = -BAD_NON_TAP_RANGE // 1000
            right = -left + MISS_OFFSET
        elif note_detail.note_type == NoteType.SLIDE:
            left = 0 if note_detail.checkpoint else -150
            right = 150 + MISS_OFFSET
        self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].setRange(left, right)
        offset = self.generator.note_offsets[number - 1]
        self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].setValue(offset)
        self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].valueChanged.connect(
            lambda: self.change_note_offset())

        self._set_custom_judgement_text(number, offset)

    def show_detail_damage_info(self, time: float):
        set_stacked_widget_index(self.info_widget.subwidgets['detail'], 1)

        self.info_widget.subwidgets['detail_note_general_number'].textbox[0].setText("-")
        self.info_widget.subwidgets['detail_note_general_time'].textbox[0].setText("{:.3f}".format(time))
        self.info_widget.subwidgets['detail_note_general_type'].textbox[0].setText("DAMAGE")

    def show_detail_skill_info(self, lane: int, idx: int):
        if self.perfect_detail is None:
            return

        skill_detail = self.perfect_detail.skill_details[lane][idx]

        set_stacked_widget_index(self.info_widget.subwidgets['detail'], 2)

        skill_type = skill_detail.skill_type

        self.info_widget.subwidgets['detail_skill_general_type'].textbox[0].setText(SKILL_BASE[skill_type]['name'])
        self.info_widget.subwidgets['detail_skill_general_time'].textbox[0].setText(
            "{:.1f} ~ {:.1f}".format(skill_detail.time_on, skill_detail.time_off))
        self.info_widget.subwidgets['detail_skill_general_prob'].textbox[0].setText(
            "{:.2%}".format(skill_detail.probability))
        self.info_widget.subwidgets['detail_skill_description'].textbox[0].setText(
            self.cards[lane - 1].sk.get_skill_description())

        if skill_detail.inact:
            set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 0)
            set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_inactivation'], 1)
            self.info_widget.subwidgets['detail_skill_general_prob'].textbox[0].setText("-")
            self.info_widget.subwidgets['detail_skill_inactivation_detail'].textbox[0].setText(
                SKILL_INACTIVATION_REASON[skill_detail.inact.value])
        elif skill_detail.deact:
            set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 0)
        else:
            if skill_type == 16:  # encore
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 1)
                encored_skill = skill_detail.encored_skill
                if encored_skill != (0, 0, 0):
                    self.info_widget.subwidgets['detail_skill_detail_encore_skill'].textbox[0].setText(
                        "[{}] {}".format(encored_skill[0], SKILL_BASE[encored_skill[1]]["name"]))
                    self.info_widget.subwidgets['detail_skill_detail_encore_time'].textbox[0].setText(
                        "{:.1f}".format(encored_skill[2]))
                else:
                    self.info_widget.subwidgets['detail_skill_detail_encore_skill'].textbox[0].setText("-")
                    self.info_widget.subwidgets['detail_skill_detail_encore_time'].textbox[0].setText("-")
            elif skill_type == 25:  # life sparkle
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 2)
                op = operator.lt if self.simulation_cache.left_inclusive else operator.le
                notes = self.generator.notes
                last_note_idx = notes.index[op(notes['sec'], skill_detail.time_on)].tolist()[-1]
                last_note = get_note_detail(self.perfect_detail.note_details, last_note_idx + 1)
                self.info_widget.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].setText(str(last_note.life))
                self.update_sparkle_value()
            elif skill_type in (35, 36, 37):  # motif
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 3)
                unit_idx = (lane - 1) // 5
                if skill_type == 35:
                    appeal = sum([card.vo for card in self.cards[unit_idx * 5: unit_idx * 5 + 5]])
                elif skill_type == 36:
                    appeal = sum([card.da for card in self.cards[unit_idx * 5: unit_idx * 5 + 5]])
                else:
                    appeal = sum([card.vi for card in self.cards[unit_idx * 5: unit_idx * 5 + 5]])
                self.info_widget.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].setText(str(appeal))
                self.update_motif_value()
            elif skill_type == 39:  # alternate
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 4)
                alt_bonus = skill_detail.amr_bonus

                note_types = ("tap", "long", "flick", "slide", "great")
                for note_type in note_types:
                    widget_name = "detail_skill_detail_alt_{}".format(note_type)
                    bonus = alt_bonus[note_type]
                    if bonus[0] == 0:
                        self.info_widget.subwidgets[widget_name].textbox[0].setText("-")
                        self.info_widget.subwidgets[widget_name].textbox[1].setText("-")
                        self.info_widget.subwidgets[widget_name].textbox[2].setText("-")
                    else:
                        self.info_widget.subwidgets[widget_name].textbox[0].setText(
                            "{:+}% ({:+}%)".format(bonus[0], bonus[1]))
                        self.info_widget.subwidgets[widget_name].textbox[1].setText(
                            "[{}] {}".format(bonus[2] + 1, SKILL_BASE[bonus[3]]['name']))
                        self.info_widget.subwidgets[widget_name].textbox[1].setCursorPosition(0)
                        self.info_widget.subwidgets[widget_name].textbox[2].setText(str(bonus[4]))
            elif skill_type == 40:  # refrain
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 5)
                ref_bonus = skill_detail.amr_bonus

                note_types = ("tap", "long", "flick", "slide", "great", "combo")
                for note_type in note_types:
                    widget_name = "detail_skill_detail_ref_{}".format(note_type)
                    bonus = ref_bonus[note_type]

                    if bonus[0] == 0:
                        self.info_widget.subwidgets[widget_name].textbox[0].setText("-")
                        self.info_widget.subwidgets[widget_name].textbox[1].setText("-")
                        self.info_widget.subwidgets[widget_name].textbox[2].setText("-")
                    else:
                        self.info_widget.subwidgets[widget_name].textbox[0].setText("{:+}%".format(bonus[0]))
                        self.info_widget.subwidgets[widget_name].textbox[1].setText(
                            "[{}] {}".format(bonus[2] + 1, SKILL_BASE[bonus[3]]['name']))
                        self.info_widget.subwidgets[widget_name].textbox[1].setCursorPosition(0)
                        self.info_widget.subwidgets[widget_name].textbox[2].setText(str(bonus[4]))
            elif skill_type == 41:  # magic
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 6)
                magic_bonus = skill_detail.magic_bonus

                note_types = ("tap", "long", "flick", "slide", "great")
                for note_type in note_types:
                    widget_name = "detail_skill_detail_magic_score_{}".format(note_type)
                    self.info_widget.subwidgets[widget_name].textbox[0].setText("{:+}%".format(magic_bonus[note_type]))

                combo_text = "{:+}%".format(magic_bonus['combo'])
                tooltip = ""
                if magic_bonus['sparkle'] != 0:
                    combo_text = "({:+}%)".format(max(magic_bonus['combo'], magic_bonus['sparkle']))
                    tooltip = "COMBO BONUS value from Life Sparkle can change while the skill is active."
                self.info_widget.subwidgets['detail_skill_detail_magic_score_combo'].textbox[0].setText(combo_text)
                self.info_widget.subwidgets['detail_skill_detail_magic_score_combo'].textbox[0].setToolTip(tooltip)

                life_text = "-{} / {:+}".format(magic_bonus['overload'], magic_bonus['life'])
                self.info_widget.subwidgets['detail_skill_detail_magic_score_life'].textbox[0].setText(life_text)

                support_text = str(Judgement(magic_bonus['perfect_support'])) if magic_bonus['perfect_support'] else "-"
                self.info_widget.subwidgets['detail_skill_detail_magic_middle_support_perfect'].textbox[0].setText(
                    support_text)
                support_text = str(Judgement(1 + magic_bonus['combo_support'])) if magic_bonus['combo_support'] else "-"
                self.info_widget.subwidgets['detail_skill_detail_magic_middle_support_combo'].textbox[0].setText(
                    support_text)

                boost_types = ("cu", "co", "pa")
                boost_attrs = ("score", "combo", "life", "support")
                for type_idx, boost_type in enumerate(boost_types):
                    for attr_idx, boost_attr in enumerate(boost_attrs):
                        widget_name = "detail_skill_detail_magic_middle_boost"
                        boost_text = "{:+}".format(magic_bonus["{}_{}".format(boost_type, boost_attr)])
                        if attr_idx < 3:
                            boost_text += "%"
                        self.info_widget.subwidgets[widget_name].textbox[type_idx + 1][attr_idx + 1].setText(boost_text)

                self.info_widget.subwidgets['detail_skill_detail_magic_misc_guard'].setChecked(magic_bonus['guard'])
                self.info_widget.subwidgets['detail_skill_detail_magic_misc_concentration'].setChecked(
                    magic_bonus['concentration'])
            elif skill_type == 42:  # mutual
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 7)
                mut_bonus = skill_detail.amr_bonus

                widget_name = "detail_skill_detail_mut_combo"
                bonus = mut_bonus['combo']
                if bonus[0] == 0:
                    self.info_widget.subwidgets[widget_name].textbox[0].setText("-")
                    self.info_widget.subwidgets[widget_name].textbox[1].setText("-")
                    self.info_widget.subwidgets[widget_name].textbox[2].setText("-")
                else:
                    self.info_widget.subwidgets[widget_name].textbox[0].setText(
                        "{:+}% ({:+}%)".format(bonus[0], bonus[1]))
                    self.info_widget.subwidgets[widget_name].textbox[1].setText(
                        "[{}] {}".format(bonus[2] + 1, SKILL_BASE[bonus[3]]['name']))
                    self.info_widget.subwidgets[widget_name].textbox[1].setCursorPosition(0)
                    self.info_widget.subwidgets[widget_name].textbox[2].setText(str(bonus[4]))
            else:
                set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_detail'], 0)

            set_stacked_widget_index(self.info_widget.subwidgets['detail_skill_inactivation'], 0)

        if self.chart_mode == ChartMode.CUSTOM:
            set_stacked_widget_index(self.info_widget.subwidgets['custom_detail'], 1)

            if skill_detail.inact:
                self.info_widget.subwidgets['custom_detail_skill_button'].setDisabled(True)
                self.info_widget.subwidgets['custom_detail_skill_status'].setText("-")
            else:
                self.info_widget.subwidgets['custom_detail_skill_button'].setDisabled(False)
                active_text = "Activated"
                if idx in self.generator.deact_skills[lane]:
                    active_text = "Not Activated"
                self.info_widget.subwidgets['custom_detail_skill_status'].setText(active_text)

    def update_sparkle_value(self):
        life = int(self.info_widget.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].text())

        rarity_ssr = self.cards[self.generator.selected_skill[0] - 1].sk.values[0] == 1
        query = "SELECT type_0{}_value FROM skill_life_value".format(1 if rarity_ssr else 2)
        sparkle_values = [_[0] for _ in db.masterdb.execute_and_fetchall(query)]

        life_trimmed = min(life // 10, len(sparkle_values) - 1)
        value = sparkle_values[life_trimmed]
        self.info_widget.subwidgets['detail_skill_detail_sparkle_combo'].textbox[0].setText("{:+}%".format(value - 100))

    def update_motif_value(self):
        appeal = int(self.info_widget.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].text())

        grand = len(self.cards) > 6
        query = "SELECT type_01_value FROM skill_motif_value{}".format("_grand" if grand else "")
        motif_values = [_[0] for _ in db.masterdb.execute_and_fetchall(query)]

        appeal_trimmed = min(appeal // 1000, len(motif_values) - 1)
        value = motif_values[int(appeal_trimmed)]
        self.info_widget.subwidgets['detail_skill_detail_motif_score'].textbox[0].setText("{:+}%".format(value - 100))

    def save_chart(self):
        self.generator.save_image()

    def change_note_offset(self):
        number = self.generator.selected_note
        offset = self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].value()
        self.generator.note_offsets[number - 1] = offset
        self._set_custom_judgement_text(number, offset)
        self.info_widget.subwidgets['custom_general_button_abuse'].setDisabled(True)

    def _set_custom_judgement_text(self, number: int, offset: int):
        note_detail = get_note_detail(self.perfect_detail.note_details, number)
        cached_offset = self.custom_offset_cache[number - 1]
        judgement_text = str(note_detail.judgement) if offset == cached_offset else "-"
        self.info_widget.subwidgets['custom_detail_note_judgement'].textbox[0].setText(judgement_text)

    def reset_note_offset(self):
        self.info_widget.subwidgets['custom_detail_note_offset-spinbox'].setValue(0)

    def change_skill_activation(self):
        card_num, act_idx = self.generator.selected_skill
        if act_idx in self.generator.deact_skills[card_num]:
            self.generator.deact_skills[card_num].remove(act_idx)
            self.info_widget.subwidgets['custom_detail_skill_status'].setText("Activated")
        else:
            self.generator.deact_skills[card_num].append(act_idx)
            self.info_widget.subwidgets['custom_detail_skill_status'].setText("Not Activated")

    def reset_custom_chart(self):
        self.reset_custom_setting()
        self.simulate_custom()
        self.generator.draw_chart(paint_skill=True)
        if self.draw_custom_abuse:
            self.generator.draw_chart(draw_abuse=True)
        self.show_detail_nothing()

    def simulate_custom(self):
        self.custom_offset_cache = self.generator.note_offsets.copy()
        eventbus.eventbus.post(CustomSimulationEvent(self.simulation_cache, self.generator.deact_skills,
                                                     self.generator.note_offsets))

    def toggle_custom_abuse(self):
        if self.draw_custom_abuse:
            self.draw_custom_abuse = False
            self.generator.draw_chart(paint_skill=True)
        else:
            self.draw_custom_abuse = True
            self.generator.draw_nothing_selected()
            self.generator.draw_chart(draw_abuse=True)
        self.show_detail_nothing()


class ChartViewerInfoWidget(QWidget):
    chart_viewer: ChartViewer
    layout: QVBoxLayout
    subwidgets: Dict[str, Any]
    sublayouts: Dict[str, Union[QVBoxLayout, QHBoxLayout, QGridLayout]]
    subwidgetgroups: Dict[str, Any]

    def __init__(self, viewer, *args):
        super().__init__(*args)
        self.chart_viewer = viewer

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)

        self.subwidgets = dict()
        self.sublayouts = dict()
        self.subwidgetgroups = dict()

        self._setup_song_info()
        self._setup_chart_mode()
        self._setup_custom()
        self._setup_note_skill_detail()

    def _setup_song_info(self):
        self.sublayouts['song'] = QHBoxLayout()
        self.sublayouts['song'].setSpacing(6)
        self.layout.addLayout(self.sublayouts['song'])
        self.layout.addSpacing(12)

        self.subwidgets['song_title'] = QLabelTextLineWidget("Title", halign=Qt.AlignLeft)
        self.sublayouts['song'].addWidget(self.subwidgets['song_title'], 9)

        self.subwidgets['song_difficulty'] = QLabelTextLineWidget("Difficulty")
        self.sublayouts['song'].addWidget(self.subwidgets['song_difficulty'], 2)

        self.subwidgets['song_level'] = QLabelTextLineWidget("Level")
        self.sublayouts['song'].addWidget(self.subwidgets['song_level'], 2)

        self.subwidgets['song_notes'] = QLabelTextLineWidget("Notes")
        self.sublayouts['song'].addWidget(self.subwidgets['song_notes'], 2)

        self.subwidgets['song_save'] = QPushButton("Save")
        self.subwidgets['song_save'].clicked.connect(lambda: self.chart_viewer.save_chart())
        self.subwidgets['song_save'].setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.sublayouts['song'].addWidget(self.subwidgets['song_save'], 2)

    def _setup_chart_mode(self):
        self.sublayouts['mode'] = QHBoxLayout()
        self.sublayouts['mode'].setSpacing(6)
        self.layout.addLayout(self.sublayouts['mode'])

        self.subwidgetgroups['mode_button'] = QButtonGroup(self)

        self.sublayouts['mode'].addStretch(1)

        self.subwidgets['mode_label'] = QLabel('Chart Mode')
        self.sublayouts['mode'].addWidget(self.subwidgets['mode_label'], 2)

        self.subwidgets['mode_default'] = QRadioButton('Default')
        self.subwidgets['mode_default'].setChecked(True)
        self.subwidgets['mode_default'].toggled.connect(self.chart_viewer.set_chart_mode)
        self.subwidgetgroups['mode_button'].addButton(self.subwidgets['mode_default'], 0)
        self.sublayouts['mode'].addWidget(self.subwidgets['mode_default'], 2)

        self.subwidgets['mode_perfect'] = QRadioButton('Perfect')
        self.subwidgets['mode_perfect'].setCheckable(False)
        self.subwidgets['mode_perfect'].toggled.connect(self.chart_viewer.set_chart_mode)
        self.subwidgetgroups['mode_button'].addButton(self.subwidgets['mode_perfect'], 1)
        self.sublayouts['mode'].addWidget(self.subwidgets['mode_perfect'], 2)

        self.subwidgets['mode_abuse'] = QRadioButton('Abuse')
        self.subwidgets['mode_abuse'].setCheckable(False)
        self.subwidgets['mode_abuse'].toggled.connect(self.chart_viewer.set_chart_mode)
        self.subwidgetgroups['mode_button'].addButton(self.subwidgets['mode_abuse'], 2)
        self.sublayouts['mode'].addWidget(self.subwidgets['mode_abuse'], 2)

        self.subwidgets['mode_custom'] = QRadioButton('Custom')
        self.subwidgets['mode_custom'].setCheckable(False)
        self.subwidgets['mode_custom'].toggled.connect(self.chart_viewer.set_chart_mode)
        self.subwidgetgroups['mode_button'].addButton(self.subwidgets['mode_custom'], 3)
        self.sublayouts['mode'].addWidget(self.subwidgets['mode_custom'], 2)

    def _setup_custom(self):
        self.subwidgets['custom'] = QStackedWidget()
        self.subwidgets['custom'].setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.layout.addWidget(self.subwidgets['custom'])

        self.subwidgets['custom'].addWidget(QWidget())
        self.subwidgets['custom'].setCurrentIndex(0)

        self.subwidgets['custom_'] = QWidget()
        self.sublayouts['custom_'] = QVBoxLayout(self.subwidgets['custom_'])
        self.sublayouts['custom_'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['custom'].addWidget(self.subwidgets['custom_'])

        self.sublayouts['custom_'].addSpacing(6)

        self.sublayouts['custom_general'] = QHBoxLayout()
        self.sublayouts['custom_'].addLayout(self.sublayouts['custom_general'])

        self.sublayouts['custom_general_score'] = QHBoxLayout()
        self.sublayouts['custom_general'].addLayout(self.sublayouts['custom_general_score'])

        self.subwidgets['custom_general_score_total'] = QLabelTextLineWidget("Total Score")
        self.subwidgets['custom_general_score_total'].textbox[0].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.sublayouts['custom_general_score'].addWidget(self.subwidgets['custom_general_score_total'])

        self.subwidgets['custom_general_score_theoretic'] = QLabelTextLineWidget("Theoretical Score")
        self.subwidgets['custom_general_score_theoretic'].textbox[0].setSizePolicy(QSizePolicy.Minimum,
                                                                                   QSizePolicy.Fixed)
        self.sublayouts['custom_general_score'].addWidget(self.subwidgets['custom_general_score_theoretic'])

        self.subwidgets['custom_general_score_prob'] = QLabelTextLineWidget("Probability")
        self.subwidgets['custom_general_score_prob'].textbox[0].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.sublayouts['custom_general_score'].addWidget(self.subwidgets['custom_general_score_prob'])

        self.sublayouts['custom_general_button'] = QGridLayout()
        self.sublayouts['custom_general'].addLayout(self.sublayouts['custom_general_button'])

        self.subwidgets['custom_general_button_update'] = QPushButton("Update")
        self.subwidgets['custom_general_button_update'].clicked.connect(lambda: self.chart_viewer.simulate_custom())
        self.sublayouts['custom_general_button'].addWidget(self.subwidgets['custom_general_button_update'], 0, 0, 1, 2)

        self.subwidgets['custom_general_button_reset'] = QPushButton("Reset All")
        self.subwidgets['custom_general_button_reset'].clicked.connect(
            lambda: self.chart_viewer.reset_custom_chart())
        self.sublayouts['custom_general_button'].addWidget(self.subwidgets['custom_general_button_reset'], 1, 0, 1, 1)

        self.subwidgets['custom_general_button_abuse'] = QPushButton("Toggle abuse")
        self.subwidgets['custom_general_button_abuse'].clicked.connect(
            lambda: self.chart_viewer.toggle_custom_abuse())
        self.sublayouts['custom_general_button'].addWidget(self.subwidgets['custom_general_button_abuse'], 1, 1, 1, 1)

        self.subwidgets['custom_detail'] = QStackedWidget()
        self.sublayouts['custom_'].addWidget(self.subwidgets['custom_detail'])

        self.subwidgets['custom_detail'].addWidget(QWidget())

        self.subwidgets['custom_detail_skill'] = QWidget()
        self.sublayouts['custom_detail_skill'] = QHBoxLayout(self.subwidgets['custom_detail_skill'])
        self.sublayouts['custom_detail_skill'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['custom_detail'].addWidget(self.subwidgets['custom_detail_skill'])

        self.subwidgets['custom_detail_skill_status'] = QLineReadOnly()
        self.subwidgets['custom_detail_skill_status'].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.sublayouts['custom_detail_skill'].addWidget(self.subwidgets['custom_detail_skill_status'])

        self.subwidgets['custom_detail_skill_button'] = QPushButton("Change Activation")
        self.subwidgets['custom_detail_skill_button'].clicked.connect(
            lambda: self.chart_viewer.change_skill_activation())
        self.sublayouts['custom_detail_skill'].addWidget(self.subwidgets['custom_detail_skill_button'])

        self.subwidgets['custom_detail_note'] = QWidget()
        self.sublayouts['custom_detail_note'] = QHBoxLayout(self.subwidgets['custom_detail_note'])
        self.sublayouts['custom_detail_note'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['custom_detail'].addWidget(self.subwidgets['custom_detail_note'])

        self.subwidgets['custom_detail_note_offset-label'] = QLabel("Offset")
        self.subwidgets['custom_detail_note_offset-label'].setAlignment(Qt.AlignCenter)
        self.subwidgets['custom_detail_note_offset-label'].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.sublayouts['custom_detail_note'].addWidget(self.subwidgets['custom_detail_note_offset-label'], 1)

        self.subwidgets['custom_detail_note_offset-spinbox'] = QSpinBox()
        self.subwidgets['custom_detail_note_offset-spinbox'].setAlignment(Qt.AlignCenter)
        self.subwidgets['custom_detail_note_offset-spinbox'].setSingleStep(10)
        self.subwidgets['custom_detail_note_offset-spinbox'].setRange(0, 0)
        self.subwidgets['custom_detail_note_offset-spinbox'].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.subwidgets['custom_detail_note_offset-spinbox'].valueChanged.connect(
            lambda: self.chart_viewer.change_note_offset())
        self.sublayouts['custom_detail_note'].addWidget(self.subwidgets['custom_detail_note_offset-spinbox'], 1)

        self.subwidgets['custom_detail_note_judgement'] = QLabelTextLineWidget("Judgement", horizontal=True)
        self.subwidgets['custom_detail_note_judgement'].layout.setStretch(0, 1)
        self.subwidgets['custom_detail_note_judgement'].layout.setStretch(1, 2)
        self.sublayouts['custom_detail_note'].addWidget(self.subwidgets['custom_detail_note_judgement'], 3)

        self.subwidgets['custom_detail_note_reset'] = QPushButton("Reset")
        self.subwidgets['custom_detail_note_reset'].clicked.connect(lambda: self.chart_viewer.reset_note_offset())
        self.sublayouts['custom_detail_note'].addWidget(self.subwidgets['custom_detail_note_reset'], 1)

        resize_stacked_widget(self.subwidgets['custom_detail'], 0)

        resize_stacked_widget(self.subwidgets['custom'], 0)

    def _setup_note_skill_detail(self):
        self.subwidgets['detail'] = QStackedWidget()
        self.subwidgets['detail'].setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.layout.addWidget(self.subwidgets['detail'])

        self.subwidgets['detail'].addWidget(QWidget())

        self.subwidgets['detail_note'] = QWidget()
        self.sublayouts['detail_note'] = QVBoxLayout(self.subwidgets['detail_note'])
        self.sublayouts['detail_note'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail'].addWidget(self.subwidgets['detail_note'])

        self.sublayouts['detail_note'].addSpacing(6)

        self.sublayouts['detail_note_general'] = QHBoxLayout()
        self.sublayouts['detail_note'].addLayout(self.sublayouts['detail_note_general'])

        self.subwidgets['detail_note_general_number'] = QLabelTextLineWidget("Note Number")
        self.sublayouts['detail_note_general'].addWidget(self.subwidgets['detail_note_general_number'])

        self.subwidgets['detail_note_general_time'] = QLabelTextLineWidget("Note Time")
        self.sublayouts['detail_note_general'].addWidget(self.subwidgets['detail_note_general_time'])

        self.subwidgets['detail_note_general_type'] = QLabelTextLineWidget("Note Type")
        self.sublayouts['detail_note_general'].addWidget(self.subwidgets['detail_note_general_type'])

        self.subwidgets['detail_note_score'] = QStackedWidget()
        self.sublayouts['detail_note'].addWidget(self.subwidgets['detail_note_score'])

        self.subwidgets['detail_note_score'].addWidget(QWidget())
        self.subwidgets['detail_note_score'].setCurrentIndex(0)

        self.subwidgets['detail_note_score_'] = QWidget()
        self.sublayouts['detail_note_score_'] = QVBoxLayout(self.subwidgets['detail_note_score_'])
        self.sublayouts['detail_note_score_'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_note_score'].addWidget(self.subwidgets['detail_note_score_'])

        self.sublayouts['detail_note_score_general'] = QHBoxLayout()
        self.sublayouts['detail_note_score_'].addLayout(self.sublayouts['detail_note_score_general'])

        self.subwidgets['detail_note_score_general_life'] = QLabelTextLineWidget("Life")
        self.sublayouts['detail_note_score_general'].addWidget(self.subwidgets['detail_note_score_general_life'])

        self.subwidgets['detail_note_score_general_combo'] = QLabelTextLineWidget("Combo")
        self.sublayouts['detail_note_score_general'].addWidget(self.subwidgets['detail_note_score_general_combo'])

        self.subwidgets['detail_note_score_general_score-bonus'] = QLabelTextLineWidget("Score bonus")
        self.sublayouts['detail_note_score_general'].addWidget(self.subwidgets['detail_note_score_general_score-bonus'])

        self.subwidgets['detail_note_score_general_combo-bonus'] = QLabelTextLineWidget("Combo bonus")
        self.sublayouts['detail_note_score_general'].addWidget(self.subwidgets['detail_note_score_general_combo-bonus'])

        self.subwidgets['detail_note_score_general_note-score'] = QLabelTextLineWidget("Note Score")
        self.sublayouts['detail_note_score_general'].addWidget(self.subwidgets['detail_note_score_general_note-score'])

        self.subwidgets['detail_note_score_general_current-score'] = QLabelTextLineWidget("Current Score")
        self.sublayouts['detail_note_score_general'].addWidget(
            self.subwidgets['detail_note_score_general_current-score'])

        self.sublayouts['detail_note_score_skill'] = QHBoxLayout()
        self.sublayouts['detail_note_score_'].addLayout(self.sublayouts['detail_note_score_skill'])

        self.subwidgets['detail_note_score_skill_score'] = QTreeWidget()
        self.subwidgets['detail_note_score_skill_score'].header().setVisible(False)
        self.subwidgets['detail_note_score_skill_score'].setFixedHeight(70)
        self.subwidgets['detail_note_score_skill_score'].setTextElideMode(Qt.ElideMiddle)
        self.sublayouts['detail_note_score_skill'].addWidget(self.subwidgets['detail_note_score_skill_score'])

        self.subwidgets['detail_note_score_skill_combo'] = QTreeWidget()
        self.subwidgets['detail_note_score_skill_combo'].header().setVisible(False)
        self.subwidgets['detail_note_score_skill_combo'].setFixedHeight(70)
        self.subwidgets['detail_note_score_skill_combo'].setTextElideMode(Qt.ElideMiddle)
        self.sublayouts['detail_note_score_skill'].addWidget(self.subwidgets['detail_note_score_skill_combo'])

        resize_stacked_widget(self.subwidgets['detail_note_score'], 0)

        self.subwidgets['detail_skill'] = QWidget()
        self.sublayouts['detail_skill'] = QVBoxLayout(self.subwidgets['detail_skill'])
        self.sublayouts['detail_skill'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail'].addWidget(self.subwidgets['detail_skill'])

        self.sublayouts['detail_skill'].addSpacing(6)

        self.sublayouts['detail_skill_general'] = QHBoxLayout()
        self.sublayouts['detail_skill'].addLayout(self.sublayouts['detail_skill_general'])

        self.subwidgets['detail_skill_general_type'] = QLabelTextLineWidget("Skill Type")
        self.sublayouts['detail_skill_general'].addWidget(self.subwidgets['detail_skill_general_type'])

        self.subwidgets['detail_skill_general_time'] = QLabelTextLineWidget("Skill Time")
        self.sublayouts['detail_skill_general'].addWidget(self.subwidgets['detail_skill_general_time'])

        self.subwidgets['detail_skill_general_prob'] = QLabelTextLineWidget("Probability")
        self.sublayouts['detail_skill_general'].addWidget(self.subwidgets['detail_skill_general_prob'])

        self.sublayouts['detail_skill'].addSpacing(6)

        self.subwidgets['detail_skill_description'] = QLabelTextBoxWidget("Effect")
        fm = QFontMetrics(self.subwidgets['detail_skill_description'].textbox[0].font())
        self.subwidgets['detail_skill_description'].textbox[0].setMaximumHeight(fm.height() * 2 + fm.leading() + 10)
        self.sublayouts['detail_skill'].addWidget(self.subwidgets['detail_skill_description'])

        self.subwidgets['detail_skill_detail'] = QStackedWidget()
        self.subwidgets['detail_skill_detail'].setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.sublayouts['detail_skill'].addWidget(self.subwidgets['detail_skill_detail'])

        self.subwidgets['detail_skill_detail'].addWidget(QWidget())
        self.subwidgets['detail_skill_detail'].setCurrentIndex(0)

        self.subwidgets['detail_skill_detail_encore'] = QWidget()
        self.sublayouts['detail_skill_detail_encore'] = QHBoxLayout(self.subwidgets['detail_skill_detail_encore'])
        self.sublayouts['detail_skill_detail_encore'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_encore'])

        self.subwidgets['detail_skill_detail_encore_skill'] = QLabelTextLineWidget("Encored skill : ", horizontal=True)
        self.sublayouts['detail_skill_detail_encore'].addWidget(self.subwidgets['detail_skill_detail_encore_skill'], 4)

        self.subwidgets['detail_skill_detail_encore_time'] = QLabelTextLineWidget("which was activated at",
                                                                                  horizontal=True)
        self.subwidgets['detail_skill_detail_encore_time'].layout.setStretch(0, 2)
        self.subwidgets['detail_skill_detail_encore_time'].layout.setStretch(1, 1)
        self.sublayouts['detail_skill_detail_encore'].addWidget(self.subwidgets['detail_skill_detail_encore_time'], 3)

        self.subwidgets['detail_skill_detail_sparkle'] = QWidget()
        self.sublayouts['detail_skill_detail_sparkle'] = QHBoxLayout(self.subwidgets['detail_skill_detail_sparkle'])
        self.sublayouts['detail_skill_detail_sparkle'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_sparkle'])

        self.subwidgets['detail_skill_detail_sparkle_life'] = QLabelTextLineWidget("Current life :", horizontal=True)
        self.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].setSizePolicy(QSizePolicy.Preferred,
                                                                                     QSizePolicy.Fixed)
        self.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].setToolTip(
            "Life Sparkle COMBO BONUS UP value can change while the skill is active.\n" +
            "The default value shown here is the life value at the moment of skill activation.")
        self.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].setReadOnly(False)
        self.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].setValidator(QIntValidator(1, 2000, None))
        self.subwidgets['detail_skill_detail_sparkle_life'].textbox[0].textEdited.connect(
            lambda: self.chart_viewer.update_sparkle_value())
        self.sublayouts['detail_skill_detail_sparkle'].addWidget(self.subwidgets['detail_skill_detail_sparkle_life'])

        self.sublayouts['detail_skill_detail_sparkle'].addSpacing(12)

        self.subwidgets['detail_skill_detail_sparkle_combo'] = QLabelTextLineWidget("Life Sparkle COMBO BONUS :",
                                                                                    horizontal=True)
        self.subwidgets['detail_skill_detail_sparkle_combo'].textbox[0].setSizePolicy(QSizePolicy.Preferred,
                                                                                      QSizePolicy.Fixed)
        self.sublayouts['detail_skill_detail_sparkle'].addWidget(self.subwidgets['detail_skill_detail_sparkle_combo'])

        self.subwidgets['detail_skill_detail_motif'] = QWidget()
        self.sublayouts['detail_skill_detail_motif'] = QHBoxLayout(self.subwidgets['detail_skill_detail_motif'])
        self.sublayouts['detail_skill_detail_motif'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_motif'])

        self.subwidgets['detail_skill_detail_motif_appeal'] = QLabelTextLineWidget("Appeal of the unit :",
                                                                                   horizontal=True)
        self.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].setSizePolicy(QSizePolicy.Preferred,
                                                                                     QSizePolicy.Fixed)
        self.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].setReadOnly(False)
        self.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].setValidator(QIntValidator(0, 99999, None))
        self.subwidgets['detail_skill_detail_motif_appeal'].textbox[0].textEdited.connect(
            lambda: self.chart_viewer.update_motif_value())
        self.sublayouts['detail_skill_detail_motif'].addWidget(self.subwidgets['detail_skill_detail_motif_appeal'])

        self.sublayouts['detail_skill_detail_motif'].addSpacing(12)

        self.subwidgets['detail_skill_detail_motif_score'] = QLabelTextLineWidget("Motif SCORE UP :", horizontal=True)
        self.subwidgets['detail_skill_detail_motif_score'].textbox[0].setSizePolicy(QSizePolicy.Preferred,
                                                                                    QSizePolicy.Fixed)
        self.sublayouts['detail_skill_detail_motif'].addWidget(self.subwidgets['detail_skill_detail_motif_score'])

        self.subwidgets['detail_skill_detail_alt'] = QWidget()
        self.sublayouts['detail_skill_detail_alt'] = QHBoxLayout(self.subwidgets['detail_skill_detail_alt'])
        self.sublayouts['detail_skill_detail_alt'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_alt'])

        self.subwidgets['detail_skill_detail_alt_tap'] = QLabelTextLineWidget("TAP", box_num=3)
        self.sublayouts['detail_skill_detail_alt'].addWidget(self.subwidgets['detail_skill_detail_alt_tap'])

        self.subwidgets['detail_skill_detail_alt_long'] = QLabelTextLineWidget("LONG", box_num=3)
        self.sublayouts['detail_skill_detail_alt'].addWidget(self.subwidgets['detail_skill_detail_alt_long'])

        self.subwidgets['detail_skill_detail_alt_flick'] = QLabelTextLineWidget("FLICK", box_num=3)
        self.sublayouts['detail_skill_detail_alt'].addWidget(self.subwidgets['detail_skill_detail_alt_flick'])

        self.subwidgets['detail_skill_detail_alt_slide'] = QLabelTextLineWidget("SLIDE", box_num=3)
        self.sublayouts['detail_skill_detail_alt'].addWidget(self.subwidgets['detail_skill_detail_alt_slide'])

        self.subwidgets['detail_skill_detail_alt_great'] = QLabelTextLineWidget("GREAT", box_num=3)
        self.sublayouts['detail_skill_detail_alt'].addWidget(self.subwidgets['detail_skill_detail_alt_great'])

        self.subwidgets['detail_skill_detail_ref'] = QWidget()
        self.sublayouts['detail_skill_detail_ref'] = QHBoxLayout(self.subwidgets['detail_skill_detail_ref'])
        self.sublayouts['detail_skill_detail_ref'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_ref'])

        self.subwidgets['detail_skill_detail_ref_tap'] = QLabelTextLineWidget("TAP", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_tap'])

        self.subwidgets['detail_skill_detail_ref_long'] = QLabelTextLineWidget("LONG", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_long'])

        self.subwidgets['detail_skill_detail_ref_flick'] = QLabelTextLineWidget("FLICK", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_flick'])

        self.subwidgets['detail_skill_detail_ref_slide'] = QLabelTextLineWidget("SLIDE", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_slide'])

        self.subwidgets['detail_skill_detail_ref_great'] = QLabelTextLineWidget("GREAT", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_great'])

        self.subwidgets['detail_skill_detail_ref_combo'] = QLabelTextLineWidget("COMBO", box_num=3)
        self.sublayouts['detail_skill_detail_ref'].addWidget(self.subwidgets['detail_skill_detail_ref_combo'])

        self.subwidgets['detail_skill_detail_magic'] = QWidget()
        self.sublayouts['detail_skill_detail_magic'] = QVBoxLayout(self.subwidgets['detail_skill_detail_magic'])
        self.sublayouts['detail_skill_detail_magic'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_magic'])

        self.sublayouts['detail_skill_detail_magic_score'] = QHBoxLayout()
        self.sublayouts['detail_skill_detail_magic'].addLayout(self.sublayouts['detail_skill_detail_magic_score'])

        self.subwidgets['detail_skill_detail_magic_score_tap'] = QLabelTextLineWidget("TAP")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_tap'])

        self.subwidgets['detail_skill_detail_magic_score_long'] = QLabelTextLineWidget("LONG")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_long'])

        self.subwidgets['detail_skill_detail_magic_score_flick'] = QLabelTextLineWidget("FLICK")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_flick'])

        self.subwidgets['detail_skill_detail_magic_score_slide'] = QLabelTextLineWidget("SLIDE")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_slide'])

        self.subwidgets['detail_skill_detail_magic_score_great'] = QLabelTextLineWidget("GREAT")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_great'])

        self.subwidgets['detail_skill_detail_magic_score_combo'] = QLabelTextLineWidget("COMBO")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_combo'])

        self.subwidgets['detail_skill_detail_magic_score_life'] = QLabelTextLineWidget("LIFE")
        self.subwidgets['detail_skill_detail_magic_score_life'].textbox[0].setToolTip(
            "Life consumed on skill activation / Life recovered on PERFECT note")
        self.sublayouts['detail_skill_detail_magic_score'].addWidget(
            self.subwidgets['detail_skill_detail_magic_score_life'])

        self.sublayouts['detail_skill_detail_magic'].addSpacing(8)

        self.sublayouts['detail_skill_detail_magic_middle'] = QHBoxLayout()
        self.sublayouts['detail_skill_detail_magic'].addLayout(self.sublayouts['detail_skill_detail_magic_middle'])

        self.sublayouts['detail_skill_detail_magic_middle_support'] = QVBoxLayout()
        self.sublayouts['detail_skill_detail_magic_middle'].addLayout(
            self.sublayouts['detail_skill_detail_magic_middle_support'])

        self.subwidgets['detail_skill_detail_magic_middle_support_perfect'] = QLabelTextLineWidget("PERFECT SUPPORT")
        self.sublayouts['detail_skill_detail_magic_middle_support'].addWidget(
            self.subwidgets['detail_skill_detail_magic_middle_support_perfect'])

        self.sublayouts['detail_skill_detail_magic_middle_support'].addSpacing(4)

        self.subwidgets['detail_skill_detail_magic_middle_support_combo'] = QLabelTextLineWidget("COMBO SUPPORT")
        self.sublayouts['detail_skill_detail_magic_middle_support'].addWidget(
            self.subwidgets['detail_skill_detail_magic_middle_support_combo'])

        self.sublayouts['detail_skill_detail_magic_middle'].addSpacing(8)

        self.subwidgets['detail_skill_detail_magic_middle_boost'] = QLabelTextGridWidget(["CUTE", "COOL", "PASSION"],
                                                                                         ["SCORE", "COMBO", "LIFE",
                                                                                          "SUPPORT"])
        self.sublayouts['detail_skill_detail_magic_middle'].addWidget(
            self.subwidgets['detail_skill_detail_magic_middle_boost'])

        self.sublayouts['detail_skill_detail_magic'].addSpacing(8)

        self.sublayouts['detail_skill_detail_magic_misc'] = QHBoxLayout()
        self.sublayouts['detail_skill_detail_magic'].addLayout(self.sublayouts['detail_skill_detail_magic_misc'])

        self.subwidgets['detail_skill_detail_magic_misc_guard'] = QCheckBoxReadOnly("Prevent life decrease")
        self.subwidgets['detail_skill_detail_magic_misc_guard'].setStyleSheet("margin-left:50%; margin-right:50%;")
        self.sublayouts['detail_skill_detail_magic_misc'].addWidget(
            self.subwidgets['detail_skill_detail_magic_misc_guard'])

        self.subwidgets['detail_skill_detail_magic_misc_concentration'] = QCheckBoxReadOnly(
            "Halve PERFECT timing window")
        self.subwidgets['detail_skill_detail_magic_misc_concentration'].setStyleSheet(
            "margin-left:10%; margin-right:10%;")
        self.sublayouts['detail_skill_detail_magic_misc'].addWidget(
            self.subwidgets['detail_skill_detail_magic_misc_concentration'])

        self.subwidgets['detail_skill_detail_mut'] = QWidget()
        self.sublayouts['detail_skill_detail_mut'] = QHBoxLayout(self.subwidgets['detail_skill_detail_mut'])
        self.sublayouts['detail_skill_detail_mut'].setContentsMargins(0, 6, 0, 0)
        self.subwidgets['detail_skill_detail'].addWidget(self.subwidgets['detail_skill_detail_mut'])

        self.subwidgets['detail_skill_detail_mut_combo'] = QLabelTextLineWidget("COMBO BONUS", box_num=3,
                                                                                horizontal=True)
        self.sublayouts['detail_skill_detail_mut'].addWidget(self.subwidgets['detail_skill_detail_mut_combo'])

        resize_stacked_widget(self.subwidgets['detail_skill_detail'], 0)

        self.subwidgets['detail_skill_inactivation'] = QStackedWidget()
        self.subwidgets['detail_skill_inactivation'].setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.sublayouts['detail_skill'].addWidget(self.subwidgets['detail_skill_inactivation'])

        self.subwidgets['detail_skill_inactivation'].addWidget(QWidget())
        self.subwidgets['detail_skill_inactivation'].setCurrentIndex(0)

        self.subwidgets['detail_skill_inactivation_detail'] = QLabelTextLineWidget(
            "[！] This skill does not activate because of the following reason:")
        self.subwidgets['detail_skill_inactivation'].addWidget(self.subwidgets['detail_skill_inactivation_detail'])

        resize_stacked_widget(self.subwidgets['detail_skill_inactivation'], 0)

        resize_stacked_widget(self.subwidgets['detail'], 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        delta = event.oldSize().height() - self.height()
        chart_widget = self.chart_viewer.chart_widget
        chart_widget.verticalScrollBar().setValue(chart_widget.verticalScrollBar().value() - delta)


class QLineReadOnly(QLineEdit):
    def __init__(self, halign=Qt.AlignHCenter, *args):
        super().__init__(*args)

        self.setReadOnly(True)
        self.setAlignment(halign)
        self.setCursorPosition(0)


class QLabelTextLineWidget(QWidget):
    def __init__(self, label_text: str, halign=Qt.AlignHCenter, box_num: int = 1, horizontal: bool = False, *args):
        super().__init__(*args)

        self.layout = QVBoxLayout(self) if not horizontal else QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)

        self.textbox = list()
        self._setup_textbox(halign, box_num)

    def _setup_textbox(self, halign, box_num: int):
        for i in range(box_num):
            self.textbox.append(QLineReadOnly(halign=halign))
            self.layout.addWidget(self.textbox[i])


class QLabelTextBoxWidget(QLabelTextLineWidget):
    def _setup_textbox(self, halign, box_num: int):
        for i in range(box_num):
            self.textbox.append(QTextEdit())
            self.textbox[i].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.textbox[i].setReadOnly(True)
            self.textbox[i].setAlignment(Qt.AlignCenter)
            self.layout.addWidget(self.textbox[i])


class QLabelTextGridWidget(QWidget):
    def __init__(self, row_label: List[str], column_label: List[str], *args):
        super().__init__(*args)

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self._setup_label(row_label, True)
        self._setup_label(column_label, False)

        self.textbox = [[]]
        self._setup_textbox()

    def _setup_label(self, labels: List[str], is_row: bool = True):
        for index, text in enumerate(labels):
            label_widget = QLabel(text)
            label_widget.setAlignment(Qt.AlignCenter)
            if is_row:
                self.layout.addWidget(label_widget, index + 1, 0)
            else:
                self.layout.addWidget(label_widget, 0, index + 1)

    def _setup_textbox(self):
        row_count = self.layout.rowCount()
        column_count = self.layout.columnCount()
        for row in range(1, row_count):
            self.textbox.append([None])
            for column in range(1, column_count):
                self.textbox[row].append(QLineReadOnly())
                self.layout.addWidget(self.textbox[row][column], row, column)


class QCheckBoxReadOnly(QCheckBox):
    def __init__(self, *args):
        super().__init__(*args)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)


def set_stacked_widget_index(widget: QStackedWidget, idx: int):
    resize_stacked_widget(widget, idx)
    widget.setCurrentIndex(idx)
    if idx == 0:
        widget.hide()
    else:
        widget.show()


def resize_stacked_widget(widget: QStackedWidget, idx: int):
    for i in range(widget.count()):
        if i == idx:
            widget.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        else:
            widget.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)


def get_song_info_from_id(song_id: int, diff: Difficulty) -> Tuple[str, str, str, str]:
    data = db.cachedb.execute_and_fetchone("""
                SELECT  name,
                        level,
                        CAST(Tap + Long + Flick + Slide AS INTEGER)
                FROM live_detail_cache WHERE live_id = ? AND difficulty = ?
            """, [song_id, diff.value])
    diff_text = db.cachedb.execute_and_fetchone("SELECT text FROM difficulty_text WHERE id = ?", [diff.value])
    return data[0], diff_text[0], data[1], data[2]


def dict_have_nonzero(d: dict) -> bool:
    return len(d) == 0 or not any(d.values())
