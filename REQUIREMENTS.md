# Wacom-OTD Switch — 需求规格文档

> **目标**：一个 Windows 系统托盘程序，帮助用户在 Wacom 官方驱动和 OpenTabletDriver (OTD) 之间一键切换。打包为单个 exe，支持开机自启、全局快捷键、GitHub Actions 自动构建发布。

---

## 一、项目结构

```
wacom-otd-switch/
├── src/
│   ├── main.py                 # 程序入口
│   ├── tray.py                 # 系统托盘图标管理
│   ├── toggle_popup.py         # 托盘上方弹出的小面板
│   ├── toggle_switch.py        # 自绘拨动开关控件
│   ├── settings_dialog.py      # 设置窗口
│   ├── shortcut_edit.py        # 快捷键捕获控件
│   ├── hotkey_manager.py       # 全局快捷键注册与监听
│   ├── driver_switcher.py      # 驱动切换核心逻辑
│   ├── config.py               # YAML 配置文件读写
│   ├── autostart.py            # 开机自启管理
│   └── lang.py                 # 中英文文本定义
├── assets/
│   └── icon.ico                # 系统托盘图标（需制作）
├── requirements.txt
├── wacom_otd_switch.spec       # PyInstaller 打包配置
└── .github/
    └── workflows/
        └── release.yml         # CI/CD 自动构建发布
```

运行时在 exe 同级目录生成：

```
config.yaml                     # 用户配置文件（明文 YAML）
```

---

## 二、技术栈

| 组件         | 选型                   | 版本   | 用途                           |
| ------------ | ---------------------- | ------ | ------------------------------ |
| GUI 框架     | PyQt6                  | ≥6.5   | 托盘图标、窗口、自绘控件       |
| 配置文件     | PyYAML                 | ≥6.0   | config.yaml 读写               |
| 全局快捷键   | ctypes (stdlib)        | —      | Win32 RegisterHotKey API       |
| 开机自启     | subprocess + schtasks  | —      | 任务计划程序，管理员无感自启   |
| 进程/服务    | subprocess (stdlib)    | —      | taskkill / sc / Popen          |
| 打包         | PyInstaller            | ≥6.0   | --onefile --noconsole          |
| CI/CD        | GitHub Actions         | —      | tag 推送自动构建 Release       |

**不使用**：pystray、keyboard、pynput、pywin32 —— 全部用 stdlib + PyQt6 覆盖。

---

## 三、配置文件 `config.yaml`

### 格式

```yaml
# Wacom-OTD Switch 配置文件
# 可手动编辑此文件，保存后重启程序生效

otd_path: "D:\\OpenTabletDriver\\OpenTabletDriver.UX.Wpf.exe"

hotkey:
  modifiers: []     # 可选值: "ctrl", "alt", "shift"。示例: ["ctrl", "shift"]
  key: ""           # 可选值: A-Z, 0-9, F1-F12。示例: "W"

autostart: false

language: "zh"      # "zh" = 中文, "en" = English
```

### 规则

1. 程序启动时读取 exe 同级目录的 `config.yaml`（路径基于当前 exe 所在目录解析，不使用当前工作目录）
2. 文件不存在 → 创建默认配置（`otd_path` 为空，`hotkey` 为空，`autostart` 为 false，`language` 为 "zh"）→ 自动弹出设置窗口
3. `otd_path` 为空或路径无效 → 自动弹出设置窗口
4. 所有配置项在设置窗口保存时写入文件
5. 用户可以直接用文本编辑器修改此文件，重启程序后生效

---

## 四、程序入口 `main.py`

### 权限架构（重要）

**程序始终以管理员权限运行。** 通过 Task Scheduler 实现无感自启（无 UAC 弹框）。

这样设计的原因：
- 操作 Windows 服务（`sc stop/start`）和强制杀进程（`taskkill /F`）需要管理员权限。
- 如果用 HKCU Run + 普通权限 + 按需提权，每次切换驱动都会弹 UAC，体验差。
- Task Scheduler 的"以最高权限运行"任务是由管理员预先授权创建的，Windows
  视为已审批，登录时自启不弹 UAC。
- 程序本身通过 PyInstaller manifest 嵌入 `requireAdministrator`，
  手动双击时弹一次 UAC（仅首次/手动启动），之后由 Task Scheduler 自启则无感。

### 启动流程

