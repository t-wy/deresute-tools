from __future__ import annotations

import copy
from bisect import bisect
from collections import defaultdict
from math import ceil, floor
from random import random
from typing import cast, Union, Optional, Dict, List, DefaultDict, Tuple

import cython
import numpy as np
import pandas as pd

from logic.live import BaseLive
from logic.skill import Skill
from static.color import Color
from static.judgement import Judgement
from static.note_type import NoteType
from static.skill import get_sparkle_bonus, SkillInact
from static.song_difficulty import PERFECT_TAP_RANGE, GREAT_TAP_RANGE, NICE_TAP_RANGE, BAD_TAP_RANGE, \
    Difficulty, FLICK_DRAIN, NONFLICK_DRAIN, FLICK_BAD_DRAIN, NONFLICK_BAD_DRAIN


class LiveDetail:
    note_details: List[NoteDetail]
    skill_details: Dict[int, List[SkillDetail]]

    def __init__(self, grand):
        self.note_details = list()
        self.skill_details = dict()

        card_num = 5 if not grand else 15
        for idx in range(1, card_num + 1):
            self.skill_details[idx] = list()


class NoteDetail:
    number: int
    time: float
    note_type: NoteType
    checkpoint: bool
    offset: int

    judgement: Judgement
    life: int
    combo: int
    weight: float

    score: int
    score_bonus: List[NoteDetailSkill]
    score_great_bonus: List[NoteDetailSkill]
    combo_bonus: List[NoteDetailSkill]

    def __init__(self, number: int, time: float, note_type: NoteType, checkpoint: bool, offset: int):
        self.number = number
        self.time = time
        self.note_type = note_type
        self.checkpoint = checkpoint
        self.offset = offset

        self.judgement = Judgement.PERFECT
        self.life = 0
        self.combo = 0
        self.weight = 0

        self.score = 0
        self.cumulative_score = 0
        self.score_bonus = list()
        self.score_great_bonus = list()
        self.combo_bonus = list()


class NoteDetailSkill:
    is_boost: bool
    lane: int
    skill_type: int
    value: int
    _boost: Optional[List[NoteDetailSkill]]

    def __init__(self, is_boost: bool, lane: int, skill_type: int, value: int):
        self.is_boost = is_boost
        self.lane = lane
        self.skill_type = skill_type
        self.value = value

        self._boost = list()

    @property
    def boost(self):
        return self._boost if not self.is_boost else None

    @property
    def pre_boost_value(self):
        return floor(self.value / (1 + sum([boost.value / 100 for boost in self._boost]))) if not self.is_boost \
            else None

    def add_boost(self, boost: Union[NoteDetailSkill, List[NoteDetailSkill], None]):
        if self.is_boost:
            return
        if type(boost) == list:
            self._boost.extend(boost)
        elif type(boost) == NoteDetailSkill:
            self._boost.append(boost)


def get_note_detail(note_details, number) -> NoteDetail:
    # Normally note detail objects have same order as chart
    if note_details[number - 1].number == number:
        return note_details[number - 1]
    # If order changed because of note offset, get corresponding note
    else:
        return next(filter(lambda note_detail: note_detail.number == number, note_details))


class SkillDetail:
    skill_type: int
    probability: float
    time_on: float
    time_off: float

    _active: bool  # Is skill activated in the simulation
    _deact: bool  # User set this skill to not activate
    _inact: Optional[SkillInact]  # Skill can't activate for some reason

    encored_skill: Tuple[int, int, float]
    amr_bonus: Dict[str, Optional[Tuple[int, int, int, int, float]]]  # (value, original_value, lane, type, time)
    magic_bonus: Dict[str, Union[int, bool]]

    def __init__(self, skill_type: int, probability: float, time_on: float, time_off: float):
        self.skill_type = skill_type
        self.probability = probability
        self.time_on = time_on
        self.time_off = time_off

        self._active = True
        self._deact = False
        self._inact = None

        self.encored_skill = (0, 0, 0)
        self.amr_bonus = {'tap': None, 'long': None, 'flick': None, 'slide': None, 'great': None, 'combo': None}
        self.magic_bonus = {'tap': 0, 'long': 0, 'flick': 0, 'slide': 0, 'great': 0, 'combo': 0, 'sparkle': 0,
                            'life': 0, 'overload': 0, 'perfect_support': 0, 'combo_support': 0,
                            'cu_score': 0, 'cu_combo': 0, 'cu_life': 0, 'cu_support': 0,
                            'co_score': 0, 'co_combo': 0, 'co_life': 0, 'co_support': 0,
                            'pa_score': 0, 'pa_combo': 0, 'pa_life': 0, 'pa_support': 0,
                            'guard': False, 'concentration': False}

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, _active: bool):
        self._active = _active
        if self._active:
            self._deact = False
            self._inact = None

    @property
    def deact(self):
        return self._deact

    @deact.setter
    def deact(self, _deact: bool):
        self._deact = _deact
        if self._deact:
            self._active = False

    @property
    def inact(self):
        return self._inact

    @inact.setter
    def inact(self, _inact: Optional[SkillInact]):
        self._inact = _inact
        if self._inact:
            self._active = False


class AbuseData:
    def __init__(self, score_delta, window_l, window_r, judgements):
        self.score_delta = score_delta
        self.window_l = window_l
        self.window_r = window_r
        self.judgements = judgements


@cython.cclass
class UnitCacheBonus:
    tap: int
    flick: int
    longg: int
    slide: int
    great: int
    combo: int
    tap_update: Tuple[int, int, float]
    longg_update: Tuple[int, int, float]
    flick_update: Tuple[int, int, float]
    slide_update: Tuple[int, int, float]
    great_update: Tuple[int, int, float]
    combo_update: Tuple[int, int, float]
    ref_tap: Dict[int, int]
    ref_flick: Dict[int, int]
    ref_long: Dict[int, int]
    ref_slide: Dict[int, int]
    ref_great: Dict[int, int]
    ref_combo: Dict[int, int]
    alt_tap: Dict[int, int]
    alt_flick: Dict[int, int]
    alt_long: Dict[int, int]
    alt_slide: Dict[int, int]
    alt_great: Dict[int, int]
    alt_combo: Dict[int, int]

    def __init__(self):
        self.tap = 0
        self.flick = 0
        self.longg = 0
        self.slide = 0
        self.great = 0
        self.combo = 0
        self.tap_update = (-1, 0, 0.0)
        self.longg_update = (-1, 0, 0.0)
        self.flick_update = (-1, 0, 0.0)
        self.slide_update = (-1, 0, 0.0)
        self.great_update = (-1, 0, 0.0)
        self.combo_update = (-1, 0, 0.0)
        self.ref_tap = defaultdict(int)
        self.ref_long = defaultdict(int)
        self.ref_flick = defaultdict(int)
        self.ref_slide = defaultdict(int)
        self.ref_great = defaultdict(int)
        self.ref_combo = defaultdict(int)
        self.alt_tap = defaultdict(int)
        self.alt_long = defaultdict(int)
        self.alt_flick = defaultdict(int)
        self.alt_slide = defaultdict(int)
        self.alt_great = defaultdict(int)
        self.alt_combo = defaultdict(int)

    def update(self, skill: Skill, skill_time):
        # Cache alternate and mutual penalty if no other skills have been activated
        if skill.is_alternate:
            if self.combo == 0:
                self.combo_update = (skill.card_idx, skill.skill_type, skill_time)
                self.combo = skill.values[2]
        if skill.is_mutual:
            if self.tap == 0:
                self.tap_update = (skill.card_idx, skill.skill_type, skill_time)
                self.tap = skill.values[0]
                self.longg_update = (skill.card_idx, skill.skill_type, skill_time)
                self.longg = skill.values[0]
                self.flick_update = (skill.card_idx, skill.skill_type, skill_time)
                self.flick = skill.values[0]
                self.slide_update = (skill.card_idx, skill.skill_type, skill_time)
                self.slide = skill.values[0]
            if self.great == 0:
                self.great_update = (skill.card_idx, skill.skill_type, skill_time)
                self.great = skill.values[1]

        # Do not update on alternate, mutual, refrain, boosters
        if skill.is_alternate or skill.is_mutual or skill.is_refrain or skill.boost:
            return
        if skill.act is not None:
            if self.tap < skill.values[0]:
                self.tap_update = (skill.card_idx, skill.skill_type, skill_time)
                self.tap = skill.values[0]
            if skill.act is NoteType.LONG:
                if self.longg < skill.values[1]:
                    self.longg_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.longg = skill.values[1]
                if self.flick < skill.values[0]:
                    self.flick_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.flick = skill.values[0]
                if self.slide < skill.values[0]:
                    self.slide_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.slide = skill.values[0]
            elif skill.act is NoteType.FLICK:
                if self.longg < skill.values[0]:
                    self.longg_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.longg = skill.values[0]
                if self.flick < skill.values[1]:
                    self.flick_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.flick = skill.values[1]
                if self.slide < skill.values[0]:
                    self.slide_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.slide = skill.values[0]
            elif skill.act is NoteType.SLIDE:
                if self.longg < skill.values[0]:
                    self.longg_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.longg = skill.values[0]
                if self.flick < skill.values[0]:
                    self.flick_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.flick = skill.values[0]
                if self.slide < skill.values[1]:
                    self.slide_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.slide = skill.values[1]
            return
        if skill.v0 > 100:
            if self.tap < skill.v0:
                self.tap_update = (skill.card_idx, skill.skill_type, skill_time)
                self.tap = skill.v0
            if self.flick < skill.v0:
                self.flick_update = (skill.card_idx, skill.skill_type, skill_time)
                self.flick = skill.v0
            if self.longg < skill.v0:
                self.longg_update = (skill.card_idx, skill.skill_type, skill_time)
                self.longg = skill.v0
            if self.slide < skill.v0:
                self.slide_update = (skill.card_idx, skill.skill_type, skill_time)
                self.slide = skill.v0
            if skill.is_score_great or skill.is_overload:
                if self.great < skill.v1:
                    self.great_update = (skill.card_idx, skill.skill_type, skill_time)
                    self.great = skill.v1
        if skill.v2 > 100:
            if self.combo < skill.v2:
                self.combo_update = (skill.card_idx, skill.skill_type, skill_time)
                self.combo = skill.v2

    def update_amr(self, skill: Skill):
        # Do not update on skills that are not alternate, mutual, refrain
        idx = skill.card_idx
        if skill.is_alternate:
            if self.tap > 100:
                self.alt_tap[idx] = ceil((self.tap - 100) * skill.values[0] / 1000)
                self.alt_flick[idx] = ceil((self.flick - 100) * skill.values[0] / 1000)
                self.alt_long[idx] = ceil((self.longg - 100) * skill.values[0] / 1000)
                self.alt_slide[idx] = ceil((self.slide - 100) * skill.values[0] / 1000)
            else:
                self.alt_tap[idx] = self.tap - 100 if self.tap != 0 else 0
                self.alt_flick[idx] = self.flick - 100 if self.flick != 0 else 0
                self.alt_long[idx] = self.longg - 100 if self.longg != 0 else 0
                self.alt_slide[idx] = self.slide - 100 if self.slide != 0 else 0
            if self.great > 100:
                self.alt_great[idx] = ceil((self.great - 100) * skill.values[1] / 1000)
            else:
                self.alt_great[idx] = self.great - 100 if self.great != 0 else 0
            return
        if skill.is_mutual:
            if self.combo > 100:
                self.alt_combo[idx] = ceil((self.combo - 100) * skill.values[2] / 1000)
            else:
                self.alt_combo[idx] = self.combo - 100 if self.combo != 0 else 0
            return
        if skill.is_refrain:
            self.ref_tap[idx] = self.tap - 100 if self.tap != 0 else 0
            self.ref_flick[idx] = self.flick - 100 if self.flick != 0 else 0
            self.ref_long[idx] = self.longg - 100 if self.longg != 0 else 0
            self.ref_slide[idx] = self.slide - 100 if self.slide != 0 else 0
            self.ref_great[idx] = self.great - 100 if self.great != 0 else 0
            self.ref_combo[idx] = self.combo - 100 if self.combo != 0 else 0
            return


