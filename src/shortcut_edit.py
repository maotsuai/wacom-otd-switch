from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLineEdit

from lang import t


MODIFIER_ORDER = ["ctrl", "alt", "shift"]
QT_MOD_TO_NAME = {
    Qt.KeyboardModifier.ControlModifier: "ctrl",
    Qt.KeyboardModifier.AltModifier: "alt",
    Qt.KeyboardModifier.ShiftModifier: "shift",
}


class ShortcutEdit(QLineEdit):
    shortcutChanged = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._capturing = False
        self._modifiers: list[str] = []
        self._key = ""
        self._refresh_display()

    def start_capturing(self) -> None:
        self._capturing = True
        self.setText(t("hotkey_prompt"))
        self.setStyleSheet("background: #FFFDE7;")
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def stop_capturing(self) -> None:
        self._capturing = False
        self.setStyleSheet("")
        self._refresh_display()

    def set_shortcut(self, modifiers: list[str], key: str) -> None:
        self._modifiers = [modifier for modifier in MODIFIER_ORDER if modifier in modifiers]
        self._key = key.upper()
        self._refresh_display()

    def clear_shortcut(self) -> None:
        self._modifiers = []
        self._key = ""
        self._refresh_display()

    def get_shortcut(self) -> tuple[list[str], str]:
        return list(self._modifiers), self._key

    def _refresh_display(self) -> None:
        if not self._key:
            self.setText(t("hotkey_none"))
            return
        self.setText(format_shortcut(self._modifiers, self._key))

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.clear_shortcut()
            self.stop_capturing()
            self.shortcutChanged.emit()
            return

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        modifier_names = [
            name
            for qt_modifier, name in QT_MOD_TO_NAME.items()
            if modifiers & qt_modifier
        ]
        if not modifier_names:
            return

        key_name = key_to_name(key)
        if not key_name:
            return

        self._modifiers = [modifier for modifier in MODIFIER_ORDER if modifier in modifier_names]
        self._key = key_name
        self.stop_capturing()
        self.shortcutChanged.emit()


def key_to_name(key: int) -> str:
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key)
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)

    function_keys = {
        Qt.Key.Key_F1: "F1",
        Qt.Key.Key_F2: "F2",
        Qt.Key.Key_F3: "F3",
        Qt.Key.Key_F4: "F4",
        Qt.Key.Key_F5: "F5",
        Qt.Key.Key_F6: "F6",
        Qt.Key.Key_F7: "F7",
        Qt.Key.Key_F8: "F8",
        Qt.Key.Key_F9: "F9",
        Qt.Key.Key_F10: "F10",
        Qt.Key.Key_F11: "F11",
        Qt.Key.Key_F12: "F12",
    }
    return function_keys.get(key, "")


def format_shortcut(modifiers: list[str], key: str) -> str:
    if not key:
        return t("hotkey_none")

    names = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
    }
    parts = [names[modifier] for modifier in MODIFIER_ORDER if modifier in modifiers]
    parts.append(key)
    return "+".join(parts)
