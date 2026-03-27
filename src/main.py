from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from config import get_resource_path, load_config, save_config
from driver_switcher import detect_current_driver
from hotkey_manager import HotkeyManager, key_to_vk, modifiers_to_win32
from lang import set_language
from settings_dialog import SettingsDialog
from tray import TrayController


ERROR_ALREADY_EXISTS = 183


class AppController(QWidget):
    def __init__(self, app: QApplication, config: dict) -> None:
        super().__init__()
        self._app = app
        self._config = config
        self._hotkey_manager: HotkeyManager | None = None
        self._icon_path = get_resource_path("assets", "icon.ico")

        self._tray = TrayController(
            icon_path=self._icon_path,
            config_provider=self.get_config,
            on_open_settings=self.open_settings,
            on_driver_changed=self._on_driver_changed,
            on_quit=self.quit,
        )
        self._register_hotkey()

    def start(self) -> None:
        self._tray.show()
        self.ensure_valid_config()

    def get_config(self) -> dict:
        return self._config

    def open_settings(self) -> None:
        dialog = SettingsDialog(dict(self._config))
        if self._icon_path.exists():
            dialog.setWindowIcon(QIcon(str(self._icon_path)))
        screen = self._app.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            dialog.move(center - QPoint(dialog.width() // 2, dialog.height() // 2))

        if dialog.exec() and dialog.was_saved():
            self._config = dialog.get_updated_config()
            set_language(self._config.get("language", "zh"))
            save_config(self._config)
            self._tray.refresh_texts()
            self._register_hotkey()

    def ensure_valid_config(self) -> None:
        otd_path = Path(self._config.get("otd_path", ""))
        if not otd_path.is_file() or otd_path.name != "OpenTabletDriver.UX.Wpf.exe":
            self.open_settings()

    def _register_hotkey(self) -> None:
        if self._hotkey_manager is not None:
            self._hotkey_manager.stop()
            self._hotkey_manager = None

        hotkey = self._config.get("hotkey", {})
        key = hotkey.get("key", "")
        modifiers = hotkey.get("modifiers", [])
        if not key or not modifiers:
            return

        vk = key_to_vk(key)
        win_modifiers = modifiers_to_win32(modifiers)
        if not vk or not win_modifiers:
            return

        self._hotkey_manager = HotkeyManager(win_modifiers, vk)
        self._hotkey_manager.triggered.connect(self._handle_hotkey_triggered)
        self._hotkey_manager.start()

    def _handle_hotkey_triggered(self) -> None:
        current_driver = detect_current_driver()
        if current_driver == "none":
            return
        target = "wacom" if current_driver == "otd" else "otd"
        self._tray.popup.request_toggle(target)

    def _on_driver_changed(self, driver: str) -> None:
        del driver

    def quit(self) -> None:
        if self._hotkey_manager is not None:
            self._hotkey_manager.stop()
            self._hotkey_manager = None
        self._tray.popup.hide()
        self._tray.tray_icon.hide()
        self._app.exit(0)
        QTimer.singleShot(500, lambda: os._exit(0))


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin() -> None:
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        " ".join(sys.argv[1:]),
        None,
        1,
    )
    sys.exit()


def create_single_instance_mutex():
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "WacomOTDSwitch_Mutex")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        sys.exit(0)
    return mutex


def main() -> int:
    if sys.platform == "win32" and not is_admin():
        run_as_admin()

    mutex = create_single_instance_mutex()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Wacom-OTD Switch", "System tray is not available.")
        return 1

    config, _ = load_config()
    set_language(config.get("language", "zh"))

    controller = AppController(app, config)
    QTimer.singleShot(0, controller.start)
    exit_code = app.exec()

    if mutex:
        ctypes.windll.kernel32.ReleaseMutex(mutex)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
