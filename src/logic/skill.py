from __future__ import annotations

from typing import Any, Union, Optional, List, Dict, Tuple

import numpy as np
import pyximport

from db import db
from static.color import Color
from static.note_type import NoteType
from static.skill import SKILL_BASE, SKILL_DESCRIPTION

pyximport.install(language_level=3)

BOOST_TYPES = {20, 32, 33, 34, 38, 45, 46, 47, 48, 49, 50}
HARMONY_TYPES = {45, 46, 47, 48, 49, 50}
COLOR_TARGETS = {21, 22, 23, 32, 33, 34, 45, 46, 47, 48, 49, 50}
ACT_TYPES = {28: NoteType.LONG, 29: NoteType.FLICK, 30: NoteType.SLIDE}
SUPPORT_TYPES = {5, 6, 7}
COMMON_TIMERS = [(7, 4.5, 'h'), (9, 6, 'h'), (11, 7.5, 'h'), (12, 7.5, 'm'),
                 (6, 4.5, 'm'), (7, 6, 'm'), (9, 7.5, 'm'), (11, 9, 'm'), (13, 9, 'h')]


class Skill:
    def __init__(self, color: Color = Color.CUTE, duration: int = 0, probability: int = 0, interval: int = 999,
                 values: List[int] = None, v0: int = 0, v1: int = 0, v2: int = 0, v3: int = 0, v4: int = 0,
                 offset: int = 0, boost: bool = False, color_target: bool = False, act: NoteType = None,
                 bonus_skill: int = 2000, skill_type: int = 0,
                 min_requirements: Union[np.array, list] = None, max_requirements: Union[np.array, list] = None,
                 song_required: Color = None, life_requirement: int = 0, skill_level: int = 10):
        if values is None and v0 == v1 == v2 == v3 == v4 == 0:
            raise ValueError("Invalid skill values", values, v0, v1, v2, v3, v4)

        if min_requirements is not None:
            assert len(min_requirements) == 3
        else:
            min_requirements = np.array([0, 0, 0])

        if max_requirements is not None:
            assert len(max_requirements) == 3
        else:
            max_requirements = np.array([99, 99, 99])

        self.color = color
        self.duration = duration
        self.probability = probability + bonus_skill
        self.cached_probability = self.probability
        self.max_probability = probability
        self.interval = interval
        self.v0, self.v1, self.v2, self.v3, self.v4 = tuple(values)
        self.values = [self.v0, self.v1, self.v2, self.v3, self.v4]
        self.offset = offset
        self.boost = boost
        self.color_target = color_target
        self.act = act
        self.skill_type = skill_type
        self.min_requirements = min_requirements
        self.max_requirements = max_requirements
        self.life_requirement = life_requirement
        self.song_required = song_required
        self.skill_level = skill_level
        self.targets = self._generate_targets()
        self.targets_harmony = self._generate_targets_harmony()
        self.normalized = False
        self.original_unit_idx = None
        self.card_idx = None
        self.cache_encore = False

    def set_original_unit_idx(self, idx: int):
        self.original_unit_idx = idx

    def set_card_idx(self, idx: int):
        self.card_idx = idx

    def _generate_targets(self) -> List[int]:
        if self.skill_type == 21 or self.skill_type == 32:
            return [0]
        if self.skill_type == 22 or self.skill_type == 33:
            return [1]
        if self.skill_type == 23 or self.skill_type == 34:
            return [2]
        if self.skill_type in (45, 46, 47, 48, 49, 50):
            return []
        return [0, 1, 2]

    def _generate_targets_harmony(self) -> Optional[List[int]]:
        if self.skill_type == 45:
            return [0, 1]
        if self.skill_type == 46:
            return [0, 2]
        if self.skill_type == 47:
            return [1, 0]
        if self.skill_type == 48:
            return [1, 2]
        if self.skill_type == 49:
            return [2, 0]
        if self.skill_type == 50:
            return [2, 1]
        return None

    @property
    def is_combo_support(self) -> bool:
        return self.skill_type == 9

    @property
    def is_score_great(self) -> bool:
        return self.skill_type == 2

    @property
    def is_guard(self) -> bool:
        return self.skill_type == 12

    @property
    def is_overload(self) -> bool:
        return self.skill_type == 14

    @property
    def is_cc(self) -> bool:
        return self.skill_type == 15

    @property
    def is_encore(self) -> bool:
        return self.skill_type == 16

    @property
    def is_focus(self) -> bool:
        return 21 <= self.skill_type <= 23

    @property
    def is_sparkle(self) -> bool:
        return self.skill_type == 25

    @property
    def is_tuning(self) -> bool:
        return self.skill_type == 31

    @property
    def is_motif(self) -> bool:
        return 35 <= self.skill_type <= 37

    @property
    def is_alternate(self) -> bool:
        return self.skill_type == 39

    @property
    def is_refrain(self) -> bool:
        return self.skill_type == 40

    @property
    def is_magic(self) -> bool:
        return self.skill_type == 41

    @property
    def is_mutual(self) -> bool:
        return self.skill_type == 42

    @property
    def is_overdrive(self) -> bool:
        return self.skill_type == 43

    @property
    def is_spike(self) -> bool:
        return self.skill_type == 44

    @property
    def is_harmony(self) -> bool:
        return 45 <= self.skill_type <= 50

    @property
    def is_tricolor(self) -> bool:
        return all(req > 0 for req in self.min_requirements)

    @property
    def have_score_bonus(self) -> bool:
        return self.skill_type in (1, 2, 14, 15, 21, 22, 23, 26, 27, 28, 29, 30, 35, 36, 37, 42)

    @property
    def have_combo_bonus(self) -> bool:
        return self.skill_type in (4, 21, 22, 23, 24, 25, 26, 27, 31, 39, 43)

    @classmethod
    def _fetch_skill_data_from_db(cls, skill_id: int, attribute = None) -> Dict[str, Any]:
        if attribute is None:
            return db.masterdb.execute_and_fetchone("""
                SELECT skill_data.*,
                    card_data.attribute,
                    probability_type.probability_max,
                    available_time_type.available_time_max
                FROM card_data, skill_data, probability_type, available_time_type
                WHERE skill_data.id = ?
                    AND card_data.skill_id = ?
                    AND probability_type.probability_type = skill_data.probability_type
                    AND available_time_type.available_time_type = skill_data.available_time_type
                """, params=[skill_id, skill_id], out_dict=True)
        else:
            temp = db.masterdb.execute_and_fetchone("""
                SELECT skill_data.*,
                    probability_type.probability_max,
                    available_time_type.available_time_max
                FROM skill_data, probability_type, available_time_type
                WHERE skill_data.id = ?
                    AND probability_type.probability_type = skill_data.probability_type
                    AND available_time_type.available_time_type = skill_data.available_time_type
                """, params=[skill_id], out_dict=True)
            temp["attribute"] = attribute
            return temp

    @classmethod
    def _fetch_boost_value_from_db(cls, skill_value: int) -> List[int]:
        values = db.masterdb.execute_and_fetchone(
            """
            SELECT  sbt1.boost_value_1 as v0,
                    sbt1.boost_value_2 as v1,
                    sbt1.boost_value_3 as v2,
                    sbt2.boost_value_2 as v3
            FROM    skill_boost_type as sbt1,
                    skill_boost_type as sbt2
            WHERE   sbt1.skill_value = ?
            AND     sbt1.target_type = 26
            AND     sbt2.skill_value = ?
            AND     sbt2.target_type = 31
            """,
            params=[skill_value, skill_value],
            out_dict=True)
        values = [values["v{}".format(_)] for _ in range(4)]
        values.insert(1, values[0])
        return values

    @classmethod
    def _fetch_custom_skill_from_db(cls, custom_card_id: int, attribute = None) -> Optional[Dict[str, Any]]:
        values = db.cachedb.execute_and_fetchone("""
            SELECT  image_id,
                    skill_type,
                    condition,
                    available_time_type,
                    probability_type,
                    value,
                    value_2,
                    value_3
            FROM custom_card WHERE id = ?
            """, params=[custom_card_id], out_dict=True)
        if values['skill_type'] == 0:
            return
        if attribute is None:
            values['attribute'] = db.masterdb.execute_and_fetchone("SELECT attribute FROM card_data WHERE id = ?",
                                                                [values['image_id']])[0]
        else:
            values['attribute'] = attribute
        values['available_time_max'] = db.masterdb.execute_and_fetchone("""
            SELECT available_time_max FROM available_time_type WHERE available_time_type = ?
            """, [values['available_time_type']])[0]
        values['probability_max'] = db.masterdb.execute_and_fetchone("""
            SELECT probability_max FROM probability_type WHERE probability_type = ?
            """, [values['probability_type']])[0]
        values['skill_trigger_type'], values['skill_trigger_value'] = db.masterdb.execute_and_fetchone("""
            SELECT  skill_trigger_type, skill_trigger_value FROM skill_data WHERE skill_type = ?
            """, params=[values['skill_type']])
        return values

    @classmethod
    def _handle_skill_type(cls, skill_type: int, skill_values: Tuple[int, int, int]) -> List[int]:
        assert len(skill_values) == 3
        values = [0, 0, 0, 0, 0]  # Score(Perfect), Score(Great), Combo, Heal, Support
        if skill_type in (9, 12):  # Damage guard, combo support
            pass
        elif skill_type in SUPPORT_TYPES:
            values[4] = skill_type - 4
        elif skill_type in ACT_TYPES:  # Act : Score(Other notes), Score(Special notes), Combo, Heal, Support
            values[0] = skill_values[0]
            values[1] = skill_values[1]
        elif skill_type == 2 or skill_type == 14:  # SU, Overload
            values[0], values[1] = skill_values[0], skill_values[0]
        elif skill_type == 4:  # CU
            values[2] = skill_values[0]
        elif skill_type == 31:  # Tuning
            values[2] = skill_values[0]
            values[4] = 2
        elif skill_type == 24 or skill_type == 43:  # All-round, Overdrive
            values[2] = skill_values[0]
            values[3] = skill_values[1]
        elif skill_type == 17:  # Healer
            values[3] = skill_values[0]
        elif skill_type == 39:  # Alt
            values[0] = skill_values[1]
            values[1] = skill_values[1]
            values[2] = skill_values[0]
        elif skill_type == 42:  # Mutual
            values[0] = skill_values[0]
            values[1] = skill_values[0]
            values[2] = skill_values[1]
        else:
            values = [skill_values[0], 0, skill_values[1], skill_values[2], 0]
        return values

    @classmethod
    def from_id(cls, skill_id: int, bonus_skill: int = 2000, attribute = None) -> Skill:
        if skill_id == 0:
            return cls(values=[0, 0, 0, 0, 0])  # Default skill that has 0 duration
        if skill_id < 500000 or skill_id > 5000000:
            skill_data = cls._fetch_skill_data_from_db(skill_id, attribute)
            life_requirement = skill_data['skill_trigger_value'] if skill_data['skill_type'] in (14, 44) else 0
        else:
            skill_data = cls._fetch_custom_skill_from_db(int(str(skill_id)[1:]), skill_data)
            if skill_data is None:
                return cls(values=[0, 0, 0, 0, 0])
            # Values for non-existing intervals were arbitrarily set
            ol_life = {4: 6, 6: 9, 7: 11, 9: 15,
                       5: 8, 8: 13, 10: 16, 11: 17, 12: 18, 13: 20, 14: 22, 15: 24, 16: 26, 17: 28, 18: 30}
            spk_life = {7: 18, 9: 22, 11: 27,
                        4: 10, 5: 13, 6: 16, 8: 20, 10: 25, 12: 30, 13: 33, 14: 36, 15: 38, 16: 40, 17: 43, 18: 46}
            assert skill_data['condition'] in ol_life
            life_requirement = ol_life[skill_data['condition']] if skill_data['skill_type'] == 14 \
                else spk_life[skill_data['condition']] if skill_data['skill_type'] == 44 else 0

        min_requirements, max_requirements = None, None
        if skill_data['skill_trigger_type'] == 2:
            min_requirements = np.array([0, 0, 0])
            max_requirements = np.array([0, 0, 0])
            max_requirements[skill_data['skill_trigger_value'] - 1] = 99
        elif skill_data['skill_trigger_type'] in (3, 5):
            min_requirements = [1, 1, 1]
        elif skill_data['skill_trigger_type'] in (12, 13, 21, 23, 31, 32):
            min_requirements = np.array([0, 0, 0])
            max_requirements = np.array([0, 0, 0])
            for c in str(skill_data['skill_trigger_type']):
                max_requirements[int(c) - 1] = 99

        song_required = None
        if skill_data['skill_trigger_type'] in (4, 5):
            song_required = Color.ALL
        if skill_data['skill_trigger_type'] in (12, 13, 21, 23, 31, 32):
            song_required = Color(skill_data['skill_trigger_type'] % 10)

        is_boost = skill_data['skill_type'] in BOOST_TYPES
        if is_boost:
            if skill_data['skill_type'] in HARMONY_TYPES:
                values = [0, 0, 0, 0, 0]
            else:
                values = cls._fetch_boost_value_from_db(skill_data['value'])
        else:
            values = cls._handle_skill_type(skill_data['skill_type'],
                                            (skill_data['value'], skill_data['value_2'], skill_data['value_3']))
        return cls(
            color=Color(skill_data['attribute'] - 1),
            duration=skill_data['available_time_max'] / 100,
            probability=skill_data['probability_max'],
            interval=skill_data['condition'],
            values=values,
            offset=0,
            boost=is_boost,
            color_target=skill_data['skill_type'] in COLOR_TARGETS,
            act=ACT_TYPES[skill_data['skill_type']] if skill_data['skill_type'] in ACT_TYPES else None,
            bonus_skill=bonus_skill,
            skill_type=skill_data['skill_type'],
            min_requirements=min_requirements,
            max_requirements=max_requirements,
            life_requirement=life_requirement,
            song_required=song_required
        )

    def get_skill_description(self) -> str:
        if self.skill_type in (5, 6, 7, 9, 12, 16, 25, 35, 36, 37, 40, 41, 45, 46, 47, 48, 49, 50):
            return SKILL_DESCRIPTION[self.skill_type]
        elif self.skill_type in (1, 2, 15):
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[0] - 100)
        elif self.skill_type in (4, 31):
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[2] - 100)
        elif self.skill_type == 17:
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[3])
        elif self.skill_type in (21, 22, 23, 27):
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[0] - 100, self.values[2] - 100)
        elif self.skill_type in (21, 22, 23, 27, 28, 29, 30):
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[0] - 100, self.values[1] - 100)
        elif self.skill_type in (24, 43):
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[2] - 100, self.values[3])
        elif self.skill_type == 26:
            return SKILL_DESCRIPTION[self.skill_type].format(self.values[0] - 100, self.values[3], self.values[2] - 100)
        elif self.skill_type == 14:
            return SKILL_DESCRIPTION[self.skill_type].format(self.life_requirement, self.values[0] - 100)
        elif self.skill_type == 39:
            return SKILL_DESCRIPTION[self.skill_type].format(100 - self.values[2], (self.values[0] - 1000) // 10)
        elif self.skill_type == 42:
            return SKILL_DESCRIPTION[self.skill_type].format(100 - self.values[0], (self.values[2] - 1000) // 10)
        elif self.skill_type == 44:
            return SKILL_DESCRIPTION[self.skill_type].format(self.life_requirement,
                                                             self.values[0] - 100, self.values[2] - 100)
        elif self.skill_type in (20, 32, 33, 34, 38):
            return SKILL_DESCRIPTION[self.skill_type].format((self.values[0] - 1000) // 10)

    def __eq__(self, other):
        if other is None or not isinstance(other, Skill):
            return False
        return self.skill_type == other.skill_type and self.duration == other.duration \
            and self.interval == other.interval

    def __str__(self):
        try:
            return "{} {}/{}: {} {} {} {}".format(SKILL_BASE[self.skill_type]["name"], self.duration, self.interval,
                                                  self.v0, self.v1, self.v2, self.v3)
        finally:
            return ""
