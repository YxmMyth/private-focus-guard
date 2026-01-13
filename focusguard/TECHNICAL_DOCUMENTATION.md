# FocusGuard v3.0 - 技术文档

## 📋 项目概述

**FocusGuard v3.0** 是一个基于上下文感知和用户信任体系的智能桌面监督 Agent，通过非侵入式监控 + 语义判断 + 动态选择题交互，帮助用户保持专注。

### 核心特性

1. **智能分心检测**：基于 LLM 语义分析，识别用户行为是否偏离目标
2. **优先级层次系统**：当下对齐 > 通用工具审查 > 历史惯性
3. **Recovery 状态识别**：用户回归工作后立即停止报警
4. **精确标签页关闭**：强制置顶 + Ctrl+W，只关闭分心标签页
5. **虚拟货币经济系统**：通过专注货币激励自律行为
6. **信任分体系**：动态调整干预策略

---

## 🏗️ 系统架构

### 四层架构

```
┌─────────────────────────────────────────┐
│      Perception Layer (感知层)           │
│  - WindowsMonitor: 窗口活动监控         │
│  - ChromeMonitor: 浏览历史监控          │
└─────────────────┬───────────────────────┘
                  │ Activity Data
┌─────────────────▼───────────────────────┐
│       Data Layer (数据层)                │
│  - activity_logs: L1 原始数据流         │
│  - session_blocks: L2 会话压缩          │
│  - user_profile: L3 长期记忆             │
└─────────────────┬───────────────────────┘
                  │ Aggregated Context
┌─────────────────▼───────────────────────┐
│    Intelligence Layer (智能层)          │
│  - LLMService: 语义分析与决策           │
│  - Priority Hierarchy: 三级判断         │
│  - Recovery Detection: 恢复期识别       │
└─────────────────┬───────────────────────┘
                  │ Action Decisions
┌─────────────────▼───────────────────────┐
│     Action & UI Layer (执行层)           │
│  - ActionManager: 动作分发              │
│  - WindowController: 窗口控制           │
│  - EnforcementService: 强制执行         │
│  - InterventionDialog: 用户交互         │
└─────────────────────────────────────────┘
```

---

## 🔧 核心模块详解

### 1. 感知层 (Perception Layer)

#### WindowsMonitor (`monitors/windows_monitor.py`)
- **功能**：每 3 秒轮询前台窗口
- **关键技术**：
  - `win32gui.GetForegroundWindow()` 获取活动窗口
  - 零宽字符过滤：`re.sub(r'[\u200b-\u200f\u2028-\u202f\u00a0\x00-\x1f]', '', title)`
  - 线程安全：使用 QThread + Signal/Slot 机制

#### ChromeMonitor (`monitors/chrome_monitor.py`)
- **挑战**：Chrome 运行时数据库被 EXCLUSIVE 锁定
- **解决方案**：
  1. 复制到临时文件：`shutil.copy2(history_path, temp_path)`
  2. 只读模式打开：`sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)`
  3. 时间过滤：只读取最近 30 秒内访问的 URL（避免历史污染）
- **Chrome 时间戳格式**：自 1601-01-01 起的微秒数
  ```python
  chrome_epoch = datetime.datetime(1601, 1, 1)
  threshold_chrome_time = int((threshold_time - chrome_epoch).total_seconds() * 1000000)
  ```

---

### 2. 数据层 (Data Layer)

#### 数据库设计 (`storage/database.py`)

**表结构**：

```sql
-- L1: 原始活动日志（自动挥发，1小时后删除）
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    app_name TEXT,
    window_title TEXT,
    url TEXT,
    duration INTEGER DEFAULT 0
);
CREATE INDEX idx_logs_timestamp ON activity_logs(timestamp);

-- L2: 会话压缩块（30分钟聚合）
CREATE TABLE session_blocks (
    id INTEGER PRIMARY KEY,
    start_time TEXT,
    focus_density REAL,           -- 专注密度（0-1）
    distraction_count INTEGER,
    energy_level REAL,            -- 能量等级（0-1）
    block_data TEXT               -- JSON 格式的详细信息
);

-- L3: 用户长期记忆
CREATE TABLE user_profile (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
```

