"""
FocusGuard v2.0 - 基于上下文感知和用户信任体系的智能桌面监督 Agent

主要模块：
- config: 配置管理
- main: 应用程序入口和核心监控循环
- monitors: 感知层（窗口监控、Chrome 历史记录）
- storage: 数据层（SQLite、数据清理）
- services: 智能层和执行层（LLM 服务、动作管理）
- ui: UI 层（干预对话框）
"""

__version__ = "2.0.0"
__author__ = "FocusGuard Team"

# 导入所有子模块以确保它们在包命名空间中可用
from . import config
from . import monitors
from . import storage
from . import services
from . import ui

from .config import config

__all__ = ["config", "monitors", "storage", "services", "ui"]