```
程序启动
  │
  ├─ 1. 检查管理员权限
  │     ├─ 是管理员 → 继续
  │     └─ 不是管理员 → ShellExecuteW("runas") 提权重启自身，当前进程退出
  │
  ├─ 2. 单实例检测（防止重复启动）
  │
  ├─ 3. 创建 QApplication
  │
  ├─ 4. 读取 config.yaml
  │     ├─ 文件不存在 → 创建默认配置
  │     └─ 读取成功
  │
  ├─ 5. 创建系统托盘图标
  │
  ├─ 6. 检测当前驱动状态（见第八节），设置 toggle 初始位置
  │
  ├─ 7. 注册全局快捷键（如果配置了的话）
  │
  ├─ 8. 如果 otd_path 为空或无效 → 弹出设置窗口
  │
  └─ 9. 进入 Qt 事件循环
```

### 管理员提权（手动启动时的防御性检查）

```python
import ctypes
import sys

def is_admin() -> bool:
    """检查当前进程是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def run_as_admin():
    """以管理员身份重新启动自身"""
    ctypes.windll.shell32.ShellExecuteW(
        None,           # 父窗口
        "runas",        # 操作（请求 UAC 提权）
        sys.executable, # 程序路径（PyInstaller 打包后就是 exe 自身）
        " ".join(sys.argv[1:]),  # 参数
        None,           # 工作目录
        1               # SW_SHOWNORMAL
    )
    sys.exit()

# main.py 入口处：
if not is_admin():
    run_as_admin()  # 弹 UAC → 提权重启 → 退出当前非管理员实例
```

> **何时会触发这个 UAC**：仅当用户手动双击 exe 时。通过 Task Scheduler 自启时，
> 任务已配置为"以最高权限运行"，Windows 直接给予管理员权限，不弹 UAC。

### 单实例检测

使用 Windows 命名互斥量防止重复启动：

```python
import ctypes

mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "WacomOTDSwitch_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    # 已经有一个实例在运行，退出
    sys.exit(0)
```

---

## 五、系统托盘 `tray.py`

### 行为

| 操作       | 响应                                       |
| ---------- | ------------------------------------------ |
| 左键单击   | 在托盘图标正上方弹出 toggle 面板           |
| 左键双击   | 同单击（不做区分）                         |
| 右键单击   | 弹出右键菜单：`设置` / `重新载入数位板硬件` / `退出` |

### QSystemTrayIcon 信号处理

```python
tray_icon.activated.connect(on_tray_activated)

def on_tray_activated(reason):
    if reason == QSystemTrayIcon.ActivationReason.Trigger:       # 左键单击
        show_toggle_popup()
    elif reason == QSystemTrayIcon.ActivationReason.DoubleClick: # 双击
        show_toggle_popup()
    # 右键菜单由 setContextMenu() 自动处理
```

### 右键菜单

```
┌──────────────────────┐
│  设置                 │  → 打开设置窗口
│  重新载入数位板硬件   │  → 尝试恢复数位板响应
│  退出                 │  → 注销快捷键 → 退出程序
└──────────────────────┘
```

---

## 六、弹出面板 `toggle_popup.py`

### 外观

```
         ┌────────────────────────────────────┐
         │   Wacom  ◉══════════○  OTD   [⚙]  │
         └────────────────────────────────────┘
                         ▲
                    （托盘图标）
```

### 规格

- 窗口类型：`QWidget`，设置 `Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint`
  - `Popup` 标志意味着：点击面板外部任意位置，面板自动关闭
- 尺寸：固定大小，约 280×50 像素（根据实际渲染效果微调）
- 定位：出现在托盘图标正上方，采用多级 fallback 策略：

  **定位算法**（按优先级依次尝试）：

  ```
  1. 首选：QSystemTrayIcon.geometry()
     - 调用 geometry()，检查返回的 QRect 是否有效（width>0 且 height>0）
     - 有效 → 面板 x = 图标中心 x - 面板宽度/2
              面板 y = 图标 y - 面板高度 - 8px 间距

  2. Fallback：QCursor.pos()（鼠标光标位置）
     - 当 geometry() 返回无效矩形时使用（托盘溢出区、某些 Windows 版本）
     - 面板 x = 光标 x - 面板宽度/2
     - 面板 y = 光标 y - 面板高度 - 16px 间距

  3. 最终：屏幕边界修正
     - 无论使用哪种定位方式，最后都检查面板是否超出所在屏幕边界
     - 通过 QApplication.screenAt(pos) 获取面板所在的屏幕（支持多屏）
     - 使用该屏幕的 availableGeometry()（排除任务栏区域）进行修正
     - 左/右越界 → 平移回屏幕内
     - 上方越界 → 改为显示在图标/光标下方
  ```

  > **为什么不只用 `QCursor.pos()`**：左键单击托盘图标时，光标一定在图标附近，
  > 但用户可能在点击后移动鼠标，导致面板位置偏移。`geometry()` 提供的是图标
  > 的固定坐标，更稳定。所以 `geometry()` 优先，光标位置作为保底。