**数据代谢机制** (`storage/cleaner.py`)：
- 每 60 秒清理一次
- 删除 1 小时前的 L1 数据
- 保留 L2 和 L3 数据

---

### 3. 智能层 (Intelligence Layer)

#### Priority Hierarchy（优先级层次）

**核心思想**：当下行为 > 历史趋势

```
Priority 1: Instant Alignment（当下对齐）
- 检查最近 30 秒的活动
- 如果当前是工作工具（VSCode/Gemini/Terminal）
- 裁决：忽略过去 5 分钟的分心记录
- 输出：status="RECOVERY", force_cease_fire=true

Priority 2: Ambiguity Check（通用工具审查）
- 检查浏览器/AI 聊天工具
- 分析窗口标题关键词
- 编程/技术关键词 → 工作
- 娱乐关键词 → 分心

Priority 3: Historical Trend（历史惯性）
- 只有在 P1/P2 无法确定时才使用
- 参考最近 5 分钟趋势
- 识别持续的分心行为
```

#### LLM Prompt 工程 (`services/llm_service.py`)

**System Prompt 设计原则**：

1. **三步推理协议**（System 2 Thinking）
   ```json
   {
     "thought_trace": [
       "Step 1: 证据收集 - 分析最近30秒活动",
       "Step 2: 模式匹配 - 与目标对比",
       "Step 3: 置信度校准 - 输出判断"
     ]
   }
   ```

2. **信任分驱动行为**
   - Trust Score < 60：严格模式，怀疑"查资料"
   - Trust Score 60-90：标准模式
   - Trust Score > 90：信任模式，减少干预

3. **Few-Shot Examples**
   - 示例 1：学习场景（VERIFY）
   - 示例 2：持续分心（STRICT_MODE）
   - 示例 3：精确关闭标签页（CLOSE_TAB）
   - 示例 4：Recovery 状态（回归工作）

---

### 4. 执行层 (Action & UI Layer)

#### WindowController (`services/window_controller.py`)

**挑战**：Windows 不允许后台进程直接关闭特定标签页

**解决方案**：强制置顶 + 快捷键

```python
def close_current_tab_safely(target_title_keyword: str, return_to_hwnd: int):
    # 步骤 1: 查找目标窗口
    target_hwnd = find_window_by_title_keyword(target_title_keyword)

    # 步骤 2: 强制置顶（绕过 Windows 限制）
    force_focus_window(target_hwnd)
    # 关键技术：AttachThreadInput 绑定输入
    win32process.AttachThreadInput(current_tid, target_tid, True)
    win32gui.SetForegroundWindow(hwnd)
    win32process.AttachThreadInput(current_tid, target_tid, False)

    # 步骤 3: 双重检查（防止误关）
    actual_title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    if target_title_keyword.lower() not in actual_title.lower():
        logger.error("ABORTING: 焦点丢失，防止误关")
        return False

    # 步骤 4: 发送 Ctrl+W 关闭标签页
    pyautogui.hotkey('ctrl', 'w')

    # 步骤 5: 返回工作窗口
    if return_to_hwnd:
        force_focus_window(return_to_hwnd)
```

#### EnforcementService (`services/enforcement_service.py`)

**窗口管理功能**：
- `close_window()`: 使用 `SendMessage` 同步发送 WM_CLOSE
- `minimize_window()`: 最小化窗口 + 启动 SNOOZE
- `block_app()`: 阻止应用运行（定期检查进程列表）

**权限检测**：
```python
import ctypes
self._is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
```

#### ActionManager (`services/action_manager.py`)

**动作类型**：
- `SNOOZE`: 暂停监控 X 分钟
- `DISMISS`: 误报补偿，增加信任分
- `WHITELIST_TEMP`: 临时白名单
- `STRICT_MODE`: 高频监控（每 10 秒）
- `CLOSE_WINDOW`: 关闭整个应用
- `MINIMIZE_WINDOW`: 最小化窗口
- `CLOSE_TAB`: 精确关闭标签页（新增）
- `BLOCK_APP`: 阻止应用运行
- `FORCE_CEASE_FIRE`: 强制停止干预（Recovery 状态，新增）

