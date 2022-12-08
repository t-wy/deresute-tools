from __future__ import annotations

from typing import Optional

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QSizePolicy, QTabWidget
from numpy import ndarray

import customlogger as logger
from exceptions import InvalidUnit
from gui.events.calculator_view_events import GetAllCardsEvent, SimulationEvent, DisplaySimulationResultEvent, \
    AddEmptyUnitEvent, YoinkUnitEvent, PushCardEvent, ContextAwarePushCardEvent, TurnOffRunningLabelFromUuidEvent, \
    TurnOffRunningLabelFromUuidGrandEvent, CacheSimulationEvent, CustomSimulationEvent, CustomSimulationResultEvent
from gui.events.chart_viewer_events import HookAbuseToChartViewerEvent, HookSimResultToChartViewerEvent
from gui.events.song_view_events import GetSongDetailsEvent
from gui.events.state_change_events import PostYoinkEvent, InjectTextEvent, YoinkCustomCardEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.utils.wrappers import BaseSimulationResultWithUuid, YoinkResults
from gui.events.value_accessor_events import GetAutoplayOffsetEvent, GetAutoplayFlagEvent, GetDoublelifeFlagEvent, \
    GetSupportEvent, GetAppealsEvent, GetCustomPotsEvent, GetPerfectPlayFlagEvent, GetMirrorFlagEvent, \
    GetCustomBonusEvent, GetGrooveSongColor, GetSkillBoundaryEvent, GetEncoreAMRFlagEvent, \
    GetEncoreMagicUnitFlagEvent, GetEncoreMagicMaxAggEvent, GetAllowGreatEvent
from gui.viewmodels.simulator.calculator import CalculatorModel, CalculatorView, CardsWithUnitUuidAndExtraData
from gui.viewmodels.simulator.custom_bonus import CustomBonusView, CustomBonusModel
from gui.viewmodels.simulator.custom_settings import CustomSettingsView, CustomSettingsModel
from gui.viewmodels.simulator.edit_card import EditCardView, EditCardModel
from gui.viewmodels.simulator.grandcalculator import GrandCalculatorView, GrandCalculatorModel
from gui.viewmodels.simulator.support import SupportView, SupportModel
from gui.viewmodels.simulator.unit_details import UnitDetailsView, UnitDetailsModel
from logic.grandlive import GrandLive
from logic.grandunit import GrandUnit
from logic.live import Live
from logic.unit import Unit
from network.api_client import get_top_build
from simulator import Simulator, SimulationResult


