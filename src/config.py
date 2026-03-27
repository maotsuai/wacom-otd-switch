from __future__ import annotations

from pathlib import Path
from typing import Any

import sys
import yaml


DEFAULT_CONFIG = {
    "otd_path": "",
    "hotkey": {
        "modifiers": [],
        "key": "",
    },
    "autostart": False,
    "language": "zh",
}

CONFIG_HEADER = [
    "# Wacom-OTD Switch configuration",
    "# You can edit this file manually. Restart the app after manual changes.",
    "",
]


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent.parent


def get_resource_path(*parts: str) -> Path:
    return get_resource_dir().joinpath(*parts)


def get_config_path() -> Path:
    return get_app_dir() / "config.yaml"


def _merge_dict(defaults: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in defaults.items():
        current_value = current.get(key)
        if isinstance(value, dict) and isinstance(current_value, dict):
            merged[key] = _merge_dict(value, current_value)
        elif current_value is None:
            merged[key] = value
        else:
            merged[key] = current_value
    return merged


def normalize_config(data: dict[str, Any] | None) -> dict[str, Any]:
    merged = _merge_dict(DEFAULT_CONFIG, data or {})
    hotkey = merged["hotkey"]
    merged["hotkey"] = {
        "modifiers": [
            modifier
            for modifier in hotkey.get("modifiers", [])
            if modifier in {"ctrl", "alt", "shift"}
        ],
        "key": str(hotkey.get("key", "")).upper(),
    }
    merged["otd_path"] = str(merged.get("otd_path", ""))
    merged["autostart"] = bool(merged.get("autostart", False))
    merged["language"] = "en" if merged.get("language") == "en" else "zh"
    return merged


def load_config() -> tuple[dict[str, Any], bool]:
    config_path = get_config_path()
    created = False
    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
        created = True

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = normalize_config(data)
    if config != data:
        save_config(config)
    return config, created


def save_config(config: dict[str, Any]) -> None:
    normalized = normalize_config(config)
    yaml_body = yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False)
    get_config_path().write_text("\n".join(CONFIG_HEADER) + yaml_body, encoding="utf-8")