---

## 💾 经济系统设计

### 虚拟货币机制 (`services/economy_service.py`)

**经济模型**：
```python
# 初始余额
initial_balance = 100

# 挖矿速率（每 30 秒）
mining_rate = 1 Coin

# 破产阈值
bankruptcy_threshold = -50 Coins

# 动作定价
CLOSE_TAB = 5 Coins
MINIMIZE_WINDOW = 2 Coins
SNOOZE_10min = 5 Coins
WHITELIST_TEMP = 20 Coins
STRICT_MODE = -10 Coins (奖励自律)
```

**定价策略**：
- **温和方式**（MINIMIZE_WINDOW）：2 Coins
- **立即停止**（CLOSE_TAB）：5 Coins
- **严厉措施**（BLOCK_APP）：15 Coins
- **自律奖励**（STRICT_MODE）：-10 Coins（负价格 = 收入）

---

## 🔐 信任分体系

### 信任分计算

**初始值**：80/100

**影响因素**：
- 选择"这是学习资料"：+2 分
- 选择"我管不住自己"（STRICT_MODE）：+5 分
- 持续专注：自动缓慢增长
- 频繁分心：自动缓慢下降

**信任分影响**：
```
Trust < 60: 严格模式
- 对"查资料"保持怀疑
- 禁用 SNOOZE > 5min
- 禁用 WHITELIST_TEMP

Trust 60-90: 标准模式
- 正常判断

Trust > 90: 信任模式
- 减少干预频率
- 允许更多模糊行为
```

---

## 🚀 Nuitka 打包注意事项

### 1. 禁止动态导入

**问题**：Nuitka 无法编译动态导入的模块

**解决方案**：所有依赖必须在顶层显式导入
```python
# ❌ 错误
module = __import__(module_name)

# ✅ 正确
from services.window_controller import WindowController
```

### 2. 资源文件路径

**问题**：打包后路径改变

**解决方案**：使用 `__file__` 相对定位
```python
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "focusguard.db")
```

### 3. PyInstaller/Nuitka 配置

**requirements.txt**：
```
PyQt6==6.6.1
pywin32==306
psutil==5.9.8
pyautogui==0.9.54
aiohttp==3.9.1
tencentcloud-sdk-python==3.0.1000
```

**Nuitka 编译命令**：
```bash
python -m nuitka \
  --standalone \
  --onefile \
  --enable-plugin=pyqt6 \
  --windows-disable-console \
  --include-data-files=focusguard/config=focusguard/config \
  --include-package=services \
  --include-package=monitors \
  --include-package=storage \
  --include-package=ui \
  focusguard/main.py
```

### 4. 已知限制

- **Chrome 历史读取**：需要复制数据库，可能有延迟
- **窗口关闭权限**：需要管理员权限才能关闭某些应用
- **Ctrl+W 快捷键**：依赖浏览器默认快捷键绑定
- **强制置顶**：可能被某些应用阻止（如游戏）

---

## 📊 性能优化

### 1. 数据库优化

**启用 WAL 模式**（提升并发性能）：
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

**索引优化**：
```sql
CREATE INDEX idx_logs_timestamp ON activity_logs(timestamp);
CREATE INDEX idx_logs_app ON activity_logs(app_name);
```

### 2. 线程管理

**QThread vs asyncio**：
- 监控线程：使用 QThread（与 Qt 事件循环集成）
- 网络 I/O：使用 asyncio（LLM API 调用）

### 3. 内存管理

**数据代谢**：
- L1 数据：1 小时后自动删除
- L2 数据：30 分钟聚合压缩
- 防止内存无限增长

---

## 🐛 已知问题与解决方案

### 问题 1：Chrome 历史时间过滤

**现象**：ChromeMonitor 返回 5 分钟前的 URL，导致误判

