# FocusGuard - AI专注力监督工具

## ✅ 监控功能 + 图形界面 + 浏览器URL追踪

### 🆕 最新功能：浏览器URL监控

不仅可以监控应用程序，**还能监控访问的具体网站！**

**支持浏览器：**
- ✅ Google Chrome
- ✅ Microsoft Edge

**监控信息：**
- 应用程序名称
- 窗口标题
- **访问的URL**（新功能！）
- **网页标题**（新功能！）
- 访问时间

---

### 🖥️ 图形界面版本（推荐）

#### 启动GUI应用
双击运行 `python/run_gui.bat`

或在命令行中：
```bash
cd python
python ui/main_window.py
```

**功能包括：**
- ✅ 实时活动窗口显示
- ✅ 浏览器URL追踪（新！）
- ✅ 一键启动/停止监控
- ✅ 活动历史表格（包含URL列）
- ✅ 统计信息展示
- ✅ 自动保存到数据库

### 📟 命令行版本

#### 启动命令行监控
双击运行 `python/start_monitoring.bat`

或在命令行中：
```bash
cd python
python quick_test.py
```

#### 测试当前窗口
```bash
cd python
python test_now.py
```

---

## 📁 项目结构

```
FocusGuard/
├── python/                    # Python版本
│   ├── ui/                   # 🆕 图形界面
│   │   └── main_window.py    # PyQt6主窗口
│   ├── monitors/             # 监控模块
│   │   ├── windows_monitor.py      # Windows窗口监控
│   │   └── chrome_monitor.py       # 🆕 浏览器历史监控
│   ├── storage/              # 数据存储
│   │   ├── database.py
│   │   └── activity_repository.py
│   ├── services/             # AI服务
│   │   └── llm_service.py
│   ├── run_gui.bat           # 🆕 GUI启动脚本
│   ├── start_monitoring.bat  # 命令行监控
│   ├── requirements.txt      # 依赖列表
│   ├── UI_GUIDE.md           # GUI使用指南
│   └── BROWSER_MONITORING_GUIDE.md  # 🆕 浏览器监控指南
├── docs/                     # 文档
├── README.md                 # 本文件
└── CLAUDE.md                 # 项目详细说明
```

---

## 📊 数据库位置

所有活动数据保存在：
```
C:\Users\你的用户名\.focusguard\data\focusguard.db
```

使用 **DB Browser for SQLite** 打开查看。

---

## 🎯 已完成功能

- ✅ Windows活动窗口监控
- ✅ **浏览器URL追踪**（Chrome/Edge）🆕
- ✅ **网页标题记录** 🆕
- ✅ PyQt6图形界面
- ✅ 实时检测窗口切换
- ✅ 数据库记录保存（包含URL）
- ✅ 应用统计查询
- ✅ 活动历史展示（带URL列）
- ⏳ 腾讯混元AI适配器（待配置）

---

## 🔧 依赖要求

```bash
pip install pywin32 psutil PyQt6 requests tencentcloud-sdk-python
```

或运行：
```bash
cd python
pip install -r requirements.txt
```

---

## 💡 使用指南

### 图形界面（推荐）
1. 双击 `python/run_gui.bat`
2. 点击"启动监控"按钮
3. 切换窗口查看实时更新
4. 查看活动历史表格

### 命令行版本
```bash
cd python
python quick_test.py  # 实时监控
python test_now.py    # 测试当前窗口
```

---

## 📝 下一步计划

- [x] PyQt6 图形界面 ✅
- [ ] AI专注力判断
- [ ] 规则引擎
- [ ] 对话管理
- [ ] 打包成exe

---

## 🔑 配置AI密钥（可选）

如果要使用AI判断功能，需要设置腾讯云密钥：

```bash
# Windows CMD
set TENCENT_SECRET_ID=你的SecretId
set TENCENT_SECRET_KEY=你的SecretKey

# Windows PowerShell
$env:TENCENT_SECRET_ID="你的SecretId"
$env:TENCENT_SECRET_KEY="你的SecretKey"
```

获取密钥: https://console.cloud.tencent.com/cam/capi

---

## 隐私政策

- 所有数据存储在本地
- 不收集个人隐私信息
- 活动记录仅用于判断专注状态

---

**最后更新**: 2025-01-10
**版本**: v1.2 - 浏览器URL监控完成
**许可证**: MIT
