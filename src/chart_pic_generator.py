from __future__ import annotations

import math
import os
from abc import abstractmethod, ABC
from collections import defaultdict
from typing import Optional, TYPE_CHECKING, Dict, List, DefaultDict, Tuple

from PyQt5.QtCore import Qt, QPoint, QRectF, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QFont, QBrush, QPainterPath, qRgba, QPolygonF
from PyQt5.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget
from pandas import DataFrame

from exceptions import InvalidUnit
from logic.card import Card
from logic.grandunit import GrandUnit
from logic.live import fetch_chart
from logic.unit import Unit
from settings import RHYTHM_ICONS_PATH, CHART_PICS_PATH
from statemachine import AbuseData
from static.judgement import Judgement
from static.note_type import NoteType
from static.skill import SKILL_BASE
from static.song_difficulty import Difficulty
from utils import storage

_QFont = QFont
def QFont():
    qf = _QFont('Sans Serif')
    qf.setStyleHint(_QFont.SansSerif)
    return qf

if TYPE_CHECKING:
    from gui.viewmodels.chart_viewer import ChartViewer

X_MARGIN = 110
LEFT_MARGIN = 50
LANE_DISTANCE = 70
SKILL_PAINT_WIDTH = 60
SEC_OFFSET_X = 105
SEC_OFFSET_Y = 17
SEC_FONT = 36

X_MARGIN_GRAND = 75
LANE_DISTANCE_GRAND = 25
SKILL_PAINT_WIDTH_GRAND = 22
SEC_OFFSET_X_GRAND = 86
SEC_OFFSET_Y_GRAND = 15
SEC_FONT_GRAND = 32

SEC_HEIGHT = 500
Y_MARGIN = 70
MAX_LABEL_Y = 5000
MAX_SECS_PER_LABEL = MAX_LABEL_Y // SEC_HEIGHT

WINDOW_WIDTH = 500
SCROLL_WIDTH = 19

ICON_HEIGHT = 45

IMAGE_HEIGHT = 5000
IMAGE_Y_MARGIN = 70

NOTE_PICS = {
    filename: QImage(str(RHYTHM_ICONS_PATH / filename))
    for filename in os.listdir(str(RHYTHM_ICONS_PATH))
}

CACHED_GRAND_NOTE_PICS = dict()


class ChartPicNote:
    num: int
    sec: float
    lane: int  # starts from the leftmost 0
    sync: int
    qgroup: int
    group_id: int
    note_type: NoteType
    right_flick: bool
    grand: bool
    span: int
    great: bool
    delta: int
    early: int
    late: int

    note_pic: Optional[QImage]
    note_pic_smol: Optional[QImage]

    def __init__(self, num: int = 0, sec: float = 0, lane: int = 0, sync: int = 0, qgroup: int = 0, group_id: int = 0,
                 note_type: NoteType = NoteType.TAP, delta: int = 0, early: int = 0, late: int = 0,
                 right_flick: bool = False, grand: bool = False, span: int = 0, great: bool = False):
        self.num = num
        self.sec = sec
        self.lane = lane
        self.sync = sync
        self.qgroup = qgroup
        self.group_id = group_id
        self.note_type = note_type
        self.right_flick = right_flick
        self.grand = grand
        self.span = span
        self.great = great
        self.delta = delta
        self.early = early
        self.late = late

        self.note_pic = None
        self.note_pic_smol = None
        self.get_note_pic()

    def get_note_pic(self):
        if self.note_type == NoteType.TAP:
            note_file_prefix = "tap"
        elif self.note_type == NoteType.LONG:
            note_file_prefix = "long"
        elif self.note_type == NoteType.SLIDE:
            note_file_prefix = "slide"
        elif self.note_type == NoteType.FLICK and self.right_flick:
            note_file_prefix = "flickr"
        elif self.note_type == NoteType.FLICK and not self.right_flick:
            note_file_prefix = "flickl"
        elif self.note_type == NoteType.DAMAGE:
            note_file_prefix = "damage"
        else:
            note_file_prefix = ""
        if self.grand:
            note_file_prefix = "g" + note_file_prefix
            self.note_pic = ChartPicNote.get_grand_note(note_file_prefix, self.span, False)
            self.note_pic_smol = ChartPicNote.get_grand_note(note_file_prefix + "e", self.span, True)
        else:
            self.note_pic = NOTE_PICS["{}.png".format(note_file_prefix)]
            self.note_pic_smol = NOTE_PICS["{}e.png".format(note_file_prefix)]

    @classmethod
    def get_grand_note(cls, note_file_prefix: str, span: int, tiny=False) -> QImage:
        if note_file_prefix in CACHED_GRAND_NOTE_PICS and span in CACHED_GRAND_NOTE_PICS[note_file_prefix]:
            return CACHED_GRAND_NOTE_PICS[note_file_prefix][span]
        if note_file_prefix not in CACHED_GRAND_NOTE_PICS:
            CACHED_GRAND_NOTE_PICS[note_file_prefix] = dict()

        CACHED_GRAND_NOTE_PICS[note_file_prefix][span] = ChartPicNote.generate_grand_note(note_file_prefix, span, tiny)
        return CACHED_GRAND_NOTE_PICS[note_file_prefix][span]

    @classmethod
    def generate_grand_note(cls, note_file_prefix: str, span: int, tiny=False) -> QImage:
        left = NOTE_PICS["{}1.png".format(note_file_prefix)]
        mid = NOTE_PICS["{}2.png".format(note_file_prefix)]
        right = NOTE_PICS["{}3.png".format(note_file_prefix)]
        width = span * LANE_DISTANCE_GRAND
        if tiny:
            width = width * 0.75
        res = QImage(left.width()
                     + right.width()
                     + width,
                     left.height(),
                     QImage.Format_ARGB32)
        res.fill(qRgba(0, 0, 0, 0))
        painter = QPainter(res)
        painter.drawImage(QPoint(0, 0), left)
        painter.drawImage(QRectF(left.width(), 0, width, mid.height()), mid, QRectF(0, 0, mid.width(), mid.height()))
        painter.drawImage(QPoint(left.width() + width, 0), right)
        return res


