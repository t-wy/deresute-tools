from typing import Union, List

from logic.card import Card
from logic.grandlive import GrandLive
from logic.live import Live
from simulator import SimulationResult, AutoSimulationResult


class BaseSimulationResultWithUuid:
    def __init__(self, uuid: str, cards: List[Card], results: Union[SimulationResult, AutoSimulationResult],
                 abuse_load: bool, live: Union[Live, GrandLive] = None):
        self.uuid = uuid
        self.cards = cards
        self.results = results
        self.abuse_load = abuse_load
        self.live = live


class YoinkResults:
    def __init__(self, cards: List[Card], support: int):
        self.cards = cards
        self.support = support
