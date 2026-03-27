from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QStackedLayout, QWidget

from driver_switcher import DriverProbeWorker, DriverStatus, SwitchWorker
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
        self._probe_worker: DriverProbeWorker | None = None
        self._current_status: DriverStatus | None = None
        self._spinner_frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
        self._spinner_index = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._advance_spinner)

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(320, 50)
        self.setStyleSheet(
            "background: #F8F9FB; border: 1px solid #D8DCE3; border-radius: 12px;"
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.wacom_label = QLabel(t("popup_wacom"))
        self.otd_label = QLabel(t("popup_otd"))
        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedWidth(28)
        self.settings_button.clicked.connect(self._open_settings)

        self.toggle_switch = ToggleSwitch()
        self.toggle_switch.toggled.connect(self._on_toggled)

        self.spinner_label = QLabel(self._spinner_frames[0])
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label.setFixedSize(44, 24)
        self.spinner_label.setToolTip(t("detecting_driver"))

        self.error_label = QLabel("X")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("color: #D32F2F; font-weight: bold;")
        self.error_label.setFixedSize(44, 24)
        self.error_label.setToolTip(t("driver_not_detected"))

        self.switch_container = QWidget()
        self.switch_layout = QHBoxLayout(self.switch_container)
        self.switch_layout.setContentsMargins(0, 0, 0, 0)
        self.switch_layout.setSpacing(6)
        self.switch_layout.addWidget(self.toggle_switch)

        self.warning_label = QLabel("?")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_label.setStyleSheet("color: #A06A00; font-weight: bold;")
        self.warning_label.setFixedSize(18, 24)
        self.warning_label.hide()
        self.switch_layout.addWidget(self.warning_label)

        self.state_widget = QWidget()
        self.state_widget.setFixedWidth(68)
        self.state_stack = QStackedLayout(self.state_widget)
        self.state_stack.setContentsMargins(0, 0, 0, 0)
        self.state_stack.addWidget(self.spinner_label)
        self.state_stack.addWidget(self.switch_container)
        self.state_stack.addWidget(self.error_label)

        layout.addWidget(self.wacom_label)
        layout.addWidget(self.state_widget)
        layout.addWidget(self.otd_label)
        layout.addStretch(1)
        layout.addWidget(self.settings_button)

    def refresh_texts(self) -> None:
        self.wacom_label.setText(t("popup_wacom"))
        self.otd_label.setText(t("popup_otd"))
        self.spinner_label.setToolTip(t("detecting_driver"))
        self.error_label.setToolTip(t("driver_not_detected"))
        self.warning_label.setToolTip(t("both_drivers_detected"))

    def show_popup(self) -> None:
        self.refresh_texts()
        self._start_probe()
        self._reposition()
        self.show()
        self.raise_()
        self.activateWindow()

    def request_toggle(self, target: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._start_switch(target)

    def _start_probe(self) -> None:
        if self._probe_worker is not None and self._probe_worker.isRunning():
            return
        self._current_status = None
        self.state_stack.setCurrentWidget(self.spinner_label)
        self.toggle_switch.setEnabled(False)
        self.warning_label.hide()
        self._spinner_index = 0
        self.spinner_label.setText(self._spinner_frames[0])
        self._spinner_timer.start()
        self._probe_worker = DriverProbeWorker(timeout_seconds=10.0)
        self._probe_worker.finished.connect(self._on_probe_finished)
        self._probe_worker.start()

    def _advance_spinner(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        self.spinner_label.setText(self._spinner_frames[self._spinner_index])

    def _on_probe_finished(self, status: DriverStatus) -> None:
        self._spinner_timer.stop()
        self._probe_worker = None
        self._current_status = status

        if not status.identified or status.active_driver is None:
            self.state_stack.setCurrentWidget(self.error_label)
            return

        self.warning_label.setVisible(status.both_running)
        self.toggle_switch.setChecked(status.active_driver == "otd")
        self.toggle_switch.setEnabled(True)
        self.state_stack.setCurrentWidget(self.switch_container)

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
                if self._current_status and self._current_status.active_driver is not None:
                    self.toggle_switch.setChecked(self._current_status.active_driver == "otd")
                self.settingsRequested.emit()
                return
        else:
            otd_path = config.get("otd_path", "")

        self.toggle_switch.setEnabled(False)
        self.warning_label.hide()
        self._worker = SwitchWorker(target, otd_path)
        self._worker.finished.connect(self._on_switch_finished)
        self._worker.start()

    def _on_switch_finished(self, success: bool, target: str, summary: str, details: str) -> None:
        self._worker = None
        if success:
            self.driverChanged.emit(target)
            self._start_probe()
            return

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle(t("switch_failed_title"))
        message_box.setText(summary or t("switch_failed_title"))
        if details.strip():
            message_box.setDetailedText(details)
        message_box.exec()

        if self._current_status and self._current_status.active_driver is not None:
            self.warning_label.setVisible(self._current_status.both_running)
            self.toggle_switch.setChecked(self._current_status.active_driver == "otd", animate=True)
            self.toggle_switch.setEnabled(True)
            self.state_stack.setCurrentWidget(self.switch_container)
            return

        self.state_stack.setCurrentWidget(self.error_label)