class ChartPicSkill:
    skill_type: int
    interval: int
    duration: float

    lane: int  # starts from the leftmost 0
    act_idx: int
    grand_offset: int  # -1 if not grand, 0 ~ 2 if grand

    qgroup: int

    selected: bool
    active: bool
    deact: bool
    inact: bool

    def __init__(self, skill_type: int = 0, interval: int = 0, duration: float = 0, lane: int = 0,
                 act_idx: int = 0, grand_offset: int = -1, qgroup: int = 0):
        self.skill_type = skill_type
        self.interval = interval
        self.duration = duration

        self.lane = lane
        self.act_idx = act_idx
        self.grand_offset = grand_offset

        self.qgroup = qgroup

        self.selected = False
        self.active = True
        self.deact = False
        self.inact = False

    @property
    def left(self) -> float:
        if self.grand_offset >= 0:
            return (3 * self.act_idx + self.grand_offset + 1) * self.interval
        else:
            return (self.act_idx + 1) * self.interval

    @property
    def right(self) -> float:
        return self.left + self.duration


class DraggableQScrollArea(QScrollArea):
    drag_start_position: QPoint
    original_x: int
    original_y: int

    def __init__(self, *args):
        super().__init__(*args)
        self.original_y = self.verticalScrollBar().value()
        self.original_x = self.horizontalScrollBar().value()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            self.original_y = self.verticalScrollBar().value()
            self.original_x = self.horizontalScrollBar().value()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        delta = event.pos() - self.drag_start_position
        if delta.manhattanLength() < QApplication.startDragDistance():
            return
        self.verticalScrollBar().setValue(self.original_y - delta.y())
        self.horizontalScrollBar().setValue(self.original_x - delta.x())


class ChartScrollArea(DraggableQScrollArea):
    note_clickable_areas: List[QPolygonF()]
    damage_clickable_areas: List[QPolygonF()]
    skill_clickable_areas: List[List[QPolygonF()]]

    def __init__(self, lane_count: int, *args):
        super().__init__(*args)

        self.note_clickable_areas = list()
        self.damage_clickable_areas = list()
        self.skill_clickable_areas = [[] for _ in range(lane_count)]


