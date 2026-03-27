from __future__ import annotations

import os
import subprocess
import sys


TASK_NAME = "WacomOTDSwitch"

HIDE_WINDOW = subprocess.STARTUPINFO()
HIDE_WINDOW.dwFlags = subprocess.STARTF_USESHOWWINDOW
HIDE_WINDOW.wShowWindow = 0


def _get_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def _run_schtasks(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks", *arguments],
        startupinfo=HIDE_WINDOW,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def enable_autostart() -> bool:
    exe_path = _get_exe_path()
    result = _run_schtasks(
        [
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            f'"{exe_path}"',
            "/SC",
            "ONLOGON",
            "/RL",
            "HIGHEST",
            "/NP",
            "/F",
        ]
    )
    return result.returncode == 0


def disable_autostart() -> bool:
    _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
    return True


def is_autostart_enabled() -> bool:
    result = _run_schtasks(["/Query", "/TN", TASK_NAME])
    return result.returncode == 0
