from __future__ import annotations

import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


HIDE_WINDOW = subprocess.STARTUPINFO()
HIDE_WINDOW.dwFlags = subprocess.STARTF_USESHOWWINDOW
HIDE_WINDOW.wShowWindow = 0

DETACHED_FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

WACOM_PROCESSES = [
    "WacomCenterUI.exe",
    "WacomDesktopCenter.exe",
    "Wacom_UpdateUtil.exe",
    "WacomHost.exe",
    "Wacom_TabletUser.exe",
    "Wacom_TouchUser.exe",
    "Wacom_Tablet.exe",
]

OTD_PROCESSES = [
    "OpenTabletDriver.UX.Wpf.exe",
    "OpenTabletDriver.Daemon.exe",
]


def _run_command(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        startupinfo=HIDE_WINDOW,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _tasklist_contains(image_name: str) -> bool:
    result = _run_command(["tasklist", "/FI", f"IMAGENAME eq {image_name}"])
    return image_name.lower() in result.stdout.lower()


def _service_running(service_name: str) -> bool:
    result = _run_command(["sc", "query", service_name])
    return "RUNNING" in result.stdout


def detect_current_driver() -> str:
    wacom_running = _service_running("WTabletServicePro")
    otd_running = _tasklist_contains("OpenTabletDriver.Daemon.exe")

    if wacom_running and not otd_running:
        return "wacom"
    if not wacom_running and otd_running:
        return "otd"
    if not wacom_running and not otd_running:
        return "none"
    return "wacom"


def _kill_processes(image_names: list[str]) -> None:
    for image_name in image_names:
        _run_command(["taskkill", "/F", "/IM", image_name])


def switch_to_otd(otd_exe_path: str) -> bool:
    path = Path(otd_exe_path)
    if not path.is_file() or path.name != "OpenTabletDriver.UX.Wpf.exe":
        return False

    _kill_processes(WACOM_PROCESSES)
    _run_command(["sc", "stop", "WTabletServicePro"])
    _run_command(["sc", "stop", "WTabletServiceCon"])
    time.sleep(2)

    try:
        subprocess.Popen(
            [str(path), "--minimized"],
            startupinfo=HIDE_WINDOW,
            creationflags=DETACHED_FLAGS,
        )
    except OSError:
        return False

    time.sleep(2)
    return _tasklist_contains("OpenTabletDriver.Daemon.exe")


def switch_to_wacom() -> bool:
    _kill_processes(OTD_PROCESSES)
    time.sleep(1)
    _run_command(["sc", "start", "WTabletServicePro"])
    _run_command(["sc", "start", "WTabletServiceCon"])
    time.sleep(2)
    return _service_running("WTabletServicePro")


class SwitchWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, target: str, otd_path: str) -> None:
        super().__init__()
        self._target = target
        self._otd_path = otd_path

    def run(self) -> None:
        if self._target == "otd":
            success = switch_to_otd(self._otd_path)
        else:
            success = switch_to_wacom()
        self.finished.emit(success, self._target)
