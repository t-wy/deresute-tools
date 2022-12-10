from typing import Union, List, Tuple

import numpy as np
import pandas as pd
import pyximport

from logic.grandunit import GrandUnit
from logic.live import BaseLive, Live
from static.color import Color
from static.song_difficulty import Difficulty

pyximport.install(language_level=3)


class GrandLive(BaseLive):
    unit: GrandUnit
    unit_lives: List[Live]

    def __init__(self, music_name: str = None, difficulty: int = None, unit: GrandUnit = None):
        self.unit_lives = list()
        for i in range(3):
            dummy_live = Live()
            self.unit_lives.append(dummy_live)
        super().__init__(music_name, difficulty, unit)

    def initialize_music(self, music_name: str = None, difficulty: Union[int, Difficulty] = None,
                         unit: GrandUnit = None):
        super().initialize_music(music_name, difficulty, unit)
        for i in range(3):
            self.unit_lives[i].initialize_music(music_name, difficulty, unit)

    def set_music(self, music_name: str = None, score_id: int = None, difficulty: Union[int, Difficulty] = None,
                  event: bool = None, skip_load_notes: bool = False, output: bool = False) \
            -> Tuple[pd.DataFrame, Color, int, int]:
        super().set_music(music_name, score_id, difficulty, event, skip_load_notes)
        for i in range(3):
            self.unit_lives[i].set_music(music_name, score_id, difficulty, event, skip_load_notes)
        if output:
            return self.notes, self.color, self.level, self.duration

    def set_chara_bonus(self, chara_bonus_set: set, chara_bonus_value: int):
        super().set_chara_bonus(chara_bonus_set, chara_bonus_value)
        for i in range(3):
            self.unit_lives[i].set_chara_bonus(chara_bonus_set, chara_bonus_value)

    def reset_attributes(self, hard_reset: bool = True):
        for i in range(3):
            self.unit_lives[i].reset_attributes(hard_reset)

    def set_unit(self, unit: GrandUnit):
        assert isinstance(unit, GrandUnit)
        self.unit = unit
        for i in range(3):
            self.unit_lives[i].set_unit(self.unit.get_unit(i))
            self.unit_lives[i].reset_attributes()

    def set_extra_bonus(self, bonuses: np.ndarray, special_option: int, special_value: int):
        super().set_extra_bonus(bonuses, special_option, special_value)
        for i in range(3):
            self.unit_lives[i].set_extra_bonus(bonuses, special_option, special_value)

    def get_attributes(self) -> np.ndarray:
        self.attribute_cache_check()
        if self.attributes is not None:
            return self.attributes

        if self.attributes is not None:
            return self.attributes

        self.get_bonuses()
        attributes = np.zeros((4, 3))  # Attributes x Units
        for unit_idx in range(3):
            attributes[:, unit_idx] = self.unit_lives[unit_idx].get_attributes()
        self.attributes = attributes
        return self.attributes

    def get_life(self) -> int:
        return np.ceil(self.get_attributes()[3].mean())

    @property
    def is_grand(self) -> bool:
        return True

    def get_bonuses(self):
        for unit_live in self.unit_lives:
            unit_live.get_bonuses()

    def get_probability(self, idx: int = None) -> float:
        return self.unit_lives[idx // 5].get_probability(idx % 5)