- 背景：白色/浅灰，圆角，带 1px 边框阴影
- 布局：水平 `QHBoxLayout`
  - "Wacom" 文字标签
  - ToggleSwitch 控件
  - "OTD" 文字标签
  - 齿轮按钮 `⚙`（Unicode 字符或小图标）

### 交互

1. 面板显示后先进入驱动识别阶段：
   - 在未识别到 Wacom / OTD 前，不显示拨动按钮，显示 loading 循环转圈
   - 后端在子线程中探测驱动状态，探测超时时间为 10 秒
2. 驱动识别结果反馈到 UI 后再显示最终状态：
   - 仅识别到 Wacom → 显示拨动按钮，朝向 Wacom
   - 仅识别到 OTD → 显示拨动按钮，朝向 OTD
   - 10 秒内两者都未识别到 → 用红色 `X` 替换 loading，hover 显示“未识别到两者驱动”提示
   - 同时识别到两者 → 显示拨动按钮朝向 Wacom，并在旁边显示 `?`，hover 提示“两者同时运行”
3. 用户拨动 ToggleSwitch → 触发切换操作（见第八节）
4. 切换过程中 ToggleSwitch **禁用**（防止重复点击），切换完成后重新启用
5. 切换失败时弹出错误窗口，显示失败原因，并提供可复制的详细输出
6. 齿轮按钮 → 关闭弹出面板 → 打开设置窗口（屏幕居中）

---

## 七、拨动开关 `toggle_switch.py`

### 外观

一个 iOS 风格的滑动开关：

```
OFF 状态（Wacom）:   ●━━━━━━━━○
ON 状态（OTD）:      ○━━━━━━━━●
```

### 规格

- 继承自 `QWidget`
- 固定尺寸：**44×24** 像素
- 轨道（track）：圆角矩形，OFF=灰色 `#CCCCCC`，ON=蓝色 `#0078D4`
- 圆形把手（thumb）：白色圆形，直径 20px，带 1px 灰色边框
- 动画：把手滑动使用 `QPropertyAnimation`，时长 200ms，缓动曲线 `InOutCubic`
- 鼠标样式：`PointingHandCursor`（手指）

### API

```python
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)      # 状态改变信号，True=OTD，False=Wacom

    def isChecked(self) -> bool: ...
    def setChecked(self, checked: bool): ...  # 程序设置状态（不触发信号）
    def setEnabled(self, enabled: bool): ...  # 切换过程中禁用
```

### paintEvent 绘制要点

1. 用 `QPainter` 绘制圆角矩形轨道
2. 根据内部 `_handle_position`（0.0~1.0）计算把手 x 坐标
3. 绘制白色圆形把手
4. 禁用时整体半透明（`setOpacity(0.5)`）

### 点击行为

在 `mouseReleaseEvent` 中切换状态，启动动画，发射 `toggled` 信号。

---

## 八、驱动切换 `driver_switcher.py`

### 当前状态检测

程序启动时、每次弹出面板时，检测当前状态：

```python
def probe_driver_status() -> DriverStatus:
    """
    返回：
      - wacom_pro_running
      - wacom_con_running
      - otd_ui_running
      - identified
      - active_driver
      - both_running

    判断逻辑：
    1. Wacom 只判断两个服务：WTabletServicePro / WTabletServiceCon
    2. OTD 只判断 OpenTabletDriver.UX.Wpf.exe 是否存在
       不再优先判断 OpenTabletDriver.Daemon.exe

    - 仅 Wacom 运行 → active_driver = "wacom"
    - 仅 OTD 运行   → active_driver = "otd"
    - 都没运行     → active_driver = None
    - 都在运行     → active_driver = "wacom"，both_running = True
    """
```

> **与 ToggleSwitch 的映射**：`active_driver == "otd"` → `setChecked(True)`；
> `active_driver == "wacom"` → `setChecked(False)`；
> 未识别到任何驱动时不显示拨动按钮，而是显示 loading / 红色 `X` 状态。

### 切换到 OTD

**入参**：`otd_exe_path`（从 config.yaml 读取）

**步骤**（按顺序执行）：

