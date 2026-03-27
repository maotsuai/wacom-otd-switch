from __future__ import annotations

import getpass
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


HIDE_WINDOW = subprocess.STARTUPINFO()
HIDE_WINDOW.dwFlags = subprocess.STARTF_USESHOWWINDOW
HIDE_WINDOW.wShowWindow = 0

WACOM_PRO_SERVICE = "WTabletServicePro"
WACOM_CON_SERVICE = "WTabletServiceCon"
OTD_UI_PROCESS = "OpenTabletDriver.UX.Wpf.exe"
OTD_DAEMON_PROCESS = "OpenTabletDriver.Daemon.exe"

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
    OTD_UI_PROCESS,
    OTD_DAEMON_PROCESS,
]


@dataclass(slots=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    def format(self) -> str:
        lines = [f"$ {' '.join(self.args)}", f"returncode: {self.returncode}"]
        if self.stdout.strip():
            lines.append("stdout:")
            lines.append(self.stdout.strip())
        if self.stderr.strip():
            lines.append("stderr:")
            lines.append(self.stderr.strip())
        return "\n".join(lines)


@dataclass(slots=True)
class DriverStatus:
    wacom_pro_running: bool
    wacom_con_running: bool
    otd_ui_running: bool
    identified: bool
    active_driver: str | None
    both_running: bool


@dataclass(slots=True)
class SwitchResult:
    success: bool
    target: str
    summary: str
    details: str


class DriverProbeWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, timeout_seconds: float = 10.0, poll_interval: float = 0.5) -> None:
        super().__init__()
        self._timeout_seconds = timeout_seconds
        self._poll_interval = poll_interval

    def run(self) -> None:
        deadline = time.monotonic() + self._timeout_seconds
        last_status = probe_driver_status()
        while time.monotonic() < deadline:
            last_status = probe_driver_status()
            if last_status.identified:
                self.finished.emit(last_status)
                return
            time.sleep(self._poll_interval)
        self.finished.emit(last_status)


class SwitchWorker(QThread):
    finished = pyqtSignal(bool, str, str, str)

    def __init__(self, target: str, otd_path: str) -> None:
        super().__init__()
        self._target = target
        self._otd_path = otd_path

    def run(self) -> None:
        if self._target == "otd":
            result = switch_to_otd(self._otd_path)
        else:
            result = switch_to_wacom()
        self.finished.emit(result.success, result.target, result.summary, result.details)


def _run_command(args: list[str], timeout: int = 10) -> CommandResult:
    completed = subprocess.run(
        args,
        startupinfo=HIDE_WINDOW,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def _tasklist_contains(image_name: str) -> bool:
    process_name = image_name[:-4] if image_name.lower().endswith(".exe") else image_name
    command = (
        f"$p = Get-Process -Name '{process_name}' -ErrorAction SilentlyContinue; "
        "if ($p) { exit 0 } else { exit 1 }"
    )
    result = _run_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        timeout=10,
    )
    return result.returncode == 0


def _service_running(service_name: str) -> bool:
    result = _run_command(["sc", "query", service_name])
    return "RUNNING" in result.stdout


def probe_driver_status() -> DriverStatus:
    wacom_pro_running = _service_running(WACOM_PRO_SERVICE)
    wacom_con_running = _service_running(WACOM_CON_SERVICE)
    otd_ui_running = _tasklist_contains(OTD_UI_PROCESS)

    wacom_running = wacom_pro_running or wacom_con_running
    both_running = wacom_running and otd_ui_running
    identified = both_running or wacom_running or otd_ui_running

    if both_running:
        active_driver = "wacom"
    elif otd_ui_running:
        active_driver = "otd"
    elif wacom_running:
        active_driver = "wacom"
    else:
        active_driver = None

    return DriverStatus(
        wacom_pro_running=wacom_pro_running,
        wacom_con_running=wacom_con_running,
        otd_ui_running=otd_ui_running,
        identified=identified,
        active_driver=active_driver,
        both_running=both_running,
    )


def detect_current_driver() -> str:
    status = probe_driver_status()
    return status.active_driver or "none"


def _kill_processes(image_names: list[str]) -> list[CommandResult]:
    results: list[CommandResult] = []
    for image_name in image_names:
        results.append(_run_command(["taskkill", "/F", "/IM", image_name]))
    return results


def _launch_otd_unelevated(otd_exe_path: str) -> CommandResult:
    task_name = "WacomOTDSwitch_OTD_Unelevated"
    username = getpass.getuser()
    task_command = f'"{otd_exe_path}" --minimized'

    create_result = _run_command(
        [
            "schtasks",
            "/Create",
            "/TN",
            task_name,
            "/TR",
            task_command,
            "/SC",
            "ONCE",
            "/ST",
            "00:00",
            "/RL",
            "LIMITED",
            "/F",
            "/IT",
            "/RU",
            username,
        ],
        timeout=15,
    )
    run_result = _run_command(["schtasks", "/Run", "/TN", task_name], timeout=15)
    delete_result = _run_command(["schtasks", "/Delete", "/TN", task_name, "/F"], timeout=15)

    combined_stdout = "\n".join(
        part for part in [create_result.stdout, run_result.stdout, delete_result.stdout] if part.strip()
    )
    combined_stderr = "\n".join(
        part for part in [create_result.stderr, run_result.stderr, delete_result.stderr] if part.strip()
    )
    return CommandResult(
        args=["schtasks", task_name],
        returncode=run_result.returncode if run_result.returncode != 0 else create_result.returncode,
        stdout=combined_stdout,
        stderr=combined_stderr,
    )


def switch_to_otd(otd_exe_path: str) -> SwitchResult:
    path = Path(otd_exe_path)
    if not path.is_file() or path.name != OTD_UI_PROCESS:
        return SwitchResult(False, "otd", "OTD executable path is invalid.", str(path))

    details: list[str] = []
    _kill_processes(WACOM_PROCESSES)
    stop_pro = _run_command(["sc", "stop", WACOM_PRO_SERVICE])
    stop_con = _run_command(["sc", "stop", WACOM_CON_SERVICE])
    details.append(stop_pro.format())
    details.append(stop_con.format())
    time.sleep(2)

    launch_result = _launch_otd_unelevated(str(path))
    details.append(launch_result.format())
    time.sleep(2)

    if _tasklist_contains(OTD_UI_PROCESS):
        return SwitchResult(True, "otd", "", "")

    summary = "OTD failed to start."
    return SwitchResult(False, "otd", summary, "\n\n".join(part for part in details if part.strip()))


def switch_to_wacom() -> SwitchResult:
    details: list[str] = []
    _kill_processes(OTD_PROCESSES)
    time.sleep(1)

    start_pro = _run_command(["sc", "start", WACOM_PRO_SERVICE])
    start_con = _run_command(["sc", "start", WACOM_CON_SERVICE])
    details.append(start_pro.format())
    details.append(start_con.format())
    time.sleep(2)

    wacom_pro_running = _service_running(WACOM_PRO_SERVICE)
    wacom_con_running = _service_running(WACOM_CON_SERVICE)
    if wacom_pro_running or wacom_con_running:
        return SwitchResult(True, "wacom", "", "")

    summary = "Wacom services failed to start."
    return SwitchResult(False, "wacom", summary, "\n\n".join(part for part in details if part.strip()))