class MainView:
    widget: QtWidgets.QWidget
    main_layout: QtWidgets.QHBoxLayout
    model: MainModel

    def __init__(self):
        self.widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QHBoxLayout(self.widget)

    def set_model(self, model: MainModel):
        self.model = model

    def setup(self):
        self._setup_calculator_and_custom_setting_layout()
        self._setup_custom_appeal_and_support_layout()

    def _setup_calculator_and_custom_setting_layout(self):
        self.calculator_and_custom_setting_layout = QtWidgets.QVBoxLayout()
        self.bottom_row_layout = QtWidgets.QHBoxLayout()
        self._set_up_big_buttons()
        self._setup_custom_settings()
        self.bottom_row_layout.setStretch(0, 1)
        self.bottom_row_layout.setStretch(1, 4)
        self._set_up_calculator()
        self.calculator_and_custom_setting_layout.addLayout(self.bottom_row_layout)
        self.calculator_and_custom_setting_layout.setStretch(0, 1)
        self.calculator_and_custom_setting_layout.setStretch(1, 0)
        self.main_layout.addLayout(self.calculator_and_custom_setting_layout)
        self.main_layout.setStretch(0, 1)

    def _set_up_big_buttons(self):
        self.button_layout = QtWidgets.QGridLayout()
        self.big_button = QtWidgets.QPushButton("Run", self.widget)
        self.add_button = QtWidgets.QPushButton("Add Empty Unit", self.widget)
        self.yoink_button = QtWidgets.QPushButton("Yoink #1 Unit", self.widget)
        self.permute_button = QtWidgets.QPushButton("Permute Units", self.widget)
        self.times_text = QtWidgets.QLineEdit(self.widget)
        self.times_text.setValidator(QIntValidator(0, 1000, None))  # Only number allowed
        self.times_text.setText("10")
        self.times_label = QtWidgets.QLabel("times", self.widget)

        font = self.big_button.font()
        font.setPointSize(16)
        self.big_button.setFont(font)
        self.big_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        self.big_button.pressed.connect(lambda: self.simulate())

        self.button_layout.addWidget(self.big_button, 0, 0, 2, 2)
        self.button_layout.addWidget(self.times_text, 2, 0, 1, 1)
        self.button_layout.addWidget(self.times_label, 2, 1, 1, 1)
        self.button_layout.addWidget(self.add_button, 0, 2, 1, 1)
        self.button_layout.addWidget(self.yoink_button, 1, 2, 1, 1)
        self.button_layout.addWidget(self.permute_button, 2, 2, 1, 1)
        self.bottom_row_layout.addLayout(self.button_layout)

    def _setup_custom_settings(self):
        self.custom_settings_view = CustomSettingsView(self.widget, self.model)
        self.custom_settings_model = CustomSettingsModel(self.custom_settings_view)
        self.custom_settings_view.set_model(self.custom_settings_model)
        self.bottom_row_layout.addWidget(self.custom_settings_view.tab_widget)

    def _set_up_calculator(self):
        self.calculator_tabs = QtWidgets.QTabWidget(self.widget)
        self.calculator_tabs.setMinimumHeight(250)
        view_wide = CalculatorView(self.widget, self)
        view_grand = GrandCalculatorView(self.widget, self)
        model_wide = CalculatorModel(view_wide)
        model_grand = GrandCalculatorModel(view_grand)
        view_wide.set_model(model_wide)
        view_grand.set_model(model_grand)
        self.views = [view_wide, view_grand]
        self.models = [model_wide, model_grand]
        self.calculator_tabs.addTab(view_wide.widget, "WIDE")
        self.calculator_tabs.addTab(view_grand.widget, "GRAND")
        self.calculator_and_custom_setting_layout.addWidget(self.calculator_tabs)
        self.calculator_tabs.setCurrentIndex(0)
        self._hook_buttons()

    def _hook_buttons(self):
        try:
            self.add_button.pressed.disconnect()
            self.yoink_button.pressed.disconnect()
            self.permute_button.pressed.disconnect()
        except TypeError:
            pass
        self.add_button.pressed.connect(
            lambda: eventbus.eventbus.post(AddEmptyUnitEvent(self.models[self.calculator_tabs.currentIndex()])))
        self.yoink_button.pressed.connect(lambda: self.model.handle_yoink_button())
        self.permute_button.pressed.connect(lambda: self.views[1].permute_units())

    def _setup_custom_appeal_and_support_layout(self):
        self.custom_appeal_and_support_layout = QtWidgets.QVBoxLayout()
        self._setup_custom_bonus()
        self._setup_custom_card_and_support()
        self.main_layout.addLayout(self.custom_appeal_and_support_layout)

    def _setup_custom_bonus(self):
        self.custom_bonus_view = CustomBonusView(self.widget, self.model)
        self.custom_bonus_model = CustomBonusModel(self.custom_bonus_view)
        self.custom_bonus_view.set_model(self.custom_bonus_model)
        self.custom_appeal_and_support_layout.addLayout(self.custom_bonus_view.layout)

    def _setup_custom_card_and_support(self):
        self.custom_card_and_support_widget = QTabWidget(self.widget)
        self._setup_support()
        self._setup_custom_card()
        self._setup_unit_details()
        self.custom_card_and_support_widget.addTab(self.support_view.widget, "Support Team")
        self.custom_card_and_support_widget.addTab(self.custom_card_view.widget, "Edit Card")
        self.custom_card_and_support_widget.addTab(self.unit_details_view.widget, "Unit Details")
        self.custom_appeal_and_support_layout.addWidget(self.custom_card_and_support_widget)

    def _setup_custom_card(self):
        self.custom_card_view = EditCardView(self.widget)
        self.custom_card_model = EditCardModel(self.custom_card_view)
        self.custom_card_view.set_model(self.custom_card_model)

    def _setup_unit_details(self):
        self.unit_details_view = UnitDetailsView(self.widget)
        self.unit_details_model = UnitDetailsModel(self.unit_details_view)
        self.unit_details_view.set_model(self.unit_details_model)

    def _setup_support(self):
        self.support_view = SupportView(self.widget)
        self.support_model = SupportModel(self.support_view)
        self.support_view.set_model(self.support_model)

    def get_current_model(self):
        return self.models[self.calculator_tabs.currentIndex()]

    def get_times(self):
        if self.times_text.text() == "" or self.times_text.text() == "0":
            return 10
        else:
            return int(self.times_text.text())

    def simulate(self, row: int = None):
        score_id, diff_id, live_detail_id, _, _ = eventbus.eventbus.post_and_get_first(GetSongDetailsEvent())
        times = self.get_times()
        all_cards: list[CardsWithUnitUuidAndExtraData] = eventbus.eventbus.post_and_get_first(
            GetAllCardsEvent(self.get_current_model(), row), required_non_none=True)
        perfect_play = eventbus.eventbus.post_and_get_first(GetPerfectPlayFlagEvent())
        custom_pots = eventbus.eventbus.post_and_get_first(GetCustomPotsEvent())
        appeals = eventbus.eventbus.post_and_get_first(GetAppealsEvent())
        support = eventbus.eventbus.post_and_get_first(GetSupportEvent())
        mirror = eventbus.eventbus.post_and_get_first(GetMirrorFlagEvent())
        doublelife = eventbus.eventbus.post_and_get_first(GetDoublelifeFlagEvent())
        autoplay = eventbus.eventbus.post_and_get_first(GetAutoplayFlagEvent())
        autoplay_offset = eventbus.eventbus.post_and_get_first(GetAutoplayOffsetEvent())
        extra_bonus, special_option, special_value = eventbus.eventbus.post_and_get_first(GetCustomBonusEvent())
        left_inclusive, right_inclusive = eventbus.eventbus.post_and_get_first(GetSkillBoundaryEvent())
        force_encore_amr_cache_to_encore_unit = eventbus.eventbus.post_and_get_first(GetEncoreAMRFlagEvent())
        force_encore_magic_to_encore_unit = eventbus.eventbus.post_and_get_first(GetEncoreMagicUnitFlagEvent())
        allow_encore_magic_to_escape_max_agg = eventbus.eventbus.post_and_get_first(GetEncoreMagicMaxAggEvent())
        allow_great = eventbus.eventbus.post_and_get_first(GetAllowGreatEvent())

        self.model.simulate_internal(
            perfect_play=perfect_play,
            left_inclusive=left_inclusive, right_inclusive=right_inclusive,
            score_id=score_id, diff_id=diff_id, times=times, all_cards=all_cards, custom_pots=custom_pots,
            appeals=appeals, support=support, extra_bonus=extra_bonus,
            special_option=special_option, special_value=special_value,
            mirror=mirror, autoplay=autoplay, autoplay_offset=autoplay_offset,
            doublelife=doublelife,
            force_encore_amr_cache_to_encore_unit=force_encore_amr_cache_to_encore_unit,
            force_encore_magic_to_encore_unit=force_encore_magic_to_encore_unit,
            allow_encore_magic_to_escape_max_agg=allow_encore_magic_to_escape_max_agg,
            allow_great=allow_great,
            row=row
        )


