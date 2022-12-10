from enum import Enum


class Judgement(Enum):
    PERFECT = 0
    GREAT = 1
    NICE = 2
    BAD = 3
    MISS = 4
    SKIPPED = -1

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __str__(self):
        return self.name
