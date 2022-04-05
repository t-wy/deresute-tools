import csv
import time

import numpy as np
import pyximport

import customlogger as logger
from settings import ABUSE_CHARTS_PATH
from statemachine import StateMachine, AbuseData
from static.live_values import WEIGHT_RANGE, DIFF_MULTIPLIERS
from static.note_type import NoteType
from utils.storage import get_writer

pyximport.install(language_level=3)
SPECIAL_OFFSET = 0.075


def check_long(notes_data, mask):
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
    def __init__(self, total_appeal, perfect_score, perfect_score_array, base, deltas, total_life, fans,
                 full_roll_chance,
                 abuse_score, abuse_data: AbuseData, cc_fr_base, cc_great_num, cc_base,
                 perfect_detail = None):
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
        self.cc_fr_base = cc_fr_base
        self.cc_great_num = cc_great_num
        self.cc_base = cc_base
        self.perfect_detail = perfect_detail


class AutoSimulationResult(BaseSimulationResult):
    def __init__(self, total_appeal, total_life, score, perfects, misses, max_combo, lowest_life, lowest_life_time,
                 all_100):
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


class LiveDetail():
    def __init__(self, note_offset, skill_inactive, life, score_bonus_skill, combo_bonus_skill, note_score_list):
        self.note_offset = note_offset
        self.skill_inactive = skill_inactive
        self.life = life
        self.score_bonus_skill = score_bonus_skill
        self.combo_bonus_skill = combo_bonus_skill
        self.note_score_list = note_score_list


