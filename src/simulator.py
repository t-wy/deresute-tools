import csv
import time
from typing import Optional, Union, cast, Dict, List, Set, DefaultDict, Tuple

import numpy as np
import pandas as pd
import pyximport

import customlogger as logger
from logic.grandlive import GrandLive
from logic.live import Live
from settings import ABUSE_CHARTS_PATH
from statemachine import StateMachine, AbuseData, LiveDetail
from static.live_values import WEIGHT_RANGE, DIFF_MULTIPLIERS
from static.note_type import NoteType
from utils.storage import get_writer

pyximport.install(language_level=3)


def check_long(notes_data: pd.DataFrame, mask: pd.Series):
    stack = dict()
    for idx, row in notes_data.iterrows():
        if not mask[idx]:
            continue
        lane = row['finishPos']
        if row['note_type'] == NoteType.LONG and lane not in stack:
            stack[lane] = idx
        elif lane in stack:
            stack.pop(lane)
            notes_data.loc[idx, 'is_long'] = True


class BaseSimulationResult:
    def __init__(self):
        pass


class SimulationResult(BaseSimulationResult):
    def __init__(self, total_appeal: int, perfect_score: int, perfect_score_array: List[int],
                 base: int, deltas: np.ndarray, total_life: int, fans: int, full_roll_chance: float,
                 abuse_score: int, abuse_data: AbuseData, perfect_detail: LiveDetail):
        super().__init__()
        self.total_appeal = total_appeal
        self.perfect_score = perfect_score
        self.perfect_score_array = perfect_score_array
        self.base = base
        self.deltas = deltas
        self.total_life = total_life
        self.fans = fans
        self.full_roll_chance = full_roll_chance
        self.abuse_score = abuse_score
        self.abuse_data = abuse_data
        self.perfect_detail = perfect_detail


class AutoSimulationResult(BaseSimulationResult):
    def __init__(self, total_appeal: int, total_life: int, score: int, perfects: int, misses: int, max_combo: int,
                 lowest_life: int, lowest_life_time: float, all_100: bool):
        super().__init__()
        self.total_appeal = total_appeal
        self.total_life = total_life
        self.score = score
        self.perfects = perfects
        self.misses = misses
        self.max_combo = max_combo
        self.lowest_life = lowest_life
        self.lowest_life_time = lowest_life_time
        self.all_100 = all_100