```
步骤 1：杀掉所有 Wacom 进程
  用 subprocess.run() 执行以下命令，每个都加 /F（强制）且忽略错误：
    taskkill /F /IM WacomCenterUI.exe
    taskkill /F /IM WacomDesktopCenter.exe
    taskkill /F /IM Wacom_UpdateUtil.exe
    taskkill /F /IM WacomHost.exe
    taskkill /F /IM Wacom_TabletUser.exe
    taskkill /F /IM Wacom_TouchUser.exe
    taskkill /F /IM Wacom_Tablet.exe

步骤 2：停止 Wacom Windows 服务
  subprocess.run(["sc", "stop", "WTabletServicePro"], ...)  # 忽略错误（服务可能不存在）
  subprocess.run(["sc", "stop", "WTabletServiceCon"], ...)  # 忽略错误

步骤 3：等待 2 秒
  让服务完全停止、USB 设备释放

步骤 4：以**非特权权限**启动 OpenTabletDriver
  - 启动参数必须包含 `--minimized`
  - 目标是让 OTD 以普通用户权限、最小化方式运行，避免弹出
    “不应以特权身份运行”的窗口

步骤 5：等待 2 秒后验证
  检查 OpenTabletDriver.UX.Wpf.exe 进程是否存在
  存在 → 切换成功
  不存在 → 切换失败（在 toggle 上恢复原状态，并弹出错误窗口）
```

### 切换到 Wacom

**步骤**（按顺序执行）：

```
步骤 1：杀掉 OTD 进程
  taskkill /F /IM OpenTabletDriver.UX.Wpf.exe   # 忽略错误
  taskkill /F /IM OpenTabletDriver.Daemon.exe    # 忽略错误

步骤 2：等待 1 秒

步骤 3：启动 Wacom 服务
  subprocess.run(["sc", "start", "WTabletServicePro"], ...)  # 忽略错误
  subprocess.run(["sc", "start", "WTabletServiceCon"], ...)  # 忽略错误
  # 服务启动后会自动拉起所有 Wacom 用户态进程（WacomHost 等），无需手动启动

步骤 4：等待 2 秒后验证
  检查 WTabletServicePro / WTabletServiceCon 是否至少有一个为 RUNNING
  是 → 切换成功
  否 → 切换失败
```

> 程序已以管理员权限运行（见第四节），所有 `sc` 和 `taskkill` 命令直接通过
> `subprocess.run()` 执行，无需额外提权，不弹 UAC。

### 异步执行

切换操作耗时数秒，**必须在子线程中执行**，不能阻塞 UI。
切换结果除了成功/失败外，还要返回：
- 失败摘要（summary）
- 详细输出（details）

失败时 UI 必须弹出错误窗口，告知：
- 哪一项启动失败
- 是否有 stdout / stderr 输出
- 详细内容可复制

```python
class SwitchWorker(QThread):
    finished = pyqtSignal(bool, str, str, str)
    # (成功, 目标驱动, summary, details)

    def __init__(self, target: str, otd_path: str):
        ...

### 手动重新载入数位板硬件

右键托盘菜单提供“重新载入数位板硬件”入口，用于**尝试**恢复偶发性的数位板无响应。

执行顺序：

```
1. 记录当前驱动状态
   - 若仅 Wacom 运行 → 最后恢复 Wacom
   - 若仅 OTD 运行   → 最后恢复 OTD
   - 若两者都没运行 / 两者都运行 → 最后默认恢复 Wacom

2. 记录 Windows Ink（TabletInputService）是否原本处于运行状态

3. 关闭所有驱动
   - 停止 Wacom 服务
   - 结束 OTD 进程

4. 如果 Windows Ink 原本在运行，则先停止 Windows Ink 服务

5. 尝试对识别到的 Wacom 设备执行：
   pnputil /restart-device <InstanceId>

6. 不管 restart-device 成功与否，都继续恢复前面记录的目标驱动

7. 如果 Windows Ink 原本在运行，则最后重新启动该服务
```

限制说明：
- 这是**实验性**恢复功能，不保证稳定成功
- `pnputil /restart-device` 在不同机器上的行为不完全一致
- `devcon` 并非所有机器都自带，也不存在可依赖的通用分发版本
- `USBDeview` 已验证对该问题无明显帮助
- 若恢复失败，最终仍需用户手动重新插拔数位板或重启系统

    def run(self):
        # 执行切换步骤
        # 完成后 emit finished
```

`toggle_popup.py` 连接 `finished` 信号：
- 成功 → toggle 动画移到正确位置
- 失败 → toggle 弹回原位，不需额外提示（静默恢复即可）