class MainModel(QObject):
    view: MainView

    process_simulation_results_signal = pyqtSignal(BaseSimulationResultWithUuid)
    process_yoink_results_signal = pyqtSignal(YoinkResults)

    def __init__(self, view: MainView, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = view
        eventbus.eventbus.register(self)
        self.process_simulation_results_signal.connect(lambda payload: self.process_results(payload))
        self.process_yoink_results_signal.connect(lambda payload: self._handle_yoink_done_signal(payload))

    @staticmethod
    def simulate_internal(perfect_play: bool, left_inclusive: bool, right_inclusive: bool, score_id: int, diff_id: int,
                          times: int, all_cards: list[CardsWithUnitUuidAndExtraData], custom_pots: Optional[list[int]],
                          appeals: Optional[int], support: Optional[int], extra_bonus: Optional[ndarray],
                          special_option: Optional[int], special_value: Optional[int],
                          mirror: bool, autoplay: bool, autoplay_offset: int, doublelife: bool,
                          force_encore_amr_cache_to_encore_unit: bool, force_encore_magic_to_encore_unit: bool,
                          allow_encore_magic_to_escape_max_agg: bool, allow_great: bool, row: int = None):
        all_cards: list[CardsWithUnitUuidAndExtraData]
        if len(all_cards) == 0:
            logger.info("Nothing to simulate")
            return

        notes, color, level, duration = None, None, None, None

        # Initialize song first because SQLite DB thread lock
        # Live objects are mutable so create one for each simulation
        # Load cards
        for extended_cards_data in all_cards:
            cards = extended_cards_data.cards
            is_grand = len(cards) == 15
            if is_grand:
                live = GrandLive()
            else:
                live = Live()

            music_loaded = all(_ is not None for _ in [notes, color, level, duration])

            groove_song_color = eventbus.eventbus.post_and_get_first(GetGrooveSongColor())

            # Load preset music if defined, else load default music
            if extended_cards_data.lock_chart:
                if extended_cards_data.score_id is None:
                    # Lock chart but no music found
                    if is_grand:
                        eventbus.eventbus.post_and_get_first(
                            TurnOffRunningLabelFromUuidGrandEvent(extended_cards_data.uuid))
                    else:
                        eventbus.eventbus.post_and_get_first(TurnOffRunningLabelFromUuidEvent(extended_cards_data.uuid))
                    continue
                if not music_loaded:
                    notes, color, level, duration = live.set_music(score_id=extended_cards_data.score_id,
                                                                   difficulty=extended_cards_data.diff_id, output=True)
                else:
                    live.set_loaded_music(extended_cards_data.score_id, extended_cards_data.diff_id,
                                          notes, color, level, duration)
                groove_song_color = extended_cards_data.groove_song_color
            elif diff_id is not None:
                if not music_loaded:
                    notes, color, level, duration = live.set_music(score_id=score_id, difficulty=diff_id, output=True)
                else:
                    live.set_loaded_music(score_id, diff_id, notes, color, level, duration)
            else:
                if is_grand:
                    eventbus.eventbus.post_and_get_first(
                        TurnOffRunningLabelFromUuidGrandEvent(extended_cards_data.uuid))
                else:
                    eventbus.eventbus.post_and_get_first(TurnOffRunningLabelFromUuidEvent(extended_cards_data.uuid))
                continue

            # Negate custom_pots + load preset appeal bonus if defined, else ignore
            if extended_cards_data.lock_unit:
                inner_custom_pots = None
                inner_extra_bonus = extended_cards_data.extra_bonus
                inner_special_option = extended_cards_data.special_option
                inner_special_value = extended_cards_data.special_value
            else:
                inner_custom_pots = custom_pots
                inner_extra_bonus = extra_bonus
                inner_special_option = special_option
                inner_special_value = special_value

            if groove_song_color is not None:
                live.color = groove_song_color

            try:
                if is_grand:
                    unit = GrandUnit.from_list(cards, inner_custom_pots)
                else:
                    if cards[5] is None:
                        cards = cards[:5]
                    unit = Unit.from_list(cards, inner_custom_pots)
            except InvalidUnit:
                logger.info("Invalid unit: {}".format(cards))
                eventbus.eventbus.post_and_get_first(TurnOffRunningLabelFromUuidEvent(extended_cards_data.uuid))
                continue

            eventbus.eventbus.post(
                SimulationEvent(extended_cards_data.uuid, extended_cards_data.short_uuid,
                                row is not None, appeals, autoplay, autoplay_offset,
                                doublelife, inner_extra_bonus, live, mirror, perfect_play, inner_special_option,
                                inner_special_value, support, times, unit, left_inclusive, right_inclusive,
                                force_encore_amr_cache_to_encore_unit, force_encore_magic_to_encore_unit,
                                allow_encore_magic_to_escape_max_agg, allow_great),
                high_priority=True, asynchronous=True)

    @pyqtSlot(BaseSimulationResultWithUuid)
    def process_results(self, payload: BaseSimulationResultWithUuid):
        eventbus.eventbus.post(DisplaySimulationResultEvent(payload))
        if isinstance(payload.results, SimulationResult):
            eventbus.eventbus.post(HookSimResultToChartViewerEvent(payload.live.score_id, payload.live.difficulty,
                                                                   payload.results.perfect_detail), asynchronous=False)
        if payload.abuse_load:
            if not isinstance(payload.results, SimulationResult):
                return
            eventbus.eventbus.post(HookAbuseToChartViewerEvent(payload.live.score_id, payload.live.difficulty,
                                                               payload.cards, payload.results.abuse_data),
                                   asynchronous=False)

    @subscribe(SimulationEvent)
    def handle_simulation_request(self, event: SimulationEvent):
        eventbus.eventbus.post(CacheSimulationEvent(event))
        event.live.set_unit(event.unit)
        if event.autoplay:
            logger.info("Simulation mode: Autoplay - {} - {}".format(event.short_uuid, event.unit))
            sim = Simulator(event.live, special_offset=0.075,
                            force_encore_amr_cache_to_encore_unit=event.force_encore_amr_cache_to_encore_unit,
                            force_encore_magic_to_encore_unit=event.force_encore_magic_to_encore_unit,
                            allow_encore_magic_to_escape_max_agg=event.allow_encore_magic_to_escape_max_agg)
            result = sim.simulate(appeals=event.appeals, extra_bonus=event.extra_bonus, support=event.support,
                                  special_option=event.special_option, special_value=event.special_value,
                                  doublelife=event.doublelife, perfect_only=not event.allow_great, auto=True,
                                  mirror=event.mirror, time_offset=event.autoplay_offset)
        else:
            if event.perfect_play:
                logger.info("Simulation mode: Perfect - {} - {}".format(event.short_uuid, event.unit))
            else:
                logger.info("Simulation mode: Normal - {} - {}".format(event.short_uuid, event.unit))
            sim = Simulator(event.live, left_inclusive=event.left_inclusive, right_inclusive=event.right_inclusive,
                            force_encore_amr_cache_to_encore_unit=event.force_encore_amr_cache_to_encore_unit,
                            force_encore_magic_to_encore_unit=event.force_encore_magic_to_encore_unit,
                            allow_encore_magic_to_escape_max_agg=event.allow_encore_magic_to_escape_max_agg)
            result = sim.simulate(times=event.times, appeals=event.appeals, extra_bonus=event.extra_bonus,
                                  support=event.support, perfect_play=event.perfect_play,
                                  special_option=event.special_option, special_value=event.special_value,
                                  doublelife=event.doublelife, perfect_only=not event.allow_great)
        self.process_simulation_results_signal.emit(
            BaseSimulationResultWithUuid(event.uuid, event.unit.all_cards(), result, event.abuse_load, event.live))

    @subscribe(CustomSimulationEvent)
    def handle_custom_simulation(self, custom_event: CustomSimulationEvent):
        event = custom_event.simulation_event
        event.live.set_unit(event.unit)

        sim = Simulator(event.live, left_inclusive=event.left_inclusive, right_inclusive=event.right_inclusive,
                        force_encore_amr_cache_to_encore_unit=event.force_encore_amr_cache_to_encore_unit,
                        force_encore_magic_to_encore_unit=event.force_encore_magic_to_encore_unit,
                        allow_encore_magic_to_escape_max_agg=event.allow_encore_magic_to_escape_max_agg)
        result = sim.simulate(times=1, appeals=event.appeals, extra_bonus=event.extra_bonus, support=event.support,
                              perfect_play=True, special_option=event.special_option, special_value=event.special_value,
                              doublelife=event.doublelife, perfect_only=False,
                              deact_skills=custom_event.deact_skills, note_offsets=custom_event.note_offsets)
        eventbus.eventbus.post(CustomSimulationResultEvent(event.live, result))

    def handle_yoink_button(self):
        _, _, live_detail_id, song_name, diff_name = eventbus.eventbus.post_and_get_first(GetSongDetailsEvent())
        if live_detail_id is None:
            return

        self.view.yoink_button.setEnabled(False)
        self.view.yoink_button.setText("Yoinking...")
        eventbus.eventbus.post(InjectTextEvent("Yoinking the top team for {} - {}".format(song_name, diff_name)))
        eventbus.eventbus.post(YoinkUnitEvent(live_detail_id), asynchronous=True)

    @pyqtSlot(YoinkResults)
    def _handle_yoink_done_signal(self, payload: YoinkResults):
        if payload.cards is not None:
            if len(payload.cards) == 15:
                self.view.views[1].add_unit(payload.cards)
            else:
                self.view.views[0].add_unit(payload.cards)
            eventbus.eventbus.post(PostYoinkEvent(payload.support))
            eventbus.eventbus.post(YoinkCustomCardEvent())
        self.view.yoink_button.setText("Yoink #1 Unit")
        self.view.yoink_button.setEnabled(True)

    @subscribe(YoinkUnitEvent)
    def _handle_yoink_signal(self, event: YoinkUnitEvent):
        try:
            cards, support = get_top_build(event.live_detail_id)
            eventbus.eventbus.post(InjectTextEvent("Yoinked successfully", 2))
        except Exception:
            cards, support = None, None
            eventbus.eventbus.post(InjectTextEvent("Yoink failed :(", 2))
        self.process_yoink_results_signal.emit(YoinkResults(cards, support))

    @subscribe(PushCardEvent)
    def context_aware_push_card(self, event: PushCardEvent):
        eventbus.eventbus.post(
            ContextAwarePushCardEvent(self.view.get_current_model(), event))
