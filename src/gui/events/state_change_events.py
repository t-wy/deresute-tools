class AutoFlagChangeEvent:
    def __init__(self, flag: bool):
        self.flag = flag


class PostYoinkEvent:
    def __init__(self, support: int):
        self.support = support


class PotentialUpdatedEvent:
    def __init__(self, card_list: list[int]):
        self.card_list = card_list


class SetTipTextEvent:
    def __init__(self, text: str):
        self.text = text


class InjectTextEvent:
    def __init__(self, text: str, offset: int = 10):
        self.text = text
        self.offset = offset


class ShutdownTriggeredEvent:
    def __init__(self):
        pass


class BackupFlagsEvent:
    def __init__(self):
        pass


class UnitStorageUpdatedEvent:
    def __init__(self, view_id: int, mode: str, unit_id: int = 0,
                 index: int = None, card_ids: str = None, name: str = None):
        assert mode in ("add", "update", "delete")
        self.view_id = view_id
        self.mode = mode
        self.unit_id = unit_id
        self.index = index
        self.card_ids = card_ids
        self.name = name


class YoinkCustomCardEvent:
    def __init__(self):
        pass


class CustomCardUpdatedEvent:
    def __init__(self, card_id: int, delete: bool = False, image_changed: bool = True):
        self.card_id = card_id
        self.delete = delete
        self.image_changed = image_changed
