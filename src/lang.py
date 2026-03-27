TEXTS = {
    "zh": {
        "settings_title": "设置",
        "otd_path_label": "OTD 程序位置:",
        "browse": "浏览",
        "hotkey_label": "切换快捷键:",
        "hotkey_set": "设置",
        "hotkey_none": "无",
        "hotkey_prompt": "请按下快捷键...",
        "language_label": "语言 Language:",
        "autostart": "开机自动启动",
        "save": "保存",
        "cancel": "取消",
        "conflict_title": "快捷键冲突",
        "conflict_message": "该快捷键已被其他程序占用，可能无法正常工作。",
        "conflict_retry": "重新选择",
        "conflict_force": "依然使用",
        "conflict_cancel": "取消",
        "hotkey_invalid": "快捷键无效，请重新选择。",
        "otd_path_invalid": "请选择有效的 OpenTabletDriver.UX.Wpf.exe 文件。",
        "tray_settings": "设置",
        "tray_quit": "退出",
        "popup_wacom": "Wacom",
        "popup_otd": "OTD",
        "settings_hint": "保存后立即生效，修改配置后重启也会重新加载。",
        "otd_missing_title": "需要设置 OTD 路径",
        "otd_missing_message": "请先选择有效的 OpenTabletDriver.UX.Wpf.exe。",
        "tray_tooltip": "Wacom-OTD Switch",
        "detecting_driver": "正在识别驱动...",
        "driver_not_detected": "10 秒内未识别到 Wacom 或 OTD 驱动。",
        "both_drivers_detected": "同时识别到了 Wacom 和 OTD，当前按 Wacom 侧展示。",
        "switch_failed_title": "切换失败",
    },
    "en": {
        "settings_title": "Settings",
        "otd_path_label": "OTD Program Path:",
        "browse": "Browse",
        "hotkey_label": "Toggle Hotkey:",
        "hotkey_set": "Set",
        "hotkey_none": "None",
        "hotkey_prompt": "Press shortcut...",
        "language_label": "语言 Language:",
        "autostart": "Start with Windows",
        "save": "Save",
        "cancel": "Cancel",
        "conflict_title": "Hotkey Conflict",
        "conflict_message": "This hotkey is already in use by another program and may not work.",
        "conflict_retry": "Choose Again",
        "conflict_force": "Use Anyway",
        "conflict_cancel": "Cancel",
        "hotkey_invalid": "Invalid hotkey, please choose again.",
        "otd_path_invalid": "Please select a valid OpenTabletDriver.UX.Wpf.exe file.",
        "tray_settings": "Settings",
        "tray_quit": "Quit",
        "popup_wacom": "Wacom",
        "popup_otd": "OTD",
        "settings_hint": "Changes apply immediately and are reloaded on next launch.",
        "otd_missing_title": "OTD Path Required",
        "otd_missing_message": "Please choose a valid OpenTabletDriver.UX.Wpf.exe first.",
        "tray_tooltip": "Wacom-OTD Switch",
        "detecting_driver": "Detecting driver...",
        "driver_not_detected": "Neither Wacom nor OTD was detected within 10 seconds.",
        "both_drivers_detected": "Both Wacom and OTD were detected. The switch is shown on the Wacom side.",
        "switch_failed_title": "Switch Failed",
    },
}

_current_lang = "zh"


def set_language(lang: str) -> None:
    global _current_lang
    _current_lang = lang if lang in TEXTS else "zh"


def get_language() -> str:
    return _current_lang


def t(key: str) -> str:
    return TEXTS.get(_current_lang, TEXTS["zh"]).get(key, key)
