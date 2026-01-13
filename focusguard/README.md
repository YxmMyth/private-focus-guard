# FocusGuard v3.0 - 智能桌面监督 Agent

> 基于上下文感知和用户信任体系的智能专注助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

---

## 📸 功能截图

![主界面](docs/screenshots/main-window.png)
*主窗口 - 显示当前状态（余额、信任分、专注时长）*

![干预对话框](docs/screenshots/intervention-dialog.png)
*智能干预 - AI 判断分心行为后提供选项*

![设置界面](docs/screenshots/settings-dialog.png)
*自定义配置 - 调整监控参数和日志级别*

---

## 🎯 项目简介

FocusGuard 是一个非侵入式的桌面监控应用，通过 LLM 语义分析判断用户行为是否偏离目标，并提供智能干预选项。与传统的应用拦截器不同，FocusGuard 尊重用户自主权，通过动态选择题和经济激励机制帮助用户建立自律习惯。

### 核心特性

- 🧠 **智能语义分析**：基于腾讯混元大模型，理解用户行为上下文
- 🎚️ **优先级层次系统**：当下对齐 > 历史趋势，避免误判死循环
- 🔄 **Recovery 状态识别**：用户回归工作后立即停止报警
- 🎯 **精确标签页关闭**：只关闭分心标签页，保留有用内容
- 💰 **虚拟货币经济**：通过专注货币激励自律行为
- 📊 **信任分体系**：动态调整干预策略，越自律越自由
- 🔒 **隐私保护**：数据本地存储，1 小时后自动挥发

---

## 📥 下载安装

### 方式一：直接使用（推荐普通用户）

**适用于**：不想配置开发环境的用户

1. **下载 Release**
   - 前往 [Releases](https://github.com/YxmMyth/private-focus-guard/releases) 页面
   - 下载最新版本的 `FocusGuard-v3.0-Windows.zip`

2. **解压运行**
   ```bash
   # 解压到任意目录
   unzip FocusGuard-v3.0-Windows.zip
   cd FocusGuard-v3.0-Windows

   # 双击运行
   FocusGuard.exe
   ```

3. **首次使用**
   - 程序会自动创建配置目录：`%USERPROFILE%\.focusguard\`
   - 内置混元 API 密钥，无需额外配置
   - 点击"开始监控"即可使用

**文件说明**：
- `FocusGuard.exe` - 主程序（约 70MB）
- `bundled_config.env` - 内置配置（包含 API 密钥，请勿删除）
- `README.txt` - 使用说明

### 方式二：从源码运行（推荐开发者）

**适用于**：想自定义或参与开发的用户

---

## 🚀 快速开始（从源码）

### 环境要求

- **Python**：3.10 或更高版本
- **操作系统**：Windows 10/11
- **内存**：至少 4GB RAM
- **网络**：需要连接腾讯云 API（LLM 服务）

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd selfsuperviseagentV2
```

2. **安装依赖**
```bash
pip install -r focusguard/requirements.txt
```

3. **配置环境变量**

创建 `focusguard/.env` 文件：
```env
# 腾讯云 API 密钥（必需）
TENCENTCLOUD_SECRET_ID=your_secret_id
TENCENTCLOUD_SECRET_KEY=your_secret_key
TENCENTCLOUD_REGION=ap-beijing

# 可选配置
LOG_LEVEL=INFO
MINING_RATE=1
INITIAL_BALANCE=100
```

4. **启动应用**
```bash
cd focusguard
python main.py
```

---

## 📖 使用指南

### 基础使用

1. **启动应用**
   - 双击 `main.py` 或运行 `python main.py`
   - 主窗口会显示当前状态（余额、信任分、专注时长）

2. **设置目标**
   - 在"当前目标"框中输入你的工作目标
   - 例如："学习 Python 编程"、"完成量化交易策略"
   - 点击"保存目标"按钮

3. **开始监控**
   - 点击主窗口的"开始监控"按钮
   - 应用会最小化到系统托盘
   - 监控开始运行

4. **响应干预**
   - 当检测到分心行为时，会弹出干预对话框
   - 选择合适的选项：
     - **关闭标签页**：精确关闭分心标签页（推荐）
     - **最小化窗口**：隐藏分心窗口，稍后提醒
     - **稍后提醒**：暂停监控 X 分钟
     - **这是学习资料**：误报补偿

### 高级功能

#### Recovery 状态（自动停止报警）

当你在 Bilibili 看视频后切换到 VSCode 工作，系统会自动识别你已经回归工作，立即停止报警。这是通过优先级层次系统实现的：

- **Priority 1**：检查最近 30 秒的活动（工作工具优先）
- **Priority 2**：检查窗口标题关键词
- **Priority 3**：参考最近 5 分钟历史趋势

#### 经济系统

- **初始余额**：100 Coins
- **挖矿速率**：每 30 秒 +1 Coin
- **动作定价**：
  - 关闭标签页：5 Coins
  - 最小化窗口：2 Coins
  - 稍后提醒 10 分钟：5 Coins
  - 进入严格模式：-10 Coins（奖励自律）

#### 信任分

- **初始值**：80/100
- **影响**：
  - < 60：严格模式，禁止稍后提醒 > 5 分钟
  - 60-90：标准模式
  - > 90：信任模式，减少干预频率

---

## 🏗️ 项目结构

```
focusguard/
├── main.py                    # 应用入口
├── config.py                  # 配置管理
├── requirements.txt           # Python 依赖
├── monitors/                  # 监控模块
│   ├── base_monitor.py        # 监控基类
│   ├── windows_monitor.py     # 窗口活动监控
│   └── chrome_monitor.py      # 浏览历史监控
├── services/                  # 核心服务
│   ├── llm_service.py        # LLM 集成
│   ├── action_manager.py     # 动作分发
│   ├── enforcement_service.py # 强制执行
│   ├── window_controller.py  # 窗口控制
│   ├── economy_service.py    # 经济系统
│   └── data_transformer.py   # 数据转换
├── storage/                   # 数据层
│   ├── database.py           # 数据库管理
│   └── cleaner.py            # 数据代谢
└── ui/                        # 用户界面
    ├── main_window.py        # 主窗口
    └── dialogs/
        └── intervention_dialog.py  # 干预对话框
```

---

## 🛡️ 安全与隐私

### 数据保护
- ✅ **本地存储**：所有数据存储在本地 SQLite 数据库
- ✅ **自动清理**：1 小时后自动删除旧数据
- ✅ **无上传**：不向任何服务器上传用户数据

### API 密钥安全
- ✅ **内置保护**：API 密钥内置在配置文件中，代码强制保护
- ✅ **不可覆盖**：用户无法通过配置文件修改 API 密钥
- ⚠️ **费用说明**：使用开发者的腾讯云 API 密钥，产生费用由开发者承担

### 隐私说明
- 监控仅在本地运行，不收集任何个人信息
- 浏览历史仅用于上下文判断，不上传到任何服务器
- 支持数据自动挥发，保护用户隐私

---

## 🏗️ 技术架构

详细的技术文档和设计思路，请参阅：

- **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)**：完整的技术文档，包含系统架构、核心模块详解、性能优化等
- **[BUILD_GUIDE.md](BUILD_GUIDE.md)**：Nuitka 打包指南，包含完整打包流程和常见问题解决方案