class Simulator:
    live: Union[Live, GrandLive]

    left_inclusive: bool
    right_inclusive: bool
    force_encore_amr_cache_to_encore_unit: bool
    force_encore_magic_to_encore_unit: bool
    allow_encore_magic_to_escape_max_agg: bool

    special_offset: float

    support: int
    total_appeal: int

    base_score: float
    helen_base_score: float

    note_count: int
    notes_data: pd.DataFrame
    song_duration: float
    weight_range: List[float]

    def __init__(self, live: Union[Live, GrandLive] = None, special_offset: float = None,
                 left_inclusive: bool = False, right_inclusive: bool = True,
                 force_encore_amr_cache_to_encore_unit: bool = False,
                 force_encore_magic_to_encore_unit: bool = False,
                 allow_encore_magic_to_escape_max_agg: bool = True):
        self.live = live
        self.left_inclusive = left_inclusive
        self.right_inclusive = right_inclusive
        self.force_encore_amr_cache_to_encore_unit = force_encore_amr_cache_to_encore_unit
        self.force_encore_magic_to_encore_unit = force_encore_magic_to_encore_unit
        self.allow_encore_magic_to_escape_max_agg = allow_encore_magic_to_escape_max_agg
        if special_offset is None:
            self.special_offset = 0
        else:
            self.special_offset = special_offset

    def _setup_simulator(self, appeals: int = None, support: int = None, extra_bonus: np.ndarray = None,
                         chara_bonus_set: Set[int] = None, chara_bonus_value: int = 0,
                         special_option: int = None, special_value: int = None, mirror: bool = False):
        self.live.set_chara_bonus(chara_bonus_set, chara_bonus_value)
        if extra_bonus is not None or special_option is not None:
            if extra_bonus is not None:
                assert isinstance(extra_bonus, np.ndarray) and extra_bonus.shape == (5, 3)
            self.live.set_extra_bonus(extra_bonus, special_option, special_value)
        [unit.get_base_motif_appeals() for unit in self.live.unit.all_units]
        self.notes_data = self.live.notes
        self.song_duration = self.notes_data.iloc[-1].sec
        self.note_count = len(self.notes_data)

        if mirror and self.live.is_grand_chart:
            start_lanes = 16 - (self.notes_data['finishPos'] + self.notes_data['status'] - 1)
            self.notes_data['finishPos'] = start_lanes

        is_flick = self.notes_data['note_type'] == NoteType.FLICK
        is_long = self.notes_data['note_type'] == NoteType.LONG
        is_slide = self.notes_data['note_type'] == NoteType.SLIDE
        is_slide = np.logical_or(is_slide, np.logical_and(self.notes_data['type'] == 3, is_flick))
        is_slide = np.logical_or(is_slide, np.logical_and(
            np.logical_or(self.notes_data['type'] == 6, self.notes_data['type'] == 7), self.notes_data['groupId'] != 0))
        self.notes_data['is_flick'] = is_flick
        self.notes_data['is_long'] = is_long
        self.notes_data['is_slide'] = is_slide
        check_long(self.notes_data, np.logical_or(is_long, is_flick))
        self._helper_mark_slide_checkpoints()

        weight_range = np.array(WEIGHT_RANGE)
        weight_range[:, 0] = np.trunc(WEIGHT_RANGE[:, 0] / 100 * len(self.notes_data) - 1)
        for idx, (bound_l, bound_r) in enumerate(zip(weight_range[:-1, 0], weight_range[1:, 0])):
            self.notes_data.loc[int(bound_l):int(bound_r), 'weight'] = weight_range[idx][1]
        self.weight_range = self.notes_data['weight'].to_list()

        if support is not None:
            self.support = support
        else:
            self.support = self.live.get_support()
        if appeals:
            self.total_appeal = appeals
        else:
            self.total_appeal = self.live.get_appeals() + self.support
        self.base_score = DIFF_MULTIPLIERS[self.live.level] * self.total_appeal / len(self.notes_data)
        self.helen_base_score = DIFF_MULTIPLIERS[self.live.level] * self.total_appeal / len(self.notes_data)

    def _helper_mark_slide_checkpoints(self):
        self.notes_data['checkpoints'] = False
        self.notes_data.loc[self.notes_data['note_type'] == NoteType.SLIDE, 'checkpoints'] = True
        for group_id in self.notes_data[self.notes_data['note_type'] == NoteType.SLIDE].groupId.unique():
            group = self.notes_data[(self.notes_data['groupId'] == group_id)]
            self.notes_data.loc[group.iloc[-1].name, 'checkpoints'] = False
            self.notes_data.loc[group.iloc[0].name, 'checkpoints'] = False

    def simulate(self, times: int = 100, appeals: int = None,
                 extra_bonus: np.ndarray = None, support: int = None, perfect_play: bool = False,
                 chara_bonus_set: Set[int] = None, chara_bonus_value: int = 0,
                 special_option: int = None, special_value: int = None, doublelife: bool = False,
                 perfect_only: bool = True, auto: bool = False, mirror: bool = False, time_offset: int = 0,
                 deact_skills: Dict[int, List[int]] = None, note_offsets: DefaultDict[int, int] = None,
                 note_misses: List[int] = None) -> Union[SimulationResult, AutoSimulationResult]:
        start = time.time()
        logger.debug("Unit: {}".format(self.live.unit))
        logger.debug("Song: {} - {} - Lv {}".format(self.live.music_name, self.live.difficulty, self.live.level))
        if perfect_play or auto:
            times = 1
            logger.debug("Only need 1 simulation for perfect play or auto.")
        if not auto:
            res = self._simulate(times, appeals=appeals, extra_bonus=extra_bonus, support=support,
                                 perfect_play=perfect_play,
                                 chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                                 special_option=special_option, special_value=special_value,
                                 doublelife=doublelife, perfect_only=perfect_only,
                                 deact_skills=deact_skills, note_offsets=note_offsets, note_misses=note_misses)
            self.save_to_file(res.perfect_score_array, res.abuse_data)
        else:
            res = self._simulate_auto(appeals=appeals, extra_bonus=extra_bonus, support=support,
                                      chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                                      special_option=special_option, special_value=special_value,
                                      time_offset=time_offset, mirror=mirror, doublelife=doublelife)
        logger.debug("Total run time for {} trials: {:04.2f}s".format(times, time.time() - start))
        return res

    def _simulate(self, times: int = 100, appeals: int = None,
                  extra_bonus: np.ndarray = None, support: int = None, perfect_play: bool = False,
                  chara_bonus_set: Set[int] = None, chara_bonus_value: int = 0,
                  special_option: int = None, special_value: int = None,
                  doublelife: bool = False, perfect_only: bool = True,
                  deact_skills: Dict[int, List[int]] = None, note_offsets: DefaultDict[int, int] = None,
                  note_misses: List[int] = None) -> SimulationResult:
        self._setup_simulator(appeals=appeals, support=support, extra_bonus=extra_bonus,
                              chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                              special_option=special_option, special_value=special_value)
        grand = self.live.is_grand

        results = self._simulate_internal(times=times, grand=grand, fail_simulate=not perfect_play,
                                          doublelife=doublelife, perfect_only=perfect_only,
                                          deact_skills=deact_skills, note_offsets=note_offsets, note_misses=note_misses)
        perfect_score, perfect_score_array, random_simulation_results, full_roll_chance, \
            abuse_score, abuse_data, perfect_detail = results

        if perfect_play:
            base = perfect_score
            deltas = np.zeros(1)
        else:
            score_array = np.array([simulation_result[0] for simulation_result in random_simulation_results])
            base = int(score_array.mean())
            deltas = score_array - base

        total_fans = 0
        if grand:
            base_fan = base / 3 * 0.001 * 1.1
            for unit_live in self.live.unit_lives:
                total_fans += int(np.ceil(base_fan * (1 + unit_live.fan / 100))) * 5
        else:
            total_fans = int(base * 0.001 * (1.1 + self.live.fan / 100)) * 5

        logger.debug("Tensor size: {}".format(self.notes_data.shape))
        logger.debug("Appeal: {}".format(int(self.total_appeal)))
        logger.debug("Support: {}".format(int(self.live.get_support())))
        logger.debug("Support team: {}".format(self.live.print_support_team()))
        logger.debug("Perfect: {}".format(int(perfect_score)))
        logger.debug("Mean: {}".format(int(base + np.round(deltas.mean()))))
        logger.debug("Median: {}".format(int(base + np.round(np.median(deltas)))))
        logger.debug("Max: {}".format(int(base + deltas.max(initial=0))))
        logger.debug("Min: {}".format(int(base + deltas.min(initial=0))))
        logger.debug("Deviation: {}".format(int(np.round(np.std(deltas)))))
        return SimulationResult(
            total_appeal=self.total_appeal,
            perfect_score=perfect_score,
            perfect_score_array=perfect_score_array,
            base=base,
            deltas=deltas,
            total_life=self.live.get_life(),
            full_roll_chance=full_roll_chance,
            fans=total_fans,
            abuse_score=int(abuse_score),
            abuse_data=abuse_data,
            perfect_detail=perfect_detail
        )

    def _simulate_internal(self, grand: bool, times: int, fail_simulate: bool = False, doublelife: bool = False,
                           perfect_only: bool = True, auto: bool = False, time_offset: int = 0,
                           deact_skills: Dict[int, List[int]] = None, note_offsets: DefaultDict[int, int] = None,
                           note_misses: List[int] = None) \
            -> Union[Tuple[np.ndarray, int, int, int, int, int, bool, int],
                     Tuple[int, List[int], List[tuple], float, int, Optional[AbuseData], LiveDetail]]:
        impl = StateMachine(grand=grand, difficulty=self.live.difficulty, doublelife=doublelife, live=self.live,
                            notes_data=self.notes_data, left_inclusive=self.left_inclusive,
                            right_inclusive=self.right_inclusive, base_score=self.base_score,
                            helen_base_score=self.helen_base_score, weights=self.weight_range,
                            force_encore_amr_cache_to_encore_unit=self.force_encore_amr_cache_to_encore_unit,
                            force_encore_magic_to_encore_unit=self.force_encore_magic_to_encore_unit,
                            allow_encore_magic_to_escape_max_agg=self.allow_encore_magic_to_escape_max_agg,
                            custom_deact_skills=deact_skills, custom_note_offsets=note_offsets,
                            custom_note_misses=note_misses)

        if auto:
            impl.reset_machine(time_offset=time_offset, special_offset=self.special_offset, auto=True)
            return impl.simulate_impl_auto()

        impl.reset_machine(perfect_play=True, perfect_only=True)
        perfect_score, perfect_score_array, perfect_detail = impl.simulate_impl()
        logger.debug("Perfect scores: " + " ".join(map(str, impl.get_note_scores())))
        full_roll_chance = impl.get_full_roll_chance()

        scores = list()
        if fail_simulate:
            for _ in range(times):
                impl.reset_machine(perfect_play=False, perfect_only=perfect_only)
                scores.append(impl.simulate_impl()[0:2])

        impl.reset_machine(perfect_play=True, abuse=True, perfect_only=False)
        abuse_result_score, abuse_data = impl.simulate_impl(skip_activation_initialization=True)
        logger.debug("Total abuse: {}".format(int(abuse_result_score)))
        logger.debug("Abuse deltas: " + " ".join(map(str, abuse_data.score_delta)))
        return perfect_score, perfect_score_array, scores, full_roll_chance, \
            abuse_result_score, abuse_data, perfect_detail

    def _simulate_auto(self, appeals: int = None, extra_bonus: np.ndarray = None, support: int = None,
                       chara_bonus_set: Set[int] = None, chara_bonus_value: int = 0,
                       special_option: int = None, special_value: int = None,
                       time_offset: int = 0, mirror: bool = False, doublelife: bool = False) -> AutoSimulationResult:
        if time_offset >= 200:
            self.special_offset = 0
        elif 125 >= time_offset > 100:
            self.special_offset = 0.075
        elif time_offset > 125:
            self.special_offset = 0.2 - time_offset / 1000

        # Pump dummy notes to check for intervals where notes fail
        self._setup_simulator(appeals=appeals, support=support, extra_bonus=extra_bonus,
                              chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                              special_option=special_option, special_value=special_value, mirror=mirror)

        grand = self.live.is_grand
        note_scores, perfects, misses, max_combo, lowest_life, lowest_life_time, all_100 \
            = self._simulate_internal(times=1, grand=grand, doublelife=doublelife, auto=True, time_offset=time_offset)

        auto_score = int(note_scores.sum())

        logger.debug("Tensor size: {}".format(self.notes_data.shape))
        logger.debug("Appeal: {}".format(int(self.total_appeal)))
        logger.debug("Support: {}".format(int(self.live.get_support())))
        logger.debug("Support team: {}".format(self.live.print_support_team()))
        logger.debug("Auto score: {}".format(auto_score))
        logger.debug("Perfects/Misses: {}/{}".format(perfects, misses))
        logger.debug("Max Combo: {}".format(max_combo))
        logger.debug("Lowest Life: {}".format(lowest_life))
        logger.debug("Lowest Life Time: {}".format(lowest_life_time))
        logger.debug("All 100: {}".format(all_100))

        ret = AutoSimulationResult(
            total_appeal=self.total_appeal,
            total_life=self.live.get_life(),
            score=auto_score,
            perfects=perfects,
            misses=misses,
            max_combo=max_combo,
            lowest_life=lowest_life,
            lowest_life_time=(lowest_life_time // 1000) / 1000,
            all_100=all_100
        )
        return ret

    def save_to_file(self, perfect_scores: List[int], abuse_data: AbuseData):
        with get_writer(ABUSE_CHARTS_PATH / "{}.csv".format(self.live.score_id), 'w', newline='') as fw:
            csv_writer = csv.writer(fw)
            csv_writer.writerow(["Card Name", "Card ID", "Vo", "Da", "Vi", "Lf", "Sk"])
            for card in self.live.unit.all_cards():
                csv_writer.writerow(
                    [str(card), card.card_id, card.vo_pots, card.da_pots, card.vi_pots, card.li_pots, card.sk_pots])
            csv_writer.writerow(["Support", self.support])
            csv_writer.writerow([])
            csv_writer.writerow(["Note", "Time", "Type", "Lane", "Perfect Score", "Left", "Right", "Delta", "Window",
                                 "Cumulative Perfect Score", "Cumulative Max Score"])
            cumsum_pft = 0
            cumsum_max = 0
            for idx, row in self.notes_data.iterrows():
                idx = cast(int, idx)
                l = abuse_data.window_l[idx]
                r = abuse_data.window_r[idx]
                window = r - l
                delta = abuse_data.score_delta[idx]
                cumsum_pft += perfect_scores[idx]
                cumsum_max += perfect_scores[idx] + delta
                csv_writer.writerow([idx, row['sec'], row['note_type'], row['finishPos'], perfect_scores[idx],
                                     l, r, delta, window, cumsum_pft, cumsum_max])
