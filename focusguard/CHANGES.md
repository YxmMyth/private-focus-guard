# FocusGuard v2.0 - 修改日志

**最后更新**: 2026-01-12 00:45

## 重要说明
本文档记录了实际代码与原始设计文档（claude.md）之间的关键差异。下次继续开发时，**请先阅读本文档**，避免重复修改已修复的内容。

---

## 1. 关键架构变更

### 1.1 LLM服务改为同步调用 ⚠️ 重要

**原设计**（claude.md）：
- 使用 `aiohttp` 进行异步HTTP请求
- `llm_service.py` 中的所有方法都是 `async def`
- 在 `main.py` 中使用 `asyncio.run()` 调用

**实际实现**（已修改）：
- 使用 `requests` 进行同步HTTP请求
- `llm_service.py` 中的所有方法都是普通 `def`
- 在 `main.py` 中直接调用，无需 `asyncio.run()`

**原因**：
- `asyncio.run()` 在QThread中会导致事件循环冲突
- `aiohttp` 的异步事件循环与PyQt6的QThread不兼容
- 同步requests更简单可靠

**相关文件**：
- `services/llm_service.py` - 第6-16行（import部分）
- `services/llm_service.py` - 第301-537行（所有方法都是同步的）
- `main.py` - 第143-150行（直接调用，无asyncio.run）

### 1.2 对话框显示改用Signal ⚠️ 重要

**原设计**：
```python
QTimer.singleShot(0, lambda: self._dialog.show_with_options(analysis, options))
```

**实际实现**（已修改）：
```python
# SupervisionEngine中定义Signal
show_dialog_requested = pyqtSignal(str, list)

# 触发时emit
self.show_dialog_requested.emit(analysis, options)

# FocusGuardApp中连接
self._engine.show_dialog_requested.connect(self._dialog.show_with_options)
```

**原因**：
- `QTimer.singleShot()` 需要事件循环才能工作
- SupervisionEngine QThread没有运行事件循环
- 使用Signal是线程安全的Qt标准做法

**相关文件**：
- `main.py` - 第58行（Signal定义）
- `main.py` - 第206行（emit调用）
- `main.py` - 第306行（Signal连接）

### 1.3 等待函数改用time.sleep() ⚠️ 重要

**原设计**：
```python
QThread.sleep(int(sleep_time * 1000))
```

**实际实现**（已修改）：
```python
import time as time_module
time_module.sleep(sleep_time)
```

**原因**：
- `QThread.sleep()` 在没有事件循环的QThread中不工作
- 会导致while循环卡住，SupervisionEngine只运行一次

**相关文件**：
- `main.py` - 第10行（import time as time_module）
- `main.py` - 第197行（使用time_module.sleep）

---

## 2. 其他重要修复

### 2.1 防止无限递归

**问题**：ChromeMonitor触发时，会再次调用ChromeMonitor，导致无限循环

**解决方案**：
```python
# FocusGuardApp中添加标志
self._processing_activity = False

def _on_activity_detected(self, ...):
    if self._processing_activity:
        return
    self._processing_activity = True
    try:
        # 处理活动...
    finally:
        self._processing_activity = False
```

**相关文件**：
- `main.py` - 第309行（标志初始化）
- `main.py` - 第322-347行（re-entry guard）

### 2.2 系统Prompt转义

**问题**：SYSTEM_PROMPT中的JSON示例花括号与`.format()`冲突

**解决方案**：
- 所有 `{` 改为 `{{`
- 所有 `}` 改为 `}}`

**相关文件**：
- `services/llm_service.py` - 第90-110行

### 2.3 腾讯混元API签名

**问题**：签名失败，API返回认证错误

**解决方案**：
- 按照腾讯云官方文档实现TC3-HMAC-SHA256签名
- canonical_headers只包含 `content-type` 和 `host`
- 使用UTC时间：`time.gmtime()`
- 添加X-TC-Region头

**相关文件**：
- `services/llm_service.py` - 第157-242行（_sign_hunyuan方法）

### 2.4 腾讯混元消息角色

**问题**：使用 `"system"` 角色导致API报错

**解决方案**：
- 将 `"system"` 改为 `"user"`

**相关文件**：
- `services/llm_service.py` - 第366-367行

---

## 3. 依赖库变更

### requirements.txt

**原设计**：
```
aiohttp==3.9.5
```

**实际需要**（如果requirements.txt还没改）：
```
requests==2.31.0
```

**注意**：`requests` 通常已预装，版本 2.32.5 也可以

---

## 4. 下次开发注意事项

### ✅ 不要做的事

1. **不要**将llm_service.py改回async/await
2. **不要**在main.py中使用`asyncio.run()`
3. **不要**将对话框显示改回`QTimer.singleShot()`
4. **不要**将等待函数改回`QThread.sleep()`
5. **不要**移除`_processing_activity`标志
6. **不要**将SYSTEM_PROMPT中的`{{`改回`{`

### ✅ 可以继续开发的功能

1. **干预对话框UI优化** - 当前对话框已能显示，可以美化
2. **学习历史记录** - `learning_history`表已创建但未使用
3. **Snooze到期回调** - ActionManager中已有Timer，可以测试
4. **白名单管理** - 临时白名单功能已实现，可以添加持久化
5. **严格模式增强** - 检测频率已改为10秒，可以测试
6. **Chrome历史记录** - 已实现，可以优化URL提取

---

## 5. 测试验证

### 当前工作状态（2026-01-12 00:45）

```log
2026-01-12 00:45:13 - SupervisionEngine check cycle started
2026-01-12 00:45:21 - Distracted behavior detected (confidence: 85%)
2026-01-12 00:45:51 - SupervisionEngine check cycle started  ✅ 30秒后继续
2026-01-12 00:45:59 - Distracted behavior detected (confidence: 75%)
```

**验证点**：
- ✅ SupervisionEngine持续运行
- ✅ 每30秒检查一次
- ✅ LLM API正常调用
- ✅ 检测到分心时触发对话框
- ✅ 用户可以操作并更新信任分

---

## 6. 文件状态

| 文件 | 状态 | 说明 |
|------|------|------|
| `services/llm_service.py` | ✅ 已修改 | 同步requests，无async |
| `main.py` | ✅ 已修改 | 无asyncio，用time.sleep |
| `requirements.txt` | ⚠️ 需检查 | 确认是requests而非aiohttp |
| `.env` | ✅ 已配置 | 腾讯混元API密钥 |
| `diagnose.py` | ✅ 可用 | 调试工具 |

---

## 7. 调试技巧

### 查看SupervisionEngine是否持续运行
```bash
python main.py 2>&1 | grep "SupervisionEngine check cycle"
```
应该看到多条日志，每隔约30秒一条

### 查看是否调用LLM API
```bash
python main.py 2>&1 | grep "Distracted behavior detected"
```

### 查看数据库状态
```bash
python diagnose.py
```

---

**最后提醒**：如果claude.md中的设计与本文档冲突，**以本文档为准**！本文档记录的是实际可工作的代码状态。
