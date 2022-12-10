class PushCardIndexEvent:
    def __init__(self, idx: int, skip_guest_push: bool, model_id: int):
        self.idx = idx
        self.skip_guest_push = skip_guest_push
        self.model_id = model_id


class ToggleQuickSearchOptionEvent:
    def __init__(self, option: str):
        self.option = option
