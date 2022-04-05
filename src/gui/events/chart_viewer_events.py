class HookUnitToChartViewerEvent:
    def __init__(self, cards):
        self.cards = cards


class HookAbuseToChartViewerEvent:
    def __init__(self, cards, abuse_df):
        self.cards = cards
        self.abuse_df = abuse_df


class HookSimResultToChartViewerEvent:
    def __init__(self, perfect_detail):
        self.perfect_detail = perfect_detail


class SendMusicEvent:
    def __init__(self, song_id, difficulty):
        self.song_id = song_id
        self.difficulty = difficulty


class ToggleMirrorEvent:
    def __init__(self, mirrored):
        self.mirrored = mirrored


class PopupChartViewerEvent:
    def __init__(self, look_for_chart=False):
        self.look_for_chart = look_for_chart
