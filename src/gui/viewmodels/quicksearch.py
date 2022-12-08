from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QCheckBox, QLineEdit, QApplication, QWidget, QLayout

import customlogger as logger
from gui.events.quicksearch_events import PushCardIndexEvent, ToggleQuickSearchOptionEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.viewmodels.card import CardView
from gui.viewmodels.song import SongView
from logic.search import search_engine


class ShortcutQuickSearchWidget(QLineEdit):
    def __init__(self, parent, *__args):
        super().__init__(parent, *__args)

        self.model_id = 0

    def keyPressEvent(self, event):
        key = event.key()
        match_dict = {
            Qt.Key_1: 0,
            Qt.Key_2: 1,
            Qt.Key_3: 2,
            Qt.Key_4: 3,
            Qt.Key_5: 4,
            Qt.Key_6: 5,
            Qt.Key_7: 6,
            Qt.Key_8: 7,
            Qt.Key_9: 8,
            Qt.Key_0: 9
        }
        if QApplication.keyboardModifiers() == Qt.AltModifier and key in match_dict:
            eventbus.eventbus.post(PushCardIndexEvent(match_dict[key], False, self.model_id))
            return
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key in match_dict:
            eventbus.eventbus.post(PushCardIndexEvent(match_dict[key], True, self.model_id))
            return
        if QApplication.keyboardModifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_Q:
            eventbus.eventbus.post(ToggleQuickSearchOptionEvent("ssr"))
            return
        if QApplication.keyboardModifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_W:
            eventbus.eventbus.post(ToggleQuickSearchOptionEvent("idolized"))
            return
        if QApplication.keyboardModifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_E:
            eventbus.eventbus.post(ToggleQuickSearchOptionEvent("owned_only"))
            return
        if QApplication.keyboardModifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_R:
            eventbus.eventbus.post(ToggleQuickSearchOptionEvent("partial_match"))
            return
        super().keyPressEvent(event)


class QuickSearchView:
    widget: ShortcutQuickSearchWidget
    model: QuickSearchModel

    def __init__(self, main: QWidget):
        self.widget = ShortcutQuickSearchWidget(main)
        self.widget.setPlaceholderText("Search for card")
        self.widget.setMaximumSize(QSize(2000, 25))

    def set_model(self, model: QuickSearchModel):
        assert isinstance(model, QuickSearchModel)
        self.model = model
        self.widget.textChanged.connect(lambda: self.trigger())

    def set_model_id(self, model_id: int):
        self.widget.model_id = model_id

    def trigger(self):
        self.model.call_searchengine(self.widget.text().strip())

    def focus(self):
        self.widget.setFocus()


class QuickSearchModel:
    view: QuickSearchView
    card_view: CardView
    options: dict[str, QCheckBox]

    def __init__(self, view: QuickSearchView, card_view: CardView):
        self.view = view
        self.card_view = card_view
        self.options = dict()
        eventbus.eventbus.register(self)

    def call_searchengine(self, query: str):
        if query == "" \
                and not self.options["ssr"].isChecked() \
                and not self.options["idolized"].isChecked() \
                and not self.options["owned_only"].isChecked():
            query = "*"
        card_ids = search_engine.advanced_single_query(
            query,
            ssr=self.options["ssr"].isChecked(),
            idolized=self.options["idolized"].isChecked(),
            partial_match=self.options["partial_match"].isChecked(),
            owned_only=self.options["owned_only"].isChecked()
        )
        logger.debug("Query: {}".format(query))
        logger.debug("Result: {}".format(card_ids))
        self.card_view.show_only_ids(card_ids)

    def _add_option(self, option: str, option_text: str, parent_layout: QLayout, main: QWidget):
        check_box = QCheckBox(main)
        check_box.setText(option_text)
        check_box.stateChanged.connect(lambda: self.call_searchengine(self.view.widget.text().strip()))
        self.options[option] = check_box
        parent_layout.addWidget(check_box)

    def add_options(self, parent_layout: QLayout, main: QWidget):
        for option, option_text in zip(
                ["ssr", "idolized", "owned_only", "partial_match", "potential_stat", "carnival"],
                ["SSR only", "Idolized only", "Owned cards only", "Partial match",
                 "Include potential stat", "Highlight Carnival Idols"]):
            self._add_option(option, option_text, parent_layout, main)
        self.options['ssr'].setToolTip("Only show SSR and SSR+.")
        self.options['idolized'].setToolTip("Only show N+, R+, SR+, and SSR+.")
        self.options['owned_only'].setToolTip("Hide all cards you don't have.")
        self.options['partial_match'].setToolTip("This option might significantly increase query time!")
        self.options['potential_stat'].setToolTip("Add stats from idol potential.")
        self.options['partial_match'].setChecked(True)
        self.options['potential_stat'].stateChanged.connect(
            lambda: self.toggle_potential(self.options['potential_stat'].isChecked()))
        self.options['carnival'].stateChanged.connect(lambda _: self.card_view.model.highlight_event_cards(_))

    @subscribe(ToggleQuickSearchOptionEvent)
    def toggle_option(self, event: ToggleQuickSearchOptionEvent):
        if type(self.options[event.option]) == QCheckBox:
            self.options[event.option].nextCheckState()

    def toggle_potential(self, potential: bool):
        self.card_view.disconnect_cell_change()
        self.card_view.model.set_potential_inclusion(potential)
        self.card_view.model.initialize_cards(potential=potential)
        self.call_searchengine(self.view.widget.text().strip())
        self.card_view.connect_cell_change()


class SongShortcutQuickSearchWidget(ShortcutQuickSearchWidget):
    def keyPressEvent(self, event):
        super(ShortcutQuickSearchWidget, self).keyPressEvent(event)


class SongQuickSearchView:
    widget: SongShortcutQuickSearchWidget
    model: SongQuickSearchModel

    def __init__(self, main: QWidget):
        self.widget = SongShortcutQuickSearchWidget(main)
        self.widget.setMaximumSize(QSize(2000, 25))
        self.widget.setPlaceholderText("Search for song")

    def set_model(self, model: SongQuickSearchModel):
        assert isinstance(model, SongQuickSearchModel)
        self.model = model
        self.widget.textChanged.connect(lambda: self.trigger())

    def trigger(self):
        self.model.call_searchengine(self.widget.text().strip())

    def focus(self):
        self.widget.setFocus()


class SongQuickSearchModel:
    view: SongQuickSearchView
    song_view: SongView

    def __init__(self, view: SongQuickSearchView, song_view: SongView):
        self.view = view
        self.song_view = song_view

    def call_searchengine(self, query: str):
        if query == "":
            live_detail_ids = search_engine.song_query("*")
        else:
            live_detail_ids = search_engine.song_query(query)
        logger.debug("Query: {}".format(query))
        logger.debug("Result: {}".format(live_detail_ids))
        self.song_view.show_only_ids(live_detail_ids)
