# FocusGuard 项目关键信息


## 🎯 核心功能

通过监控电脑活动并使用AI判断用户是否分心，帮助保持专注：
- 🖥️ 监控Windows活动窗口
- 🌐 监控Chrome浏览器访问记录
- 🤖 使用腾讯混元AI智能判断
- 💬 弹窗对话干预，与用户辩论
- 📊 本地存储所有数据（SQLite）

## 🛠️ 技术栈

### 必须学习的技术
1. **TypeScript** - JavaScript的超集，添加类型系统
2. **Electron** - 用Web技术构建桌面应用
3. **React** - Facebook的前端UI框架
4. **Vite** - 新一代前端构建工具
5. **SQLite (better-sqlite3)** - 嵌入式数据库
6. **腾讯混元API** - 腾讯的AI模型服务

### 推荐学习顺序
```
1. TypeScript基础 (2-3天)
   ├─ 类型系统
   ├─ 接口和类型别名
   └─ 泛型

2. React基础 (3-5天)
   ├─ 组件化思想
   ├─ JSX语法
   ├─ Hooks (useState, useEffect)
   └─ 组件通信

3. Electron入门 (2-3天)
   ├─ 主进程 vs 渲染进程
   ├─ IPC通信
   └─ Node.js集成

4. Vite构建 (1-2天)
   ├─ 项目配置
   └─ 开发/生产环境

5. SQLite数据库 (2-3天)
   ├─ SQL基础
   ├─ better-sqlite3包使用
   └─ 数据库设计

6. 腾讯混元API (1-2天)
   ├─ API文档阅读
   ├─ Node.js SDK使用
   └─ 提示词工程
```

### 学习资源推荐

**TypeScript**:
- 官方文档: https://www.typescriptlang.org/docs/
- 中文教程: https://ts.xcatliu.com/

**React**:
- 官方文档: https://react.dev/learn
- 菜鸟教程: https://www.runoob.com/react/react-tutorial.html

**Electron**:
- 官方文档: https://www.electronjs.org/docs/latest/
- 中文教程: https://www.w3cschool.cn/electronmanual/

**SQLite**:
- SQL基础: https://www.runoob.com/sql/sql-tutorial.html
- better-sqlite3: https://github.com/WiseLibs/better-sqlite3

**腾讯混元**:
- API文档: https://cloud.tencent.com/document/product/1729/104753
- SDK文档: https://cloud.tencent.com/document/sdk/Java

## 📁 项目结构

```
E:\selfsuperviseagent\
├── src/
│   ├── domain/              ✅ 核心数据模型（已完成）
│   │   ├── activity.ts      # 活动数据定义
│   │   ├── focus-goal.ts    # 专注目标定义
│   │   └── rule.ts          # 规则引擎定义
│   │
│   ├── storage/             ✅ 数据存储层（已完成）
│   │   ├── database.ts      # SQLite数据库管理
│   │   └── repositories/    # 数据访问层
│   │
│   ├── services/            ✅ 业务服务（已完成）
│   │   └── llm/            # AI相关
│   │       ├── adapter.ts  # LLM接口
│   │       └── hunyuan.ts  # 腾讯混元实现
│   │
│   ├── main/               ✅ Electron主进程（已完成）
│   │   ├── index.ts        # 主进程入口
│   │   └── ipc/handlers.ts # IPC通信
│   │
│   └── renderer/           ✅ React前端（已完成80%）
│       ├── App.tsx         # 主应用
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   └── Settings.tsx
│       └── index.css
│
├── docs/
│   └── PROGRESS.md         # 详细进度报告
│
├── package.json            # 项目配置
├── tsconfig.json           # TypeScript配置
├── vite.config.ts          # Vite配置
└── README.md               # 项目说明
```

## 🚀 如何继续开发

### 1. 安装依赖
```bash
cd E:\selfsuperviseagent
npm install
```

⚠️ **注意**: 以下包可能需要额外处理：
- `better-sqlite3` - 需要编译，可能需要安装构建工具
- `@tencentcloud/hunyuan-sdk-nodejs` - 腾讯云SDK
- `active-win` - Windows窗口监控

### 2. 开发模式
```bash
npm run electron:dev
```

### 3. 下一步任务（Week 2）

**优先级1 - 监控功能**:
- 实现 `src/main/monitors/windows-monitor.ts`
  - 使用 `active-win` 包获取当前窗口
  - 获取进程名称和窗口标题

- 实现 `src/main/monitors/chrome-monitor.ts`
  - 找到Chrome用户数据目录
  - 复制并读取History SQLite
  - 提取最近访问的URL

