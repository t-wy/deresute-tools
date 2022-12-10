import uuid
from pathlib import Path
from typing import Any, Callable, Union

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath
from PyQt5.QtWidgets import QWidget, QTableWidgetItem
from numpy import int32


class ImageWidget(QWidget):
    picture: QPixmap
    padding: int
    border: bool
    border_length: int
    color: str
    card_idx: int

    def __init__(self, path: Union[str, Path] = None, parent: QWidget = None, card_idx: int = None):
        super(ImageWidget, self).__init__(parent)
        self.set_path(path)
        self.set_padding()
        self.border = False
        self.border_length = 0
        self.color = 'black'
        self.card_idx = card_idx

    def set_path(self, path: Union[str, Path, None]):
        if path is None:
            self.picture = QPixmap(0, 0)
        else:
            self.picture = QPixmap(str(path))

    def toggle_border(self, value: bool = False, border_length: int = 0):
        self.border = value
        self.border_length = border_length + 1

    def set_padding(self, padding: int = 5):
        self.padding = padding

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.border:
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, self.border_length, self.border_length), int(self.border_length // 16),
                                int(self.border_length // 16))
            color = QColor(self.color)
            painter.setPen(QPen(color))
            painter.drawPath(path)
            color.setAlpha(40)
            painter.fillPath(path, color)
        painter.drawPixmap(self.padding, self.padding, self.picture)


class NumericalTableWidgetItem(QTableWidgetItem):
    def __init__(self, value: Any):
        if isinstance(value, int) or isinstance(value, float) or isinstance(value, int32):
            self.number = value
        QTableWidgetItem.__init__(self, str(value))

    def __lt__(self, other):
        if not isinstance(other, NumericalTableWidgetItem):
            comparatee = 0
        else:
            comparatee = other.number
        return self.number < comparatee

    def setData(self, role: Qt.ItemDataRole, value: Any, class_type: type = int):
        super().setData(role, value)
        try:
            class_type(value)
        except ValueError:
            return
        self.number = class_type(value)


class ValidatableNumericalTableWidgetItem(NumericalTableWidgetItem):
    def __init__(self, value: Any, validator: Callable[[int], bool], class_type: type):
        super().__init__(value)
        self.validator = validator
        self.class_type = class_type

    def setData(self, role: Qt.ItemDataRole, value: Any, class_type: type = int):
        passed = False
        try:
            self.class_type(value)
            passed = True
        except Exception:
            pass
        if passed and self.validator(self.class_type(value)):
            super().setData(role, value, self.class_type)
        else:
            super().setData(role, self.number, self.class_type)


class UniversalUniqueIdentifiable:
    def __init__(self):
        self.__uuid = uuid.uuid4().hex

    def get_uuid(self) -> str:
        return self.__uuid

    def get_short_uuid(self) -> str:
        return self.__uuid[:6]
