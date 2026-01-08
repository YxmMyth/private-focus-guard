# FocusGuard - AI专注力监督工具

一个由AI驱动的自我监督工具，帮助您保持专注，提高工作效率。

## 功能特性

- 🖥️ **Windows应用监控** - 实时监控当前活动窗口
- 🌐 **Chrome浏览器监控** - 追踪访问的网站
- 🤖 **AI智能判断** - 使用腾讯混元lite分析活动是否分心
- 💬 **智能对话干预** - 与AI辩论，判断真实意图
- ⚙️ **规则引擎** - 黑名单/白名单快速判断
- 💾 **本地存储** - 所有数据存储在本地SQLite数据库

## 技术栈

- **桌面应用**: Electron + React + TypeScript
- **数据库**: SQLite (better-sqlite3)
- **AI模型**: 腾讯混元lite (免费)
- **状态管理**: Zustand
- **构建工具**: Vite + Electron Builder

## 开发进度

### MVP (4周)
- [x] 项目初始化
- [ ] 核心数据模型
- [ ] Windows监控实现
- [ ] Chrome History读取
- [ ] 腾讯混元集成
- [ ] 规则引擎
- [ ] UI界面
- [ ] 对话功能

## 快速开始

### 安装依赖
```bash
npm install
```

### 开发模式
```bash
npm run electron:dev
```

### 构建应用
```bash
npm run electron:build
```

## 配置

首次运行需要配置腾讯混元API密钥：
1. 访问 [腾讯云控制台](https://console.cloud.tencent.com/hunyuan) 获取API密钥
2. 在应用设置中输入密钥

## 隐私政策

- 所有数据存储在本地
- 不收集个人隐私信息
- 浏览器历史仅用于判断专注状态

## 许可证

MIT
