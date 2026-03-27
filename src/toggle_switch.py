from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checked = False
        self._handle_position = 0.0
        self._animation = QPropertyAnimation(self, b"handlePosition", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = False) -> None:
        self._checked = bool(checked)
        target_position = 1.0 if self._checked else 0.0
        if animate:
            self._animate_to(target_position)
        else:
            self._handle_position = target_position
            self.update()

    def toggleByUser(self, checked: bool) -> None:
        self._checked = checked
        self._animate_to(1.0 if checked else 0.0)
        self.toggled.emit(checked)

    def _animate_to(self, value: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(value)
        self._animation.start()

    def get_handle_position(self) -> float:
        return self._handle_position

    def set_handle_position(self, value: float) -> None:
        self._handle_position = float(value)
        self.update()

    handlePosition = pyqtProperty(float, get_handle_position, set_handle_position)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.toggleByUser(not self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.5)

        rect = QRectF(0, 0, self.width(), self.height())
        track_color = QColor("#2A8CFF") if self._checked else QColor("#C9CDD3")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        thumb_size = 20
        margin = 2
        available = self.width() - thumb_size - margin * 2
        thumb_x = margin + available * self._handle_position
        thumb_rect = QRectF(thumb_x, margin, thumb_size, thumb_size)
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#B5B5B5"), 1))
        painter.drawEllipse(thumb_rect)
