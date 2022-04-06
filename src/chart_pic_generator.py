import math
import os
import sys
from abc import abstractmethod, ABC
from collections import defaultdict

from PyQt5.QtCore import Qt, QPoint, QRectF, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QFont, QBrush, QPainterPath, qRgba, QPolygon, QPolygonF
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QScrollArea, QVBoxLayout, QWidget

from exceptions import InvalidUnit
from logic.grandunit import GrandUnit
from logic.live import fetch_chart, Live
from logic.unit import Unit
from settings import RHYTHM_ICONS_PATH, CHART_PICS_PATH
from simulator import Simulator, SimulationResult
from statemachine import AbuseData
from static.judgement import Judgement
from static.note_type import NoteType
from static.skill import SKILL_BASE
from static.song_difficulty import Difficulty
from utils import storage

X_MARGIN = 110
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
MAX_LABEL_Y = 32000
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
    def __init__(self, num, sec, note_type, lane, sync, qgroup, group_id, delta, early, late, right_flick=False,
                 grand=False, span=0, great=False):
        self.num = num
        self.sec = sec
        self.lane = int(lane)
        self.sync = sync
        self.qgroup = qgroup
        self.group_id = group_id
        self.note_type = note_type
        self.right_flick = right_flick
        self.grand = grand
        self.span = span
        self.great = great

        self.get_note_pic()

        self.delta = int(delta)
        self.early = int(early)
        self.late = int(late)

    def get_note_pic(self):
        if self.note_type == NoteType.TAP:
            note_file_prefix = "tap"
        elif self.note_type == NoteType.LONG:
            note_file_prefix = "long"
        elif self.note_type == NoteType.SLIDE:
            note_file_prefix = "slide"
        elif self.note_type == NoteType.FLICK and self.right_flick:
            note_file_prefix = "flickr"
        else:
            note_file_prefix = "flickl"
        if self.grand:
            note_file_prefix = "g" + note_file_prefix
            self.note_pic = ChartPicNote.get_grand_note(note_file_prefix, self.span, False)
            self.note_pic_smol = ChartPicNote.get_grand_note(note_file_prefix + "e", self.span, True)
        else:
            self.note_pic = NOTE_PICS["{}.png".format(note_file_prefix)]
            self.note_pic_smol = NOTE_PICS["{}e.png".format(note_file_prefix)]

    @classmethod
    def get_grand_note(cls, note_file_prefix, span, tiny=False):
        if note_file_prefix in CACHED_GRAND_NOTE_PICS and span in CACHED_GRAND_NOTE_PICS[note_file_prefix]:
            return CACHED_GRAND_NOTE_PICS[note_file_prefix][span]
        if note_file_prefix not in CACHED_GRAND_NOTE_PICS:
            CACHED_GRAND_NOTE_PICS[note_file_prefix] = dict()

        CACHED_GRAND_NOTE_PICS[note_file_prefix][span] = ChartPicNote.generate_grand_note(note_file_prefix, span, tiny)
        return CACHED_GRAND_NOTE_PICS[note_file_prefix][span]

    @classmethod
    def generate_grand_note(cls, note_file_prefix, span, tiny=False):
        l = NOTE_PICS["{}1.png".format(note_file_prefix)]
        m = NOTE_PICS["{}2.png".format(note_file_prefix)]
        r = NOTE_PICS["{}3.png".format(note_file_prefix)]
        w = span * LANE_DISTANCE_GRAND
        if tiny:
            w = w * 0.75
        res = QImage(l.width()
                     + r.width()
                     + w,
                     l.height(),
                     QImage.Format_ARGB32)
        res.fill(qRgba(0, 0, 0, 0))
        painter = QPainter(res)
        painter.drawImage(QPoint(0, 0), l)
        painter.drawImage(QRectF(l.width(), 0, w, m.height()), m, QRectF(0, 0, m.width(), m.height()))
        painter.drawImage(QPoint(l.width() + w, 0), r)
        return res


class DraggableQScrollArea(QScrollArea):
    scroll_area: QScrollArea

    def __init__(self, *args):
        super().__init__(*args)

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


