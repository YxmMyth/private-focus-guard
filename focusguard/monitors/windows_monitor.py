"""
FocusGuard v2.0 - Windows Monitor Module

监控 Windows 前台窗口，每 3 秒轮询一次窗口标题。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

import win32gui
import win32process
from PyQt6.QtCore import QThread

# 相对导入
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


def sanitize_title(title: str) -> str:
    """
    移除窗口标题中的零宽字符和非打印字符，并修复中文编码。

    Args:
        title: 原始窗口标题

    Returns:
        str: 清理后的标题
    """
    # 处理可能的编码问题
    if isinstance(title, bytes):
        try:
            title = title.decode('utf-8')
        except UnicodeDecodeError:
            try:
                title = title.decode('gbk')
            except UnicodeDecodeError:
                title = title.decode('utf-8', errors='ignore')

    # 确保是字符串类型
    if not isinstance(title, str):
        title = str(title)

    # 移除零宽字符、控制字符、不间断空格等
    title = re.sub(r'[\u200b-\u200f\u2028-\u202f\u00a0\x00-\x1f]', '', title)

    return title.strip()


def get_app_name_from_window(hwnd: int) -> Optional[str]:
    """
    根据窗口句柄获取应用程序名称。

    Args:
        hwnd: 窗口句柄

    Returns:
        Optional[str]: 应用程序名称（如 "chrome.exe"），失败时返回 None
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        import psutil
        process = psutil.Process(pid)
        return process.name()
    except Exception:
        return None


class WindowsMonitor(BaseMonitor):
    """
    Windows 窗口监控器。

    功能：
    - 每 3 秒轮询一次前台窗口
    - 提取应用程序名称和窗口标题
    - 发出 activity_detected Signal
    - 自动清理标题中的零宽字符
    """

    def __init__(self, poll_interval: int = 3, parent: Optional[QThread] = None) -> None:
        """
        初始化 Windows 监控器。

        Args:
            poll_interval: 轮询间隔（秒），默认 3 秒
            parent: 父 QThread
        """
        super().__init__(parent)

        self._poll_interval = poll_interval
        self._last_app_name: Optional[str] = None
        self._last_window_title: Optional[str] = None

        logger.info(f"WindowsMonitor initialized with {poll_interval}s interval")

    def run(self) -> None:
        """
        主监控循环。

        逻辑：
        1. 获取前台窗口句柄
        2. 提取应用名称和窗口标题
        3. 如果有变化，发出 Signal
        4. 异常不会导致线程退出
        """
        self._running = True
        logger.info("WindowsMonitor thread started")

        while self._running:
            try:
                # 获取前台窗口句柄
                hwnd = win32gui.GetForegroundWindow()
                if hwnd == 0:
                    logger.debug("No foreground window detected")
                    time.sleep(self._poll_interval)
                    continue

                # 获取窗口标题
                raw_title = win32gui.GetWindowText(hwnd)
                window_title = sanitize_title(raw_title) if raw_title else ""

                # 获取应用程序名称
                app_name = get_app_name_from_window(hwnd)

                if not app_name:
                    logger.debug(f"Failed to get app name for window: {window_title[:30]}...")
                    time.sleep(self._poll_interval)
                    continue

                # 检查是否有变化（避免重复记录）
                if (app_name != self._last_app_name or
                    window_title != self._last_window_title):

                    self.activity_detected.emit(app_name, window_title, None)

                    self._last_app_name = app_name
                    self._last_window_title = window_title

                    logger.debug(f"Activity detected: {app_name} - {window_title[:50]}")

            except Exception as e:
                # 监控异常不应导致线程退出
                logger.warning(f"WindowsMonitor error (will retry): {e}", exc_info=True)

            # 等待下一次轮询
            # 使用可中断的 sleep，通过检查 _running
            remaining_time = self._poll_interval
            while remaining_time > 0 and self._running:
                sleep_time = min(0.5, remaining_time)  # 最多睡 0.5 秒
                time.sleep(sleep_time)
                remaining_time -= sleep_time

        logger.info("WindowsMonitor thread stopped gracefully")

    def stop(self) -> None:
        """
        停止监控。
        """
        super().stop()

    def set_poll_interval(self, seconds: int) -> None:
        """
        动态设置轮询间隔（用于调试或动态调整）。

        Args:
            seconds: 轮询间隔（秒）
        """
        if seconds < 1:
            logger.warning(f"Poll interval too short: {seconds}s, keeping 1s minimum")
            seconds = 1

        self._poll_interval = seconds
        logger.info(f"Poll interval set to {seconds}s")
