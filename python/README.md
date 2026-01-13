# FocusGuard Python - AI专注力监督工具

## 📌 项目简介

FocusGuard 是一个帮助你保持专注的桌面应用。它会监控你的电脑活动，并使用AI判断你是否在分心，通过智能对话帮助你回到专注状态。

### 当前状态：核心功能已完成 ✅

- ✅ Windows活动窗口监控
- ✅ 本地SQLite数据库存储
- ✅ 腾讯混元AI适配器
- ✅ 基础测试程序

## 🚀 快速开始

### 安装依赖

```bash
cd python
pip install -r requirements.txt
```

### 运行测试

```bash
python main.py
```

你会看到：
- 实时监控窗口切换
- 活动数据保存到数据库
- 统计信息显示

按 `Ctrl+C` 停止监控。

## 📁 项目结构

```
python/
├── monitors/
│   └── windows_monitor.py     # Windows窗口监控
├── storage/
│   ├── database.py            # SQLite数据库管理
│   └── activity_repository.py # 活动数据仓库
├── services/
│   └── llm_service.py         # 腾讯混元AI服务
├── ui/                         # PyQt6 UI (待开发)
├── config/                     # 配置文件 (待开发)
├── main.py                     # 主程序
└── requirements.txt            # 依赖列表
```

## 🛠️ 技术栈

- **Python 3.10+**
- **PyQt6** - 桌面UI框架
- **pywin32** - Windows API
- **psutil** - 进程信息
- **sqlite3** - 数据库（Python内置）
- **tencentcloud-sdk-python** - 腾讯混元AI

## 🔑 配置AI密钥

### 方法1：环境变量（推荐）

```bash
# Windows PowerShell
$env:TENCENT_SECRET_ID="你的SecretId"
$env:TENCENT_SECRET_KEY="你的SecretKey"

# Windows CMD
set TENCENT_SECRET_ID=你的SecretId
set TENCENT_SECRET_KEY=你的SecretKey
```

### 方法2：代码中硬编码（仅测试）

```python
# 在 main.py 中添加
adapter = create_hunyuan_adapter(
    secret_id="你的SecretId",
    secret_key="你的SecretKey"
)
```

## 📊 数据存储

所有数据存储在本地SQLite数据库：
```
C:\Users\你的用户名\.focusguard\data\focusguard.db
```

## 🎯 下一步开发

1. **创建PyQt6 UI** - 图形界面
2. **规则引擎** - 自动判断分心活动
3. **对话管理器** - 多轮对话逻辑
4. **打包成exe** - PyInstaller打包

## 📝 开发计划

- [x] Windows监控模块
- [x] 数据库层
- [x] LLM适配器
- [x] 基础测试程序
- [ ] PyQt6 UI
- [ ] 规则引擎服务
- [ ] 对话管理器
- [ ] 打包配置

## 🔍 测试监控功能

运行 `main.py` 后：
1. 切换到不同的应用程序（Chrome、VSCode等）
2. 查看控制台输出的监控信息
3. 检查数据库中的活动记录

## 📦 打包成exe

```bash
# 安装PyInstaller
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed main.py

# exe文件在 dist/ 目录
```

## ⚠️ 注意事项

1. **隐私保护**：所有数据存储在本地，不上传云端
2. **AI免费**：腾讯混元lite模型完全免费
3. **Windows only**：当前仅支持Windows

## 🆘 常见问题

**Q: pywin32安装失败？**
A: 需要安装Visual C++ Build Tools

**Q: 监控不到活动？**
A: 确保以管理员权限运行

**Q: 数据库在哪里？**
A: `C:\Users\你的用户名\.focusguard\data\focusguard.db`

## 📞 获取帮助

遇到问题？查看原项目文档：
```
E:\selfsuperviseagent\CLAUDE.md
```

---

**最后更新**: 2025-01-10
**项目状态**: 核心功能已完成，UI开发中