---

## 🔧 开发指南

### 添加新的监控器

1. 继承 `BaseMonitor` 类
2. 实现 `_monitoring_loop()` 方法
3. 通过 `activity_detected` Signal 发送数据

示例：
```python
from monitors.base_monitor import BaseMonitor

class CustomMonitor(BaseMonitor):
    def __init__(self, parent=None):
        super().__init__(parent, interval=5)  # 5 秒轮询

    def _monitoring_loop(self):
        # 实现监控逻辑
        self.activity_detected.emit(
            app_name="app.exe",
            window_title="Window Title",
            url="https://example.com"
        )
```

### 添加新的动作类型

1. 在 `action_manager.py` 中添加处理方法
2. 在 LLM Prompt 中添加动作说明
3. 在 JSON Schema 中添加动作类型

示例：
```python
def _handle_custom_action(self, payload: dict) -> None:
    logger.info(f"Executing custom action: {payload}")
    # 实现动作逻辑
```

---

## 🐛 常见问题

### 1. 提示"pyautogui not available"

**解决**：安装 pyautogui
```bash
pip install pyautogui
```

### 2. Chrome 历史读取失败

**原因**：Chrome 正在运行，数据库被锁定

**解决**：已自动处理（复制到临时文件读取）

### 3. 无法关闭某些窗口

**原因**：权限不足

**解决**：以管理员身份运行应用

### 4. LLM API 调用失败

**检查**：
- 网络连接是否正常
- `.env` 文件中的 API 密钥是否正确
- 账户余额是否充足

---

## ⚖️ License

MIT License

---

## 🙏 致谢

感谢以下开源项目：
- **PyQt6**：GUI 框架
- **pywin32**：Windows API
- **pyautogui**：自动化控制
- **腾讯混元**：LLM 服务

---

## 📞 联系方式

- **项目地址**：[GitHub Repository]
- **问题反馈**：[Issues]
- **技术文档**：详见 `TECHNICAL_DOCUMENTATION.md`

---

**版本**：v3.0
**最后更新**：2026-01-13
**作者**：Claude Code Assistant