@cython.cclass
class StateMachine:
    left_inclusive: bool
    right_inclusive: bool
    fail_simulate: bool
    perfect_only: bool

    grand: bool
    difficulty: Difficulty
    doublelife: bool
    live: BaseLive
    notes_data: pd.DataFrame
    base_score: float
    helen_base_score: float
    weights: List[int]

    _note_type_stack: List[NoteType]
    _note_idx_stack: List[int]
    _special_note_types: List[List[NoteType]]

    note_time_stack: List[int]
    note_time_deltas: List[int]
    note_type_stack: List[NoteType]
    note_idx_stack: List[int]
    special_note_types: List[List[NoteType]]
    checkpoints: List[bool]

    unit_offset: int
    probabilities: List[float]
    has_cc: bool

    _sparkle_bonus_ssr: List[int]
    _sparkle_bonus_sr: List[int]

    skill_times: List[int]
    skill_indices: List[int]
    skill_queue: Dict[int, Union[Skill, List[Skill]]]
    reference_skills: List[Optional[Skill]]

    life: int
    max_life: int
    combo: int
    combos: List[int]
    judgements: List[Judgement]

    full_roll_chance: float

    note_scores: Optional[np.ndarray]
    np_score_bonuses: Optional[np.ndarray]
    score_bonuses: List[int]
    np_score_great_bonuses: Optional[np.ndarray]
    score_great_bonuses: List[int]
    np_combo_bonuses: Optional[np.ndarray]
    combo_bonuses: List[int]

    last_activated_skill: List[int]
    last_activated_time: List[int]

    has_skill_change: bool
    cache_max_boosts: Optional[List[List[int]]]
    cache_max_boosts_pointer: Optional[List[List[Optional[NoteDetailSkill]]]]
    cache_sum_boosts: Optional[List[List[int]]]
    cache_sum_boosts_pointer: Optional[List[List[List[NoteDetailSkill]]]]
    cache_life_bonus: int
    cache_support_bonus: int
    cache_combo_support_bonus: int
    cache_score_bonus: int
    cache_score_bonus_skill: List[NoteDetailSkill]
    cache_score_great_bonus: int
    cache_score_great_bonus_skill: List[NoteDetailSkill]
    cache_combo_bonus: int
    cache_combo_bonus_skill: List[NoteDetailSkill]
    cache_magics: Dict[int, Union[Skill, List[Skill]]]
    cache_non_magics: Dict[int, Union[Skill, List[Skill]]]
    cache_ls: Dict[int, int]
    cache_act: Dict[int, int]
    cache_alt: Dict[int, Tuple[int, int]]
    cache_mut: Dict[int, int]
    cache_ref: Dict[int, Tuple[int, int, int]]
    cache_enc: Dict[int, int]

    unit_caches: List[UnitCacheBonus]

    abuse: bool
    cache_hps: List[int]
    is_abuse: List[bool]
    cache_perfect_score_array: Optional[np.ndarray]
    note_time_deltas_backup: List[int]
    note_idx_stack_backup: List[int]
    is_abuse_backup: List[bool]

    auto: bool
    time_offset: int
    special_offset: int
    finish_pos: List[int]
    status: List[int]
    group_ids: List[int]
    delayed: List[bool]
    being_held: Dict[int, bool]
    lowest_life: int
    lowest_life_time: int

    force_encore_amr_cache_to_encore_unit: bool
    force_encore_magic_to_encore_unit: bool
    allow_encore_magic_to_escape_max_agg: bool

    live_detail: LiveDetail
    note_details: List[NoteDetail]
    skill_details: Dict[int, List[SkillDetail]]

    custom: bool
    custom_deact_skills: Optional[List[List[int]]]
    custom_note_offsets: Optional[DefaultDict[int, int]]
    custom_note_misses: Optional[DefaultDict[int, int]]

    def __init__(self, grand, difficulty, doublelife, live, notes_data, left_inclusive, right_inclusive, base_score,
                 helen_base_score, weights,
                 force_encore_amr_cache_to_encore_unit=False,
                 force_encore_magic_to_encore_unit=False,
                 allow_encore_magic_to_escape_max_agg=False,
                 custom_deact_skills=None, custom_note_offsets=None, custom_note_misses=None):
        self.left_inclusive = left_inclusive
        self.right_inclusive = right_inclusive

        self.grand = grand
        self.difficulty = difficulty
        self.doublelife = doublelife
        self.live = live
        self.notes_data = notes_data
        self.base_score = base_score
        self.helen_base_score = helen_base_score
        self.weights = weights

        self._note_type_stack = self.notes_data.note_type.to_list()
        self._note_idx_stack = self.notes_data.index.to_list()
        self._special_note_types = list()
        self._setup_special_note_types()
        self.checkpoints = self.notes_data["checkpoints"].to_list()

        self.unit_offset = 3 if grand else 1
        self.probabilities = list()
        self._setup_probabilities()
        self.has_cc = any([card.skill.is_cc for card in self.live.unit.all_cards()])

        self._sparkle_bonus_ssr = get_sparkle_bonus(8, self.grand)
        self._sparkle_bonus_sr = get_sparkle_bonus(6, self.grand)

        self.full_roll_chance = 1

        # Abuse stuff
        self.abuse = False
        self.cache_hps = list()
        self.is_abuse = [False] * len(self.notes_data)
        self.cache_perfect_score_array = None

        self.force_encore_amr_cache_to_encore_unit = force_encore_amr_cache_to_encore_unit
        self.force_encore_magic_to_encore_unit = force_encore_magic_to_encore_unit
        self.allow_encore_magic_to_escape_max_agg = allow_encore_magic_to_escape_max_agg

        if any((custom_deact_skills, custom_note_offsets, custom_note_misses)):
            assert len(custom_deact_skills) == 15
            custom_deact_skills = [custom_deact_skills[idx] for idx in range(1, 16)]

            self.custom = True
            self.custom_deact_skills = custom_deact_skills if custom_deact_skills else [[] for _ in range(15)]
            self.custom_note_offsets = custom_note_offsets if custom_note_offsets else defaultdict(int)
            self.custom_note_misses = custom_note_misses if custom_note_misses else defaultdict(int)
        else:
            self.custom = False
            self.custom_deact_skills = None
            self.custom_note_offsets = None
            self.custom_note_misses = None

    def _setup_special_note_types(self):
        for _, note in self.notes_data.iterrows():
            temp = list()
            if note.is_flick:
                temp.append(NoteType.FLICK)
            if note.is_long:
                temp.append(NoteType.LONG)
            if note.is_slide:
                temp.append(NoteType.SLIDE)
            self._special_note_types.append(temp)

    def _setup_probabilities(self):
        for unit_idx, unit in enumerate(self.live.unit.all_units):
            for card_idx, card in enumerate(unit.all_cards()):
                probability = self.live.get_probability(unit_idx * 5 + card_idx)
                self.probabilities.append(probability)
                card.skill.set_original_unit_idx(unit_idx)
                card.skill.set_card_idx(unit_idx * 5 + card_idx)
                card.skill.probability = probability

    def reset_machine(self, perfect_play=True, perfect_only=True, abuse=False, time_offset=0, special_offset=0,
                      auto=False):
        self.fail_simulate = not perfect_play
        self.perfect_only = perfect_only

        # These 2 lists have the same length and should be mutated together.
        # List of all skill timestamps, contains activations and deactivations.
        self.skill_times = list()
        # List of all skill indices, indicating which skill is activating/deactivating.
        # Positive = activation, negative = deactivation.
        # E.g. 4 means the skill in slot 4 (counting from 1) activation, -4 means its deactivation
        self.skill_indices = list()
        self.skill_queue = dict()  # What skills are currently active
        # List of all skill objects. Should not mutate. Original sets.
        self.reference_skills = [None]
        for _ in range(len(self.live.unit.all_cards())):
            self.reference_skills.append(None)

        # Transient values of a state
        self.life = self.live.get_start_life(doublelife=self.doublelife)
        self.max_life = self.live.get_start_life(doublelife=True)
        self.combo = 0
        self.combos = [0] * len(self.notes_data)
        self.judgements = list()

        # Metrics
        self.full_roll_chance = 1

        self.note_scores = None
        self.np_score_bonuses = None
        self.score_bonuses = list()
        self.np_score_great_bonuses = None
        self.score_great_bonuses = list()
        self.np_combo_bonuses = None
        self.combo_bonuses = list()

        # Encore stuff
        self.last_activated_skill = list()
        self.last_activated_time = list()

        # Hacky cache stuff
        self.has_skill_change = True
        self.cache_max_boosts = None
        self.cache_max_boosts_pointer = None
        self.cache_sum_boosts = None
        self.cache_sum_boosts_pointer = None
        self.cache_life_bonus = 0
        self.cache_support_bonus = 0
        self.cache_combo_support_bonus = 0
        self.cache_score_bonus = 0
        self.cache_score_bonus_skill = list()
        self.cache_combo_bonus = 0
        self.cache_score_great_bonus_skill = list()
        self.cache_score_great_bonus = 0
        self.cache_combo_bonus_skill = list()
        self.cache_magics = dict()
        self.cache_non_magics = dict()
        self.cache_ls = dict()
        self.cache_act = dict()
        self.cache_alt = dict()
        self.cache_mut = dict()
        self.cache_ref = dict()
        self.cache_enc = dict()

        # Cache for AMR
        self.unit_caches = list()
        for _ in range(len(self.live.unit.all_units)):
            self.unit_caches.append(UnitCacheBonus())

        self.abuse = abuse

        # Auto stuff
        self.auto = auto
        if self.auto:
            self.time_offset = int(time_offset * 1E3)
            self.special_offset = int(special_offset * 1E6)
            self.finish_pos = self.notes_data["finishPos"].map(int).to_list()
            self.status = self.notes_data["status"].map(int).to_list()
            self.group_ids = self.notes_data["groupId"].map(int).to_list()
            self.delayed = [False] * len(self.notes_data)
            self.being_held = dict()
            self.judgements = [Judgement.PERFECT for _ in range(len(self.notes_data))]
            self.score_bonuses = [0] * len(self.notes_data)
            self.score_great_bonuses = [0] * len(self.notes_data)
            self.combo_bonuses = [0] * len(self.notes_data)
            self.lowest_life = 9000
            self.lowest_life_time = -1

        # Initializing note data
        if perfect_play and not self.custom:
            self.note_time_stack = self.notes_data.sec.map(lambda x: int(x * 1E6)).to_list()
            self.note_time_deltas = [0] * len(self.note_time_stack)
            self.note_type_stack = self._note_type_stack.copy()
            self.note_idx_stack = self._note_idx_stack.copy()
            self.special_note_types = self._special_note_types.copy()
        else:
            if self.custom:
                temp = self.notes_data.sec.copy()
                for idx in self.custom_note_offsets:
                    temp[idx] += self.custom_note_offsets[idx] / 1000
            else:
                random_range = PERFECT_TAP_RANGE[self.difficulty] / 2E6 \
                    if perfect_only else GREAT_TAP_RANGE[self.difficulty] / 2E6
                temp = self.notes_data.sec + np.random.random(len(self.notes_data)) * 2 * random_range - random_range
            temp[self.notes_data["checkpoints"]] = np.maximum(
                temp[self.notes_data["checkpoints"]],
                self.notes_data.loc[self.notes_data["checkpoints"], "sec"])
            temp_note_time_deltas = (temp - self.notes_data.sec).map(lambda x: int(x * 1E6))
            temp_note_time_stack = temp.map(lambda x: int(x * 1E6))
            sorted_indices = np.argsort(temp_note_time_stack)
            self.note_time_stack = temp_note_time_stack[sorted_indices].tolist()
            self.note_time_deltas = temp_note_time_deltas[sorted_indices].tolist()
            self.note_type_stack = [self._note_type_stack[_] for _ in sorted_indices]
            self.note_idx_stack = [self._note_idx_stack[_] for _ in sorted_indices]
            self.special_note_types = [self._special_note_types[_] for _ in sorted_indices]
        self.note_idx_stack_backup = self.note_idx_stack.copy()

        if abuse:
            self.initialize_live_detail()
            self.initialize_activation_arrays()
            self._helper_fill_abuse_dummies()
            return

        self.initialize_live_detail()

    def initialize_live_detail(self):
        self.live_detail = LiveDetail(self.grand)
        self.note_details = self.live_detail.note_details
        self.skill_details = self.live_detail.skill_details

        for index, row in self.notes_data.iterrows():
            index = cast(int, index)
            offset = 0
            if self.custom and index in self.custom_note_offsets:
                offset = self.custom_note_offsets[index]
            if len(self._special_note_types[index]) == 0:
                note_type = NoteType.TAP
            else:
                note_type = self._special_note_types[index][0]
            note_detail = NoteDetail(index + 1, row['sec'], note_type, row['checkpoints'], offset)
            self.note_details.append(note_detail)

    def _helper_fill_abuse_dummies(self):
        # Abuse should be the last stage of a simulation pipeline
        assert len(self.checkpoints) == len(self.notes_data)

        def get_range(note_type_internal, special_note_types_internal, checkpoint_internal, lane_fixed_internal):
            if note_type_internal == NoteType.TAP:
                l_g = -GREAT_TAP_RANGE[self.live.difficulty]
                l_p = -PERFECT_TAP_RANGE[self.live.difficulty]
                r_g = GREAT_TAP_RANGE[self.live.difficulty]
                r_p = PERFECT_TAP_RANGE[self.live.difficulty]
                return (l_g, r_g), (l_g, l_p, r_p, r_g)
            elif NoteType.FLICK in special_note_types_internal and NoteType.SLIDE in special_note_types_internal:
                l_p = -150000
                r_p = 150000
                return (l_p, r_p), (l_p, r_p)
            elif note_type_internal == NoteType.FLICK or note_type_internal == NoteType.LONG:
                l_g = -180000
                l_p = -150000
                r_g = 180000
                r_p = 150000
                return (l_g, r_g), (l_g, l_p, r_p, r_g)
            elif not checkpoint_internal:
                l_p = -150000
                r_p = 150000
                return (l_p, r_p), (l_p, r_p)
            elif lane_fixed_internal:
                return (0, 0), (0,)
            else:
                r_p = 200000
                return (0, r_p), (r_p,)

        lanes = self.notes_data["finishPos"].to_list()
        previous_lanes = lanes.copy()
        previous_lanes.insert(0, 0)
        previous_lanes.pop()
        lane_matches = [i == j for i, j in zip(lanes, previous_lanes)]

        for note_time, note_time_delta, note_type, note_idx, special_note_types, checkpoint, weight, lane_match in zip(
                self.note_time_stack[:],
                self.note_time_deltas[:],
                self.note_type_stack[:],
                self.note_idx_stack[:],
                self.special_note_types[:],
                self.checkpoints[:],
                self.weights[:],
                lane_matches[:]
        ):
            lane_fixed = False
            if self.live.difficulty == Difficulty.TRICK and checkpoint and lane_match:
                lane_fixed = True
            boundaries, deltas = get_range(note_type, special_note_types, checkpoint, lane_fixed)
            for delta in deltas:
                dummy_range = [delta]
                if self.has_cc and delta != 0:
                    dummy_range.append(delta // 2)
                for _ in dummy_range:
                    self.note_time_stack.append(note_time + _)
                    self.note_time_deltas.append(_)
                    self.note_type_stack.append(note_type)
                    self.note_idx_stack.append(note_idx)
                    self.special_note_types.append(special_note_types)
                    self.checkpoints.append(checkpoint)
                    self.is_abuse.append(True)
                    self.weights.append(weight)
            left, right = boundaries
            left = note_time + left
            right = note_time + right
            for skill_time in self.skill_times:
                for d in [-1, 0, 1]:
                    test_skill_time = skill_time + d
                    if test_skill_time > right:
                        break
                    if test_skill_time < left:
                        continue
                    if test_skill_time == note_time:
                        continue
                    delta = test_skill_time - note_time
                    self.note_time_stack.append(test_skill_time)
                    self.note_time_deltas.append(delta)
                    self.note_type_stack.append(note_type)
                    self.note_idx_stack.append(note_idx)
                    self.special_note_types.append(special_note_types)
                    self.checkpoints.append(checkpoint)
                    self.is_abuse.append(True)
                    self.weights.append(weight)

        sorted_indices = np.argsort(self.note_time_stack)
        self.note_time_stack = [self.note_time_stack[_] for _ in sorted_indices]
        self.note_time_deltas = [self.note_time_deltas[_] for _ in sorted_indices]
        self.note_type_stack = [self.note_type_stack[_] for _ in sorted_indices]
        self.note_idx_stack = [self.note_idx_stack[_] for _ in sorted_indices]
        self.special_note_types = [self.special_note_types[_] for _ in sorted_indices]
        self.checkpoints = [self.checkpoints[_] for _ in sorted_indices]
        self.is_abuse = [self.is_abuse[_] for _ in sorted_indices]
        self.weights = [self.weights[_] for _ in sorted_indices]

        self.note_time_deltas_backup = self.note_time_deltas.copy()
        self.note_idx_stack_backup = self.note_idx_stack.copy()
        self.is_abuse_backup = self.is_abuse.copy()

    def initialize_activation_arrays(self):
        skill_times = list()
        skill_indices = list()
        for unit_idx, unit in enumerate(self.live.unit.all_units):
            iterating_order = list()
            _cache_guard = list()
            _cache_alt = list()
            _cache_mut = list()
            _cache_ref = list()
            _cache_magic = list()
            for card_idx, card in enumerate(unit.all_cards()):
                if card.skill.is_magic:
                    _cache_magic.append((card_idx, card))
                    continue
                if card.skill.is_guard:
                    _cache_guard.append((card_idx, card))
                    continue
                if card.skill.is_alternate:
                    _cache_alt.append((card_idx, card))
                    continue
                if card.skill.is_mutual:
                    _cache_mut.append((card_idx, card))
                    continue
                if card.skill.is_refrain:
                    _cache_ref.append((card_idx, card))
                    continue
                iterating_order.append((card_idx, card))
            iterating_order = _cache_magic + _cache_guard + iterating_order + _cache_alt + _cache_mut + _cache_ref

            for card_idx, card in iterating_order:
                skill = copy.copy(card.skill)
                idx = unit_idx * 5 + card_idx
                self.reference_skills[idx + 1] = skill

                skill_inact = None
                if self.probabilities[idx] == 0:
                    if skill.skill_type == 21:
                        skill_inact = SkillInact.NOT_CU_ONLY
                    elif skill.skill_type == 22:
                        skill_inact = SkillInact.NOT_CO_ONLY
                    elif skill.skill_type == 23:
                        skill_inact = SkillInact.NOT_PA_ONLY
                    elif skill.skill_type in (26, 38, 44):
                        skill_inact = SkillInact.NOT_TRICOLOR

                if skill.song_all_required and self.live.color != Color.ALL:
                    skill_inact = SkillInact.NOT_ALL_SONG

                total_activation = int((self.notes_data.iloc[-1].sec - 3) // skill.interval)
                skill_range = list(range(skill.offset + 1, total_activation + 1, self.unit_offset))

                not_active = 0
                for act_idx in skill_range:
                    on = act_idx * skill.interval
                    off = act_idx * skill.interval \
                        + min(skill.interval, skill.duration) / 1.5 * (1 + (skill.skill_level - 1) / 18)

                    skill_detail = SkillDetail(skill.skill_type, self.probabilities[idx], on, off)
                    self.skill_details[idx + 1].append(skill_detail)

                    if self.custom:
                        if (act_idx - 1) // self.unit_offset in self.custom_deact_skills[idx]:
                            skill_detail.deact = True
                            not_active += 1
                            continue

                    # Set inact first and change to None later to handle the case of 0 magic skills
                    # To handle cases magic not having any skills to activate
                    if skill.skill_type == 41:
                        skill_detail.inact = SkillInact.NO_MAGIC_SKILL
                    else:
                        skill_detail.inact = skill_inact

                    if self.probabilities[idx] < 1 and self.fail_simulate:
                        if random() > self.probabilities[idx]:
                            skill_detail.active = False
                            continue

                    skill_times.append(int(on * 1E6))
                    skill_times.append(int(off * 1E6))
                    skill_indices.append(unit_idx * 5 + card_idx + 1)
                    skill_indices.append(-unit_idx * 5 - card_idx - 1)
                if self.probabilities[idx] > 0:
                    self.full_roll_chance *= self.probabilities[idx] ** (len(skill_range) - not_active)
                    self.full_roll_chance *= (1 - self.probabilities[idx]) ** not_active
        np_skill_times = np.array(skill_times)
        np_skill_indices = np.array(skill_indices)
        sorted_indices = np.argsort(np_skill_times, kind='stable')
        self.skill_times = np_skill_times[sorted_indices].tolist()
        self.skill_indices = np_skill_indices[sorted_indices].tolist()

    def simulate_impl(self, skip_activation_initialization=False) \
            -> Union[Tuple[int, List[int], LiveDetail], Tuple[int, AbuseData]]:
        if not skip_activation_initialization:
            self.initialize_activation_arrays()

        while True:
            # Terminal condition: No more skills and no more notes
            if len(self.skill_times) == 0 and len(self.note_time_stack) == 0:
                break

            if len(self.skill_times) == 0:
                self.handle_note()
            elif len(self.note_time_stack) == 0:
                self.handle_skill()
            elif self.note_time_stack[0] < self.skill_times[0]:
                self.handle_note()
            elif self.skill_times[0] < self.note_time_stack[0]:
                self.handle_skill()
            else:
                if (self.skill_indices[0] > 0 and self.left_inclusive) \
                        or (self.skill_indices[0] < 0 and not self.right_inclusive):
                    self.handle_skill()
                else:
                    self.handle_note()

        self.np_score_bonuses = 1 + np.array(self.score_bonuses) / 100
        self.np_score_great_bonuses = 1 + np.array(self.score_great_bonuses) / 100
        self.np_combo_bonuses = 1 + np.array(self.combo_bonuses) / 100

        if self.abuse or (self.fail_simulate and not self.perfect_only) or self.custom:
            judgement_multipliers = np.array([
                1.0 if x is Judgement.PERFECT
                else
                0.7 if x is Judgement.GREAT
                else
                0.4 if x is Judgement.NICE
                else
                0.1 if x is Judgement.BAD
                else 0
                for x in self.judgements])
            final_bonus = judgement_multipliers
            mask = final_bonus == 1.0
            mask_great = final_bonus == 0.7
            if len(mask) > 0:
                final_bonus[mask] *= self.np_score_bonuses[mask]
            if len(mask_great) > 0:
                final_bonus[mask_great] *= self.np_score_great_bonuses[mask_great]
            if self.abuse:
                final_bonus *= self.np_combo_bonuses
            else:
                mask_combo = [_ > 1 for _ in self.combos]
                if any(mask_combo):
                    final_bonus[mask_combo] *= self.np_combo_bonuses[mask_combo]
        else:
            judgement_multipliers = 1
            final_bonus = judgement_multipliers
            final_bonus *= self.np_score_bonuses
            final_bonus[1:] *= self.np_combo_bonuses[1:]

        if not self.abuse:
            self.weights = [1.0 if combo == 0 else self.weights[combo - 1] for combo in self.combos]

        self.note_scores = np.round(self.base_score * np.array(self.weights) * final_bonus)
        note_scores_list = cast(List[int], self.note_scores.tolist())

        if not self.fail_simulate and not self.abuse:
            self.cache_perfect_score_array = self.note_scores.copy()

        for note_detail in self.note_details:
            weight = 1.0
            if note_detail.combo > 0:
                note_detail.weight = self.weights[note_detail.combo - 1]
            note_detail.weight = weight
            note_detail.score = int(self.note_scores[self.note_idx_stack_backup.index(note_detail.number - 1)])

        note_details_time_sort = self.note_details.copy()
        if self.custom:
            note_details_time_sort.sort(key=lambda note: note.time + note.offset / 1000)
        for note_idx, note_detail in enumerate(note_details_time_sort):
            if note_idx == 0:
                note_detail.cumulative_score = note_detail.score
            else:
                note_detail.cumulative_score = note_details_time_sort[note_idx - 1].cumulative_score + note_detail.score
            get_note_detail(self.note_details, note_detail.number).cumulative_score = note_detail.cumulative_score

        if self.abuse:
            assert self.cache_perfect_score_array is not None
            return self._handle_abuse_results()
        else:
            return int(self.note_scores.sum()), note_scores_list, self.live_detail

    def simulate_impl_auto(self):
        self.initialize_activation_arrays()
        while True:
            # Terminal condition: No more skills and no more notes
            if len(self.skill_times) == 0 and len(self.note_time_stack) == 0:
                break

            if len(self.skill_times) == 0:
                self.handle_note_auto()
            elif len(self.note_time_stack) == 0:
                temp = self.skill_times[0]
                self.handle_skill()
                self.break_hold(temp)
            elif self.note_time_stack[0] < self.skill_times[0]:
                self.handle_note_auto()
            elif self.skill_times[0] < self.note_time_stack[0]:
                temp = self.skill_times[0]
                self.handle_skill()
                self.break_hold(temp)
            else:
                if (self.skill_indices[0] > 0 and self.left_inclusive) \
                        or (self.skill_indices[0] < 0 and not self.right_inclusive):
                    temp = self.skill_times[0]
                    self.handle_skill()
                    self.break_hold(temp)
                else:
                    self.handle_note_auto()

        self.np_score_bonuses = 1 + np.array(self.score_bonuses) / 100
        self.np_score_great_bonuses = 1 + np.array(self.score_great_bonuses) / 100
        self.np_combo_bonuses = 1 + np.array(self.combo_bonuses) / 100

        judgement_multipliers = np.array([1 if x is Judgement.PERFECT else 0 for x in self.judgements])
        final_bonus = judgement_multipliers.astype("float")
        mask = [_ > 1 for _ in self.combos]
        if any(mask):
            final_bonus[mask] *= self.np_combo_bonuses[mask]
        final_bonus *= self.np_score_bonuses
        self.weights = [
            0 if combo == 0 else self.weights[combo - 1] for combo in self.combos
        ]

        self.note_scores = np.round(
            self.base_score
            * np.array(self.weights)
            * final_bonus
        )

        return self.note_scores, len(list(filter(lambda x: x is Judgement.PERFECT, self.judgements))), \
            len(list(filter(lambda x: x is Judgement.MISS, self.judgements))), max(self.combos), \
            self.lowest_life, self.lowest_life_time, self.full_roll_chance == 1

    def break_hold(self, skill_time):
        self.separate_magics_non_magics()
        magics = self.cache_magics
        non_magics = self.cache_non_magics
        max_boosts, sum_boosts = self._evaluate_bonuses_phase_boost(magics, non_magics)
        life_bonus, support_bonus, combo_support_bonus = self._evaluate_bonuses_phase_life_support(magics, non_magics,
                                                                                                   max_boosts,
                                                                                                   sum_boosts)
        if support_bonus < 4:
            to_be_removed = list()
            for held_group, bug in self.being_held.items():
                if combo_support_bonus < 3:
                    self.combo = 0
                else:
                    self.combo += 1
                if held_group < 0:
                    self._handle_long_break(held_group)
                    to_be_removed.append(held_group)
                else:
                    self._handle_slide_break(held_group)
                    if held_group in self.being_held and not self.being_held[held_group]:
                        to_be_removed.append(held_group)
            for _ in to_be_removed:
                self.being_held.pop(_)
        if self.life < self.lowest_life:
            self.lowest_life = self.life
            self.lowest_life_time = skill_time

    def _handle_slide_break(self, group_id):
        if group_id not in self.being_held or not self.being_held[group_id]:
            remove_indices = list()
            last_was_slide = True
            for idx, (check_note_idx, check_group_id) in enumerate(zip(self.note_idx_stack, self.group_ids)):
                check_note_type = self.note_type_stack[check_note_idx]
                if check_group_id == group_id:
                    if check_note_type is NoteType.SLIDE or last_was_slide:
                        self.judgements[check_note_idx] = Judgement.SKIPPED  # Skipped
                        remove_indices.append(idx)
                    if last_was_slide and check_note_type is not NoteType.SLIDE:
                        last_was_slide = False
            # Make sure there is a MISS between PERFECT and skipped notes
            _ = self.notes_data["groupId"].map(int).to_list()
            group_notes = [i for i in range(len(_)) if _[i] == group_id]
            judgements = [self.judgements[i] for i in group_notes]
            if Judgement.SKIPPED in judgements:
                idx = judgements.index(Judgement.SKIPPED)
                if judgements[idx - 1] != Judgement.MISS:
                    self.judgements[group_notes[idx]] = Judgement.MISS
                    if not self._check_guard():
                        self.life -= NONFLICK_DRAIN[self.difficulty]
            for idx in reversed(remove_indices):
                self.note_idx_stack.pop(idx)
                self.note_time_stack.pop(idx)
                self.delayed.pop(idx)
                self.group_ids.pop(idx)

    def _handle_long_break(self, neg_finish_pos, is_long_start=False):
        if neg_finish_pos in self.being_held or is_long_start:
            note_idx_stack = self.note_idx_stack.copy()
            note_idx_stack.sort()
            check_note_idx = note_idx_stack[0]
            for idx, check_note_idx in enumerate(note_idx_stack):
                if self.finish_pos[check_note_idx] == -neg_finish_pos:
                    break
            idx = self.note_idx_stack.index(check_note_idx)
            self.note_idx_stack.pop(idx)
            self.note_time_stack.pop(idx)
            self.delayed.pop(idx)
            self.group_ids.pop(idx)
            if is_long_start:
                self.judgements[check_note_idx] = Judgement.SKIPPED
            else:
                self.judgements[check_note_idx] = Judgement.MISS
                if not self._check_guard():
                    self.life -= NONFLICK_DRAIN[self.difficulty]

    def handle_note_auto(self):
        note_idx = self.note_idx_stack.pop(0)
        note_time = self.note_time_stack.pop(0)
        delayed = self.delayed.pop(0)
        group_id = self.group_ids.pop(0)
        note_type = self.note_type_stack[note_idx]
        is_checkpoint = self.checkpoints[note_idx]
        finish_pos = self.finish_pos[note_idx]
        status = self.status[note_idx]

        checkpoint_bug = self.grand and finish_pos < 10 and finish_pos + status > 6 and is_checkpoint

        # If not checkpoint bug, delay note for evaluation later
        if not checkpoint_bug and not delayed:
            new_note_time = note_time + self.time_offset
            if note_type != NoteType.TAP:
                new_note_time += self.special_offset
            insert_idx = bisect(self.note_time_stack, new_note_time)
            self.note_time_stack.insert(insert_idx, new_note_time)
            self.note_idx_stack.insert(insert_idx, note_idx)
            self.delayed.insert(insert_idx, True)
            self.group_ids.insert(insert_idx, group_id)
            return

        if self.has_skill_change:
            self.separate_magics_non_magics()
        magics = self.cache_magics
        non_magics = self.cache_non_magics
        max_boosts, sum_boosts = self._evaluate_bonuses_phase_boost(magics, non_magics)

        life_bonus, support_bonus, combo_support_bonus = self._evaluate_bonuses_phase_life_support(magics, non_magics,
                                                                                                   max_boosts,
                                                                                                   sum_boosts)

        covered = self._auto_covered(support_bonus=support_bonus,
                                     is_flick=NoteType.FLICK in self.special_note_types[note_idx])

        # If covered or in buggy unit C grand group and checkpoint bug
        if covered or (group_id in self.being_held and self.being_held[group_id] and checkpoint_bug):
            self.life += life_bonus
            self.life = min(self.max_life, self.life)  # Cap life
            self._helper_evaluate_ls(fixed_life=False)
            self._helper_evaluate_act(self.special_note_types[note_idx])
            self._helper_evaluate_alt_mutual_ref(self.special_note_types[note_idx])
            self._helper_normalize_score_combo_bonuses()
            score_bonus, score_great_bonus, combo_bonus = self._evaluate_bonuses_phase_score_combo(magics, non_magics,
                                                                                                   max_boosts,
                                                                                                   sum_boosts)

            self.combo += 1

            is_long_start = note_type is NoteType.LONG and -finish_pos not in self.being_held
            if is_long_start:
                self.being_held[-finish_pos] = False
            # Long end
            elif -finish_pos in self.being_held:
                self.being_held.pop(-finish_pos)

            if note_type is NoteType.SLIDE:
                self.being_held[group_id] = False

        # If not covered but checkpoint bug and not yet delayed, queue to try again later
        elif checkpoint_bug and not delayed:
            new_note_time = note_time + self.time_offset
            if note_type != NoteType.TAP:
                new_note_time += self.special_offset
            insert_idx = bisect(self.note_time_stack, new_note_time)
            self.note_time_stack.insert(insert_idx, new_note_time)
            self.note_idx_stack.insert(insert_idx, note_idx)
            self.delayed.insert(insert_idx, True)
            self.group_ids.insert(insert_idx, group_id)
            return
        else:
            score_bonus = 0
            score_great_bonus = 0
            combo_bonus = 0
            self.judgements[note_idx] = Judgement.MISS
            if note_type is NoteType.LONG:
                is_long_start = note_type is NoteType.LONG and -finish_pos not in self.being_held
                self._handle_long_break(-finish_pos, is_long_start)
            if note_type is NoteType.SLIDE:
                self._handle_slide_break(group_id)
            if combo_support_bonus < 3:
                self.combo = 0
            else:
                self.combo += 1

        self.combos[note_idx] = self.combo
        self.score_bonuses[note_idx] = score_bonus
        self.score_great_bonuses[note_idx] = score_great_bonus
        self.combo_bonuses[note_idx] = combo_bonus if self.combo > 1 else 0
        self.has_skill_change = False
        if self.life < self.lowest_life:
            self.lowest_life = self.life
            self.lowest_life_time = note_time

    def _handle_abuse_results(self):
        left_windows = [2E9] * len(self.notes_data)
        right_windows = [-2E9] * len(self.notes_data)
        max_score = self.cache_perfect_score_array.copy()
        is_abuses = [False] * len(self.notes_data)
        judgements = [Judgement.PERFECT] * len(self.notes_data)
        for _, (delta, note_idx, score, is_abuse, judgement) in enumerate(zip(
                self.note_time_deltas_backup,
                self.note_idx_stack_backup,
                self.note_scores,
                self.is_abuse_backup,
                self.judgements)):
            if score < max_score[note_idx]:
                continue
            if score > max_score[note_idx]:
                judgements[note_idx] = judgement
                max_score[note_idx] = score
                is_abuses[note_idx] = is_abuses[note_idx] or is_abuse
                left_windows[note_idx] = delta
                right_windows[note_idx] = delta
            else:
                left_windows[note_idx] = min(left_windows[note_idx], delta)
                right_windows[note_idx] = max(right_windows[note_idx], delta)

        for _, (l, r) in enumerate(zip(left_windows, right_windows)):
            if l < 0 < r:  # Revert score if not abuse
                max_score[_] = self.cache_perfect_score_array[_]

        score_delta = max_score - self.cache_perfect_score_array
        abuse_data = AbuseData(score_delta, left_windows, right_windows, judgements)
        return sum(max_score), abuse_data

    def handle_skill(self):
        self.has_skill_change = True
        if self.skill_indices[0] > 0:
            if not self._expand_encore():
                return
            self._expand_magic()
            self._handle_skill_activation()
            # By this point, all skills that can be activated should be in self.skill_queue
            self._evaluate_motif()
            self._evaluate_ls()
            self._cache_skill_data()
            self._cache_amr()
            self.skill_indices.pop(0)
            self.skill_times.pop(0)
        else:
            self.skill_queue.pop(-self.skill_indices[0])
            self.skill_indices.pop(0)
            self.skill_times.pop(0)

    def handle_note(self):
        if self.abuse:
            self._handle_note_abuse()
        else:
            self._handle_note_no_abuse()

    def _handle_note_no_abuse(self):
        note_time = self.note_time_stack.pop(0)
        note_delta = self.note_time_deltas.pop(0)
        note_type = self.note_type_stack.pop(0)
        note_idx = self.note_idx_stack.pop(0)
        note_detail = get_note_detail(self.note_details, note_idx + 1)

        score_bonus, score_great_bonus, combo_bonus, support_bonus, combo_support_bonus \
            = self.evaluate_bonuses(self.special_note_types[note_idx], note_time=note_time)
        self.score_bonuses.append(score_bonus)
        self.score_great_bonuses.append(score_great_bonus)
        self.combo_bonuses.append(combo_bonus)

        if (self.fail_simulate and not self.perfect_only) or self.custom:
            if self.custom and note_idx in self.custom_note_misses:
                judgement = Judgement.MISS
            else:
                judgement = self.evaluate_judgement(note_delta, note_type, self.special_note_types[note_idx],
                                                    perfect_support=support_bonus)
        else:
            judgement = Judgement.PERFECT
        self.judgements.append(judgement)
        note_detail.judgement = judgement

        if judgement == Judgement.PERFECT:
            self.combo += 1
            note_detail.score_bonus.extend(self.cache_score_bonus_skill)
        elif judgement == Judgement.GREAT:
            self.combo += 1
            note_detail.score_great_bonus.extend(self.cache_score_great_bonus_skill)
        else:
            if judgement.value >= Judgement(combo_support_bonus + 2):
                self.combo = 0
            else:
                self.combo += 1
        if self.combo > 1:
            note_detail.combo_bonus.extend(self.cache_combo_bonus_skill)
        self.combos[note_idx] = self.combo
        note_detail.combo = self.combo

        self.has_skill_change = False

        if not self._check_guard():
            if judgement == Judgement.BAD:
                if note_type == NoteType.FLICK:
                    self.life -= FLICK_BAD_DRAIN[self.difficulty]
                else:
                    self.life -= NONFLICK_BAD_DRAIN[self.difficulty]
            elif judgement == Judgement.MISS:
                if note_type == NoteType.FLICK:
                    self.life -= FLICK_DRAIN[self.difficulty]
                else:
                    self.life -= NONFLICK_DRAIN[self.difficulty]
        note_detail.life = int(self.life)

    def _handle_note_abuse(self):
        note_time = self.note_time_stack.pop(0)
        note_delta = self.note_time_deltas.pop(0)
        note_type = self.note_type_stack.pop(0)
        note_idx = self.note_idx_stack.pop(0)
        special_note_types = self.special_note_types.pop(0)
        is_checkpoint = self.checkpoints.pop(0)
        is_abuse = self.is_abuse.pop(0)

        if not is_abuse:
            self.combo += 1
            cached_life = None
        else:
            cached_life = self.cache_hps[note_idx]
        self.combos.append(self.combo)

        score_bonus, score_great_bonus, combo_bonus, _, _ = self.evaluate_bonuses(special_note_types,
                                                                                  skip_healing=is_abuse,
                                                                                  fixed_life=cached_life,
                                                                                  note_time=note_time)
        self.judgements.append(
            self.evaluate_judgement(note_delta, note_type, special_note_types,
                                    abuse_check=True, is_checkpoint=is_checkpoint))
        self.score_bonuses.append(score_bonus)
        self.score_great_bonuses.append(score_great_bonus)
        self.combo_bonuses.append(combo_bonus)
        self.has_skill_change = False

    def evaluate_judgement(self, note_delta, note_type, special_note_types,
                           abuse_check=False, is_checkpoint=False, perfect_support=0) -> Judgement:
        def check_cc() -> bool:
            for _, skills in self.skill_queue.items():
                if isinstance(skills, Skill) and skills.is_cc:
                    return True
                for skill in skills:
                    if skill.is_cc:
                        return True
            return False

        has_cc = self.has_cc and check_cc()
        if abuse_check:
            if note_type == NoteType.TAP:
                l_g = GREAT_TAP_RANGE[self.live.difficulty]
                r_g = GREAT_TAP_RANGE[self.live.difficulty]
                l_p = PERFECT_TAP_RANGE[self.live.difficulty]
                r_p = PERFECT_TAP_RANGE[self.live.difficulty]
            elif NoteType.FLICK in special_note_types and NoteType.SLIDE in special_note_types:
                l_g = 0
                r_g = 0
                l_p = 150000
                r_p = 150000
            elif note_type == NoteType.FLICK or note_type == NoteType.LONG:
                l_g = 180000
                r_g = 180000
                l_p = 150000
                r_p = 150000
            elif not is_checkpoint:
                l_g = 0
                r_g = 0
                l_p = 200000
                r_p = 200000
            else:
                l_g = 0
                r_g = 0
                l_p = 0
                r_p = 200000

            inner_l_g = l_g
            inner_l_p = l_p if not has_cc else l_p // 2
            inner_r_p = r_p if not has_cc else r_p // 2
            inner_r_g = r_g
            if -inner_l_p <= note_delta <= inner_r_p:
                return Judgement.PERFECT
            if note_type == NoteType.TAP or note_type == NoteType.FLICK or note_type == NoteType.LONG:
                if -inner_l_g <= note_delta < -inner_l_p or inner_r_p < note_delta <= inner_r_g:
                    return Judgement.GREAT
            return Judgement.MISS
        else:
            if note_type == NoteType.TAP:
                l_b = BAD_TAP_RANGE[self.live.difficulty]
                r_b = BAD_TAP_RANGE[self.live.difficulty]
                l_n = NICE_TAP_RANGE[self.live.difficulty]
                r_n = NICE_TAP_RANGE[self.live.difficulty]
                l_g = GREAT_TAP_RANGE[self.live.difficulty]
                r_g = GREAT_TAP_RANGE[self.live.difficulty]
                l_p = PERFECT_TAP_RANGE[self.live.difficulty]
                r_p = PERFECT_TAP_RANGE[self.live.difficulty]
            elif note_type == NoteType.FLICK or note_type == NoteType.LONG:
                l_b = 200000
                r_b = 200000
                l_n = 190000
                r_n = 190000
                l_g = 180000
                r_g = 180000
                l_p = 150000
                r_p = 150000
            elif not is_checkpoint:
                l_b = 0
                r_b = 0
                l_n = 0
                r_n = 0
                l_g = 0
                r_g = 0
                l_p = 200000
                r_p = 200000
            else:
                l_b = 0
                r_b = 0
                l_n = 0
                r_n = 0
                l_g = 0
                r_g = 0
                l_p = 0
                r_p = 200000

            if has_cc:
                l_p /= 2
                r_p /= 2

            if -l_p <= note_delta <= r_p:
                judgement = Judgement.PERFECT
            elif -l_g <= note_delta <= r_g:
                judgement = Judgement.GREAT
            elif -l_n <= note_delta <= r_n:
                judgement = Judgement.NICE
            elif -l_b <= note_delta <= r_b:
                judgement = Judgement.BAD
            else:
                judgement = Judgement.MISS

            if judgement <= Judgement(min(perfect_support, 4)):
                judgement = Judgement.PERFECT

            return judgement

    def evaluate_bonuses(self, special_note_types, skip_healing=False, fixed_life=None, note_time=0) \
            -> Tuple[int, int, int, int, int]:
        if self.has_skill_change:
            self.separate_magics_non_magics()
        magics = self.cache_magics
        non_magics = self.cache_non_magics
        max_boosts, sum_boosts = self._evaluate_bonuses_phase_boost(magics, non_magics)
        life_bonus, support_bonus, combo_support_bonus = self._evaluate_bonuses_phase_life_support(magics, non_magics,
                                                                                                   max_boosts,
                                                                                                   sum_boosts)
        if not skip_healing:
            self.life += life_bonus
            self.life = min(self.max_life, self.life)  # Cap life
        if not self.fail_simulate and not self.abuse:
            self.cache_hps.append(self.life)
        self._helper_evaluate_ls(fixed_life, note_time=note_time)
        self._helper_evaluate_act(special_note_types)
        self._helper_evaluate_alt_mutual_ref(special_note_types)
        self._helper_normalize_score_combo_bonuses()
        score_bonus, score_great_bonus, combo_bonus = self._evaluate_bonuses_phase_score_combo(magics, non_magics,
                                                                                               max_boosts, sum_boosts)
        return score_bonus, score_great_bonus, combo_bonus, support_bonus, combo_support_bonus

    def separate_magics_non_magics(self):
        magics = dict()
        non_magics = dict()
        for skill_idx, skills in self.skill_queue.items():
            if self.live.unit.get_card(skill_idx - 1).skill.is_magic \
                    or not self.allow_encore_magic_to_escape_max_agg \
                    and self.live.unit.get_card(skill_idx - 1).skill.is_encore \
                    and self.reference_skills[self.cache_enc[skill_idx]].is_magic:
                magics[skill_idx] = skills
            else:
                non_magics[skill_idx] = skills
        self.cache_magics = magics
        self.cache_non_magics = non_magics

    def _check_guard(self) -> bool:
        for _, skills in self.skill_queue.items():
            if isinstance(skills, Skill):
                if skills.is_guard:
                    return True
                else:
                    return False
            for skill in skills:
                if skill.is_guard:
                    return True
        return False

    def _auto_covered(self, support_bonus, is_flick) -> bool:
        # MISS covered
        if support_bonus >= 4:
            return True
        if not self._check_guard():
            self.life -= FLICK_DRAIN[self.difficulty] if is_flick else NONFLICK_DRAIN[self.difficulty]
        return False

    def _helper_evaluate_ls(self, fixed_life=None, note_time=0):
        if fixed_life is not None:
            trimmed_life = fixed_life // 10
        else:
            trimmed_life = self.life // 10
        for idx, skills in self.skill_queue.items():
            for skill in skills:
                if skill.is_sparkle:
                    if skill.values[0] == 1:
                        skill.v2 = self._sparkle_bonus_ssr[trimmed_life]
                    else:
                        skill.v2 = self._sparkle_bonus_sr[trimmed_life]
                    if idx not in self.cache_ls or self.cache_ls[idx] != skill.v2:
                        self.has_skill_change = True
                        self.unit_caches[skill.card_idx // 5].update(skill, round(note_time, -3) / 1E6)
                    skill.v2 -= 100
                    self.cache_act[idx] = skill.v2
                    skill.v0 = 0
                    skill.v1 = 0
                    skill.normalized = True

    def _helper_evaluate_act(self, special_note_types):
        for idx, skills in self.skill_queue.items():
            for skill in skills:
                if skill.act is not None:
                    if skill.act in special_note_types:
                        skill.v0 = skill.values[1]
                        skill.v1 = 0
                        skill.v2 = 0
                    else:
                        skill.v0 = skill.values[0]
                        skill.v1 = 0
                        skill.v2 = 0
                    if idx not in self.cache_act or self.cache_act[idx] != skill.v0:
                        self.has_skill_change = True
                    self.cache_act[idx] = skill.v0
                    skill.normalized = False

    def _helper_normalize_score_combo_bonuses(self):
        for idx, skills in self.skill_queue.items():
            for skill in skills:
                if skill.boost or skill.normalized:
                    continue
                if skill.v0 > 0:
                    skill.v0 -= 100
                if skill.v1 > 0:
                    skill.v1 -= 100
                if skill.v2 > 0:
                    skill.v2 -= 100
                skill.normalized = True

    def _helper_evaluate_alt_mutual_ref(self, special_note_types):
        for idx, skills in self.skill_queue.items():
            for skill in skills:
                if self.force_encore_amr_cache_to_encore_unit:
                    unit_idx = (idx - 1) // 5
                else:
                    unit_idx = skill.original_unit_idx
                if skill.is_alternate:
                    skill.v2 = skill.values[2] - 100
                    skill.v0 = self.unit_caches[unit_idx].alt_tap[skill.card_idx]
                    if NoteType.FLICK in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].alt_flick[skill.card_idx])
                    if NoteType.LONG in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].alt_long[skill.card_idx])
                    if NoteType.SLIDE in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].alt_slide[skill.card_idx])
                    skill.v1 = self.unit_caches[unit_idx].alt_great[skill.card_idx]
                    if idx not in self.cache_alt \
                            or self.cache_alt[idx][0] != skill.v0 or self.cache_alt[idx][1] != skill.v1:
                        self.has_skill_change = True
                    self.cache_alt[idx] = (skill.v0, skill.v1)
                    skill.normalized = True
                    continue
                if skill.is_mutual:
                    skill.v0 = skill.values[0] - 100
                    skill.v1 = skill.values[1] - 100
                    skill.v2 = self.unit_caches[unit_idx].alt_combo[skill.card_idx]
                    if idx not in self.cache_mut or self.cache_mut[idx] != skill.v2:
                        self.has_skill_change = True
                    self.cache_mut[idx] = skill.v2
                    skill.normalized = True
                    continue
                if skill.is_refrain:
                    skill.v0 = self.unit_caches[unit_idx].ref_tap[skill.card_idx]
                    if NoteType.FLICK in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].ref_tap[skill.card_idx])
                    if NoteType.LONG in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].ref_long[skill.card_idx])
                    if NoteType.SLIDE in special_note_types:
                        skill.v0 = max(skill.v0, self.unit_caches[unit_idx].ref_slide[skill.card_idx])
                    skill.v1 = self.unit_caches[unit_idx].ref_great[skill.card_idx]
                    skill.v2 = self.unit_caches[unit_idx].ref_combo[skill.card_idx]
                    if idx not in self.cache_ref \
                            or self.cache_ref[idx][0] != skill.v0 or self.cache_ref[idx][1] != skill.v1 \
                            or self.cache_ref[idx][2] != skill.v2:
                        self.has_skill_change = True
                    self.cache_ref[idx] = (skill.v0, skill.v1, skill.v2)
                    skill.normalized = True
                    continue

    def _evaluate_bonuses_phase_boost(self, magics: Dict[int, List[Skill]], non_magics: Dict[int, List[Skill]]) \
            -> Tuple[List[List[int]], List[List[int]]]:
        if not self.has_skill_change:
            return self.cache_max_boosts, self.cache_sum_boosts
        magic_boosts = [
            # Score(Perfect), Score(Great), Combo, Life, Support
            [1000, 1000, 1000, 1000, 0],  # Cute
            [1000, 1000, 1000, 1000, 0],  # Cool
            [1000, 1000, 1000, 1000, 0]  # Passion
        ]
        for magic_idx, skills in magics.items():
            for skill in skills:
                if not skill.boost:
                    continue
                for target in skill.targets:
                    for attr in range(5):
                        magic_boosts[target][attr] = max(magic_boosts[target][attr], skill.values[attr])
            # All skill interval should be magic's interval here
            num = int((self.skill_times[0] / 1E6 // skills[0].interval - 1) // self.unit_offset)
            magic_bonus = self.skill_details[magic_idx][num].magic_bonus
            target_texts = ("cu", "co", "pa")
            attr_texts = ("score", "combo", "life", "support")
            for target_idx, target_text in enumerate(target_texts):
                for attr_idx, attr_text in enumerate(attr_texts):
                    if attr_idx > 0:
                        attr_idx += 1
                    if attr_idx < 4:
                        magic_bonus['{}_{}'.format(target_text, attr_text)] \
                            = magic_boosts[target_idx][attr_idx] // 10 - 100
                    else:
                        magic_bonus['{}_{}'.format(target_text, attr_text)] = magic_boosts[target_idx][attr_idx]

        max_boosts = [
            [1000, 1000, 1000, 1000, 0],
            [1000, 1000, 1000, 1000, 0],
            [1000, 1000, 1000, 1000, 0]
        ]
        max_boosts_pointer: List[List[Optional[NoteDetailSkill]]]
        max_boosts_pointer = [
            [None, None, None, None, None],
            [None, None, None, None, None],
            [None, None, None, None, None]
        ]
        sum_boosts = [
            [1000, 1000, 1000, 1000, 0],
            [1000, 1000, 1000, 1000, 0],
            [1000, 1000, 1000, 1000, 0]
        ]
        sum_boosts_pointer: List[List[List[NoteDetailSkill]]]
        sum_boosts_pointer = [
            [[], [], [], [], []],
            [[], [], [], [], []],
            [[], [], [], [], []]
        ]

        def update_boosts(idx, skill_type, _target, _attr, value):
            if (_attr < 4 and value != 1000) or (_attr == 4 and value != 0):
                if value > max_boosts[_target][_attr]:
                    max_boosts[_target][_attr] = max(max_boosts[_target][_attr], value)
                    max_boosts_pointer[_target][_attr] = NoteDetailSkill(True, idx + 1, skill_type,
                                                                         round((value - 1000) / 10))
                sum_helper = 1000 if _attr < 4 else 0
                sum_boosts[_target][_attr] = sum_boosts[_target][_attr] + value - sum_helper
                sum_boosts_pointer[_target][_attr].append(NoteDetailSkill(True, idx + 1, skill_type,
                                                                          round((value - 1000) / 10)))

        for non_magic_idx, skills in non_magics.items():
            assert len(skills) == 1 or (self.reference_skills[non_magic_idx].is_encore
                                        and self.reference_skills[self.cache_enc[non_magic_idx]].is_magic)
            for skill in skills:
                if not skill.boost:
                    continue
                for target in skill.targets:
                    for attr in range(5):
                        if attr < 4 and skill.values[attr] == 0:
                            continue
                        update_boosts(non_magic_idx - 1, skill.skill_type if not skill.cache_encore else 16,
                                      target, attr, skill.values[attr])
        for target in range(3):
            for attr in range(5):
                if len(magics) > 0:
                    magic_idx = list(magics.keys())[0]
                    update_boosts(magic_idx - 1, 41, target, attr, magic_boosts[target][attr])

        # Normalize boosts
        for target in range(3):
            for attr in range(4):
                max_boosts[target][attr] /= 1000
                sum_boosts[target][attr] /= 1000
        self.cache_max_boosts = max_boosts
        self.cache_sum_boosts = sum_boosts
        self.cache_max_boosts_pointer = max_boosts_pointer
        self.cache_sum_boosts_pointer = sum_boosts_pointer
        return max_boosts, sum_boosts

    def _evaluate_bonuses_phase_life_support(self, magics: Dict[int, List[Skill]], non_magics: Dict[int, List[Skill]],
                                             max_boosts: List[List[int]], sum_boosts: List[List[int]]) \
            -> Tuple[int, int, int]:
        if not self.has_skill_change:
            return self.cache_life_bonus, self.cache_support_bonus, self.cache_combo_support_bonus
        temp_life_results = dict()
        temp_support_results = dict()
        temp_combo_support_results = dict()
        for magic_idx, skills in magics.items():
            magic_idx -= 1
            unit_idx = magic_idx // 5
            boost_dict = sum_boosts if self.live.unit.all_units[unit_idx].resonance else max_boosts
            temp_life_results[magic_idx] = 0
            temp_life_raw = 0
            temp_support_results[magic_idx] = 0
            temp_support_raw = 0
            temp_combo_support_results[magic_idx] = 0
            temp_combo_support_raw = 0
            for skill in skills:
                if skill.boost:
                    continue
                color = int(self.live.unit.get_card(magic_idx).color.value)
                if not skill.is_guard and not skill.is_combo_support and not skill.is_overload \
                        and skill.v3 == 0 and skill.v4 == 0:
                    continue
                if skill.v3 > 0:
                    temp_life_results[magic_idx] = max(temp_life_results[magic_idx],
                                                       ceil(skill.v3 * boost_dict[color][3]))
                    temp_life_raw = max(temp_life_raw, skill.v3)
                if skill.v4 > 0:
                    temp_support_results[magic_idx] = max(temp_support_results[magic_idx],
                                                          ceil(skill.v4 + boost_dict[color][4]))
                    temp_support_raw = max(temp_support_raw, skill.v4)
                if skill.is_guard:
                    temp_life_results[magic_idx] = max(temp_life_results[magic_idx], ceil(boost_dict[color][4]))
                if skill.is_combo_support:
                    temp_combo_support_results[magic_idx] = max(temp_combo_support_results[magic_idx],
                                                                ceil(1 + boost_dict[color][4]))
                    temp_combo_support_raw = max(temp_combo_support_raw, 1)
                if skill.is_overload:
                    temp_combo_support_results[magic_idx] = max(temp_combo_support_results[magic_idx], 2)
                    temp_combo_support_raw = max(temp_combo_support_raw, 2)
            # All skill interval should be magic's interval here
            num = int((self.skill_times[0] / 1E6 // skills[0].interval - 1) // self.unit_offset)
            magic_bonus = self.skill_details[magic_idx + 1][num].magic_bonus
            magic_bonus['life'] = temp_life_raw
            magic_bonus['perfect_support'] = temp_support_raw
            magic_bonus['combo_support'] = temp_combo_support_raw

        for non_magic_idx, skills in non_magics.items():
            assert len(skills) == 1 \
                   or self.reference_skills[non_magic_idx].is_encore \
                   and self.reference_skills[self.cache_enc[non_magic_idx]].is_magic
            for skill in skills:
                if skill.boost:
                    continue
                non_magic_idx = non_magic_idx - 1
                color = int(self.live.unit.get_card(non_magic_idx).color.value)
                unit_idx = non_magic_idx // 5
                boost_dict = sum_boosts if self.live.unit.all_units[unit_idx].resonance else max_boosts
                if not skill.is_guard and not skill.is_combo_support and not skill.is_overload \
                        and skill.v3 == 0 and skill.v4 == 0:
                    continue
                if skill.v3 > 0:
                    temp_life_results[non_magic_idx] = ceil(skill.v3 * boost_dict[color][3])
                if skill.v4 > 0:
                    temp_support_results[non_magic_idx] = ceil(skill.v4 + boost_dict[color][4])
                if skill.is_guard:
                    temp_life_results[non_magic_idx] = ceil(boost_dict[color][4])
                if skill.is_combo_support:
                    temp_combo_support_results[non_magic_idx] = ceil(1 + boost_dict[color][4])
                if skill.is_overload:
                    temp_combo_support_results[non_magic_idx] = 2

        unit_life_bonuses = list()
        unit_support_bonuses = list()
        unit_combo_support_bonuses = list()
        for unit_idx in range(len(self.live.unit.all_units)):
            agg_func = sum if self.live.unit.all_units[unit_idx].resonance else max

            unit_magics = {_ - 1 for _ in magics.keys() if unit_idx * 5 < _ <= unit_idx * 5 + 5}
            unit_non_magics = {_ - 1 for _ in non_magics.keys() if unit_idx * 5 < _ <= unit_idx * 5 + 5}
            # Unify magic
            unified_magic_life = 0
            unified_magic_support = 0
            unified_magic_combo_support = 0
            unified_non_magic_life = 0
            unified_non_magic_support = 0
            unified_non_magic_combo_support = 0
            if len(unit_magics) >= 1:
                for magic_idx in unit_magics:
                    if magic_idx in temp_life_results:
                        unified_magic_life = max((unified_magic_life, temp_life_results[magic_idx]))
                    if magic_idx in temp_support_results:
                        unified_magic_support = max((unified_magic_support, temp_support_results[magic_idx]))
                    if magic_idx in temp_combo_support_results:
                        unified_magic_combo_support = max(
                            (unified_magic_combo_support, temp_combo_support_results[magic_idx]))
            for non_magic in unit_non_magics:
                if non_magic in temp_life_results:
                    unified_non_magic_life = agg_func((unified_non_magic_life, temp_life_results[non_magic]))
                if non_magic in temp_support_results:
                    unified_non_magic_support = agg_func((unified_non_magic_support, temp_support_results[non_magic]))
                if non_magic in temp_combo_support_results:
                    unified_non_magic_combo_support = agg_func(
                        (unified_non_magic_combo_support, temp_combo_support_results[non_magic]))
            unit_life_bonuses.append(agg_func((unified_magic_life, unified_non_magic_life)))
            unit_support_bonuses.append(agg_func((unified_magic_support, unified_non_magic_support)))
            unit_combo_support_bonuses.append(agg_func((unified_magic_combo_support, unified_non_magic_combo_support)))
        self.cache_life_bonus = max(unit_life_bonuses)
        self.cache_support_bonus = max(unit_support_bonuses)
        self.cache_combo_support_bonus = max(unit_combo_support_bonuses)
        return self.cache_life_bonus, self.cache_support_bonus, self.cache_combo_support_bonus

    def _evaluate_bonuses_phase_score_combo(self, magics: Dict[int, List[Skill]], non_magics: Dict[int, List[Skill]],
                                            max_boosts: List[List[int]], sum_boosts: List[List[int]]) \
            -> Tuple[int, int, int]:
        if not self.has_skill_change:
            return self.cache_score_bonus, self.cache_score_great_bonus, self.cache_combo_bonus

        # Score and combo bonuses can have negative value so use None instead of 0 as default value
        # Use functions that supports parameters with None
        # Consider None as the lowest value
        def lt_none(a, b):
            return a < b if all((a, b)) else True if b is not None else False

        def gt_none(a, b):
            return a > b if all((a, b)) else True if a is not None else False

        def max_none(l):
            return max(filter(lambda x: x is not None, l)) if any(i is not None for i in l) else None

        def sum_none(l):
            return sum(filter(lambda x: x is not None, l)) if any(i is not None for i in l) else None

        def none_to_zero(x):
            return x if x is not None else 0

        temp_score_results: Dict[int, Optional[int]] = dict()
        temp_score_skills: Dict[int, Optional[NoteDetailSkill]] = dict()
        temp_score_great_results: Dict[int, Optional[int]] = dict()
        temp_score_great_skills: Dict[int, Optional[NoteDetailSkill]] = dict()
        temp_combo_results: Dict[int, Optional[int]] = dict()
        temp_combo_skills: Dict[int, Optional[NoteDetailSkill]] = dict()
        for magic_idx, skills in magics.items():
            magic_idx -= 1
            unit_idx = magic_idx // 5
            resonance = self.live.unit.all_units[unit_idx].resonance
            boost_dict = sum_boosts if resonance else max_boosts
            boost_pointer_dict = self.cache_sum_boosts_pointer if resonance else self.cache_max_boosts_pointer
            temp_score_results[magic_idx] = None
            temp_score_skills[magic_idx] = None
            temp_score_tap_raw = None
            temp_score_long_raw = None
            temp_score_flick_raw = None
            temp_score_slide_raw = None
            temp_score_great_results[magic_idx] = None
            temp_score_great_skills[magic_idx] = None
            temp_score_great_raw = None
            temp_combo_results[magic_idx] = None
            temp_combo_skills[magic_idx] = None
            temp_combo_raw = None
            temp_sparkle_raw = None
            for skill in skills:
                if skill.boost:
                    continue
                color = int(self.live.unit.get_card(magic_idx).color.value)
                if skill.v0 == 0 and skill.v1 == 0 and skill.v2 == 0:
                    continue
                if skill.v0 != 0:
                    boost_value = boost_dict[color][0] if skill.v0 > 0 else 1
                    boost_skill = boost_pointer_dict[color][0] if skill.v0 > 0 else None
                    temp_result = temp_score_results[magic_idx]
                    temp_score_results[magic_idx] = max_none(
                        (temp_score_results[magic_idx], ceil(skill.v0 * boost_value)))
                    if temp_result != temp_score_results[magic_idx]:
                        temp_score_skills[magic_idx] = NoteDetailSkill(False, magic_idx + 1, 41,
                                                                       temp_score_results[magic_idx])
                        temp_score_skills[magic_idx].add_boost(boost_skill)
                    # Cache values to magic skill detail
                    if skill.skill_type == 28:  # Long Act
                        temp_score_tap_raw = max_none((temp_score_tap_raw, skill.values[0] - 100))
                        temp_score_long_raw = max_none((temp_score_long_raw, skill.values[1] - 100))
                        temp_score_flick_raw = max_none((temp_score_flick_raw, skill.values[0] - 100))
                        temp_score_slide_raw = max_none((temp_score_slide_raw, skill.values[0] - 100))
                    elif skill.skill_type == 29:  # Flick Act
                        temp_score_tap_raw = max_none((temp_score_tap_raw, skill.values[0] - 100))
                        temp_score_long_raw = max_none((temp_score_long_raw, skill.values[0] - 100))
                        temp_score_flick_raw = max_none((temp_score_flick_raw, skill.values[1] - 100))
                        temp_score_slide_raw = max_none((temp_score_slide_raw, skill.values[0] - 100))
                    elif skill.skill_type == 30:  # Slide Act
                        temp_score_tap_raw = max_none((temp_score_tap_raw, skill.values[0] - 100))
                        temp_score_long_raw = max_none((temp_score_long_raw, skill.values[0] - 100))
                        temp_score_flick_raw = max_none((temp_score_flick_raw, skill.values[0] - 100))
                        temp_score_slide_raw = max_none((temp_score_slide_raw, skill.values[1] - 100))
                    elif skill.is_alternate:
                        temp_score_tap_raw = max_none((temp_score_tap_raw,
                                                       self.unit_caches[unit_idx].alt_tap[skill.card_idx]))
                        temp_score_long_raw = max_none((temp_score_long_raw,
                                                        self.unit_caches[unit_idx].alt_long[skill.card_idx]))
                        temp_score_flick_raw = max_none((temp_score_flick_raw,
                                                         self.unit_caches[unit_idx].alt_flick[skill.card_idx]))
                        temp_score_slide_raw = max_none((temp_score_slide_raw,
                                                         self.unit_caches[unit_idx].alt_slide[skill.card_idx]))
                    elif skill.is_refrain:
                        temp_score_tap_raw = max_none((temp_score_tap_raw,
                                                       self.unit_caches[unit_idx].ref_tap[skill.card_idx]))
                        temp_score_long_raw = max_none((temp_score_long_raw,
                                                        self.unit_caches[unit_idx].ref_long[skill.card_idx]))
                        temp_score_flick_raw = max_none((temp_score_flick_raw,
                                                         self.unit_caches[unit_idx].ref_flick[skill.card_idx]))
                        temp_score_slide_raw = max_none((temp_score_slide_raw,
                                                         self.unit_caches[unit_idx].ref_slide[skill.card_idx]))
                    else:
                        temp_score_tap_raw = max_none((temp_score_tap_raw, skill.v0))
                        temp_score_long_raw = max_none((temp_score_long_raw, skill.v0))
                        temp_score_flick_raw = max_none((temp_score_flick_raw, skill.v0))
                        temp_score_slide_raw = max_none((temp_score_slide_raw, skill.v0))
                if skill.v1 != 0:
                    boost_value = boost_dict[color][1] if skill.v1 > 0 else 1
                    boost_skill = boost_pointer_dict[color][1] if skill.v1 > 0 else None
                    temp_result = temp_score_great_results[magic_idx]
                    temp_score_great_results[magic_idx] = max_none(
                        (temp_score_great_results[magic_idx], ceil(skill.v1 * boost_value)))
                    if temp_result != temp_score_great_results[magic_idx]:
                        temp_score_great_skills[magic_idx] = NoteDetailSkill(False, magic_idx + 1, 41,
                                                                             temp_score_great_results[magic_idx])
                        temp_score_great_skills[magic_idx].add_boost(boost_skill)
                    temp_score_great_raw = max_none((temp_score_great_raw, skill.v1))
                if skill.v2 != 0:
                    boost_value = boost_dict[color][2] if skill.v2 > 0 else 1
                    boost_skill = boost_pointer_dict[color][2] if skill.v2 > 0 else None
                    temp_result = temp_combo_results[magic_idx]
                    temp_combo_results[magic_idx] = max_none(
                        (temp_combo_results[magic_idx], ceil(skill.v2 * boost_value)))
                    if temp_result != temp_combo_results[magic_idx]:
                        temp_combo_skills[magic_idx] = NoteDetailSkill(False, magic_idx + 1, 41,
                                                                       temp_combo_results[magic_idx])
                        temp_combo_skills[magic_idx].add_boost(boost_skill)
                    if skill.is_sparkle:
                        temp_sparkle_raw = max_none((temp_sparkle_raw, skill.v2))
                    else:
                        temp_combo_raw = max_none((temp_combo_raw, skill.v2))
            num = int((self.skill_times[0] / 1E6 // skills[0].interval - 1) // self.unit_offset)
            magic_bonus = self.skill_details[magic_idx + 1][num].magic_bonus
            magic_bonus['tap'] = none_to_zero(temp_score_tap_raw)
            magic_bonus['long'] = none_to_zero(temp_score_long_raw)
            magic_bonus['flick'] = none_to_zero(temp_score_flick_raw)
            magic_bonus['slide'] = none_to_zero(temp_score_slide_raw)
            magic_bonus['great'] = none_to_zero(temp_score_great_raw)
            if magic_bonus['sparkle'] == 0:  # Update Life Sparkle combo bonus only once
                magic_bonus['sparkle'] = none_to_zero(temp_sparkle_raw)
            magic_bonus['combo'] = none_to_zero(temp_combo_raw)

        for non_magic_idx, skills in non_magics.items():
            assert len(skills) == 1 \
                   or self.reference_skills[non_magic_idx].is_encore \
                   and self.reference_skills[self.cache_enc[non_magic_idx]].is_magic
            for skill in skills:
                if skill.boost:
                    continue
                non_magic_idx = non_magic_idx - 1
                color = int(self.live.unit.get_card(non_magic_idx).color.value)
                unit_idx = non_magic_idx // 5
                resonance = self.live.unit.all_units[unit_idx].resonance
                boost_dict = sum_boosts if resonance else max_boosts
                boost_pointer_dict = self.cache_sum_boosts_pointer if resonance else self.cache_max_boosts_pointer

                if skill.v0 == 0 and skill.v1 == 0 and skill.v2 == 0:
                    continue
                skill_type = skill.skill_type if not skill.cache_encore else 16
                if skill.v0 != 0:
                    boost_value = boost_dict[color][0] if skill.v0 > 0 else 1
                    boost_skill = boost_pointer_dict[color][0] if skill.v0 > 0 else None
                    temp_score_results[non_magic_idx] = ceil(skill.v0 * boost_value)
                    temp_score_skills[non_magic_idx] = NoteDetailSkill(False, non_magic_idx + 1, skill_type,
                                                                       temp_score_results[non_magic_idx])
                    temp_score_skills[non_magic_idx].add_boost(boost_skill)
                if skill.v1 != 0:
                    boost_value = boost_dict[color][1] if skill.v1 > 0 else 1
                    boost_skill = boost_pointer_dict[color][1] if skill.v1 > 0 else None
                    temp_score_great_results[non_magic_idx] = ceil(skill.v1 * boost_value)
                    temp_score_great_skills[non_magic_idx] = NoteDetailSkill(False, non_magic_idx + 1, skill_type,
                                                                             temp_score_great_results[non_magic_idx])
                    temp_score_great_skills[non_magic_idx].add_boost(boost_skill)
                if skill.v2 != 0:
                    boost_value = boost_dict[color][2] if skill.v2 > 0 else 1
                    boost_skill = boost_pointer_dict[color][2] if skill.v2 > 0 else None
                    temp_combo_results[non_magic_idx] = ceil(skill.v2 * boost_value)
                    temp_combo_skills[non_magic_idx] = NoteDetailSkill(False, non_magic_idx + 1, skill_type,
                                                                       temp_combo_results[non_magic_idx])
                    temp_combo_skills[non_magic_idx].add_boost(boost_skill)

        unit_score_bonuses: List[int] = list()
        unit_score_skills: List[List[NoteDetailSkill]] = list()
        unit_score_great_bonuses: List[int] = list()
        unit_score_great_skills: List[List[NoteDetailSkill]] = list()
        unit_combo_bonuses: List[int] = list()
        unit_combo_skills: List[List[NoteDetailSkill]] = list()
        for unit_idx in range(len(self.live.unit.all_units)):
            resonance = self.live.unit.all_units[unit_idx].resonance
            agg_func = sum_none if resonance else max_none

            unit_magics = {_ - 1 for _ in magics.keys() if unit_idx * 5 < _ <= unit_idx * 5 + 5}
            unit_non_magics = {_ - 1 for _ in non_magics.keys() if unit_idx * 5 < _ <= unit_idx * 5 + 5}

            unified_magic_score: Optional[int] = None
            unified_magic_score_skill: Optional[NoteDetailSkill] = None
            unified_magic_score_great: Optional[int] = None
            unified_magic_score_great_skill: Optional[NoteDetailSkill] = None
            unified_magic_combo: Optional[int] = None
            unified_magic_combo_skill: Optional[NoteDetailSkill] = None
            if len(unit_magics) >= 1:
                for magic_idx in unit_magics:
                    if magic_idx in temp_score_results:
                        if lt_none(unified_magic_score, temp_score_results[magic_idx]):
                            unified_magic_score = temp_score_results[magic_idx]
                            unified_magic_score_skill = temp_score_skills[magic_idx]
                    if magic_idx in temp_score_great_results:
                        if lt_none(unified_magic_score_great, temp_score_great_results[magic_idx]):
                            unified_magic_score_great = temp_score_great_results[magic_idx]
                            unified_magic_score_great_skill = temp_score_great_skills[magic_idx]
                    if magic_idx in temp_combo_results:
                        if lt_none(unified_magic_combo, temp_combo_results[magic_idx]):
                            unified_magic_combo = temp_combo_results[magic_idx]
                            unified_magic_combo_skill = temp_combo_skills[magic_idx]

            unified_non_magic_score: Optional[int] = None
            unified_non_magic_score_skill: List[Optional[NoteDetailSkill]] = list()
            unified_non_magic_score_great: Optional[int] = None
            unified_non_magic_score_great_skill: List[Optional[NoteDetailSkill]] = list()
            unified_non_magic_combo: Optional[int] = None
            unified_non_magic_combo_skill: List[Optional[NoteDetailSkill]] = list()
            for non_magic in unit_non_magics:
                if non_magic in temp_score_results:
                    if lt_none(unified_non_magic_score, temp_score_results[non_magic]) or resonance:
                        unified_non_magic_score = agg_func((unified_non_magic_score, temp_score_results[non_magic]))
                        if not resonance:
                            unified_non_magic_score_skill.clear()
                        unified_non_magic_score_skill.append(temp_score_skills[non_magic])
                if non_magic in temp_score_great_results:
                    if lt_none(unified_non_magic_score_great, temp_score_great_results[non_magic]) or resonance:
                        unified_non_magic_score_great = agg_func(
                            (unified_non_magic_score_great, temp_score_great_results[non_magic]))
                        if not resonance:
                            unified_non_magic_score_great_skill.clear()
                        unified_non_magic_score_great_skill.append(temp_score_great_skills[non_magic])
                if non_magic in temp_combo_results:
                    if lt_none(unified_non_magic_combo, temp_combo_results[non_magic]) or resonance:
                        unified_non_magic_combo = agg_func((unified_non_magic_combo, temp_combo_results[non_magic]))
                        if not resonance:
                            unified_non_magic_combo_skill.clear()
                        unified_non_magic_combo_skill.append(temp_combo_skills[non_magic])

            unit_score_bonuses.append(agg_func((unified_magic_score, unified_non_magic_score)))
            unit_score_great_bonuses.append(agg_func((unified_magic_score_great, unified_non_magic_score_great)))
            unit_combo_bonuses.append(agg_func((unified_magic_combo, unified_non_magic_combo)))

            unified_score_skills: List[NoteDetailSkill] = list()
            unified_score_great_skills: List[NoteDetailSkill] = list()
            unified_combo_skills: List[NoteDetailSkill] = list()
            if resonance:
                if unified_magic_score_skill is not None:
                    unified_score_skills.append(unified_magic_score_skill)
                unified_score_skills.extend(unified_non_magic_score_skill)
                if unified_magic_score_great_skill is not None:
                    unified_score_great_skills.append(unified_magic_score_great_skill)
                unified_score_great_skills.extend(unified_non_magic_score_great_skill)
                if unified_magic_combo_skill is not None:
                    unified_combo_skills.append(unified_magic_combo_skill)
                unified_combo_skills.extend(unified_non_magic_combo_skill)
            else:
                if gt_none(unified_magic_score, unified_non_magic_score) and unified_magic_score_skill is not None:
                    unified_score_skills.append(unified_magic_score_skill)
                else:
                    unified_score_skills.extend(unified_non_magic_score_skill)
                if gt_none(unified_magic_score_great, unified_non_magic_score_great) \
                        and unified_magic_score_great_skill is not None:
                    unified_score_great_skills.append(unified_magic_score_great_skill)
                else:
                    unified_score_great_skills.extend(unified_non_magic_score_great_skill)
                if gt_none(unified_magic_combo, unified_non_magic_combo) and unified_magic_combo_skill is not None:
                    unified_combo_skills.append(unified_magic_combo_skill)
                else:
                    unified_combo_skills.extend(unified_non_magic_combo_skill)
            unit_score_skills.append(unified_score_skills)
            unit_score_great_skills.append(unified_score_great_skills)
            unit_combo_skills.append(unified_combo_skills)

        max_score_bonus = max_none(unit_score_bonuses)
        max_score_bonus_index = unit_score_bonuses.index(max_score_bonus)
        max_score_great_bonus = max_none(unit_score_great_bonuses)
        max_score_great_bonus_index = unit_score_great_bonuses.index(max_score_great_bonus)
        max_combo_bonus = max_none(unit_combo_bonuses)
        max_combo_bonus_index = unit_combo_bonuses.index(max_combo_bonus)

        self.cache_score_bonus = none_to_zero(max_score_bonus)
        self.cache_score_bonus_skill = unit_score_skills[max_score_bonus_index]
        self.cache_score_great_bonus = none_to_zero(max_score_great_bonus)
        self.cache_score_great_bonus_skill = unit_score_great_skills[max_score_great_bonus_index]
        self.cache_combo_bonus = none_to_zero(max_combo_bonus)
        self.cache_combo_bonus_skill = unit_combo_skills[max_combo_bonus_index]
        return self.cache_score_bonus, self.cache_score_great_bonus, self.cache_combo_bonus

    def _expand_magic(self):
        skill = copy.deepcopy(self.reference_skills[self.skill_indices[0]])
        if skill.is_magic or (skill.is_encore and self.skill_queue[self.skill_indices[0]].is_magic):
            if skill.is_magic or self.force_encore_magic_to_encore_unit:
                unit_idx = (self.skill_indices[0] - 1) // 5
            else:
                unit_idx = (self.cache_enc[self.skill_indices[0]] - 1) // 5

            self.skill_queue[self.skill_indices[0]] = list()
            iterating_order = list()
            _cache_guard = list()
            _cache_alt = list()
            _cache_mut = list()
            _cache_ref = list()
            magic_idx = self.skill_indices[0]
            num = (int(self.skill_times[0] / 1E6 / skill.interval) - 1) // self.unit_offset
            magic_bonus = self.skill_details[magic_idx][num].magic_bonus
            for idx in range(unit_idx * 5 + 1, unit_idx * 5 + 6):
                copied_skill = copy.deepcopy(self.reference_skills[idx])

                # Skip skills that cannot activate
                if self.reference_skills[idx].probability == 0:
                    continue
                # Magic does not copy itself
                if self.reference_skills[idx].is_magic:
                    continue
                # Expand encore
                if self.reference_skills[idx].is_encore:
                    copied_skill = self._get_last_encoreable_skill()
                    # But there's nothing for encore to copy yet, skip
                    if copied_skill is None:
                        continue
                    # Or the skill for encore to copy is magic as well, skip
                    # Do not allow magic-encore-magic
                    copied_skill = copy.deepcopy(self.reference_skills[copied_skill])
                    if copied_skill.is_magic:
                        continue
                    # Else let magic copy the encored skill instead

                copied_skill.set_card_idx(self.skill_indices[0] - 1)
                copied_skill.interval = skill.interval
                copied_skill.duration = skill.duration

                if copied_skill.is_guard:
                    _cache_guard.append(copied_skill)
                    magic_bonus['guard'] = True
                    continue
                if copied_skill.is_alternate:
                    _cache_alt.append(copied_skill)
                    continue
                if copied_skill.is_mutual:
                    _cache_mut.append(copied_skill)
                    continue
                if copied_skill.is_refrain:
                    _cache_ref.append(copied_skill)
                    continue
                if copied_skill.is_overload or copied_skill.is_spike:
                    magic_bonus['overload'] += copied_skill.life_requirement
                if copied_skill.is_overload:
                    magic_bonus['combo_support'] = max(magic_bonus['combo_support'], 2)
                if copied_skill.is_cc:
                    magic_bonus['concentration'] = True
                iterating_order.append(copied_skill)

            iterating_order = _cache_guard + iterating_order + _cache_alt + _cache_mut + _cache_ref
            for _ in iterating_order:
                self.skill_queue[self.skill_indices[0]].append(_)
            if magic_bonus['guard']:
                magic_bonus['overload'] = 0

    def _expand_encore(self):
        skill = self.reference_skills[self.skill_indices[0]]
        if skill.is_encore:
            idx = self.skill_indices[0]
            num = (int(self.skill_times[0] / 1E6 / skill.interval) - 1) // self.unit_offset
            last_encoreable_skill = self._get_last_encoreable_skill()
            if last_encoreable_skill is None:
                pop_skill_index = self.skill_indices.index(-self.skill_indices[0])
                self.skill_times.pop(pop_skill_index)
                self.skill_indices.pop(pop_skill_index)
                self.skill_indices.pop(0)
                self.skill_times.pop(0)
                self.skill_details[idx][num].inact = SkillInact.NO_ENCOREABLE
                return False

            encore_copy: Skill = copy.deepcopy(self.reference_skills[last_encoreable_skill])
            encore_copy.interval = skill.interval
            encore_copy.duration = skill.duration
            encore_copy.cache_encore = True

            self.skill_queue[self.skill_indices[0]] = encore_copy
            self.cache_enc[self.skill_indices[0]] = last_encoreable_skill
            if self.last_activated_time[-1] == self.skill_times[0]:
                time = self.last_activated_time[-2] // 1E6
            else:
                time = self.last_activated_time[-1] // 1E6
            self.skill_details[idx][num].encored_skill = (encore_copy.card_idx + 1, encore_copy.skill_type, time)
        return True

    def _get_last_encoreable_skill(self) -> Optional[int]:
        if len(self.last_activated_skill) == 0:
            return None
        if self.skill_times[0] > self.last_activated_time[-1]:
            return self.last_activated_skill[-1]
        elif len(self.last_activated_time) == 1:
            return None
        else:
            return self.last_activated_skill[-2]

    def _evaluate_motif(self):
        skills_to_check = self._helper_get_current_skills()
        unit_idx = (self.skill_indices[0] - 1) // 5
        for skill in skills_to_check:
            if skill.is_motif:
                skill.v0 = self.live.unit.all_units[unit_idx].convert_motif(skill.skill_type, self.grand)
                skill.normalized = False

    def _evaluate_ls(self):
        skills_to_check = self._helper_get_current_skills()
        for skill in skills_to_check:
            if skill.is_sparkle:
                trimmed_life = self.life // 10
                if trimmed_life < 0:
                    trimmed_life = 0
                if skill.values[0] == 1:
                    skill.v2 = self._sparkle_bonus_ssr[trimmed_life]
                else:
                    skill.v2 = self._sparkle_bonus_sr[trimmed_life]
                skill.v0 = 0
                skill.v1 = 0

    # noinspection PyTypeChecker
    def _cache_amr(self):
        skills_to_check = self._helper_get_current_skills()
        for skill in skills_to_check:
            if skill.is_alternate or skill.is_mutual or skill.is_refrain:
                if self.force_encore_amr_cache_to_encore_unit:
                    unit_idx = (self.skill_indices[0] - 1) // 5
                else:
                    unit_idx = skill.original_unit_idx
                self.unit_caches[unit_idx].update_amr(skill)
                unit = self.unit_caches[unit_idx]
                idx = self.skill_indices[0]
                num = (int(self.skill_times[0] / 1E6 / skill.interval) - 1) // self.unit_offset
                if skill.is_refrain:
                    bonuses = (unit.ref_tap[idx - 1], unit.ref_long[idx - 1], unit.ref_flick[idx - 1],
                               unit.ref_slide[idx - 1], unit.ref_great[idx - 1], unit.ref_combo[idx - 1])
                else:
                    bonuses = (unit.alt_tap[idx - 1], unit.alt_long[idx - 1], unit.alt_flick[idx - 1],
                               unit.alt_slide[idx - 1], unit.alt_great[idx - 1], unit.alt_combo[idx - 1])
                amr_bonus = self.skill_details[idx][num].amr_bonus
                amr_bonus['tap'] = (bonuses[0], unit.tap - 100) + unit.tap_update
                amr_bonus['long'] = (bonuses[1], unit.longg - 100) + unit.longg_update
                amr_bonus['flick'] = (bonuses[2], unit.flick - 100) + unit.flick_update
                amr_bonus['slide'] = (bonuses[3], unit.slide - 100) + unit.slide_update
                amr_bonus['great'] = (bonuses[4], unit.great - 100) + unit.great_update
                amr_bonus['combo'] = (bonuses[5], unit.combo - 100) + unit.combo_update

    def _helper_get_current_skills(self) -> List[Skill]:
        if self.skill_indices[0] not in self.skill_queue:
            return []
        skills_to_check = self.skill_queue[self.skill_indices[0]]
        if isinstance(skills_to_check, Skill):
            skills_to_check = [skills_to_check]
        return skills_to_check

    def _cache_skill_data(self):
        skills_to_check = self._helper_get_current_skills()
        unit_idx = (self.skill_indices[0] - 1) // 5
        for skill in skills_to_check:
            self.unit_caches[unit_idx].update(skill, self.skill_times[0] / 1E6)

    def _handle_skill_activation(self):
        def update_last_activated_skill(replace, skill_time):
            """
            Update last activated skill for encore
            :type replace: True if new skill activates after the cached skill, False if same time
            :type skill_time: encore time to check for skills before that
            """
            if self.reference_skills[self.skill_indices[0]].is_encore:
                return
            if replace:
                self.last_activated_skill.append(self.skill_indices[0])
                self.last_activated_time.append(skill_time)
            else:
                self.last_activated_skill[-1] = min(self.last_activated_skill[-1], self.skill_indices[0])

        # If skill is still not queued after self._expand_magic and self._expand_encore
        if self.skill_indices[0] not in self.skill_queue:
            self.skill_queue[self.skill_indices[0]] = copy.deepcopy(self.reference_skills[self.skill_indices[0]])

        # Pop deactivation out if skill cannot activate
        if not self._can_activate():
            skill_id = self.skill_indices[0]
            self.skill_queue.pop(self.skill_indices[0])
            # First index of -skill_id should be the correct value
            # because a skill cannot activate twice before deactivating once
            pop_skill_index = self.skill_indices.index(-skill_id)
            # Pop the deactivation first to avoid messing up the index
            self.skill_times.pop(pop_skill_index)
            self.skill_indices.pop(pop_skill_index)
            # Don't need to pop the activation because it will be pop in the outer sub
            return

        # Update last activated skill for encore
        # If new skill is strictly after cached last skill, just replace it
        if len(self.last_activated_time) == 0 or self.last_activated_time[-1] < self.skill_times[0]:
            update_last_activated_skill(replace=True, skill_time=self.skill_times[0])
        elif self.last_activated_time[-1] == self.skill_times[0]:
            # Else update taking skill index order into consideration
            update_last_activated_skill(replace=False, skill_time=self.skill_times[0])

    def _handle_life_drain(self, life_requirement) -> bool:
        if self.life > life_requirement:
            if not self._check_guard():
                self.life -= life_requirement
            return False
        else:
            return True

    def _check_focus_activation(self, unit_idx, skill) -> bool:
        card_colors = [card.color for card in self.live.unit.all_units[unit_idx].all_cards()]
        if skill.skill_type == 21:
            return not any(filter(lambda x: x is not Color.CUTE, card_colors))
        if skill.skill_type == 22:
            return not any(filter(lambda x: x is not Color.COOL, card_colors))
        if skill.skill_type == 23:
            return not any(filter(lambda x: x is not Color.PASSION, card_colors))
        # Should not reach here
        raise ValueError("Reached invalid state of focus activation check: ", skill)

    def _check_tricolor_activation(self, unit_idx) -> bool:
        card_colors = [card.color for card in self.live.unit.all_units[unit_idx].all_cards(guest=True)]
        return all(color in card_colors for color in (Color.CUTE, Color.COOL, Color.PASSION))

    def _can_activate(self) -> bool:
        """
        Checks if a (list of) queued skill(s) can activate or not.
        """
        skills_to_check = self.skill_queue[self.skill_indices[0]]
        is_magic = True
        magic_have_score_bonus = False
        magic_have_combo_bonus = False
        if isinstance(skills_to_check, Skill):
            skills_to_check = [skills_to_check]
            is_magic = False
        if len(skills_to_check) == 0:
            return False
        has_failed = False
        to_be_removed = list()
        magic_alt_mut_check = list()
        for skill in skills_to_check:
            idx = self.skill_indices[0]
            num = (int(self.skill_times[0] / 1E6 / skill.interval) - 1) // self.unit_offset
            if self.force_encore_amr_cache_to_encore_unit:
                unit_idx = (self.skill_indices[0] - 1) // 5
            else:
                unit_idx = skill.original_unit_idx

            if skill.is_encore:
                # Encore should not be here, all encores should have already been replaced
                to_be_removed.append(skill)
                if not is_magic:
                    self.skill_details[idx][num].inact = SkillInact.NO_ENCOREABLE
                continue
            # Check alt and mut in magic again after all other magic skills are checked
            if skill.is_alternate and self.unit_caches[unit_idx].tap == 0:
                if is_magic:
                    magic_alt_mut_check.append(skill)
                else:
                    to_be_removed.append(skill)
                    self.skill_details[idx][num].inact = SkillInact.NO_SCORE_BONUS
                continue
            if skill.is_mutual and self.unit_caches[unit_idx].combo == 0:
                if is_magic:
                    magic_alt_mut_check.append(skill)
                else:
                    to_be_removed.append(skill)
                    self.skill_details[idx][num].inact = SkillInact.NO_COMBO_BONUS
                continue
            if skill.is_refrain and self.unit_caches[unit_idx].tap == 0 and self.unit_caches[unit_idx].combo == 0:
                to_be_removed.append(skill)
                if not is_magic:
                    self.skill_details[idx][num].inact = SkillInact.NO_SCORE_COMBO
                continue
            if skill.is_focus:
                if not self._check_focus_activation(unit_idx=(self.skill_indices[0] - 1) // 5, skill=skill):
                    to_be_removed.append(skill)
                    if skill.skill_type == 21:
                        if not is_magic:
                            self.skill_details[idx][num].inact = SkillInact.NOT_CU_ONLY
                    if skill.skill_type == 22:
                        if not is_magic:
                            self.skill_details[idx][num].inact = SkillInact.NOT_CO_ONLY
                    if skill.skill_type == 23:
                        if not is_magic:
                            self.skill_details[idx][num].inact = SkillInact.NOT_PA_ONLY
                    continue
            if skill.is_tricolor:
                if not self._check_tricolor_activation(unit_idx=(self.skill_indices[0] - 1) // 5):
                    to_be_removed.append(skill)
                    if not is_magic:
                        self.skill_details[idx][num].inact = SkillInact.NOT_TRICOLOR
                    continue
            if skill.is_overload or skill.is_spike:
                if not has_failed:
                    has_failed = self._handle_life_drain(skill.life_requirement)
                if has_failed:
                    to_be_removed.append(skill)
                    if not is_magic:
                        self.skill_details[idx][num].inact = SkillInact.LIFE_LOW
                    continue
            if is_magic:
                if skill.have_score_bonus:
                    magic_have_score_bonus = True
                if skill.have_combo_bonus:
                    magic_have_combo_bonus = True
        for skill in magic_alt_mut_check:
            if skill.is_alternate and not magic_have_score_bonus:
                to_be_removed.append(skill)
                continue
            if skill.is_mutual and not magic_have_combo_bonus:
                to_be_removed.append(skill)
                continue
        if is_magic and len(skills_to_check) > len(to_be_removed):
            idx = self.skill_indices[0]
            interval = skills_to_check[0].interval
            num = (int(self.skill_times[0] / 1E6 / interval) - 1) // self.unit_offset
            self.skill_details[idx][num].active = True
        for skill in to_be_removed:
            skills_to_check.remove(skill)
            if skill.probability > 0:
                self.full_roll_chance /= skill.probability
        self.skill_queue[self.skill_indices[0]] = skills_to_check
        return len(skills_to_check) > 0

    def get_note_scores(self) -> np.ndarray:
        return self.note_scores

    def get_full_roll_chance(self) -> float:
        return self.full_roll_chance
