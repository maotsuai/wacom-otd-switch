from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from lang import t
from toggle_popup import TogglePopup


class TrayController:
    def __init__(
        self,
        icon_path: Path,
        config_provider,
        on_open_settings,
        on_driver_changed,
        on_reload_hardware,
        on_quit,
    ) -> None:
        self._config_provider = config_provider
        self._on_open_settings = on_open_settings
        self._on_driver_changed = on_driver_changed
        self._on_reload_hardware = on_reload_hardware
        self._on_quit = on_quit
        self.tray_icon = QSystemTrayIcon(QIcon(str(icon_path)))
        self.popup = TogglePopup(self.tray_icon, config_provider)
        self.popup.settingsRequested.connect(self._on_open_settings)
        self.popup.driverChanged.connect(self._on_driver_changed)

        self._menu = QMenu()
        self._settings_action = QAction()
        self._reload_action = QAction()
        self._quit_action = QAction()
        self._settings_action.triggered.connect(self._on_open_settings)
        self._reload_action.triggered.connect(self._on_reload_hardware)
        self._quit_action.triggered.connect(self._on_quit)
        self._menu.addAction(self._settings_action)
        self._menu.addAction(self._reload_action)
        self._menu.addAction(self._quit_action)

        self.tray_icon.setContextMenu(self._menu)
        self.tray_icon.activated.connect(self._on_activated)
        self.refresh_texts()

    def show(self) -> None:
        self.tray_icon.show()

    def refresh_texts(self) -> None:
        self.tray_icon.setToolTip(t("tray_tooltip"))
        self._settings_action.setText(t("tray_settings"))
        self._reload_action.setText(t("tray_reload_tablet"))
        self._quit_action.setText(t("tray_quit"))
        self.popup.refresh_texts()

    def _on_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.popup.show_popup()
