"""
FocusGuard v2.0 - Base Monitor Module

定义监控器的抽象基类接口。
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class BaseMonitor(QThread):
    """
    监控器抽象基类。

    所有监控器必须：
    1. 继承此类
    2. 实现 run() 方法（主循环）
    3. 定义 activity_detected Signal (app_name, window_title, url)
    4. 实现 stop() 方法（优雅关闭）
    5. 异常不能导致线程退出

    注意：由于 QThread 已有自己的元类，这里不使用 ABCMeta。
    子类必须重写 run() 方法。
    """

    # Signal: 检测到新活动时发出
    # 参数：
    #   - app_name: 应用程序名称
    #   - window_title: 窗口标题
    #   - url: URL（如果有，如 Chrome/Edge，可为空字符串）
    activity_detected = pyqtSignal(str, str, str)

    def __init__(self, parent: Optional[QThread] = None) -> None:
        """
        初始化监控器。

        Args:
            parent: 父 QThread
        """
        super().__init__(parent)
        self._running = False
        logger.info(f"{self.__class__.__name__} initialized")

    def run(self) -> None:
        """
        主监控循环（子类必须实现）。

        要求：
        1. 设置 self._running = True
        2. 在循环中检查 self._running
        3. 检测到活动时发出 activity_detected Signal
        4. 异常不能退出循环，只记录日志
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run() method")

    def stop(self) -> None:
        """
        请求停止监控（优雅关闭）。

        子类可以重写此方法以添加额外的清理逻辑。
        """
        logger.info(f"{self.__class__.__name__} stop requested")
        self._running = False

        # 等待线程结束（最多 5 秒）
        self.wait(5000)
        if self.isRunning():
            logger.warning(f"{self.__class__.__name__} did not stop within timeout")

    def is_monitoring(self) -> bool:
        """
        检查监控器是否正在运行。

        Returns:
            bool: 是否正在监控
        """
        return self._running and self.isRunning()