### subprocess 调用规范

所有 subprocess 调用都需要隐藏命令行窗口：

```python
HIDE_WINDOW = subprocess.STARTUPINFO()
HIDE_WINDOW.dwFlags = subprocess.STARTF_USESHOWWINDOW
HIDE_WINDOW.wShowWindow = 0  # SW_HIDE

subprocess.run(
    ["taskkill", "/F", "/IM", "WacomHost.exe"],
    startupinfo=HIDE_WINDOW,
    capture_output=True,
    timeout=10,
    check=False  # 不抛异常，进程不存在时 taskkill 会返回非零
)
```

---

## 九、设置窗口 `settings_dialog.py`

### 外观

```
┌──────────────────────────────────────────────────────┐
│                       设置                           │
├──────────────────────────────────────────────────────┤
│                                                      │
│  OTD 程序位置:   [D:\OTD\OpenTabletDriver.U...]  [浏览]│
│                                                      │
│  切换快捷键:     [          无          ]  [设置]     │
│                                                      │
│  语言 Language:  ○ 中文  ● English                   │
│                                                      │
│  ☑ 开机自动启动                                      │
│                                                      │
│                          [保存]  [取消]               │
└──────────────────────────────────────────────────────┘
```

### 各行详细规格

#### 第一行：OTD 程序位置

- 左侧标签：`"OTD 程序位置:"`
- 中间文本框：`QLineEdit`，显示当前路径，可手动输入也可用 Browse 选择
- 右侧按钮：`"浏览"`，点击弹出 `QFileDialog.getOpenFileName`
  - 过滤器：`"OpenTabletDriver (OpenTabletDriver.UX.Wpf.exe)"`
  - 用户选择后将路径写入文本框
- 保存时验证：
  - 路径不为空
  - 文件存在
  - 文件名为 `OpenTabletDriver.UX.Wpf.exe`
  - 验证失败 → 文本框边框变红，下方显示红色提示文字

#### 第二行：切换快捷键

- 左侧标签：`"切换快捷键:"`
- 中间显示区：`ShortcutEdit` 控件（见下方详述），显示当前快捷键或 `"无"`
- 右侧按钮：`"设置"`，点击让 ShortcutEdit 进入捕获模式
- 默认值：空（不设置快捷键）
- 清除快捷键：在捕获模式中按 `Esc` → 清空快捷键，恢复为 `"无"`

#### 第三行：语言

- 左侧标签：`"语言 Language:"`（此标签始终中英双语显示，不随语言切换变化）
- 右侧：两个 `QRadioButton` 组成 `QButtonGroup`
  - `○ 中文`
  - `○ English`
- 切换后界面文字立即更新（调用 `lang.py` 的 `set_language()` 并刷新所有控件文本）

#### 第四行：开机自动启动

- `QCheckBox`：`"开机自动启动"`
- 勾选 → 保存时调用 `autostart.enable_autostart()`
- 取消 → 保存时调用 `autostart.disable_autostart()`

#### 底部按钮

- `"保存"` 按钮：
  1. 验证 OTD 路径
  2. 如果快捷键有变化 → 调用冲突检测（见下方）
  3. 所有验证通过 → 写入 config.yaml → 重新注册快捷键 → 关闭窗口
- `"取消"` 按钮：丢弃所有修改，关闭窗口

### 快捷键冲突处理流程

```
用户按下保存
  │
  ├─ 快捷键为空 → 跳过检测，注销已有快捷键
  │
  ├─ 快捷键未变化 → 跳过检测
  │
  └─ 快捷键有变化：
       │
       ├─ 调用 hotkey_manager.is_hotkey_available(modifiers, vk)
       │     返回 (bool, reason) 元组：
       │       (True,  "")               → 可用
       │       (False, "conflict")       → 被占用（错误码 1409）
       │       (False, "invalid_params") → 参数无效
       │       (False, "unknown:...")     → 其他错误
       │
       ├─ 可用 → 保存，正式注册
       │
       ├─ "conflict" → 弹出 QMessageBox：
       │     "该快捷键已被其他程序占用，可能无法正常工作。"
       │     三个按钮：
       │       [重新选择]  → 关闭对话框，焦点回到 ShortcutEdit
       │       [依然使用]  → 保存配置（快捷键可能不生效，用户知情）
       │       [取消]      → 关闭对话框，不保存
       │
       └─ "invalid_params" 或 "unknown:..." → 弹出 QMessageBox：
             "快捷键无效，请重新选择。"
             单按钮 [确定]，焦点回到 ShortcutEdit
```

