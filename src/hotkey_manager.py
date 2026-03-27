from __future__ import annotations

import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QThread, pyqtSignal


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 0xC0DE

user32 = ctypes.WinDLL("user32", use_last_error=True)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


def modifiers_to_win32(modifiers: list[str]) -> int:
    flags = 0
    if "ctrl" in modifiers:
        flags |= MOD_CONTROL
    if "alt" in modifiers:
        flags |= MOD_ALT
    if "shift" in modifiers:
        flags |= MOD_SHIFT
    return flags


def key_to_vk(key: str) -> int:
    if len(key) == 1 and key.isalnum():
        return ord(key.upper())
    if key.startswith("F") and key[1:].isdigit():
        value = int(key[1:])
        if 1 <= value <= 12:
            return 0x6F + value
    return 0


class HotkeyManager(QThread):
    triggered = pyqtSignal()

    def __init__(self, modifiers: int, vk: int) -> None:
        super().__init__()
        self._modifiers = modifiers
        self._vk = vk
        self._thread_id = 0

    def run(self) -> None:
        self._thread_id = int(QThread.currentThreadId())
        message = MSG()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)
        if not user32.RegisterHotKey(None, HOTKEY_ID, self._modifiers | MOD_NOREPEAT, self._vk):
            return

        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == WM_HOTKEY and message.wParam == HOTKEY_ID:
                    self.triggered.emit()
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self.wait(1000)

    @staticmethod
    def is_hotkey_available(modifiers: int, vk: int) -> tuple[bool, str]:
        probe_id = 0xBEEF
        success = user32.RegisterHotKey(None, probe_id, modifiers | MOD_NOREPEAT, vk)
        if success:
            user32.UnregisterHotKey(None, probe_id)
            return (True, "")

        error_code = ctypes.get_last_error()
        if error_code == 1409:
            return (False, "conflict")
        if error_code == 87:
            return (False, "invalid_params")
        return (False, f"unknown:{error_code}")
