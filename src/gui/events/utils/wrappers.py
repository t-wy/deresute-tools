from simulator import BaseSimulationResult


class BaseSimulationResultWithUuid:
    def __init__(self, uuid, cards, results: BaseSimulationResult, abuse_load, live = None):
        self.uuid = uuid
        self.cards = cards
        self.results = results
        self.abuse_load = abuse_load
        self.live = live


class YoinkResults:
    def __init__(self, cards, support):
        self.cards = cards
        self.support = support
