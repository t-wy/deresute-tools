from __future__ import annotations

from collections import defaultdict
from typing import Union, Optional, TYPE_CHECKING

from numpy import ndarray

from gui.events.utils.wrappers import BaseSimulationResultWithUuid
from logic.grandlive import GrandLive
from logic.grandunit import GrandUnit
from logic.live import Live
from logic.unit import Unit
from simulator import SimulationResult
from static.song_difficulty import Difficulty

if TYPE_CHECKING:
    from gui.viewmodels.simulator.calculator import CalculatorModel, CardsWithUnitUuidAndExtraData
    from gui.viewmodels.simulator.grandcalculator import GrandCalculatorModel


class GetAllCardsEvent:
    def __init__(self, model: Union[CalculatorModel, GrandCalculatorModel], row: Optional[int]):
        self.model = model
        self.row = row


class SimulationEvent:
    def __init__(self, uuid: str, short_uuid: str, abuse_load: bool, appeals: int, autoplay: bool, autoplay_offset: int,
                 doublelife: bool, extra_bonus: ndarray, live: Union[Live, GrandLive], mirror: bool, perfect_play: bool,
                 special_option: int, special_value: int, support: int, times: int, unit: Union[Unit, GrandUnit],
                 left_inclusive: bool, right_inclusive: bool, force_encore_amr_cache_to_encore_unit: bool = False,
                 force_encore_magic_to_encore_unit: bool = False, allow_encore_magic_to_escape_max_agg: bool = True,
                 allow_great: bool = False):
        self.uuid = uuid
        self.short_uuid = short_uuid
        self.abuse_load = abuse_load
        self.appeals = appeals
        self.autoplay = autoplay
        self.autoplay_offset = autoplay_offset
        self.doublelife = doublelife
        self.extra_bonus = extra_bonus
        self.live = live
        self.mirror = mirror
        self.perfect_play = perfect_play
        self.special_option = special_option
        self.special_value = special_value
        self.support = support
        self.times = times
        self.unit = unit
        self.left_inclusive = left_inclusive
        self.right_inclusive = right_inclusive
        self.force_encore_amr_cache_to_encore_unit = force_encore_amr_cache_to_encore_unit
        self.force_encore_magic_to_encore_unit = force_encore_magic_to_encore_unit
        self.allow_encore_magic_to_escape_max_agg = allow_encore_magic_to_escape_max_agg
        self.allow_great = allow_great


class DisplaySimulationResultEvent:
    def __init__(self, payload: BaseSimulationResultWithUuid):
        self.payload = payload


class AddEmptyUnitEvent:
    def __init__(self, active_tab: Union[CalculatorModel, GrandCalculatorModel]):
        self.active_tab = active_tab


class YoinkUnitEvent:
    def __init__(self, live_detail_id: int):
        self.live_detail_id = live_detail_id


class SetSupportCardsEvent:
    def __init__(self, extended_cards_data: CardsWithUnitUuidAndExtraData):
        self.extended_cards_data = extended_cards_data


class RequestSupportTeamEvent:
    def __init__(self):
        pass


class SupportTeamSetMusicEvent:
    def __init__(self, score_id: int, difficulty: Difficulty):
        self.score_id = score_id
        self.difficulty = difficulty


class PushCardEvent:
    def __init__(self, card_id: int, skip_guest_push: bool = False):
        self.card_id = card_id
        self.skip_guest_push = skip_guest_push


class ContextAwarePushCardEvent:
    def __init__(self, model: Union[CalculatorModel, GrandCalculatorModel], event: PushCardEvent):
        self.model = model
        self.event = event


class TurnOffRunningLabelFromUuidEvent:
    def __init__(self, uuid: str):
        self.uuid = uuid


class TurnOffRunningLabelFromUuidGrandEvent:
    def __init__(self, uuid: str):
        self.uuid = uuid


class ToggleUnitLockingOptionsVisibilityEvent:
    def __init__(self):
        pass


class CacheSimulationEvent:
    def __init__(self, event: SimulationEvent):
        self.event = event


class CustomSimulationEvent:
    def __init__(self, simulation_event: SimulationEvent,
                 deact_skills: dict[int, list[int]], note_offsets: defaultdict[int, int]):
        self.simulation_event = simulation_event
        self.deact_skills = deact_skills
        self.note_offsets = note_offsets


class CustomSimulationResultEvent:
    def __init__(self, live: Union[Live, GrandLive], result: SimulationResult):
        self.live = live
        self.result = result