**解决方案**：
```python
# 添加时间阈值过滤
WHERE last_visit_time >= ?
# 转换为 Chrome 时间戳（微秒）
threshold_chrome_time = int((threshold_time - chrome_epoch).total_seconds() * 1000000)
```

### 问题 2：回归工作后的误判死循环

**现象**：用户从 Bilibili 切换到 VSCode，AI 仍因 5 分钟历史报警

**解决方案**：
- 实现 Priority Hierarchy
- 添加 RECOVERY 状态识别
- 使用 `force_cease_fire` 机制

### 问题 3：LockSetForegroundWindow 不可用

**现象**：pywin32 没有 `LockSetForegroundWindow` API

**解决方案**：
- 使用 `AttachThreadInput` 绑定线程
- 直接调用 `SetForegroundWindow`
- 移除 `LockSetForegroundWindow` 调用

### 问题 4：pyautogui 未安装

**现象**：`pyautogui not available, hotkey simulation disabled`

**解决方案**：
```bash
pip install pyautogui
```

---

## 🔮 未来改进方向

### 1. 机器学习增强

- 学习用户工作习惯
- 自动识别工作模式
- 动态调整检测阈值

### 2. 多平台支持

- macOS 支持（使用 AppleScript）
- Linux 支持（使用 xdotool）

### 3. 高级功能

- 屏幕时间统计
- 专注报告生成
- 与日历应用集成
- 团队协作模式

### 4. 性能优化

- 减少 LLM API 调用频率
- 本地小模型（如 LLaMA 3）
- 缓存机制优化

---

## 📝 开发规范

### 代码风格

- **类型提示**：所有函数必须添加类型注解
- **文档字符串**：Google Style Docstrings
- **错误处理**：监控线程绝不能因异常崩溃
- **日志记录**：使用 `logging` 模块，不用 `print`

### Git Commit 规范

```
feat: 添加 CLOSE_TAB 功能
fix: 修复 Chrome 时间过滤问题
docs: 更新技术文档
test: 测试 Recovery 状态
refactor: 重构 ActionManager
```

---

## 🎯 测试清单

### 功能测试

- [x] WindowsMonitor 正常捕获活动
- [x] ChromeMonitor 正确读取历史（有时间过滤）
- [x] LLM 语义分析准确
- [x] CLOSE_WINDOW 成功关闭窗口
- [x] MINIMIZE_WINDOW 成功最小化窗口
- [x] CLOSE_TAB 精确关闭标签页
- [ ] Recovery 状态识别
- [ ] 经济系统正常运作
- [ ] 信任分动态调整

### 边界测试

- [ ] 长时间运行（24 小时）内存泄漏
- [ ] 高频切换应用性能
- [ ] 数据库并发冲突
- [ ] 网络断开时的降级策略

### 用户体验测试

- [ ] 干预对话框响应速度
- [ ] 动作执行反馈及时性
- [ ] 误报率统计

---

## 📞 技术支持

### 关键文件位置

```
focusguard/
├── main.py                    # 应用入口
├── config.py                  # 配置管理
├── monitors/                  # 监控模块
│   ├── windows_monitor.py
│   ├── chrome_monitor.py
│   └── base_monitor.py
├── services/                  # 核心服务
│   ├── llm_service.py        # LLM 集成
│   ├── action_manager.py     # 动作分发
│   ├── enforcement_service.py # 强制执行
│   ├── window_controller.py  # 窗口控制
│   ├── economy_service.py    # 经济系统
│   └── data_transformer.py   # 数据转换
├── storage/                   # 数据层
│   ├── database.py
│   └── cleaner.py
└── ui/                        # 用户界面
    ├── main_window.py
    └── dialogs/
        └── intervention_dialog.py
```

### 日志位置

- Windows: `C:/Users/Evan/.focusguard/`
- 数据库: `C:/Users/Evan/.focusguard/focusguard.db`
- 日志文件: 控制台输出（可配置文件输出）

---

## 📄 License

MIT License

---

**最后更新**：2026-01-13
**版本**：v3.0
**作者**：Claude Code Assistant
