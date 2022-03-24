from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QStackedWidget

from chart_pic_generator import BaseChartPicGenerator, WINDOW_WIDTH, SCROLL_WIDTH, MAX_LABEL_Y
from gui.events.chart_viewer_events import SendMusicEvent, HookAbuseToChartViewerEvent, HookUnitToChartViewerEvent, \
    ToggleMirrorEvent, PopupChartViewerEvent
from gui.events.song_view_events import GetSongDetailsEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.value_accessor_events import GetMirrorFlagEvent


class ChartViewerListener:
    def __init__(self):
        self.chart_viewer = None
        eventbus.eventbus.register(self)

    @subscribe(PopupChartViewerEvent)
    def popup_chart_viewer(self, event=None):
        if self.chart_viewer is None:
            self.chart_viewer = ChartViewer(self)
        if event.look_for_chart:
            score_id, diff_id, _, _, _ = eventbus.eventbus.post_and_get_first(GetSongDetailsEvent())
            if score_id is None:
                return
            eventbus.eventbus.post(SendMusicEvent(score_id, diff_id))


class ChartViewer:
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.generator = None
        
        self.widget = QWidget(parent)
        self.widget.layout = QVBoxLayout(self.widget)
        self.info_widget = QWidget() #QStackedWidget
        self.chart_widget = QScrollArea()
        self.chart_widget.setFixedWidth(WINDOW_WIDTH + SCROLL_WIDTH)
        self.widget.layout.addWidget(self.info_widget)
        self.widget.layout.addWidget(self.chart_widget)
        
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
        mirror_flag = eventbus.eventbus.post_and_get_first(GetMirrorFlagEvent())
        self.generator = BaseChartPicGenerator.get_generator(event.song_id, event.difficulty, self, reset_main=False,
                                                             mirrored=mirror_flag)

    @subscribe(HookAbuseToChartViewerEvent)
    def hook_abuse(self, event: HookAbuseToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_abuse(event.cards, event.abuse_df)

    @subscribe(HookUnitToChartViewerEvent)
    def hook_unit(self, event: HookUnitToChartViewerEvent):
        if self.generator is None:
            return
        self.generator.hook_cards(event.cards)

    @subscribe(ToggleMirrorEvent)
    def toggle_mirror(self, event: ToggleMirrorEvent):
        if self.generator is None:
            return
        self.generator = self.generator.mirror_generator(event.mirrored)

    '''
    def keyPressEvent(self, event):
        key = event.key()
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_S:
            self.generator.save_image()
    '''


listener = ChartViewerListener()