---

## 十、快捷键捕获控件 `shortcut_edit.py`

### 外观与行为

- 继承 `QLineEdit`，只读模式
- 正常状态：显示当前快捷键文本，如 `"Ctrl+Shift+W"` 或 `"无"`
- 捕获模式（由旁边"设置"按钮触发）：
  - 文本变为 `"请按下快捷键..."` / `"Press shortcut..."`
  - 背景色变为浅黄色 `#FFFDE7`
  - 等待用户按下按键组合

### 按键处理逻辑

重写 `keyPressEvent`：

```python
def keyPressEvent(self, event):
    if not self._capturing:
        return

    key = event.key()
    modifiers = event.modifiers()

    # 按 Esc → 取消/清空
    if key == Qt.Key.Key_Escape:
        self._clear_shortcut()
        self._stop_capturing()
        return

    # 忽略单独的修饰键按下（Ctrl、Shift、Alt 本身）
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return

    # 至少需要一个修饰键 + 一个普通键
    if not modifiers & (Qt.KeyboardModifier.ControlModifier |
                        Qt.KeyboardModifier.AltModifier |
                        Qt.KeyboardModifier.ShiftModifier):
        # 没有修饰键，忽略此次按键
        return

    # 记录组合键
    self._modifiers = modifiers
    self._key = key
    self._update_display()   # 显示如 "Ctrl+Shift+W"
    self._stop_capturing()
    self.shortcutChanged.emit()
```

### 显示格式

组合键文本格式：`Ctrl+Alt+Shift+<Key>`，按此固定顺序排列。

示例：`Ctrl+W`、`Ctrl+Shift+F1`、`Alt+Shift+D`

### 修饰键到 Win32 MOD 的映射

```python
QT_MOD_TO_WIN32 = {
    Qt.KeyboardModifier.ControlModifier: 0x0002,  # MOD_CONTROL
    Qt.KeyboardModifier.AltModifier:     0x0001,  # MOD_ALT
    Qt.KeyboardModifier.ShiftModifier:   0x0004,  # MOD_SHIFT
}
```

Qt Key Code 到 Win32 VK Code：对于 A-Z 和 0-9，Qt key code == Win32 VK code（值相同，直接用）。F1-F12 也一样（Qt.Key.Key_F1 == 0x01000030，需映射到 VK_F1 == 0x70）。

---

## 十一、全局快捷键 `hotkey_manager.py`

### 架构

```python
class HotkeyManager(QThread):
    """
    在独立线程中注册全局快捷键并监听。
    RegisterHotKey 和 GetMessageW 必须在同一线程。
    """
    triggered = pyqtSignal()   # 快捷键被按下

    def __init__(self, modifiers: int, vk: int): ...

    def run(self):
        """线程主函数"""
        # 1. PeekMessageW 初始化消息队列（必须！）
        # 2. RegisterHotKey(None, HOTKEY_ID, modifiers | MOD_NOREPEAT, vk)
        # 3. GetMessageW 循环等待 WM_HOTKEY
        # 4. 收到 WM_HOTKEY → emit triggered
        # 5. 收到 WM_QUIT → 退出循环
        # 6. UnregisterHotKey 清理

    def stop(self):
        """从外部线程安全停止"""
        # PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
```

### 冲突探测（静态方法）

```python
@staticmethod
def is_hotkey_available(modifiers: int, vk: int) -> tuple[bool, str]:
    """
    尝试注册快捷键来探测是否可用。

    返回 (is_available, reason):
      (True,  "")                 — 可用
      (False, "conflict")         — 被其他程序占用（ERROR_HOTKEY_ALREADY_REGISTERED = 1409）
      (False, "invalid_params")   — 参数无效（ERROR_INVALID_PARAMETER = 87 等）
      (False, "unknown:<code>")   — 其他未知错误
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    PROBE_ID = 0xBEEF
    success = user32.RegisterHotKey(None, PROBE_ID, modifiers | 0x4000, vk)  # 0x4000 = MOD_NOREPEAT
    if success:
        user32.UnregisterHotKey(None, PROBE_ID)
        return (True, "")

    error_code = ctypes.get_last_error()
    if error_code == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
        return (False, "conflict")
    elif error_code == 87:  # ERROR_INVALID_PARAMETER
        return (False, "invalid_params")
    else:
        return (False, f"unknown:{error_code}")
```

