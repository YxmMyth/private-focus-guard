# FocusGuard v2.0 - Project Context

## Role
15年经验的 Python 系统架构师，精通 PyQt6 桌面开发、SQLite 数据库优化以及 LLM Agent 的设计模式。代码风格严谨、注重类型安全（Type Hinting）、擅长异步编程（Async/QThread）和模块解耦。

---

## Project Overview
**FocusGuard v2.0 Ultimate** - 基于上下文感知和用户信任体系的智能桌面监督 Agent

目标：通过非侵入式监控 + 语义判断 + 动态选择题交互，帮助用户保持专注。

---

## Tech Stack & Constraints
- **Language**: Python 3.10+
- **GUI Framework**: PyQt6 (必须使用 Signal/Slot 机制，严禁主线程阻塞)
- **Database**: SQLite3 (使用 context manager 管理连接，启用 WAL 模式)
- **System API**: `pywin32` (Windows), `psutil`
- **AI Provider**: Tencent Hunyuan / OpenAI API (兼容接口)
- **Packaging**: Nuitka 打包兼容性要求：
  - 禁止使用 `__import__()` 或 `importlib.import_module()` 动态导入
  - 禁止使用 `exec()` / `eval()` 执行代码字符串
  - 所有依赖模块必须在顶层显式 import
  - 资源文件路径使用 `__file__` 相对定位，不依赖 `sys._MEIPASS`

---

## System Architecture

系统分为四层：**感知层 (Perception)** -> **数据层 (Volatile Memory)** -> **智能层 (Brain)** -> **执行层 (Action)**.

### 1. Perception Layer (监控端)
负责采集"世界发生了什么"。

#### `monitors/windows_monitor.py`:
- 每 3 秒轮询 `win32gui.GetForegroundWindow()`
- **Requirement**: 必须过滤 Window Title 中的零宽字符和非打印字符
  ```python
  import re
  def sanitize_title(title: str) -> str:
      # 移除零宽字符、控制字符
      return re.sub(r'[\u200b-\u200f\u2028-\u202f\u00a0\x00-\x1f]', '', title).strip()
  ```

#### `monitors/chrome_monitor.py`:
- **Critical**: Chrome 运行时数据库被锁定（SQLite EXCLUSIVE lock）
- **Strategy**:
  1. 动态获取 History 路径：
     ```python
     import os
     history_path = os.path.join(
         os.environ.get('LOCALAPPDATA', ''),
         r'Google\Chrome\User Data\Default\History'
     )
     # Edge 路径: Microsoft\Edge\User Data\Default\History
     ```
  2. 使用 `shutil.copy2()` 复制到 `tempfile.NamedTemporaryFile(delete=False)`
  3. 以 `uri=file:...?mode=ro` 只读模式打开副本
  4. 读取完成后 `os.unlink()` 删除临时文件
- **Trigger Condition**: 仅当窗口标题包含 "Chrome" / "Edge" / "Chromium" 时触发

---

### 2. Data Layer (数据层 - The Volatile Lake)
负责数据的"暂存"与"挥发"。

#### `storage/database.py`:

**连接配置**:
```python
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")  # 提升并发读写性能
    conn.execute("PRAGMA busy_timeout=5000")  # 锁等待超时 5s
    conn.row_factory = sqlite3.Row
    return conn
```

**Table `activity_logs`** (The Raw Stream):
```sql
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    app_name TEXT,
    window_title TEXT,
    url TEXT,
    duration INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON activity_logs(timestamp);
```

**Table `focus_sessions`** (The Contract):
```sql
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_text TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'abandoned'))
);
```

**Table `user_profile`** (The Long-term Memory):
```sql
CREATE TABLE IF NOT EXISTS user_profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);
-- 初始化信任分
INSERT OR IGNORE INTO user_profile (key, value) VALUES ('trust_score', '80');
```

**Thread Safety**: 更新 `trust_score` 时使用事务 + 乐观锁：
```python
def update_trust_score(delta: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE user_profile SET value = MAX(0, MIN(100, CAST(value AS INTEGER) + ?)), "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime') "
            "WHERE key = 'trust_score' RETURNING CAST(value AS INTEGER)",
            (delta,)
        )
        return cursor.fetchone()[0]
```

**Table `learning_history`**:
```sql
CREATE TABLE IF NOT EXISTS learning_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    context_summary TEXT,
    user_choice TEXT,
    was_correct INTEGER  -- 1=用户后续确认选择正确, 0=用户后悔, NULL=未知
);
```

#### `storage/cleaner.py` (The Evaporation Logic):
后台守护线程 `DataCleaner(QThread)`
- **Logic**: 每 60 秒执行清理
  ```python
  def run(self) -> None:
      while not self._stop_event.is_set():
          try:
              with get_connection() as conn:
                  # 使用 localtime 保持时区一致性
                  conn.execute("""
                      DELETE FROM activity_logs
                      WHERE timestamp < strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-1 hour')
                  """)
                  conn.commit()
          except sqlite3.Error as e:
              logger.warning(f"Cleaner error (non-fatal): {e}")
          self._stop_event.wait(60)
  ```