class BaseChartPicGenerator(ABC):
    X_MARGIN: int
    LANE_DISTANCE: int
    SKILL_PAINT_WIDTH: int
    SEC_OFFSET_X: int
    SEC_OFFSET_Y: int
    SEC_FONT: int

    song_id: int
    difficulty: Difficulty
    viewer: ChartViewer
    grand: bool
    mirrored: bool

    lane_count: int

    last_sec_float: float
    last_sec: int

    label_total: int
    note_labels: List[List[ChartPicNote]]
    damage_labels: List[List[ChartPicNote]]
    skill_labels: List[List[List[ChartPicSkill]]]

    note_offsets: DefaultDict[int, int]
    deact_skills: Dict[int, List[int]]

    chart_widget: Optional[ChartScrollArea]
    chart_image_widget: QWidget
    chart_image_layout: QVBoxLayout

    image_labels: List[QLabel]
    pixmap_caches: List[Optional[QPixmap]]
    painters: List[QPainter]

    selected_note: int
    selected_skill: Tuple[int, int]

    notes: DataFrame

    unit: Optional[Unit] = None

    def __init__(self, song_id: int, difficulty: Difficulty, parent: ChartViewer, grand: bool, mirrored: bool = False):
        self.song_id = song_id
        self.difficulty = difficulty
        self.viewer = parent
        self.grand = grand
        self.mirrored = mirrored

        self.lane_count = 5 if not grand else 15

        self.last_sec_float = 0
        self.last_sec = 0

        self.label_total = 0
        self.note_labels = list()
        self.damage_labels = list()
        self.skill_labels = list()

        self.note_offsets = defaultdict(int)
        self.deact_skills = {card_num: [] for card_num in range(1, 16)}

        self.height = 0
        self.width = 0

        self.chart_widget = None
        self.chart_image_widget = QWidget()
        self.chart_image_layout = QVBoxLayout(self.chart_image_widget)

        self.image_labels = list()
        self.pixmap_caches = [None] * self.label_total
        self.painters = list()

        self.selected_note = 0  # num
        self.selected_skill = (0, 0)  # (card_num, act_idx)

        self.get_notes_from_chart()
        self.notes_into_group()
        self.generate_note_objects()
        self.initialize_ui()
        self.initialize_painters()
        self.draw_chart()

    def get_notes_from_chart(self):
        self.notes = fetch_chart(None, self.song_id, self.difficulty, event=False, skip_load_notes=False,
                                 skip_damage_notes=False)[0]
        if self.notes is None:
            self.notes = fetch_chart(None, self.song_id, self.difficulty, event=True, skip_load_notes=False)[0]

        self.notes = self.notes.reset_index()
        self.notes['finishPos'] -= 1

        if self.mirrored:
            if not self.grand:
                self.notes['finishPos'] = 4 - self.notes['finishPos']
            else:
                self.notes['finishPos'] = 15 - (self.notes['finishPos'] + self.notes['status'])

    def notes_into_group(self):
        long_groups = list()
        long_stack = defaultdict(lambda: list())
        for _, note in self.notes.iterrows():
            lane = note['finishPos']
            if note['note_type'] == NoteType.LONG and lane not in long_stack:
                long_stack[lane].append((_, note))
            elif lane in long_stack:
                long_stack[lane].append((_, note))
                long_groups.append(long_stack.pop(lane))
        long_dummy_group = 2000
        for pair in long_groups:
            group_id = max(pair[0][1]['groupId'], pair[1][1]['groupId'])
            if group_id == 0:
                group_id = long_dummy_group
                long_dummy_group += 1
            self.notes.loc[pair[0][0], 'groupId'] = group_id
            self.notes.loc[pair[1][0], 'groupId'] = group_id

    def generate_note_objects(self, abuse_data: AbuseData = None):
        self.note_labels.clear()
        self.damage_labels.clear()

        self.last_sec_float = self.notes.sec.iloc[-1]
        self.last_sec = int(self.last_sec_float) + 1

        notes_damage_removed = self.notes[self.notes['note_type'] != NoteType.DAMAGE].reset_index(drop=True)
        damages = self.notes[self.notes['note_type'] == NoteType.DAMAGE].reset_index(drop=True)

        self.label_total = (self.last_sec * SEC_HEIGHT + 2 * Y_MARGIN) // MAX_LABEL_Y + 1
        for n in range(self.label_total):
            note_group = list()
            damage_group = list()
            df_slice = notes_damage_removed[
                (notes_damage_removed['sec'] >= n * MAX_SECS_PER_LABEL - (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT) &
                (notes_damage_removed['sec'] <= (n + 1) * MAX_SECS_PER_LABEL + (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT)]
            for index, note in df_slice.iterrows():
                right_flick = note['note_type'] == NoteType.FLICK and (note['status'] == 2 and not self.grand) \
                              or (note['type'] == 7 and self.grand)
                if self.mirrored:
                    right_flick = not right_flick
                delta = 0
                early = 0
                late = 0
                great = False
                if abuse_data is not None and abuse_data.score_delta[index] > 0:
                    delta = int(abuse_data.score_delta[index])
                    early = int(abuse_data.window_l[index] // 1E3)
                    late = int(abuse_data.window_r[index] // 1E3)
                    great = abuse_data.judgements[index] is Judgement.GREAT
                note_object = ChartPicNote(num=index + 1, sec=note['sec'], lane=note['finishPos'],
                                           sync=note['sync'], qgroup=n, group_id=note['groupId'],
                                           note_type=note['note_type'], delta=delta, early=early, late=late,
                                           right_flick=right_flick, grand=self.grand,
                                           span=note['status'] - 1 if self.grand else 0, great=great)
                note_group.append(note_object)
            df_slice = damages[
                (damages['sec'] >= n * MAX_SECS_PER_LABEL - (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT) &
                (damages['sec'] <= (n + 1) * MAX_SECS_PER_LABEL + (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT)]
            for index, note in df_slice.iterrows():
                note_object = ChartPicNote(num=-(index + 1), sec=note['sec'], lane=note['finishPos'],
                                           note_type=note['note_type'])
                damage_group.append(note_object)
            self.note_labels.append(note_group)
            self.damage_labels.append(damage_group)

    def generate_skill_objects(self):
        self.skill_labels.clear()
        for i in range(self.label_total):
            self.skill_labels.append(list())

        for card_idx, card in enumerate(self.unit.all_cards()):
            for label in self.skill_labels:
                label.append(list())

            skill = card.sk
            interval = skill.interval
            duration = skill.duration / 1.5 * (1 + (skill.skill_level - 1) / 18)
            lane = self.convert_index_to_lane(card_idx)

            skill_total_activation = (self.last_sec_float - 1e-8 - 3) // interval
            skill_current_activation = 0

            label_idx = 0
            group = list()
            while label_idx < self.label_total:
                left = (skill_current_activation + 1) * interval
                label_end_height = ((label_idx + 1) * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT
                if left > label_end_height:
                    self.skill_labels[label_idx][card_idx].extend(group)
                    group.clear()
                    label_idx += 1
                    previous_right = skill_current_activation * interval + duration
                    if previous_right > label_end_height:
                        skill_current_activation -= 1
                    continue
                if self.grand and skill_current_activation % 3 != skill.offset:
                    skill_current_activation += 1
                    continue
                if skill_current_activation >= skill_total_activation:
                    self.skill_labels[label_idx][card_idx].extend(group)
                    break

                skill_current_activation_converted = skill_current_activation
                offset = -1
                if self.grand:
                    skill_current_activation_converted //= 3
                    offset = skill.offset

                skill_object = ChartPicSkill(skill_type=skill.skill_type, interval=interval, duration=duration,
                                             lane=lane, act_idx=skill_current_activation_converted, grand_offset=offset,
                                             qgroup=label_idx)
                group.append(skill_object)
                skill_current_activation += 1

    def initialize_ui(self):
        self.height = self.last_sec * SEC_HEIGHT + 2 * Y_MARGIN
        self.width = LEFT_MARGIN + (2 * self.X_MARGIN + (self.lane_count - 1) * self.LANE_DISTANCE)

        self.chart_image_layout.setSpacing(0)
        self.chart_image_layout.setContentsMargins(0, 0, 0, 0)

        for label_idx in range(self.label_total):
            label_y = MAX_LABEL_Y
            if label_idx == self.label_total - 1:
                label_y = self.height - MAX_LABEL_Y * label_idx

            label = QLabel()
            label.setAlignment(Qt.AlignBottom)
            label.setFixedSize(self.width, label_y)

            canvas = QPixmap(self.width, label_y)
            label.setPixmap(canvas)

            self.image_labels.append(label)

        for label_idx in range(self.label_total - 1, -1, -1):
            self.chart_image_layout.addWidget(self.image_labels[label_idx])

        self.chart_widget = ChartScrollArea(self.lane_count)
        self.chart_widget.setWidget(self.chart_image_widget)
        self.chart_widget.mousePressEvent = self.mouse_pressed
        vbar = self.chart_widget.verticalScrollBar()
        vbar.setValue(vbar.maximum())  # Scroll to bottom

        self.viewer.layout.replaceWidget(self.viewer.chart_widget, self.chart_widget)
        self.viewer.chart_widget.deleteLater()
        self.viewer.chart_widget = self.chart_widget

    def mirror_generator(self, mirrored: bool) -> BaseChartPicGenerator:
        if self.mirrored == mirrored:
            return self
        return BaseChartPicGenerator.get_generator(self.song_id, self.difficulty, self.viewer, mirrored=mirrored)

    @classmethod
    def get_generator(cls, song_id: int, difficulty: Difficulty, parent: ChartViewer, mirrored: bool = False) \
            -> BaseChartPicGenerator:
        if difficulty == Difficulty.PIANO or difficulty == Difficulty.FORTE:
            return GrandChartPicGenerator(song_id, difficulty, parent, True, mirrored)
        else:
            return BasicChartPicGenerator(song_id, difficulty, parent, False, mirrored)

    def draw(self, draw_label_idx: Optional[List[int]] = None):
        self.begin_painters()

        if draw_label_idx is None:
            draw_label_idx = list()
        self.draw_grid_and_secs(draw_label_idx)
        self.draw_sync_lines(draw_label_idx)
        self.draw_group_lines(draw_label_idx)
        self.draw_notes(draw_label_idx)

        from gui.viewmodels.chart_viewer import ChartMode
        if self.viewer.chart_mode == ChartMode.CUSTOM:
            self.draw_offset(draw_label_idx)

        self.end_painters()

    def draw_grid_and_secs(self, draw_label_idx: List[int]):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))
        draw_painter = [self.painters[i] for i in draw_label_idx]

        font = QFont()
        font.setPixelSize(self.SEC_FONT)
        for painter in draw_painter:
            painter.setFont(font)

        vertical_grid_pen = QPen(QColor(80, 80, 80))
        vertical_grid_pen.setWidth(5)
        for painter in draw_painter:
            painter.setPen(vertical_grid_pen)
        for lane in range(self.lane_count):
            x = self.get_x(lane)
            for painter in draw_painter:
                painter.drawLine(x, 0, x, MAX_LABEL_Y)

        horizontal_grid_bold_pen = QPen(QColor(120, 120, 120))
        horizontal_grid_bold_pen.setWidth(5)
        horizontal_grid_light_pen = QPen(QColor(80, 80, 80))
        horizontal_grid_light_pen.setWidth(3)
        for label_idx in draw_label_idx:
            for sec in range(MAX_LABEL_Y // SEC_HEIGHT + 1):
                if (sec + MAX_LABEL_Y * label_idx // SEC_HEIGHT) % 5 == 0:
                    self.painters[label_idx].setPen(horizontal_grid_bold_pen)
                else:
                    self.painters[label_idx].setPen(horizontal_grid_light_pen)
                y = self.get_y(sec + MAX_LABEL_Y * label_idx // SEC_HEIGHT, label_idx)
                self.painters[label_idx].drawLine(self.get_x(0), y, self.get_x(self.lane_count - 1), y)
                tm = sec + MAX_LABEL_Y * label_idx // SEC_HEIGHT
                self.painters[label_idx].drawText(
                    QRect(self.get_x(0) - self.SEC_OFFSET_X, y - self.SEC_OFFSET_Y, 70, 100), Qt.AlignRight,
                    "{}:{:0>2}\n{}".format(tm // 60, tm % 60, self.notes[self.notes['sec'] <= tm].shape[0]))

    def draw_sync_lines(self, draw_label_idx: List[int]):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))
        draw_painter = [self.painters[i] for i in draw_label_idx]

        sync_line_pen = QPen(QColor(250, 250, 240))
        sync_line_pen.setWidth(3)
        for painter in draw_painter:
            painter.setPen(sync_line_pen)
        for label_idx in draw_label_idx:
            label = self.note_labels[label_idx]

            sync_pairs = defaultdict(lambda: list())
            for note in label:
                if note.sync == 0:
                    continue
                sync_pairs[note.sec].append(note)
            for values in sync_pairs.values():
                # Skip in case of sync == 1 but only 1 value because this game has dumb codes
                if len(values) != 2:
                    continue
                l = min(values[0].lane, values[1].lane)
                r = max(values[0].lane, values[1].lane)
                sec = values[0].sec
                y = self.get_y(sec, label_idx)
                self.painters[label_idx].drawLine(self.get_x(l), y, self.get_x(r), y)

    def draw_group_lines(self, draw_label_idx: List[int]):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))

        for label_idx in draw_label_idx:
            label = self.note_labels[label_idx]

            group_ids = set()
            for note in label:
                if note.group_id == 0:
                    continue
                group_ids.add(note.group_id)
            grouped_notes_df = self.notes[self.notes['groupId'].isin(group_ids)]
            for group_id, grouped_notes in grouped_notes_df.groupby("groupId"):
                for l, r in zip(grouped_notes.iloc[1:].T.to_dict().values(),
                                grouped_notes.iloc[:-1].T.to_dict().values()):
                    self._draw_group_line(l, r, label_idx)

    @abstractmethod
    def _draw_group_line(self, note1: dict, note2: dict, label_idx: int):
        pass

    @abstractmethod
    def draw_notes(self, draw_label_idx: List[int], update_clickable_areas: bool = True):
        pass

    def draw_offset(self, draw_label_idx: List[int]):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))

        for label_idx in draw_label_idx:
            label = self.note_labels[label_idx]

            for note in label:
                if self.note_offsets[note.num - 1] == 0:
                    continue
                x = self.get_x(note.lane + note.span / 2) - note.note_pic_smol.width() // 2
                y = self.get_y(note.sec + self.note_offsets[note.num - 1] / 1000,
                               label_idx) - note.note_pic_smol.height() // 2
                self.painters[label_idx].drawImage(QPoint(x, y), note.note_pic_smol)

    def paint_skill(self, draw_label_idx: List[int], update_clickable_areas: bool = True):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))
        else:
            update_clickable_areas = False

        if update_clickable_areas:
            for skill in self.chart_widget.skill_clickable_areas:
                skill.clear()

        self.begin_painters()

        for label_idx in draw_label_idx:
            label = self.skill_labels[label_idx]
            for card in label:
                for skill in card:
                    if skill.inact:
                        skill_brush = QBrush(QColor(*SKILL_BASE[skill.skill_type]['color'], 100), Qt.Dense6Pattern)
                    elif skill.deact:
                        skill_brush = QBrush(QColor(*SKILL_BASE[skill.skill_type]['color'], 100), Qt.DiagCrossPattern)
                    else:
                        skill_brush = QBrush(QColor(*SKILL_BASE[skill.skill_type]['color'], 100))
                    self.painters[label_idx].setPen(QPen())
                    self.painters[label_idx].setBrush(skill_brush)

                    x = self.get_x(skill.lane)
                    y = self.get_y(skill.right, label_idx)
                    self.painters[label_idx].drawRect(x - self.SKILL_PAINT_WIDTH // 2, y, self.SKILL_PAINT_WIDTH,
                                                      skill.duration * SEC_HEIGHT)

                    if self._is_double_drawn_skill(skill, 1):
                        continue

                    if not update_clickable_areas:
                        continue
                    y_scroll = self.height + (label_idx + 1) - (Y_MARGIN + skill.right * SEC_HEIGHT)
                    polygon = QPolygonF()
                    polygon.append(QPoint(x - self.SKILL_PAINT_WIDTH // 2, y_scroll))
                    polygon.append(QPoint(x - self.SKILL_PAINT_WIDTH // 2, y_scroll + skill.duration * SEC_HEIGHT))
                    polygon.append(QPoint(x + self.SKILL_PAINT_WIDTH // 2, y_scroll + skill.duration * SEC_HEIGHT))
                    polygon.append(QPoint(x + self.SKILL_PAINT_WIDTH // 2, y_scroll))
                    self.chart_widget.skill_clickable_areas[self.convert_lane_to_index(skill.lane)].append(polygon)

        self.end_painters()

    def _is_double_drawn_note(self, note: ChartPicNote, direction: int = 0) -> bool:
        assert direction in (-1, 0, 1)
        for n in range(self.label_total):
            if MAX_SECS_PER_LABEL * n - (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT <= note.sec \
                    <= MAX_SECS_PER_LABEL * n + (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT:
                if direction == 0:
                    return True
                elif direction == 1:
                    if note.qgroup == n + 1:
                        return True
                else:
                    if note.qgroup == n:
                        return True
        return False

    def _is_double_drawn_skill(self, skill: ChartPicSkill, direction: int = 0) -> bool:
        assert direction in (-1, 0, 1)
        for n in range(self.label_total):
            if skill.left <= MAX_SECS_PER_LABEL * n - Y_MARGIN / SEC_HEIGHT <= skill.right:
                if direction == 0:
                    return True
                elif direction == 1:
                    if skill.qgroup == n:
                        return True
                else:
                    if skill.qgroup == n - 1:
                        return True
        return False

    def hook_cards(self, all_cards: List[Card]) -> bool:
        try:
            if len(all_cards) == 15:
                unit = GrandUnit.from_list(all_cards)
            else:
                unit = Unit.from_list(cards=all_cards[:5])
        except InvalidUnit:
            return False
        # Skip drawing if same unit else reset drawing
        if not self.grand and isinstance(unit, GrandUnit):
            unit = unit.ua
        if unit == self.unit:
            return False
        self.unit = unit
        self.generate_skill_objects()
        return True

    def hook_abuse(self, all_cards: List[Card], abuse_data: AbuseData):
        self.hook_cards(all_cards)
        self.generate_note_objects(abuse_data)

    def draw_abuse(self, note: ChartPicNote, label_idx: int):
        if note.delta == 0:
            return

        self.begin_painters()

        x_note = self.get_x(note.lane + note.span / 2) - note.note_pic_smol.width() // 2
        y_early = self.get_y(note.sec + note.early / 1000, label_idx)
        shifted_y_early = y_early - note.note_pic_smol.height() // 2
        y_late = self.get_y(note.sec + note.late / 1000, label_idx)
        shifted_y_late = y_late - note.note_pic_smol.height() // 2
        self.painters[label_idx].drawImage(QPoint(x_note, shifted_y_early), note.note_pic_smol)
        self.painters[label_idx].drawImage(QPoint(x_note, shifted_y_late), note.note_pic_smol)
        lane_l = self.get_x(0)
        lane_r = self.get_x(self.lane_count - 1)
        self.painters[label_idx].setPen(QPen(Qt.green))
        self.painters[label_idx].drawLine(lane_l, y_early, lane_r, y_early)
        self.painters[label_idx].setPen(QPen(Qt.red))
        self.painters[label_idx].drawLine(lane_l, y_late, lane_r, y_late)

        x = self.get_x(note.lane + note.span / 2) - note.note_pic.width() // 2
        y = self.get_y(note.sec, label_idx) + note.note_pic.height()
        font = QFont()
        font.setBold(True)
        font.setPixelSize(30)
        pen = QPen()
        pen.setWidth(1)
        pen.setColor(Qt.white)
        if note.great:
            brush = QBrush(QColor(66, 13, 110))
        else:
            brush = QBrush(Qt.black)
        path = QPainterPath()
        path.addText(x, y, font, str(note.delta))
        self.painters[label_idx].setFont(font)
        self.painters[label_idx].setPen(pen)
        self.painters[label_idx].setBrush(brush)
        self.painters[label_idx].drawPath(path)
        font.setPixelSize(24)
        path = QPainterPath()
        path.addText(x, y + 40, font, "{} {}".format(note.early, note.late))
        self.painters[label_idx].drawPath(path)

        self.end_painters()

    def save_image(self):
        path = CHART_PICS_PATH / "{}-{}.png".format(self.song_id, str(self.difficulty)[11:])
        uniq = 1
        while os.path.exists(path):
            path = CHART_PICS_PATH / "{}-{}({}).png".format(self.song_id, str(self.difficulty)[11:], uniq)
            uniq += 1
        storage.exists(path)

        column_num = self.height // (IMAGE_HEIGHT - IMAGE_Y_MARGIN) + 1
        saved_image = QImage(WINDOW_WIDTH * column_num, IMAGE_HEIGHT, QImage.Format_ARGB32)
        saved_image.fill(qRgba(0, 0, 0, 255))
        painter = QPainter(saved_image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)

        y_temp = 0
        column = 0
        while y_temp < self.height:
            for n in range(self.label_total):
                if y_temp >= n * MAX_LABEL_Y \
                        and y_temp + IMAGE_HEIGHT <= (n + 1) * MAX_LABEL_Y:  # label is totally inside the column
                    if y_temp + IMAGE_HEIGHT > self.height:  # final part of the chart
                        h = self.image_labels[n].pixmap().height() - (y_temp - n * MAX_LABEL_Y)
                        painter.drawPixmap(column * WINDOW_WIDTH, IMAGE_HEIGHT - h,
                                           self.image_labels[n].pixmap().copy(0, 0, WINDOW_WIDTH, h))
                    else:
                        y = self.image_labels[n].pixmap().height() - (y_temp - n * MAX_LABEL_Y) - IMAGE_HEIGHT
                        painter.drawPixmap(column * WINDOW_WIDTH, 0,
                                           self.image_labels[n].pixmap().copy(0, y, WINDOW_WIDTH, IMAGE_HEIGHT))
                    break
                else:
                    # label's top is in next column
                    if n * MAX_LABEL_Y <= y_temp + IMAGE_HEIGHT <= (n + 1) * MAX_LABEL_Y:
                        if y_temp + IMAGE_HEIGHT > self.height:  # final part of the chart
                            h = self.image_labels[n].pixmap().height() - (y_temp - n * MAX_LABEL_Y)
                            painter.drawPixmap(column * WINDOW_WIDTH, IMAGE_HEIGHT - h,
                                               self.image_labels[n].pixmap().copy(0, 0, WINDOW_WIDTH, h))
                        else:
                            y = self.image_labels[n].pixmap().height() - (y_temp - n * MAX_LABEL_Y) - IMAGE_HEIGHT
                            h = self.image_labels[n].pixmap().height() - y
                            painter.drawPixmap(column * WINDOW_WIDTH, 0,
                                               self.image_labels[n].pixmap().copy(0, y, WINDOW_WIDTH, h))
                    # label's bottom is in previous column
                    if n * MAX_LABEL_Y <= y_temp < (n + 1) * MAX_LABEL_Y:
                        h = self.image_labels[n].pixmap().height() - (y_temp - n * MAX_LABEL_Y)
                        painter.drawPixmap(column * WINDOW_WIDTH, IMAGE_HEIGHT - h,
                                           self.image_labels[n].pixmap().copy(0, 0, WINDOW_WIDTH, h))
            y_temp += IMAGE_HEIGHT - IMAGE_Y_MARGIN
            column += 1
        saved_image.save(str(path))
        painter.end()

    def draw_chart(self, paint_skill: bool = False, draw_abuse: bool = False):
        self.begin_painters()

        for painter in self.painters:
            painter.fillRect(0, 0, self.width, self.height, Qt.black)
        if paint_skill or draw_abuse:
            self.paint_skill([])
        self.draw()
        if draw_abuse:
            for group_idx, qt_group in enumerate(self.note_labels):
                for note in qt_group:
                    self.draw_abuse(note, group_idx)
        for label in self.image_labels:
            label.repaint()
        self.pixmap_caches = [None] * self.label_total

        self.end_painters()

    def mouse_pressed(self, event):
        scroll = self.chart_widget
        super(ChartScrollArea, scroll).mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            scroll.drag_start_position = event.pos()
            scroll.original_y = scroll.verticalScrollBar().value()
            scroll.original_x = scroll.horizontalScrollBar().value()

        pos = event.pos() + QPoint(scroll.original_x, scroll.original_y)
        for idx, area in enumerate(scroll.note_clickable_areas):
            if area.containsPoint(pos, Qt.FillRule.OddEvenFill):
                num = self.get_note_from_index(idx).num
                self.selected_note = num
                self.draw_selected_note(num)
                self.viewer.show_detail_nothing()
                self.viewer.show_detail_note_info(num)
                return
        for idx, area in enumerate(scroll.damage_clickable_areas):
            if area.containsPoint(pos, Qt.FillRule.OddEvenFill):
                note = self.get_note_from_index(idx, True)
                self.draw_selected_note(note.num, True)
                self.viewer.show_detail_nothing()
                self.viewer.show_detail_damage_info(note.sec)
                return
        from gui.viewmodels.chart_viewer import ChartMode
        if self.viewer.chart_mode != ChartMode.DEFAULT:
            for card_idx, card in enumerate(scroll.skill_clickable_areas):
                for act_idx, area in enumerate(card):
                    if area.containsPoint(pos, Qt.FillRule.OddEvenFill):
                        skill = self.get_skill_from_index(card_idx, act_idx)
                        card_num = self.convert_lane_to_index(skill.lane) + 1
                        self.selected_skill = (card_num, skill.act_idx)
                        self.draw_selected_skill(skill.lane, skill.act_idx)
                        self.viewer.show_detail_nothing()
                        self.viewer.show_detail_skill_info(card_num, skill.act_idx)
                        return
        self.selected_note = 0
        self.selected_skill = (0, 0)
        self.draw_nothing_selected()
        self.viewer.show_detail_nothing()

    def draw_nothing_selected(self):
        self.begin_painters()

        for label_idx in range(self.label_total):
            if self.pixmap_caches[label_idx] is not None:
                self.painters[label_idx].drawImage(QPoint(0, 0), self.pixmap_caches[label_idx].toImage())
                self.pixmap_caches[label_idx] = None

        for label in self.image_labels:
            label.repaint()

        self.end_painters()

    def draw_selected_note(self, num: int, damage: bool = False):
        self.draw_nothing_selected()

        self.begin_painters()

        labels = self.note_labels if not damage else self.damage_labels
        for label_idx, label in enumerate(labels):
            self._set_selection_pen(label_idx)

            for note_idx, note in enumerate(label):
                if num == note.num:
                    self.pixmap_caches[label_idx] = self.image_labels[label_idx].pixmap().copy()
                    x = self.get_x(note.lane + note.span / 2)
                    y = self.get_y(note.sec, label_idx)
                    w = note.note_pic.width() + 4
                    h = note.note_pic.height() + 4
                    self.painters[label_idx].drawRoundedRect(x - w // 2, y - h // 2, w, h, 2, 2)

        for label in self.image_labels:
            label.repaint()

        self.end_painters()

    def draw_selected_skill(self, lane: int, act_idx: int):
        self.draw_nothing_selected()

        card_idx = self.convert_lane_to_index(lane)
        draw_label = self.get_label_of_skill(card_idx, act_idx)

        self.begin_painters()
        for painter_idx in draw_label:
            self.pixmap_caches[painter_idx] = self.image_labels[painter_idx].pixmap().copy()
            self.painters[painter_idx].fillRect(0, 0, self.width, self.height, Qt.black)
        self.paint_skill(draw_label, False)

        self.begin_painters()
        for label_idx in draw_label:
            self._set_selection_pen(label_idx)

            skills = self.skill_labels[label_idx][card_idx]
            for skill in skills:
                if skill.lane == lane and skill.act_idx == act_idx:
                    x = self.get_x(lane)
                    y = self.get_y(skill.right, label_idx)
                    w = self.SKILL_PAINT_WIDTH + 2
                    h = skill.duration * SEC_HEIGHT
                    self.painters[label_idx].drawRoundedRect(x - w // 2, y - 1, w, h, 2, 2)
        self.draw(draw_label)

        from gui.viewmodels.chart_viewer import ChartMode
        if self.viewer.chart_mode == ChartMode.ABUSE \
                or (self.viewer.chart_mode == ChartMode.CUSTOM and self.viewer.draw_custom_abuse):
            for label_idx in draw_label:
                for note in self.note_labels[label_idx]:
                    self.draw_abuse(note, label_idx)

        for label in self.image_labels:
            label.repaint()

    def _set_selection_pen(self, label_idx: int):
        pen = QPen(QColor(255, 128, 0, 255))
        pen.setWidth(2)
        self.painters[label_idx].setPen(pen)
        group_line_brush = QBrush(QColor(0, 0, 0, 0))
        self.painters[label_idx].setBrush(group_line_brush)

    def get_x(self, lane: float) -> int:
        return round(LEFT_MARGIN + self.X_MARGIN + lane * self.LANE_DISTANCE)

    def get_y(self, sec: float, label_idx: int) -> int:
        y = (label_idx + 1) * (MAX_LABEL_Y + 1) - Y_MARGIN - sec * SEC_HEIGHT
        if label_idx == self.height // MAX_LABEL_Y:
            y -= MAX_LABEL_Y - self.height % MAX_LABEL_Y
        return round(y)

    def get_note_from_index(self, idx: int, damage: bool = False) -> ChartPicNote:
        labels = self.note_labels if not damage else self.damage_labels
        notes = sum(labels, [])
        double_drawn_num = 0
        for note in notes:
            if note.num >= idx:
                break
            if self._is_double_drawn_note(note, 1):
                double_drawn_num += 1
        return notes[idx + double_drawn_num]

    def get_skill_from_index(self, card_idx: int, act_idx: int) -> ChartPicSkill:
        skills = sum([label[card_idx] for label in self.skill_labels], [])
        return next((skill for skill in skills if skill.act_idx == act_idx))

    def get_all_skills_of_index(self, card_idx: int, act_idx: int) -> List[ChartPicSkill]:
        skills = sum([label[card_idx] for label in self.skill_labels], [])
        return [skill for skill in skills if skill.act_idx == act_idx]

    def get_label_of_skill(self, card_idx: int, act_idx: int) -> List[int]:
        skill = self.get_skill_from_index(card_idx, act_idx)
        skill_label = list()
        for label_idx in range(self.label_total):
            if skill.left > ((label_idx + 1) * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT:
                continue
            if skill.right < (label_idx * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT:
                continue
            skill_label.append(label_idx)
        return skill_label

    def convert_index_to_lane(self, idx: int) -> int:
        converter = (2, 1, 3, 0, 4)
        if self.grand:
            if idx < 5:
                idx += 5
            elif 5 <= idx < 10:
                idx -= 5
        return 5 * (idx // 5) + converter[idx % 5]

    def convert_lane_to_index(self, lane: int) -> int:
        converter = (3, 1, 0, 2, 4)
        if self.grand:
            if lane < 5:
                lane += 5
            elif 5 <= lane < 10:
                lane -= 5
        return 5 * (lane // 5) + converter[lane % 5]

    def initialize_painters(self):
        for idx in range(self.label_total):
            self.painters.append(QPainter(self.image_labels[idx].pixmap()))
            self.painters[idx].setRenderHint(QPainter.Antialiasing)

    def begin_painters(self):
        for painter_idx, painter in enumerate(self.painters):
            if not painter.isActive():
                painter.begin(self.image_labels[painter_idx].pixmap())
                painter.setRenderHint(QPainter.Antialiasing)

    def end_painters(self):
        for painter in self.painters:
            if painter.isActive():
                painter.end()


class BasicChartPicGenerator(BaseChartPicGenerator):
    X_MARGIN = X_MARGIN
    LANE_DISTANCE = LANE_DISTANCE
    SKILL_PAINT_WIDTH = SKILL_PAINT_WIDTH
    SEC_OFFSET_X = SEC_OFFSET_X
    SEC_OFFSET_Y = SEC_OFFSET_Y
    SEC_FONT = SEC_FONT

    def _draw_group_line(self, note1: dict, note2: dict, label_idx: int):
        group_line_pen = QPen(QColor(180, 180, 180))
        group_line_pen.setWidth(20)
        self.painters[label_idx].setPen(group_line_pen)
        x1 = self.get_x(note1['finishPos'])
        x2 = self.get_x(note2['finishPos'])
        y1 = self.get_y(note1['sec'], label_idx)
        y2 = self.get_y(note2['sec'], label_idx)
        self.painters[label_idx].drawLine(x1, y1, x2, y2)

    def draw_notes(self, draw_label_idx: List[int], update_clickable_areas: bool = True):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))
        else:
            update_clickable_areas = False

        if update_clickable_areas:
            self.viewer.chart_widget.note_clickable_areas.clear()
            self.viewer.chart_widget.damage_clickable_areas.clear()

        for label_idx in draw_label_idx:
            for note in self.note_labels[label_idx]:
                w = note.note_pic.width()
                h = note.note_pic.height()
                x = self.get_x(note.lane)
                y = self.get_y(note.sec, label_idx)
                self.painters[label_idx].drawImage(QPoint(x - w // 2, y - h // 2), note.note_pic)

                if not update_clickable_areas:
                    continue
                polygon = QPolygonF()
                px, py = 0, 0
                y_scroll = self.height + (label_idx + 1) - (Y_MARGIN + note.sec * SEC_HEIGHT)
                if note.note_type == NoteType.FLICK:
                    if note.right_flick:
                        for theta in range(60, 301, 30):
                            px = x - w // 10 + h // 2 * math.cos(math.pi * (theta / 180))
                            py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                            polygon.append(QPoint(px, py))
                        vertex = QPoint(x + w // 2, y_scroll)
                        polygon.append(
                            QPoint(px + (vertex.x() - px) // 2, vertex.y() + (py - vertex.y()) // 2 + h // 12))
                        polygon.append(vertex)
                        polygon.append(
                            QPoint(px + (vertex.x() - px) // 2, vertex.y() - (py - vertex.y()) // 2 - h // 12))
                    else:
                        for theta in range(240, 481, 30):
                            px = x + w // 10 + h // 2 * math.cos(math.pi * (theta / 180))
                            py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                            polygon.append(QPoint(px, py))
                        vertex = QPoint(x - w // 2, y_scroll)
                        polygon.append(
                            QPoint(vertex.x() + (px - vertex.x()) // 2, vertex.y() - (vertex.y() - py) // 2 - h // 12))
                        polygon.append(vertex)
                        polygon.append(
                            QPoint(vertex.x() + (px - vertex.x()) // 2, vertex.y() + (vertex.y() - py) // 2 + h // 12))
                else:
                    for theta in range(0, 360, 30):
                        px = x + w // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                self.viewer.chart_widget.note_clickable_areas.append(polygon)

            for note in self.damage_labels[label_idx]:
                w = note.note_pic.width()
                h = note.note_pic.height()
                x = self.get_x(note.lane)
                y = self.get_y(note.sec, label_idx)
                self.painters[label_idx].drawImage(QPoint(x - w // 2, y - h // 2), note.note_pic)

                if not update_clickable_areas:
                    continue
                polygon = QPolygonF()
                y_scroll = self.height + (label_idx + 1) - (Y_MARGIN + note.sec * SEC_HEIGHT)
                for theta in range(0, 360, 90):
                    px = x + w // 2 * math.cos(math.pi * (theta / 180))
                    py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                    polygon.append(QPoint(px, py))
                self.viewer.chart_widget.damage_clickable_areas.append(polygon)


class GrandChartPicGenerator(BaseChartPicGenerator):
    X_MARGIN = X_MARGIN_GRAND
    LANE_DISTANCE = LANE_DISTANCE_GRAND
    SKILL_PAINT_WIDTH = SKILL_PAINT_WIDTH_GRAND
    SEC_OFFSET_X = SEC_OFFSET_X_GRAND
    SEC_OFFSET_Y = SEC_OFFSET_Y_GRAND
    SEC_FONT = SEC_FONT_GRAND

    def _draw_group_line(self, note1: dict, note2: dict, label_idx: int):
        group_line_pen = QPen(QColor(0, 0, 0, 0))
        group_line_pen.setWidth(0)
        self.painters[label_idx].setPen(group_line_pen)
        group_line_brush = QBrush(QColor(180, 180, 180, 150))
        self.painters[label_idx].setBrush(group_line_brush)
        polygon = QPolygonF()
        x1l = self.get_x(note1['finishPos'])
        x1r = self.get_x(note1['finishPos'] + note1['status'] - 1)
        x2l = self.get_x(note2['finishPos'])
        x2r = self.get_x(note2['finishPos'] + note2['status'] - 1)
        y1 = self.get_y(note1['sec'], label_idx)
        y2 = self.get_y(note2['sec'], label_idx)
        polygon.append(QPoint(x1l, y1))
        polygon.append(QPoint(x1r, y1))
        polygon.append(QPoint(x2r, y2))
        polygon.append(QPoint(x2l, y2))
        self.painters[label_idx].drawConvexPolygon(polygon)

    def draw_notes(self, draw_label_idx: List[int], update_clickable_areas: bool = True):
        if len(draw_label_idx) == 0:
            draw_label_idx = list(range(self.label_total))
        else:
            update_clickable_areas = False

        if update_clickable_areas:
            self.viewer.chart_widget.note_clickable_areas.clear()

        for label_idx in draw_label_idx:
            label = self.note_labels[label_idx]

            for note in label:
                w = note.note_pic.width()
                h = note.note_pic.height()
                x = self.get_x(note.lane + note.span / 2)
                y = self.get_y(note.sec, label_idx)
                self.painters[label_idx].drawImage(QPoint(x - w // 2, y - h // 2), note.note_pic)

                if not update_clickable_areas:
                    continue
                polygon = QPolygonF()
                y_scroll = self.height + (label_idx + 1) - (Y_MARGIN + note.sec * SEC_HEIGHT)
                if note.note_type == NoteType.FLICK:
                    if note.right_flick:
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 23, y_scroll))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 5, y_scroll + h // 2))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 5, y_scroll + h // 2 - 4))
                        polygon.append(QPoint(self.get_x(note.lane) - 21, y_scroll + h // 2 - 4))
                        polygon.append(QPoint(self.get_x(note.lane) - 11, y_scroll))
                        polygon.append(QPoint(self.get_x(note.lane) - 21, y_scroll - h // 2 + 4))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 5, y_scroll - h // 2 + 4))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 5, y_scroll - h // 2))
                    else:
                        polygon.append(QPoint(self.get_x(note.lane) - 23, y_scroll))
                        polygon.append(QPoint(self.get_x(note.lane) - 5, y_scroll + h // 2))
                        polygon.append(QPoint(self.get_x(note.lane) - 5, y_scroll + h // 2 - 4))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 21, y_scroll + h // 2 - 4))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 11, y_scroll))
                        polygon.append(QPoint(self.get_x(note.lane + note.span) + 21, y_scroll - h // 2 + 4))
                        polygon.append(QPoint(self.get_x(note.lane) - 5, y_scroll - h // 2 + 4))
                        polygon.append(QPoint(self.get_x(note.lane) - 5, y_scroll - h // 2))
                elif note.note_type == NoteType.TAP:
                    for theta in range(90, 271, 30):
                        px = self.get_x(note.lane) + 1 + h // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                    for theta in range(270, 451, 30):
                        px = self.get_x(note.lane + note.span) - 1 + h // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                elif note.note_type == NoteType.SLIDE:
                    for theta in range(90, 271, 30):
                        px = self.get_x(note.lane) - 2 + h // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                    for theta in range(270, 451, 30):
                        px = self.get_x(note.lane + note.span) + 2 + h // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                self.viewer.chart_widget.note_clickable_areas.append(polygon)
