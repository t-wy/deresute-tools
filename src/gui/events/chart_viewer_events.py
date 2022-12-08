from logic.card import Card
from simulator import LiveDetail
from statemachine import AbuseData
from static.song_difficulty import Difficulty


class HookUnitToChartViewerEvent:
    def __init__(self, cards: list[Card]):
        self.cards = cards


class HookAbuseToChartViewerEvent:
    def __init__(self, song_id: int, difficulty: Difficulty, cards: list[Card], abuse_df: AbuseData):
        self.song_id = song_id
        self.difficulty = difficulty
        self.cards = cards
        self.abuse_df = abuse_df


class HookSimResultToChartViewerEvent:
    def __init__(self, song_id: int, difficulty: Difficulty, perfect_detail: LiveDetail):
        self.song_id = song_id
        self.difficulty = difficulty
        self.perfect_detail = perfect_detail


class SendMusicEvent:
    def __init__(self, song_id: int, difficulty: Difficulty):
        self.song_id = song_id
        self.difficulty = difficulty


class ToggleMirrorEvent:
    def __init__(self, mirrored: bool):
        self.mirrored = mirrored