> **注意**：必须调用 `ctypes.get_last_error()` 而不是 `GetLastError()`，
> 需要在 ctypes 函数声明时设置 `use_last_error=True`，或用
> `ctypes.windll.user32.RegisterHotKey` 的 `ctypes.WinDLL('user32', use_last_error=True)` 版本。

### 快捷键按下时的行为

`triggered` 信号连接到 `driver_switcher` 的 toggle 逻辑：
- 检测当前状态
- 切换到另一个驱动
- 更新 toggle 开关位置（如果弹出面板正在显示）

---

## 十二、开机自启 `autostart.py`

### 方案：Windows 任务计划程序（Task Scheduler）

使用 Windows 任务计划程序创建一个"用户登录时以最高权限运行"的计划任务。
这是唯一能同时满足"管理员权限"和"无 UAC 弹框自启"的方案。

### 原理

- Task Scheduler 的任务由管理员创建时，会在创建时弹一次 UAC（因为程序本身已经是管理员，
  所以实际上连这一次都不会弹）。
- 之后每次登录触发时，Windows 认为该任务已经过管理员审批，直接以管理员权限启动，不弹 UAC。

### 任务参数

| 属性         | 值                                                               |
| ------------ | ---------------------------------------------------------------- |
| 任务名       | `WacomOTDSwitch`                                                 |
| 安全选项     | 当用户登录时再运行（Interactive Logon）                          |
| 配置         | Windows 10                                                       |
| 触发器       | 当任何用户登录时触发                                             |
| 操作         | 启动 exe（当前 exe 的绝对路径）                                  |
| 权限         | 以最高权限运行                                                   |
| 电源条件     | 去掉“只有在电脑使用交流电时才启用此任务”的限制                  |

### API

实现上允许使用 `schtasks.exe` 或 PowerShell `ScheduledTasks` 接口，但创建出来的任务属性必须与上表一致。

关键要求：
- 任务绑定当前登录用户的交互式会话
- 运行级别为 Highest
- 兼容配置为 Windows 10
- 触发器保持“当任何用户登录时”
- 不加“仅交流电”限制
- 重复启用时应覆盖旧任务，保持幂等

### 注意事项

- 创建/删除任务需要管理员权限——程序已以管理员运行（见第四节），所以直接调用即可。
- 任务创建逻辑必须覆盖旧任务，保证重复启用是幂等操作。
- 任务的目标是“用户登录后无 UAC、稳定显示托盘图标地启动程序”。

---

## 十三、中英文支持 `lang.py`

### 设计

不使用 i18n 框架，直接用字典：

```python
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
        "otd_path_invalid": "请选择有效的 OpenTabletDriver.UX.Wpf.exe 文件",
        "tray_settings": "设置",
        "tray_quit": "退出",
    },
    "en": {
        "settings_title": "Settings",
        "otd_path_label": "OTD Program Path:",
        "browse": "Browse",
        "hotkey_label": "Toggle Hotkey:",
        "hotkey_set": "Set",
        "hotkey_none": "None",
        "hotkey_prompt": "Press shortcut...",
        "language_label": "语言 Language:",   # 始终中英双语
        "autostart": "Start with Windows",
        "save": "Save",
        "cancel": "Cancel",
        "conflict_title": "Hotkey Conflict",
        "conflict_message": "This hotkey is already in use by another program and may not work.",
        "conflict_retry": "Choose Again",
        "conflict_force": "Use Anyway",
        "conflict_cancel": "Cancel",
        "hotkey_invalid": "Invalid hotkey, please choose again.",
        "otd_path_invalid": "Please select a valid OpenTabletDriver.UX.Wpf.exe file",
        "tray_settings": "Settings",
        "tray_quit": "Quit",
    },
}

_current_lang = "zh"

def set_language(lang: str):
    global _current_lang
    _current_lang = lang

def t(key: str) -> str:
    """获取当前语言的文本"""
    return TEXTS[_current_lang].get(key, key)
```

### 语言切换即时生效

设置窗口中切换语言单选按钮后，立即调用 `set_language()` 并刷新当前窗口所有控件的文本（重新调用每个控件的 `setText(t("key"))` ）。

---

## 十四、托盘图标 `assets/icon.ico`

### 设计要求

- 内容：一支数位板笔的简约轮廓 + 双向箭头（表示切换）
- 尺寸：`.ico` 文件包含 16×16, 32×32, 48×48, 256×256 四种尺寸
- 风格：单色线条，深灰/深蓝，透明背景
- 在系统托盘 16×16 尺寸下必须清晰可辨

> 可用 Python Pillow 脚本生成，或用在线 ICO 生成器制作。

