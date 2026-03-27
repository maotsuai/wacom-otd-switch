from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from driver_switcher import SwitchWorker, detect_current_driver
from lang import t
from toggle_switch import ToggleSwitch


class TogglePopup(QWidget):
    settingsRequested = pyqtSignal()
    driverChanged = pyqtSignal(str)

    def __init__(self, tray_icon, config_provider, parent=None) -> None:
        super().__init__(parent)
        self._tray_icon = tray_icon
        self._config_provider = config_provider
        self._worker: SwitchWorker | None = None
        self._current_driver = "wacom"
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(280, 50)
        self.setStyleSheet(
            "background: #F8F9FB; border: 1px solid #D8DCE3; border-radius: 12px;"
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.wacom_label = QLabel(t("popup_wacom"))
        self.toggle_switch = ToggleSwitch()
        self.otd_label = QLabel(t("popup_otd"))
        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedWidth(28)
        self.settings_button.clicked.connect(self._open_settings)
        self.toggle_switch.toggled.connect(self._on_toggled)

        layout.addWidget(self.wacom_label)
        layout.addWidget(self.toggle_switch)
        layout.addWidget(self.otd_label)
        layout.addStretch(1)
        layout.addWidget(self.settings_button)

    def refresh_texts(self) -> None:
        self.wacom_label.setText(t("popup_wacom"))
        self.otd_label.setText(t("popup_otd"))

    def refresh_state(self) -> None:
        current_driver = detect_current_driver()
        self._current_driver = current_driver if current_driver in {"wacom", "otd"} else "wacom"
        self.toggle_switch.setChecked(self._current_driver == "otd")
        self.toggle_switch.setEnabled(True)

    def show_popup(self) -> None:
        self.refresh_state()
        self.refresh_texts()
        self._reposition()
        self.show()
        self.raise_()
        self.activateWindow()

    def request_toggle(self, target: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_state()
        self._start_switch(target)

    def _reposition(self) -> None:
        tray_geometry = self._tray_icon.geometry()
        if tray_geometry.isValid():
            x = tray_geometry.center().x() - self.width() // 2
            y = tray_geometry.y() - self.height() - 8
            anchor = tray_geometry.center()
        else:
            cursor_pos = QCursor.pos()
            x = cursor_pos.x() - self.width() // 2
            y = cursor_pos.y() - self.height() - 16
            anchor = cursor_pos

        screen = QApplication.screenAt(anchor)
        if screen:
            bounds = screen.availableGeometry()
            x = max(bounds.left(), min(x, bounds.right() - self.width()))
            if y < bounds.top():
                y = anchor.y() + 8
            y = max(bounds.top(), min(y, bounds.bottom() - self.height()))

        self.move(x, y)

    def _open_settings(self) -> None:
        self.hide()
        self.settingsRequested.emit()

    def _on_toggled(self, checked: bool) -> None:
        self._start_switch("otd" if checked else "wacom")

    def _start_switch(self, target: str) -> None:
        config = self._config_provider()
        if target == "otd":
            otd_path = config.get("otd_path", "")
            if not otd_path:
                QMessageBox.information(self, t("otd_missing_title"), t("otd_missing_message"))
                self.toggle_switch.setChecked(self._current_driver == "otd")
                self.settingsRequested.emit()
                return
        else:
            otd_path = config.get("otd_path", "")

        self.toggle_switch.setEnabled(False)
        self._worker = SwitchWorker(target, otd_path)
        self._worker.finished.connect(self._on_switch_finished)
        self._worker.start()

    def _on_switch_finished(self, success: bool, target: str) -> None:
        if success:
            self._current_driver = target
            self.toggle_switch.setChecked(target == "otd", animate=True)
            self.driverChanged.emit(target)
        else:
            self.toggle_switch.setChecked(self._current_driver == "otd", animate=True)
        self.toggle_switch.setEnabled(True)
        self._worker = None