class BaseChartPicGenerator(ABC):
    X_MARGIN = X_MARGIN
    LANE_DISTANCE = LANE_DISTANCE
    SKILL_PAINT_WIDTH = SKILL_PAINT_WIDTH
    SEC_OFFSET_X = SEC_OFFSET_X
    SEC_OFFSET_Y = SEC_OFFSET_Y
    SEC_FONT = SEC_FONT

    unit = None

    def __init__(self, song_id, difficulty, parent, grand, reset_main=True, mirrored=False):
        self.song_id = song_id
        self.difficulty = difficulty
        self.viewer = parent
        self.grand = grand
        if grand:
            self.lane_count = 15
        else:
            self.lane_count = 5

        self.notes = fetch_chart(None, song_id, difficulty, event=False, skip_load_notes=False)[0]
        if self.notes is None:
            self.notes = fetch_chart(None, song_id, difficulty, event=True, skip_load_notes=False)[0]
        self.notes['finishPos'] -= 1
        self.notes_offset = [0] * len(self.notes)
        self.mirrored = mirrored
        if mirrored:
            if not grand:
                self.notes['finishPos'] = 4 - self.notes['finishPos']
            else:
                self.notes['finishPos'] = 15 - (self.notes['finishPos'] + self.notes['status'])
        self.notes_into_group()
        self.generate_note_objects()

        self.skill_inactive_list = [[] for _ in range(15)]
        self.skills = []

        self.initialize_ui()

        self.p = list()        
        for _ in range(self.n_label):        
            self.p.append(QPainter(self.label[_].pixmap()))
            self.p[_].setRenderHint(QPainter.Antialiasing)
        
        self.draw()
        for l in self.label: l.repaint()

    def mirror_generator(self, mirrored):
        if self.mirrored == mirrored:
            return self
        return BaseChartPicGenerator.get_generator(self.song_id, self.difficulty, self.viewer, reset_main=False,
                                                   mirrored=mirrored)

    @classmethod
    def get_generator(cls, song_id, difficulty, main_window, reset_main=True, mirrored=False):
        if isinstance(difficulty, int):
            difficulty = Difficulty(difficulty)
        if difficulty == Difficulty.PIANO or difficulty == Difficulty.FORTE:
            return GrandChartPicGenerator(song_id, difficulty, main_window, True, reset_main, mirrored)
        else:
            return BasicChartPicGenerator(song_id, difficulty, main_window, False, reset_main, mirrored)

    def notes_into_group(self):
        long_groups = list()
        long_stack = defaultdict(lambda: list())
        for _, note in self.notes.iterrows():
            # Handle long differently
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

    def initialize_ui(self):
        self.y_total = self.last_sec * SEC_HEIGHT + 2 * Y_MARGIN
        self.x_total = (2 * self.X_MARGIN + (self.lane_count - 1) * self.LANE_DISTANCE)
        
        self.chart_label = QWidget()
        self.chart_label_layout = QVBoxLayout(self.chart_label)
        self.chart_label_layout.setSpacing(0)
        self.chart_label_layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = list()
        for _ in range(self.n_label):
            self.label.append(QLabel())
            self.label[_].setAlignment(Qt.AlignBottom)
            label_y = MAX_LABEL_Y
            if _ == self.n_label - 1:
                label_y = self.y_total - MAX_LABEL_Y * _
            self.label[_].setFixedSize(self.x_total, label_y)
            
            canvas = QPixmap(self.x_total, label_y)
            self.label[_].setPixmap(canvas)
            
        for _ in range(self.n_label): self.chart_label_layout.addWidget(self.label[self.n_label - 1 - _])

        self.pixmap_cache = [None] * self.n_label
        scroll = DraggableQScrollArea()
        scroll.setWidget(self.chart_label)
        scroll.note_clickable_areas = []
        scroll.skill_clickable_areas = []
        scroll.mousePressEvent = self.mouse_pressed
        # Scroll to bottom
        vbar = scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())
        self.viewer.widget.layout.replaceWidget(self.viewer.chart_widget, scroll)
        self.viewer.chart_widget.deleteLater()
        self.viewer.chart_widget = scroll
        self.viewer.chart_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)

    def get_x(self, lane):
        return self.X_MARGIN + lane * self.LANE_DISTANCE

    def get_y(self, sec, label):
        y = (label + 1) * MAX_LABEL_Y - Y_MARGIN - sec * SEC_HEIGHT + label
        if label == self.y_total // MAX_LABEL_Y:
            y -= MAX_LABEL_Y - self.y_total % MAX_LABEL_Y
        return y
    
    def get_note_from_index(self, idx):
        notes = sum(self.note_labels , [])
        double_drawn_num = 0
        for i in range(idx):
            if self._is_double_drawn_note(notes[i], 1):
                double_drawn_num += 1
        return notes[idx + double_drawn_num]
    
    # Lanes start from 0
    def generate_note_objects(self, abuse_data: AbuseData = None):
        self.last_sec_float = self.notes.sec.iloc[-1]
        self.last_sec = int(self.last_sec_float) + 1
        
        self.n_label = (self.last_sec * SEC_HEIGHT + 2 * Y_MARGIN) // MAX_LABEL_Y + 1
        self.note_labels = list()
        for n in range(self.n_label):
            group = list()
            df_slice = self.notes[(n * MAX_SECS_PER_LABEL - (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT <= self.notes['sec']) &
                                  (self.notes['sec'] <= (n + 1) * MAX_SECS_PER_LABEL + (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT)]
            for _, row in df_slice.iterrows():
                right_flick = row['note_type'] == NoteType.FLICK and (row['status'] == 2 and not self.grand) or (
                        row['type'] == 7 and self.grand)
                if self.mirrored:
                    right_flick = not right_flick
                if abuse_data is not None and abuse_data.score_delta[_] > 0:
                    delta = abuse_data.score_delta[_]
                    early = abuse_data.window_l[_] // 1E3
                    late = abuse_data.window_r[_] // 1E3
                    great = abuse_data.judgements[_] is Judgement.GREAT
                else:
                    delta = 0
                    early = 0
                    late = 0
                    great = False
                note_object = ChartPicNote(num=_+1, sec=row['sec'], note_type=row['note_type'], lane=row['finishPos'],
                                           sync=row['sync'], qgroup=n, group_id=row['groupId'],
                                           delta=delta, early=early, late=late, right_flick=right_flick,
                                           grand=self.grand, span=row['status'] - 1 if self.grand else 0,
                                           great=great)
                group.append(note_object)
            self.note_labels.append(group)

    def draw(self):
        self.draw_grid_and_secs()
        self.draw_sync_lines()
        self.draw_group_lines()
        self.draw_notes()

    def hook_cards(self, all_cards):
        try:
            if len(all_cards) == 15:
                unit = GrandUnit.from_list(all_cards)
            else:
                unit = Unit.from_list(cards=all_cards[:5])
        except InvalidUnit:
            return
        # Skip drawing if same unit else reset drawing
        if not self.grand and isinstance(unit, GrandUnit):
            unit = unit.ua
        if unit == self.unit:
            return
        self.unit = unit

    def paint_skill(self):
        self.skills = []
        self.viewer.chart_widget.skill_clickable_areas = []
        for card_idx, card in enumerate(self.unit.all_cards()):
            skill = card.sk
            interval = skill.interval
            duration = skill.duration
            skill_times = int((self.last_sec_float - 3) // interval)
            skill_time = 1
            label = 0
            self.skills.append({'type' : skill.skill_type, 'time' : []})
            self.viewer.chart_widget.skill_clickable_areas.append([])
            while label < self.n_label:
                left = skill_time * interval
                right = skill_time * interval + duration
                
                #  Do not paint if skill entirely outside label
                if left > ((label + 1) * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT:
                    label += 1
                    skill_time -= 1
                    continue
                if self.grand and (skill_time - 1) % 3 != skill.offset:
                    skill_time += 1
                    continue
                if skill_time > skill_times:
                    break
                if skill.skill_type is None:
                    skill_time += 1
                    continue
                if skill_time - 1 in self.skill_inactive_list[card_idx]:
                    skill_time += 1
                    continue
                skill_brush = QBrush(QColor(*SKILL_BASE[skill.skill_type]['color'], 100))
                self.p[label].setPen(QPen())
                self.p[label].setBrush(skill_brush)
                # Need to convert grand lane
                draw_card_idx = card_idx
                if self.grand:
                    if card_idx < 5:
                        draw_card_idx += 5
                    elif 5 <= card_idx < 10:
                        draw_card_idx -= 5
                x = self.get_x(draw_card_idx)
                y = self.get_y(right, label)
                self.p[label].drawRect(x - self.SKILL_PAINT_WIDTH // 2,
                                y,
                                self.SKILL_PAINT_WIDTH,
                                duration * SEC_HEIGHT)
                
                self.skills[card_idx]['time'].append((left, right))
                
                y_scroll = self.y_total - (Y_MARGIN + right * SEC_HEIGHT)
                polygon = QPolygonF()
                polygon.append(QPoint(x - self.SKILL_PAINT_WIDTH // 2, y_scroll))
                polygon.append(QPoint(x - self.SKILL_PAINT_WIDTH // 2, y_scroll + duration * SEC_HEIGHT))
                polygon.append(QPoint(x + self.SKILL_PAINT_WIDTH // 2, y_scroll + duration * SEC_HEIGHT))
                polygon.append(QPoint(x + self.SKILL_PAINT_WIDTH // 2, y_scroll))
                self.viewer.chart_widget.skill_clickable_areas[card_idx].append(polygon)
                skill_time += 1

    def draw_grid_and_secs(self):
        font = QFont()
        font.setPixelSize(self.SEC_FONT)
        for p in self.p: p.setFont(font)

        vertical_grid_pen = QPen(QColor(80, 80, 80))
        vertical_grid_pen.setWidth(5)
        for p in self.p: p.setPen(vertical_grid_pen)
        for lane in range(self.lane_count):
            x = self.get_x(lane)
            for p in self.p: p.drawLine(x, 0, x, MAX_LABEL_Y)
            
        horizontal_grid_bold_pen = QPen(QColor(120, 120, 120))
        horizontal_grid_bold_pen.setWidth(5)
        horizontal_grid_light_pen = QPen(QColor(80, 80, 80))
        horizontal_grid_light_pen.setWidth(3)
        for label in range(self.n_label):
            for sec in range(MAX_LABEL_Y // SEC_HEIGHT + 1):
                if (sec + MAX_LABEL_Y * label // SEC_HEIGHT) % 5 == 0:
                    self.p[label].setPen(horizontal_grid_bold_pen)
                else:
                    self.p[label].setPen(horizontal_grid_light_pen)
                y = self.get_y(sec + MAX_LABEL_Y * label // SEC_HEIGHT, label)
                self.p[label].drawLine(self.get_x(0), y, self.get_x(self.lane_count - 1), y)
                self.p[label].drawText(QRect(self.get_x(0) - self.SEC_OFFSET_X, y - self.SEC_OFFSET_Y, 70, 50), Qt.AlignRight,
                                str(sec + MAX_LABEL_Y * label // SEC_HEIGHT))

    @abstractmethod
    def draw_notes(self):
        pass

    def _is_double_drawn_note(self, note: ChartPicNote, direction = 0):
        assert direction in [-1, 0, 1]
        for _ in range(self.n_label):
            if MAX_SECS_PER_LABEL * _ - (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT <= note.sec <= MAX_SECS_PER_LABEL * _ + (Y_MARGIN + ICON_HEIGHT) / SEC_HEIGHT:
                if direction == 0:
                    return True
                elif direction == 1:
                    if note.qgroup == _ + 1:
                        return True
                else:
                    if note.qgroup == _:
                        return True
        return False

    def draw_sync_lines(self):
        sync_line_pen = QPen(QColor(250, 250, 240))
        sync_line_pen.setWidth(3)
        for p in self.p : p.setPen(sync_line_pen)
        for label_idx, qt_label in enumerate(self.note_labels):
            sync_pairs = defaultdict(lambda: list())
            for note in qt_label:
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
                self.p[label_idx].drawLine(self.get_x(l), y, self.get_x(r), y)

    @abstractmethod
    def _draw_group_line(self, note1, note2, group):
        pass

    def draw_group_lines(self):
        for group_idx, qt_group in enumerate(self.note_labels):
            group_ids = set()
            for note in qt_group:
                if note.group_id == 0:
                    continue
                group_ids.add(note.group_id)
            grouped_notes_df = self.notes[self.notes['groupId'].isin(group_ids)]
            for group_id, grouped_notes in grouped_notes_df.groupby("groupId"):
                for l, r in zip(grouped_notes.iloc[1:].T.to_dict().values(),
                                grouped_notes.iloc[:-1].T.to_dict().values()):
                    self._draw_group_line(l, r, group_idx)

    def hook_abuse(self, all_cards, abuse_data):
        self.hook_cards(all_cards)

        self.generate_note_objects(abuse_data)

    def draw_abuse(self, note: ChartPicNote, label):
        if note.delta == 0:
            return

        x_note = self.get_x(note.lane + note.span / 2) - note.note_pic_smol.width() // 2
        y_early = self.get_y(note.sec + note.early / 1000, label)
        shifted_y_early = y_early - note.note_pic_smol.height() // 2
        y_late = self.get_y(note.sec + note.late / 1000, label)
        shifted_y_late = y_late - note.note_pic_smol.height() // 2
        self.p[label].drawImage(QPoint(x_note, shifted_y_early), note.note_pic_smol)
        self.p[label].drawImage(QPoint(x_note, shifted_y_late), note.note_pic_smol)
        lane_l = self.get_x(0)
        lane_r = self.get_x(self.lane_count - 1)
        self.p[label].setPen(QPen(Qt.green))
        self.p[label].drawLine(lane_l, y_early, lane_r, y_early)
        self.p[label].setPen(QPen(Qt.red))
        self.p[label].drawLine(lane_l, y_late, lane_r, y_late)

        x = self.get_x(note.lane + note.span / 2) - note.note_pic.width() // 2
        y = self.get_y(note.sec, label) + note.note_pic.height()
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
        self.p[label].setFont(font)
        self.p[label].setPen(pen)
        self.p[label].setBrush(brush)
        self.p[label].drawPath(path)
        font.setPixelSize(24)
        path = QPainterPath()
        path.addText(x, y + 40, font, "{} {}".format(note.early, note.late))
        self.p[label].drawPath(path)

    def draw_offset(self):
        for label_idx, label in enumerate(self.note_labels):
            for note in label:
                if self.notes_offset[note.num-1] == 0:
                    continue
                x = self.get_x(note.lane + note.span / 2) - note.note_pic_smol.width() // 2
                y = self.get_y(note.sec + self.notes_offset[note.num-1] / 1000, label_idx)
                self.p[label_idx].drawImage(QPoint(x, y), note.note_pic_smol)

    def save_image(self):
        path = CHART_PICS_PATH / "{}-{}.png".format(self.song_id, str(self.difficulty)[11:])
        uniq = 1
        while os.path.exists(path):
          path = CHART_PICS_PATH / "{}-{}({}).png".format(self.song_id, str(self.difficulty)[11:], uniq)
          uniq += 1
        storage.exists(path)
        group_num = self.y_total // (IMAGE_HEIGHT - IMAGE_Y_MARGIN) + 1
        self.saved_image = QImage(WINDOW_WIDTH * group_num, IMAGE_HEIGHT, QImage.Format_ARGB32)
        self.saved_image.fill(qRgba(0, 0, 0, 255))
        painter = QPainter(self.saved_image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        group = 0
        y_current = 0
        while y_current < self.y_total:
            for n in range(self.n_label):
                if n * MAX_LABEL_Y <= y_current and y_current + IMAGE_HEIGHT < (n+1) * MAX_LABEL_Y:
                    if y_current + IMAGE_HEIGHT > self.y_total + Y_MARGIN: #Final part of the chart
                        h = self.label[n].pixmap().height() - (y_current - n * MAX_LABEL_Y)
                        painter.drawPixmap(group * WINDOW_WIDTH, IMAGE_HEIGHT - h, self.label[n].pixmap().copy(0, 0, WINDOW_WIDTH, h))
                    else:
                        y = self.label[n].pixmap().height() - (y_current - n * MAX_LABEL_Y) - IMAGE_HEIGHT
                        painter.drawPixmap(group * WINDOW_WIDTH, 0, self.label[n].pixmap().copy(0, y, WINDOW_WIDTH, IMAGE_HEIGHT))
                    break
                else:
                    if n * MAX_LABEL_Y <= y_current + IMAGE_HEIGHT <= (n+1) * MAX_LABEL_Y:
                        y = self.label[n].pixmap().height() - (y_current - n * MAX_LABEL_Y) - IMAGE_HEIGHT
                        h = self.label[n].pixmap().height() - y
                        painter.drawPixmap(group * WINDOW_WIDTH, 0, self.label[n].pixmap().copy(0, y, WINDOW_WIDTH, h))
                    if n * MAX_LABEL_Y <= y_current < (n+1) * MAX_LABEL_Y:
                        h = self.label[n].pixmap().height() - (y_current - n * MAX_LABEL_Y)
                        painter.drawPixmap(group * WINDOW_WIDTH, IMAGE_HEIGHT - h, self.label[n].pixmap().copy(0, 0, WINDOW_WIDTH, h))
            y_current += IMAGE_HEIGHT - IMAGE_Y_MARGIN     
            group += 1
        self.saved_image.save(str(path))

    def draw_default_chart(self):
        for p in self.p: p.fillRect(0, 0, self.x_total, self.y_total, Qt.black)
        self.draw()
        for l in self.label: l.repaint()
    
    def draw_perfect_chart(self):
        for p in self.p: p.fillRect(0, 0, self.x_total, self.y_total, Qt.black)
        self.paint_skill()
        self.draw()
        for l in self.label: l.repaint()
    
    def draw_abuse_chart(self):
        for group_idx, qt_group in enumerate(self.note_labels):
            for note in qt_group:
                self.draw_abuse(note, group_idx)
        for l in self.label: l.repaint()
    
    def mouse_pressed(self, event):
        scroll = self.viewer.chart_widget
        super(DraggableQScrollArea, scroll).mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            scroll.drag_start_position = event.pos()
            scroll.original_y = scroll.verticalScrollBar().value()
            scroll.original_x = scroll.horizontalScrollBar().value()
            
        pos = event.pos() + QPoint(scroll.original_x, scroll.original_y)
        for idx, area in enumerate(scroll.note_clickable_areas):
            if area.containsPoint(pos, Qt.FillRule.OddEvenFill):
                note = self.get_note_from_index(idx)
                self.draw_selected_note(idx)
                self.viewer.show_detail_note_info(str(note.num), "{:.3f}".format(note.sec), str(note.note_type)[9:])
                return
        
        if self.viewer.chart_mode != 0:
            for card_idx, card in enumerate(scroll.skill_clickable_areas):
                for idx, area in enumerate(card):
                    if area.containsPoint(pos, Qt.FillRule.OddEvenFill):
                        skill_type = self.skills[card_idx]['type']
                        skill_type_text = SKILL_BASE[skill_type]['name']
                        skill_time = self.skills[card_idx]['time'][idx]
                        skill_time_text = "{:.1f} ~ {:.1f}".format(skill_time[0], skill_time[1])
                        self.draw_selected_skill(card_idx, idx)
                        self.viewer.show_detail_skill_info(skill_type_text, skill_time_text, "")
                        return
        self.draw_nothing_selected()
        self.viewer.show_detail_nothing()

    def draw_nothing_selected(self):
        for label_idx, label in enumerate(self.note_labels):
            if self.pixmap_cache[label_idx] is not None:
                self.p[label_idx].drawImage(QPoint(0, 0), self.pixmap_cache[label_idx].toImage())
                self.pixmap_cache[label_idx] = None
        for l in self.label: l.repaint()
    
    def draw_selected_note(self, idx):
        self.draw_nothing_selected()
        num = self.get_note_from_index(idx).num
        for label_idx, label in enumerate(self.note_labels):
            pen = QPen(QColor(255, 128, 0, 255))
            pen.setWidth(2)
            self.p[label_idx].setPen(pen)
            group_line_brush = QBrush(QColor(0, 0, 0, 0))
            self.p[label_idx].setBrush(group_line_brush)
            
            for note in label:
                if note.num == num:
                    self.pixmap_cache[label_idx] = self.label[label_idx].pixmap().copy()
                    w = note.note_pic.width() + 4
                    h = note.note_pic.height() + 4
                    x = self.get_x(note.lane + note.span / 2)
                    y = self.get_y(note.sec, label_idx)
                    self.p[label_idx].drawRoundedRect(x - w // 2, y - h // 2, w, h, 2, 2)
        for l in self.label: l.repaint()

    def draw_selected_skill(self, card_idx, idx):
        self.draw_nothing_selected()
        for label_idx, label in enumerate(self.note_labels):
            pen = QPen(QColor(255, 128, 0, 255))
            pen.setWidth(2)
            self.p[label_idx].setPen(pen)
            group_line_brush = QBrush(QColor(0, 0, 0, 0))
            self.p[label_idx].setBrush(group_line_brush)
            
            left = self.skills[card_idx]['time'][idx][0]
            right = self.skills[card_idx]['time'][idx][1]
            duration = right - left
            if left > ((label_idx + 1) * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT + 3:
                continue
            if right < ((label_idx) * MAX_LABEL_Y - Y_MARGIN) / SEC_HEIGHT - 3:
                continue
            self.pixmap_cache[label_idx] = self.label[label_idx].pixmap().copy()
            draw_card_idx = card_idx
            if self.grand:
                if card_idx < 5:
                    draw_card_idx += 5
                elif 5 <= card_idx < 10:
                    draw_card_idx -= 5
            x = self.get_x(draw_card_idx)
            y = self.get_y(right, label_idx)
            w = self.SKILL_PAINT_WIDTH + 2
            h = duration * SEC_HEIGHT
            self.p[label_idx].drawRoundedRect(x - w // 2, y - 1, w, h, 2, 2)
        for l in self.label: l.repaint()


class BasicChartPicGenerator(BaseChartPicGenerator):
    def _draw_group_line(self, note1, note2, label):
        group_line_pen = QPen(QColor(180, 180, 180))
        group_line_pen.setWidth(20)
        self.p[label].setPen(group_line_pen)
        x1 = self.get_x(note1['finishPos'])
        x2 = self.get_x(note2['finishPos'])
        y1 = self.get_y(note1['sec'], label)
        y2 = self.get_y(note2['sec'], label)
        self.p[label].drawLine(x1, y1, x2, y2)

    def draw_notes(self):
        for label_idx, label in enumerate(self.note_labels):
            for note in label:
                w = note.note_pic.width()
                h = note.note_pic.height()
                x = self.get_x(note.lane)
                y = self.get_y(note.sec, label_idx)
                self.p[label_idx].drawImage(QPoint(x - w // 2, y - h // 2), note.note_pic)
                
                polygon = QPolygonF()
                y_scroll = self.y_total - (Y_MARGIN + note.sec * SEC_HEIGHT)
                if note.note_type == NoteType.FLICK:
                    if note.right_flick:
                        for theta in range(60, 301, 30):
                            px = x - w // 10 + h // 2 * math.cos(math.pi * (theta / 180))
                            py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                            polygon.append(QPoint(px, py))
                        vertex = QPoint(x + w // 2, y_scroll)
                        polygon.append(QPoint(px + (vertex.x() - px) // 2, vertex.y() + (py - vertex.y()) // 2 + h // 12))
                        polygon.append(vertex)
                        polygon.append(QPoint(px + (vertex.x() - px) // 2, vertex.y() - (py - vertex.y()) // 2 - h // 12))
                    else:
                        for theta in range(240, 481, 30):
                            px = x + w // 10 + h // 2 * math.cos(math.pi * (theta / 180))
                            py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                            polygon.append(QPoint(px, py))
                        vertex = QPoint(x - w // 2, y_scroll)
                        polygon.append(QPoint(vertex.x() + (px - vertex.x()) // 2, vertex.y() - (vertex.y() - py) // 2 - h // 12))
                        polygon.append(vertex)
                        polygon.append(QPoint(vertex.x() + (px - vertex.x()) // 2, vertex.y() + (vertex.y() - py) // 2 + h // 12))
                else:
                    for theta in range(0, 360, 30):
                        px = x + w // 2 * math.cos(math.pi * (theta / 180))
                        py = y_scroll - h // 2 * math.sin(math.pi * (theta / 180))
                        polygon.append(QPoint(px, py))
                self.viewer.chart_widget.note_clickable_areas.append(polygon)


class GrandChartPicGenerator(BaseChartPicGenerator):
    X_MARGIN = X_MARGIN_GRAND
    LANE_DISTANCE = LANE_DISTANCE_GRAND
    SKILL_PAINT_WIDTH = SKILL_PAINT_WIDTH_GRAND
    SEC_OFFSET_X = SEC_OFFSET_X_GRAND
    SEC_OFFSET_Y = SEC_OFFSET_Y_GRAND
    SEC_FONT = SEC_FONT_GRAND

    def _draw_group_line(self, note1, note2, label):
        group_line_pen = QPen(QColor(0, 0, 0, 0))
        group_line_pen.setWidth(0)
        self.p[label].setPen(group_line_pen)
        group_line_brush = QBrush(QColor(180, 180, 180, 150))
        self.p[label].setBrush(group_line_brush)
        polygon = QPolygonF()
        x1l = self.get_x(note1['finishPos'])
        x1r = self.get_x(note1['finishPos'] + note1['status'] - 1)
        x2l = self.get_x(note2['finishPos'])
        x2r = self.get_x(note2['finishPos'] + note2['status'] - 1)
        y1 = self.get_y(note1['sec'], label)
        y2 = self.get_y(note2['sec'], label)
        polygon.append(QPoint(x1l, y1))
        polygon.append(QPoint(x1r, y1))
        polygon.append(QPoint(x2r, y2))
        polygon.append(QPoint(x2l, y2))
        self.p[label].drawConvexPolygon(polygon)

    def draw_notes(self):
        for label_idx, label in enumerate(self.note_labels):
            for note in label:
                w = note.note_pic.width()
                h = note.note_pic.height()
                x = self.get_x(note.lane + note.span / 2)
                y = self.get_y(note.sec, label_idx)
                self.p[label_idx].drawImage(QPoint(x - w // 2, y - h // 2), note.note_pic)
            
                polygon = QPolygonF()
                y_scroll = self.y_total - (Y_MARGIN + note.sec * SEC_HEIGHT)
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
                        px = self.get_x(note.lane + note.span) - 1   + h // 2 * math.cos(math.pi * (theta / 180))
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Bruh")
    main_window = QMainWindow()
    main_window.show()
    unit = Unit.from_list([100936, 100708, 100914, 100584, 100456, 100964])
    live = Live()
    live.set_music(score_id=19, difficulty=4)
    live.set_unit(unit)
    sim = Simulator(live)
    # res: SimulationResult = sim.simulate(perfect_play=True, abuse=True)
    cpg = BaseChartPicGenerator.get_generator(637, Difficulty(5), main_window, mirrored=True)
    cpg.hook_cards(unit.all_cards())
    # cpg.hook_abuse(unit.all_cards(), res.abuse_data)
    app.exec_()