- **Graceful Shutdown**: 提供 `stop()` 方法设置 `_stop_event`

---

### 3. Intelligence Layer (智能层 - The Brain)
负责"判断"与"生成选项"。

#### `services/llm_service.py`:

**Input Context**:
1. **Snapshots**: SQL 聚合近 30秒、5分钟、20分钟的活动摘要
   ```sql
   -- 30秒内活动
   SELECT app_name, window_title, url, SUM(duration) as total_duration
   FROM activity_logs
   WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-30 seconds')
   GROUP BY app_name, window_title
   ORDER BY total_duration DESC
   LIMIT 5;
   ```
2. **Trust Score**: 从 `user_profile` 读取
3. **Session Goal**: 当前 `focus_sessions` 中 `status='active'` 的目标

**Trust-based Behavior**:
| Trust Score | Mode | Behavior |
|-------------|------|----------|
| < 60 | 严格模式 | 对"查资料"等模糊行为保持怀疑，禁用 SNOOZE > 5min |
| 60-90 | 标准模式 | 正常判断 |
| > 90 | 信任模式 | 允许更多模糊行为，减少干预频率 |

**Output: 强制 JSON Schema**:
```json
{
  "is_distracted": true,
  "confidence": 85,
  "analysis_summary": "检测到您在 Bilibili 观看视频，与学习目标不符",
  "options": [
    {
      "label": "再看 5 分钟",
      "action_type": "SNOOZE",
      "payload": { "duration_minutes": 5 },
      "trust_impact": -3,
      "style": "warning",
      "disabled": false,
      "disabled_reason": null
    },
    {
      "label": "这是学习资料",
      "action_type": "DISMISS",
      "payload": {},
      "trust_impact": 2,
      "style": "normal",
      "disabled": false,
      "disabled_reason": null
    },
    {
      "label": "加入临时白名单",
      "action_type": "WHITELIST_TEMP",
      "payload": { "app": "chrome.exe", "duration_hours": 1 },
      "trust_impact": 0,
      "style": "normal",
      "disabled": true,
      "disabled_reason": "信任分低于 70 时不可用"
    },
    {
      "label": "我管不住自己",
      "action_type": "STRICT_MODE",
      "payload": { "duration_minutes": 30 },
      "trust_impact": 5,
      "style": "primary",
      "disabled": false,
      "disabled_reason": null
    }
  ]
}
```

**Retry Strategy**:
```python
import asyncio
from typing import Optional

async def call_llm_with_retry(
    prompt: str,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Optional[dict]:
    for attempt in range(max_retries):
        try:
            response = await self._call_api(prompt)
            return self._parse_json_response(response)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # 指数退避: 1s, 2s, 4s
                await asyncio.sleep(delay)
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
    return None  # 所有重试失败，返回 None，由调用方决定回退策略
```

---

### 4. Action & UI Layer (执行层 - The Interaction)

#### `ui/dialogs/intervention_dialog.py`:
- **Layout**: Card Style 卡片式布局
  - 顶部：AI 的简短分析 (`analysis_summary`)
  - 中部：3-4 个动态按钮
  - 底部："其他原因" 输入框 + 提交按钮

- **Window Flags**:
  ```python
  self.setWindowFlags(
      Qt.WindowType.FramelessWindowHint |
      Qt.WindowType.WindowStaysOnTopHint |
      Qt.WindowType.Tool  # 不在任务栏显示
  )
  self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
  ```

- **Button Styling**:
  ```python
  STYLE_MAP = {
      "normal": "background: #f0f0f0; color: #333;",
      "warning": "background: #ff9800; color: white;",
      "primary": "background: #2196f3; color: white;",
  }
  # Disabled 状态
  if option["disabled"]:
      btn.setEnabled(False)
      btn.setToolTip(option.get("disabled_reason", "不可用"))
      btn.setStyleSheet("background: #ccc; color: #888;")
  ```

#### `services/action_manager.py`:
**Signal 定义** (类型安全):
```python
from PyQt6.QtCore import QObject, pyqtSignal

class ActionManager(QObject):
    # 明确 Signal 参数类型
    snooze_expired = pyqtSignal()  # 无参数
    trust_updated = pyqtSignal(int)  # 新的 trust_score
    intervention_requested = pyqtSignal(dict)  # LLM 返回的完整 JSON
```

