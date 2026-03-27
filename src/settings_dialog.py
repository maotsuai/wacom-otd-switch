from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

import autostart
from hotkey_manager import HotkeyManager, key_to_vk, modifiers_to_win32
from lang import set_language, t
from shortcut_edit import ShortcutEdit


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._saved = False
        self._config = config
        self._build_ui()
        self._load_config()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        self.setModal(True)
        self.resize(560, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        row1 = QHBoxLayout()
        self.otd_label = QLabel()
        self.otd_path_edit = QLineEdit()
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._browse_otd_path)
        row1.addWidget(self.otd_label)
        row1.addWidget(self.otd_path_edit, 1)
        row1.addWidget(self.browse_button)
        layout.addLayout(row1)

        self.otd_error_label = QLabel()
        self.otd_error_label.setStyleSheet("color: #C62828;")
        self.otd_error_label.hide()
        layout.addWidget(self.otd_error_label)

        row2 = QHBoxLayout()
        self.hotkey_label = QLabel()
        self.shortcut_edit = ShortcutEdit()
        self.shortcut_button = QPushButton()
        self.shortcut_button.clicked.connect(self.shortcut_edit.start_capturing)
        row2.addWidget(self.hotkey_label)
        row2.addWidget(self.shortcut_edit, 1)
        row2.addWidget(self.shortcut_button)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.language_label = QLabel()
        self.lang_group = QButtonGroup(self)
        self.zh_radio = QRadioButton("中文")
        self.en_radio = QRadioButton("English")
        self.zh_radio.toggled.connect(self._on_language_changed)
        self.lang_group.addButton(self.zh_radio)
        self.lang_group.addButton(self.en_radio)
        row3.addWidget(self.language_label)
        row3.addWidget(self.zh_radio)
        row3.addWidget(self.en_radio)
        row3.addStretch(1)
        layout.addLayout(row3)

        self.autostart_checkbox = QCheckBox()
        layout.addWidget(self.autostart_checkbox)

        self.hint_label = QLabel()
        self.hint_label.setStyleSheet("color: #5F6368;")
        layout.addWidget(self.hint_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.save_button = QPushButton()
        self.cancel_button = QPushButton()
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.cancel_button)
        layout.addStretch(1)
        layout.addLayout(button_row)

    def _load_config(self) -> None:
        self.otd_path_edit.setText(self._config.get("otd_path", ""))
        hotkey = self._config.get("hotkey", {})
        self.shortcut_edit.set_shortcut(hotkey.get("modifiers", []), hotkey.get("key", ""))
        if self._config.get("language") == "en":
            self.en_radio.setChecked(True)
        else:
            self.zh_radio.setChecked(True)
        self.autostart_checkbox.setChecked(bool(self._config.get("autostart", False)))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(t("settings_title"))
        self.otd_label.setText(t("otd_path_label"))
        self.browse_button.setText(t("browse"))
        self.hotkey_label.setText(t("hotkey_label"))
        self.shortcut_button.setText(t("hotkey_set"))
        self.language_label.setText(t("language_label"))
        self.autostart_checkbox.setText(t("autostart"))
        self.hint_label.setText(t("settings_hint"))
        self.save_button.setText(t("save"))
        self.cancel_button.setText(t("cancel"))
        self.shortcut_edit.stop_capturing()

    def get_updated_config(self) -> dict:
        return self._config

    def was_saved(self) -> bool:
        return self._saved

    def _browse_otd_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("browse"),
            self.otd_path_edit.text(),
            "OpenTabletDriver (OpenTabletDriver.UX.Wpf.exe)",
        )
        if file_path:
            self.otd_path_edit.setText(file_path)
            self._clear_otd_error()

    def _clear_otd_error(self) -> None:
        self.otd_path_edit.setStyleSheet("")
        self.otd_error_label.hide()
        self.otd_error_label.clear()

    def _show_otd_error(self) -> None:
        self.otd_path_edit.setStyleSheet("border: 1px solid #C62828;")
        self.otd_error_label.setText(t("otd_path_invalid"))
        self.otd_error_label.show()

    def _validate_otd_path(self) -> bool:
        path = Path(self.otd_path_edit.text().strip())
        valid = path.is_file() and path.name == "OpenTabletDriver.UX.Wpf.exe"
        if valid:
            self._clear_otd_error()
            return True
        self._show_otd_error()
        return False

    def _on_language_changed(self) -> None:
        set_language("en" if self.en_radio.isChecked() else "zh")
        self.retranslate_ui()

    def _check_hotkey_conflict(self, modifiers: list[str], key: str) -> bool:
        if not key:
            return True

        original_hotkey = self._config.get("hotkey", {})
        if original_hotkey.get("modifiers", []) == modifiers and original_hotkey.get("key", "") == key:
            return True

        available, reason = HotkeyManager.is_hotkey_available(modifiers_to_win32(modifiers), key_to_vk(key))
        if available:
            return True

        if reason == "conflict":
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Icon.Warning)
            message_box.setWindowTitle(t("conflict_title"))
            message_box.setText(t("conflict_message"))
            retry_button = message_box.addButton(t("conflict_retry"), QMessageBox.ButtonRole.RejectRole)
            force_button = message_box.addButton(t("conflict_force"), QMessageBox.ButtonRole.AcceptRole)
            message_box.addButton(t("conflict_cancel"), QMessageBox.ButtonRole.DestructiveRole)
            message_box.exec()
            clicked = message_box.clickedButton()
            if clicked == force_button:
                return True
            if clicked == retry_button:
                self.shortcut_edit.start_capturing()
            else:
                self.shortcut_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return False

        QMessageBox.warning(self, t("conflict_title"), t("hotkey_invalid"))
        self.shortcut_edit.start_capturing()
        return False

    def _save(self) -> None:
        if not self._validate_otd_path():
            return

        modifiers, key = self.shortcut_edit.get_shortcut()
        if key and key_to_vk(key) == 0:
            QMessageBox.warning(self, t("conflict_title"), t("hotkey_invalid"))
            return

        if not self._check_hotkey_conflict(modifiers, key):
            return

        self._config = {
            "otd_path": self.otd_path_edit.text().strip(),
            "hotkey": {
                "modifiers": modifiers,
                "key": key,
            },
            "autostart": self.autostart_checkbox.isChecked(),
            "language": "en" if self.en_radio.isChecked() else "zh",
        }

        if self._config["autostart"]:
            autostart.enable_autostart()
        else:
            autostart.disable_autostart()

        self._saved = True
        self.accept()