---

## 十五、PyInstaller 打包 `wacom_otd_switch.spec`

### 关键配置

```python
# wacom_otd_switch.spec
a = Analysis(
    ['src/main.py'],
    datas=[('assets/icon.ico', 'assets')],
    hiddenimports=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'pandas', 'numpy'],
)

exe = EXE(
    ...
    name='WacomOTDSwitch',
    console=False,        # 无控制台窗口
    icon='assets/icon.ico',
    uac_admin=True,       # manifest 嵌入 requireAdministrator
)
```

### 注意事项

- `uac_admin=True`：在 exe manifest 中嵌入 `requireAdministrator`。
  手动双击 exe 时 Windows 弹一次 UAC 确认；通过 Task Scheduler 自启时不弹。
  `main.py` 中的 `is_admin()` + `run_as_admin()` 作为防御性检查保留，
  以应对 manifest 被剥离等极端情况。
- `console=False`：GUI 程序不显示命令行窗口
- `excludes`：排除不需要的大包，减小 exe 体积

### requirements.txt

```
PyQt6>=6.5
PyYAML>=6.0
```

仅两个第三方依赖。

---

## 十六、GitHub Actions `release.yml`

### 触发方式

推送 `v*` 格式的 tag 时触发构建（如 `v1.0.0`）。

### 完整 workflow

```yaml
name: Build & Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build exe
        shell: pwsh
        run: |
          pyinstaller wacom_otd_switch.spec

      - name: Rename with version
        shell: pwsh
        run: |
          $version = "${{ github.ref_name }}"
          Move-Item dist\WacomOTDSwitch.exe "dist\WacomOTDSwitch-$version.exe"

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/WacomOTDSwitch-${{ github.ref_name }}.exe
          generate_release_notes: true
```

### 发布流程

```bash
git tag v1.0.0
git push origin v1.0.0
# → Actions 自动构建 → 生成 Release 页面 → 附带 WacomOTDSwitch-v1.0.0.exe
```

---

## 十七、完整交互流程汇总

### 首次启动

```
双击 exe
  → UAC 弹框（仅手动启动时出现，后续 Task Scheduler 自启不弹）
  → 用户确认
  → 系统托盘出现图标
  → 检测到 config.yaml 不存在
  → 创建默认配置
  → 检测到 otd_path 为空
  → 自动弹出设置窗口
  → 用户选择 OTD 路径、设置快捷键（可选）、勾选开机自启（可选）
  → 保存（如勾选自启 → 创建 Task Scheduler 计划任务）
  → 程序进入就绪状态
```

### 日常使用（开机自启场景）

```
用户登录 Windows
  → Task Scheduler 自动启动程序（管理员权限，无 UAC 弹框）
  → 系统托盘出现图标
  → 程序安静地在后台运行
用户点击托盘图标
  → 弹出面板出现在图标上方
  → 先显示 loading 循环转圈
  → 后端在 10 秒内探测驱动状态
  → 若识别到单一驱动：显示对应方向的拨动按钮
  → 若两者同时识别到：显示朝向 Wacom 的拨动按钮，并显示问号提示
  → 若 10 秒内都未识别到：显示红色 X，并在 hover 时提示未识别到驱动
  → 用户拨动开关
  → 开关禁用，开始切换（子线程）
  → 若切换失败：弹出错误窗口，并附详细输出
  → 若切换成功：开关滑到新位置并重新启用
  → 用户点击面板外部 → 面板关闭

或者：用户按下全局快捷键
  → 直接执行切换（无需打开面板）
  → 如果面板正在显示，更新开关位置
```

### 修改设置

```
右键托盘图标 → 点击"设置"
  → 设置窗口在屏幕中央弹出
  → 用户修改配置 → 保存
  → 快捷键变化时进行冲突检测
  → 配置写入 config.yaml
```

---

## 十八、不做的事情（明确排除）

- ❌ 不做可靠的 USB 设备重置/拔插模拟方案
  - 程序仅提供实验性的 `pnputil /restart-device` 尝试恢复
  - 若失败，仍需用户手动重新插拔数位板或重启系统
- ❌ 不做 Wacom 驱动安装/卸载
- ❌ 不做 OTD 的自动安装/更新
- ❌ 不做多语言 i18n 框架（只有中/英硬编码）
- ❌ 不做 macOS / Linux 支持
- ❌ 不做 toast 通知弹窗
- ❌ 不做日志文件输出
- ❌ 不做系统主题适配（深色/浅色）—— 使用固定的浅色配色