**The Enforced Loop (Snooze Timer)**:
```python
from PyQt6.QtCore import QTimer

def handle_snooze(self, duration_minutes: int) -> None:
    self._snooze_timer = QTimer(self)
    self._snooze_timer.setSingleShot(True)
    self._snooze_timer.timeout.connect(self._on_snooze_expired)
    self._snooze_timer.start(duration_minutes * 60 * 1000)

def _on_snooze_expired(self) -> None:
    """Snooze 结束，跳过 AI 判断，直接强制回调"""
    self.intervention_requested.emit({
        "is_distracted": True,
        "confidence": 100,
        "analysis_summary": "休息时间结束，请确认当前状态",
        "options": [
            {"label": "继续工作", "action_type": "DISMISS", "trust_impact": 3, "style": "primary", "disabled": False},
            {"label": "再休息 5 分钟", "action_type": "SNOOZE", "payload": {"duration_minutes": 5}, "trust_impact": -5, "style": "warning", "disabled": False},
        ],
        "_forced_callback": True  # 内部标记
    })
```

---

## Action Type Definitions

| Action | 效果 | 副作用 |
|--------|------|--------|
| `SNOOZE` | 暂停监控 X 分钟 | 扣除 trust_impact 分，启动强制回调 Timer |
| `DISMISS` | 关闭弹窗，重置检测计数器 | 增加 trust_impact 分（误报补偿） |
| `WHITELIST_TEMP` | 当前 App 加入临时白名单（默认 1 小时） | 存入内存 `Set[str]`，不持久化 |
| `STRICT_MODE` | 进入高频监控（每 10 秒检测） | 增加 trust_impact 分（奖励自律） |

---

## The Master System Prompt

```
你是 FocusGuard 的智能监督 Agent。你的职责是帮助用户保持专注，同时尊重用户的自主权。

## 当前上下文
- 用户目标：{goal}
- 用户信任分：{trust_score}/100（{trust_level}）
- 当前时间：{current_time}

## 用户活动记录
【最近 30 秒】
{instant_log}

【最近 5 分钟趋势】
{short_trend}

【最近 20 分钟趋势】
{context_trend}

## 你的任务
1. 分析用户当前行为是否偏离目标
2. 考虑信任分调整判断严格程度：
   - 信任分 < 60：对模糊行为（如"查资料"）保持怀疑
   - 信任分 > 90：给予更多自主空间
3. 生成 3-4 个交互选项供用户选择

## 输出要求
你必须且只能输出以下 JSON 格式，不要包含任何其他文字：

```json
{
  "is_distracted": boolean,
  "confidence": number (0-100),
  "analysis_summary": "一句话分析，不超过 30 字",
  "options": [
    {
      "label": "按钮文字",
      "action_type": "SNOOZE" | "DISMISS" | "WHITELIST_TEMP" | "STRICT_MODE",
      "payload": {},
      "trust_impact": number,
      "style": "normal" | "warning" | "primary",
      "disabled": boolean,
      "disabled_reason": "string 或 null"
    }
  ]
}
```

## 注意事项
- 如果信任分 < 60，禁用 duration > 5 分钟的 SNOOZE 选项
- 如果信任分 < 70，禁用 WHITELIST_TEMP 选项
- options 数组必须包含 3-4 个选项
- trust_impact 范围建议 -5 到 +5
```

---

## Code Style Guidelines

### Threading Model
- **QThread**: 用于需要与 Qt 事件循环集成的后台任务（如 Monitor、Cleaner）
- **asyncio**: 用于网络 I/O（如 LLM API 调用）
- **协作方式**: 在 QThread 中使用 `asyncio.run()` 或 `qasync` 库桥接

### Error Handling
```python
# 监控线程绝不能因异常而 Crash
def run(self) -> None:
    while self._running:
        try:
            self._do_work()
        except Exception as e:
            logger.exception(f"Monitor error (will retry): {e}")
            # 继续运行，不要 break
        self._wait(self.interval)
```

### Type Hints
```python
from typing import Optional, TypedDict, Literal

class LLMOption(TypedDict):
    label: str
    action_type: Literal["SNOOZE", "DISMISS", "WHITELIST_TEMP", "STRICT_MODE"]
    payload: dict
    trust_impact: int
    style: Literal["normal", "warning", "primary"]
    disabled: bool
    disabled_reason: Optional[str]
```

### Comments
- 关键逻辑必须加注释（Chrome 文件锁处理、Trust Score 计算、Snooze 强制回调）
- 使用 docstring 描述类和公共方法的用途

---

## Project Structure

```
focusguard/
├── claude.md                    # This file - project context
├── main.py                      # Application entry point
├── config.py                    # Configuration management
├── requirements.txt             # Dependencies
├── monitors/
│   ├── __init__.py
│   ├── base_monitor.py          # Abstract base class
│   ├── windows_monitor.py       # Window title monitoring
│   └── chrome_monitor.py        # Chrome history tracking
├── storage/
│   ├── __init__.py
│   ├── database.py              # SQLite connection & schema
│   └── cleaner.py               # Data cleanup QThread
├── services/
│   ├── __init__.py
│   ├── llm_service.py           # LLM API integration
│   └── action_manager.py        # Signal dispatch & action handling
└── ui/
    ├── __init__.py
    └── dialogs/
        ├── __init__.py
        └── intervention_dialog.py  # Dynamic choice dialog
```

---

## Version History
- **v2.0 Ultimate**: Initial architecture with trust-based AI supervision
