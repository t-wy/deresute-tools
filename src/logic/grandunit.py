from __future__ import annotations

from typing import Union

import pyximport

from logic.card import Card
from logic.unit import Unit, BaseUnit

pyximport.install(language_level=3)


class GrandUnit(BaseUnit):
    ua: Unit
    ub: Unit
    uc: Unit

    def __init__(self, ua: Unit, ub: Unit, uc: Unit):
        self.ua = ua
        self.ub = ub
        self.uc = uc
        self._units = [self.ua, self.ub, self.uc]
        for idx, unit in enumerate(self._units):
            unit.set_offset(idx)

    @classmethod
    def from_list(cls, card_list: list[Union[str, int, Card]], custom_pots: list[int] = None) -> GrandUnit:
        return cls(
            Unit.from_list(card_list[0:5], custom_pots),
            Unit.from_list(card_list[5:10], custom_pots),
            Unit.from_list(card_list[10:15], custom_pots))

    def get_unit(self, idx: int) -> Unit:
        return self._units[idx]

    @property
    def all_units(self) -> list[Unit]:
        return self._units

    def all_cards(self) -> list[Card]:
        result = []
        for unit in self._units:
            result.extend(unit.all_cards())
        return result

    def get_card(self, idx: int) -> Card:
        return self.all_cards()[idx]

    def __str__(self):
        return " ".join(map(str, self._units))