class Simulator:
    def __init__(self, live=None, special_offset=None, left_inclusive=False, right_inclusive=True,
                 force_encore_amr_cache_to_encore_unit=False,
                 force_encore_magic_to_encore_unit=False,
                 allow_encore_magic_to_escape_max_agg=True,
                 cc_great=0):
        self.live = live
        self.left_inclusive = left_inclusive
        self.right_inclusive = right_inclusive
        self.force_encore_amr_cache_to_encore_unit = force_encore_amr_cache_to_encore_unit
        self.force_encore_magic_to_encore_unit = force_encore_magic_to_encore_unit
        self.allow_encore_magic_to_escape_max_agg = allow_encore_magic_to_escape_max_agg
        self.cc_great = cc_great
        if special_offset is None:
            self.special_offset = 0
        else:
            self.special_offset = special_offset

    def _setup_simulator(self, appeals=None, support=None, extra_bonus=None, chara_bonus_set=None, chara_bonus_value=0,
                         special_option=None, special_value=None, mirror=False):
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
            group = self.notes_data[
                (self.notes_data['groupId'] != 0) & (self.notes_data['groupId'] == group_id)]
            self.notes_data.loc[group.iloc[-1].name, 'checkpoints'] = False
            self.notes_data.loc[group.iloc[0].name, 'checkpoints'] = False

    def simulate(self, times=100, appeals=None, extra_bonus=None, support=None, perfect_play=False,
                 chara_bonus_set=None, chara_bonus_value=0, special_option=None, special_value=None,
                 doublelife=False, perfect_only=True, abuse=False, output=False, auto=False, mirror=False,
                 time_offset=0):
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
                                 doublelife=doublelife, perfect_only=perfect_only, abuse=abuse)
            if output:
                self.save_to_file(res.perfect_score_array, res.abuse_data)
        else:
            res = self._simulate_auto(appeals=appeals, extra_bonus=extra_bonus, support=support,
                                      chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                                      special_option=special_option, special_value=special_value,
                                      time_offset=time_offset, mirror=mirror, doublelife=doublelife)
        logger.debug("Total run time for {} trials: {:04.2f}s".format(times, time.time() - start))
        return res

    def save_to_file(self, perfect_scores, abuse_data):
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
                l = abuse_data.window_l[idx]
                r = abuse_data.window_r[idx]
                window = r - l
                delta = abuse_data.score_delta[idx]
                cumsum_pft += perfect_scores[idx]
                cumsum_max += perfect_scores[idx] + delta
                csv_writer.writerow([idx, row['sec'], row['note_type'],
                                     row['finishPos'],
                                     perfect_scores[idx],
                                     l, r,
                                     delta,
                                     window,
                                     cumsum_pft,
                                     cumsum_max
                                     ])

    def _simulate(self,
                  times=1000,
                  appeals=None,
                  extra_bonus=None,
                  support=None,
                  perfect_play=False,
                  chara_bonus_set=None,
                  chara_bonus_value=0,
                  special_option=None,
                  special_value=None,
                  doublelife=False,
                  perfect_only=True,
                  abuse=False
                  ):

        self._setup_simulator(appeals=appeals, support=support, extra_bonus=extra_bonus,
                              chara_bonus_set=chara_bonus_set, chara_bonus_value=chara_bonus_value,
                              special_option=special_option, special_value=special_value)
        grand = self.live.is_grand

        if self.cc_great > 0:
            cc_fr_results = self._simulate_internal(times=times, grand=grand, fail_simulate=False,
                                              doublelife=doublelife, perfect_only=False, abuse=False, cc_great=self.cc_great)
            _, _, cc_fr_random_simulation_results, _, _, _, cc_great_num_list, _ = cc_fr_results
            
            cc_results = self._simulate_internal(times=times, grand=grand, fail_simulate=True,
                                              doublelife=doublelife, perfect_only=False, abuse=False, cc_great=self.cc_great)
            _, _, cc_random_simulation_results, _, _, _, _, _ = cc_results
                        
            cc_fr_array = np.array([_[0] for _ in cc_fr_random_simulation_results])
            cc_fr_num_score_list = [(cc_great_num_list[_], cc_fr_array[_]) for _ in range(len(cc_great_num_list))]
            cc_fr_num_score_list.sort()
            if len(cc_fr_num_score_list) % 2 == 0:
                cc_fr_num_score_list = cc_fr_num_score_list[:-1]
            m = cc_fr_num_score_list[len(cc_fr_num_score_list)//2]
            cc_great_num = m[0]
            cc_fr_base = int(m[1])
            cc_array = np.array([_[0] for _ in cc_random_simulation_results])
            cc_base = int(np.median(cc_array))
        else:
            cc_fr_base, cc_great_num, cc_base = 0, 0, 0
        
        results = self._simulate_internal(times=times, grand=grand, fail_simulate=not perfect_play,
                                          doublelife=doublelife, perfect_only=perfect_only, abuse=abuse, cc_great=0)
        
        perfect_score, perfect_score_array, random_simulation_results, full_roll_chance, abuse_score, abuse_data, _, perfect_detail = results
        
        if perfect_play:
            base = perfect_score
            deltas = np.zeros(1)
        else:
            score_array = np.array([_[0] for _ in random_simulation_results])
            base = int(score_array.mean())
            deltas = score_array - base

        total_fans = 0
        if grand:
            base_fan = base / 3 * 0.001 * 1.1
            for _ in self.live.unit_lives:
                total_fans += int(np.ceil(base_fan * (1 + _.fan / 100))) * 5
        else:
            total_fans = int(base * 0.001 * (1.1 + self.live.fan / 100)) * 5

        logger.debug("Tensor size: {}".format(self.notes_data.shape))
        logger.debug("Appeal: {}".format(int(self.total_appeal)))
        logger.debug("Support: {}".format(int(self.live.get_support())))
        logger.debug("Support team: {}".format(self.live.print_support_team()))
        logger.debug("Perfect: {}".format(int(perfect_score)))
        logger.debug("Mean: {}".format(int(base + np.round(deltas.mean()))))
        logger.debug("Median: {}".format(int(base + np.round(np.median(deltas)))))
        logger.debug("Max: {}".format(int(base + deltas.max())))
        logger.debug("Min: {}".format(int(base + deltas.min())))
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
            cc_fr_base=cc_fr_base,
            cc_great_num=cc_great_num,
            cc_base=cc_base,
            perfect_detail=LiveDetail(perfect_detail['note_offset'],
                                      perfect_detail['skill_inactive'],
                                      perfect_detail['life'],
                                      perfect_detail['score_bonus_skill'],
                                      perfect_detail['combo_bonus_skill'],
                                      perfect_detail['score_list']
                                      )
        )

    def _simulate_internal(self, grand, times, fail_simulate=False, doublelife=False, perfect_only=True, abuse=False,
                           auto=False, time_offset=0, cc_great=0):
        impl = StateMachine(
            grand=grand,
            difficulty=self.live.difficulty,
            doublelife=doublelife,
            live=self.live,
            notes_data=self.notes_data,
            left_inclusive=self.left_inclusive,
            right_inclusive=self.right_inclusive,
            base_score=self.base_score,
            helen_base_score=self.helen_base_score,
            weights=self.weight_range,
            force_encore_amr_cache_to_encore_unit=self.force_encore_amr_cache_to_encore_unit,
            force_encore_magic_to_encore_unit=self.force_encore_magic_to_encore_unit,
            allow_encore_magic_to_escape_max_agg=self.allow_encore_magic_to_escape_max_agg,
            cc_great=cc_great
        )

        if auto:
            impl.reset_machine(time_offset=time_offset, special_offset=self.special_offset, auto=True)
            return impl.simulate_impl_auto()

        impl.reset_machine(perfect_play=True, perfect_only=True)
        perfect_score, perfect_score_array, perfect_detail = impl.simulate_impl()
        logger.debug("Perfect scores: " + " ".join(map(str, impl.get_note_scores())))
        full_roll_chance = impl.get_full_roll_chance()

        scores = list()
        if cc_great == 0 and fail_simulate:
            for _ in range(times):
                impl.reset_machine(perfect_play=False, perfect_only=perfect_only)
                scores.append(impl.simulate_impl()[0:2])

        cc_great_num = list()
        if cc_great > 0:
            if not fail_simulate: #fr
                for _ in range(times):
                    impl.reset_machine(perfect_play=True, perfect_only=True)
                    scores.append(impl.simulate_impl()[0:2])
                    cc_great_num.append(impl.get_cc_great_num())
            else: #not fr
                for _ in range(times):
                    impl.reset_machine(perfect_play=False, perfect_only=True)
                    scores.append(impl.simulate_impl()[0:2])
                    
        abuse_result_score = 0
        abuse_data: AbuseData = None
        if abuse:
            impl.reset_machine(perfect_play=True, abuse=True, perfect_only=False)
            abuse_result_score, abuse_data = impl.simulate_impl(skip_activation_initialization=True)
            logger.debug("Total abuse: {}".format(int(abuse_result_score)))
            logger.debug("Abuse deltas: " + " ".join(map(str, abuse_data.score_delta)))
        return perfect_score, perfect_score_array, scores, full_roll_chance, abuse_result_score, abuse_data, cc_great_num, perfect_detail

    def _simulate_auto(self,
                       appeals=None,
                       extra_bonus=None,
                       support=None,
                       chara_bonus_set=None,
                       chara_bonus_value=0,
                       special_option=None,
                       special_value=None,
                       time_offset=0,
                       mirror=False,
                       doublelife=False
                       ):

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
        note_scores, perfects, max_combo, lowest_life, lowest_life_time, all_100 \
            = self._simulate_internal(times=1, grand=grand, doublelife=doublelife, auto=True, time_offset=time_offset)

        auto_score = int(note_scores.sum())

        logger.debug("Tensor size: {}".format(self.notes_data.shape))
        logger.debug("Appeal: {}".format(int(self.total_appeal)))
        logger.debug("Support: {}".format(int(self.live.get_support())))
        logger.debug("Support team: {}".format(self.live.print_support_team()))
        logger.debug("Auto score: {}".format(auto_score))
        logger.debug("Perfects/Misses: {}/{}".format(perfects, len(self.notes_data) - perfects))
        logger.debug("Max Combo: {}".format(max_combo))
        logger.debug("Lowest Life: {}".format(lowest_life))
        logger.debug("Lowest Life Time: {}".format(lowest_life_time))
        logger.debug("All 100: {}".format(all_100))

        ret = AutoSimulationResult(
            total_appeal=self.total_appeal,
            total_life=self.live.get_life(),
            score=auto_score,
            perfects=perfects,
            misses=len(self.notes_data) - perfects,
            max_combo=max_combo,
            lowest_life=lowest_life,
            lowest_life_time=(lowest_life_time // 1000) / 1000,
            all_100=all_100
        )
        return ret
