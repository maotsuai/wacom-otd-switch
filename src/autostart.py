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


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        startupinfo=HIDE_WINDOW,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def enable_autostart() -> bool:
    exe_path = _get_exe_path()
    escaped_exe = exe_path.replace("'", "''")
    script = (
        f"$taskName = '{TASK_NAME}'; "
        f"$exePath = '{escaped_exe}'; "
        "$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
        "$action = New-ScheduledTaskAction -Execute $exePath; "
        "$trigger = New-ScheduledTaskTrigger -AtLogOn; "
        "$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Highest; "
        "$settings = New-ScheduledTaskSettingsSet -Compatibility Win8 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        "$task = New-ScheduledTask -Action $action -Principal $principal -Trigger $trigger -Settings $settings; "
        "Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null"
    )
    result = _run_powershell(script)
    return result.returncode == 0


def disable_autostart() -> bool:
    _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
    return True


def is_autostart_enabled() -> bool:
    result = _run_schtasks(["/Query", "/TN", TASK_NAME])
    return result.returncode == 0