**优先级2 - 判断服务**:
- 实现 `src/services/focus-guard.ts`
  - 协调规则引擎和LLM
  - 编排判断流程

- 实现 `src/services/dialog-manager.ts`
  - 多轮对话逻辑
  - 对话历史管理

**优先级3 - UI完善**:
- 实现 `src/renderer/components/InterventionDialog.tsx`
  - 弹窗对话UI
  - 用户输入处理

## 📊 当前进度

### ✅ 已完成（Week 1 - 100%）
- [x] 项目初始化和配置
- [x] 核心数据模型（3个文件）
- [x] SQLite数据库层（4个文件）
- [x] Electron主进程框架（2个文件）
- [x] LLM适配器（2个文件）
- [x] React基础UI（6个文件）

**共完成**: 20+ 个核心文件

### ⏳ 待实现（Week 2-4 - 75%）
- [ ] Windows监控功能
- [ ] Chrome History读取
- [ ] 规则引擎服务
- [ ] 专注守卫服务
- [ ] 对话管理器
- [ ] 干预对话框组件
- [ ] Preload脚本
- [ ] Vite配置优化

## 🔑 关键设计决策

1. **平台**: Windows only (MVP)，后期扩展跨平台
2. **LLM**: 腾讯混元lite（完全免费）
3. **浏览器监控**: Chrome History读取（15-30秒延迟）
4. **架构**: 简化单包结构（非monorepo）
5. **数据存储**: 本地SQLite（保护隐私）

## 📝 重要文件说明

### 核心文件（必须理解）
1. **src/domain/activity.ts**
   - 定义Activity接口（用户活动的数据结构）
   - 浏览器活动、应用活动、系统活动

2. **src/storage/database.ts**
   - SQLite数据库管理
   - 6张表的Schema定义

3. **src/services/llm/hunyuan.ts**
   - 腾讯混元适配器
   - AI判断和对话功能

4. **src/main/ipc/handlers.ts**
   - 主进程和渲染进程的通信桥梁
   - 12个IPC API定义

5. **src/renderer/App.tsx**
   - React主应用
   - 路由和导航

## ⚠️ 注意事项

### 存储空间问题
- node_modules 可能占用几百MB
- 建议将项目移到非系统盘（如D盘）
- 或者使用 npm 的全局缓存设置

### 环境要求
- Node.js 18+
- npm 9+
- Windows 10/11
- TypeScript 5+

### API密钥
- 需要腾讯云账号
- 获取SecretId和SecretKey
- 访问: https://console.cloud.tencent.com/cam/capi

## 📚 学习检查清单

使用这个清单跟踪学习进度：

### TypeScript □
- [ ] 基础类型（string, number, boolean等）
- [ ] 接口（interface）
- [ ] 类型别名（type）
- [ ] 泛型
- [ ] 模块系统

### React □
- [ ] JSX语法
- [ ] 组件（函数组件）
- [ ] Props和State
- [ ] Hooks (useState, useEffect)
- [ ] 事件处理

### Electron □
- [ ] 主进程 vs 渲染进程
- [ ] IPC通信
- [ ] 窗口管理
- [ ] 安全性（Context Isolation）

### SQLite □
- [ ] SQL基础语法
- [ ] CRUD操作
- [ ] 索引和约束
- [ ] better-sqlite3包

### 腾讯混元API □
- [ ] API认证
- [ ] 调用接口
- [ ] 提示词工程
- [ ] 响应解析

## 🔗 有用的链接

- **项目进度**: `docs/PROGRESS.md`
- **实施计划**: `E:\selfsuperviseagent\`（查看本目录的plan文件）
- **GitHub**: （如果已上传）
- **腾讯云控制台**: https://console.cloud.tencent.com/

## 💡 开发建议

1. **先学习，再开发** - 至少掌握TypeScript和React基础
2. **小步快跑** - 每次只实现一个小功能
3. **多测试** - 每完成一个功能就测试
4. **看文档** - 遇到问题先查官方文档
5. **写注释** - 给代码添加清晰的注释

## 🆘 常见问题

**Q: 项目能直接运行吗？**
A: 不能。还需要实现监控功能、Preload脚本等核心部分。

**Q: 需要多长时间学会？**
A: 如果有JavaScript基础，2-3周可以入门。如果没有，可能需要1-2个月。

**Q: 可以用其他AI吗？**
A: 可以。项目设计为可插拔架构，后期可以接入Claude、GPT等。

**Q: 数据会上传到云端吗？**
A: 不会。所有数据都存在本地SQLite数据库中。

**Q: 腾讯混元免费吗？**
A: hunyuan-lite模型完全免费，有调用次数限制但够个人使用。
