"""
FocusGuard v2.0 - Chrome Monitor Module

监控 Chrome/Edge 浏览历史记录。

关键挑战：Chrome 运行时数据库被 EXCLUSIVE 锁定，需要复制到临时文件读取。
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import tempfile
from typing import Optional

from PyQt6.QtCore import QThread, QTimer

# 相对导入
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)

# Chrome/Edge 关键词
BROWSER_KEYWORDS = ["chrome", "edge", "chromium"]


def get_chrome_history_path() -> Optional[str]:
    """
    动态获取 Chrome History 文件路径。

    Returns:
        Optional[str]: History 文件路径，如果不存在则返回 None
    """
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if not local_app_data:
        return None

    # 尝试 Chrome
    chrome_path = os.path.join(
        local_app_data,
        r'Google\Chrome\User Data\Default\History'
    )
    if os.path.exists(chrome_path):
        return chrome_path

    # 尝试 Edge
    edge_path = os.path.join(
        local_app_data,
        r'Microsoft\Edge\User Data\Default\History'
    )
    if os.path.exists(edge_path):
        return edge_path

    return None


def read_chrome_history(
    history_path: str,
    limit: int = 1,
    time_threshold_seconds: int = 30
) -> Optional[dict]:
    """
    从 Chrome History 文件读取最近的 URL。

    策略：
    1. 复制数据库到临时文件（避免 EXCLUSIVE 锁）
    2. 以只读模式打开副本
    3. 只读取最近 N 秒内访问的 URL（过滤历史记录）
    4. 读取完成后删除临时文件

    Args:
        history_path: Chrome History 文件路径
        limit: 读取的 URL 数量
        time_threshold_seconds: 时间阈值（秒），只返回此时间内访问的 URL

    Returns:
        Optional[dict]: 最近的历史记录，失败时返回 None
    """
    temp_fd = None
    temp_path = None

    try:
        # 创建临时文件（delete=False，需要手动清理）
        temp_fd, temp_path = tempfile.mkstemp(suffix='.sqlite', prefix='chrome_history_')
        os.close(temp_fd)  # 关闭文件描述符，shutil.copy2 需要路径

        # 复制数据库到临时文件
        shutil.copy2(history_path, temp_path)

        # 以只读模式打开副本
        conn = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Chrome 时间戳是自 1601-01-01 以来的微秒数
        # 计算时间阈值
        import datetime
        chrome_epoch = datetime.datetime(1601, 1, 1)
        current_time = datetime.datetime.now()
        threshold_time = current_time - datetime.timedelta(seconds=time_threshold_seconds)

        # 转换为 Chrome 时间戳（微秒）
        threshold_chrome_time = int((threshold_time - chrome_epoch).total_seconds() * 1000000)

        # 查询最近的 URL（按最后访问时间排序，并过滤时间）
        cursor = conn.execute(
            """
            SELECT url, title, last_visit_time
            FROM urls
            WHERE last_visit_time >= ?
            ORDER BY last_visit_time DESC
            LIMIT ?
            """,
            (threshold_chrome_time, limit)
        )

        rows = cursor.fetchall()
        conn.close()

        if rows:
            return {
                "url": rows[0]["url"],
                "title": rows[0]["title"],
            }

        # 如果没有找到最近的 URL，返回 None
        logger.debug(f"No URLs found in the last {time_threshold_seconds} seconds")
        return None

    except Exception as e:
        logger.warning(f"Failed to read Chrome history: {e}", exc_info=True)
        return None

    finally:
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                logger.warning(f"Failed to delete temp file: {temp_path}")


class ChromeMonitor(BaseMonitor):
    """
    Chrome/Edge 历史记录监控器。

    功能：
    - 仅在窗口标题包含浏览器关键词时触发
    - 复制数据库到临时文件读取（避免锁冲突）
    - 发出 activity_detected Signal（附带 URL）

    注意：
    - 不使用轮询，而是通过 QTimer 按需触发
    - 由外部（如 WindowsMonitor）调用 check_history()
    """

    def __init__(self, parent: Optional[QThread] = None) -> None:
        """
        初始化 Chrome 监控器。

        Args:
            parent: 父 QThread
        """
        super().__init__(parent)

        self._history_path: Optional[str] = None
        self._last_url: Optional[str] = None

        # 尝试自动检测 History 路径
        self._history_path = get_chrome_history_path()
        if self._history_path:
            logger.info(f"ChromeMonitor initialized with path: {self._history_path}")
        else:
            logger.warning("Chrome/Edge history file not found, monitor will be disabled")

    def run(self) -> None:
        """
        主循环（本监控器不使用主动轮询，因此此方法为空实现）。

        使用方式：
        - 由外部调用 check_history(app_name, window_title) 按需触发
        - 仅当窗口标题包含浏览器关键词时才读取历史
        """
        self._running = True
        # ChromeMonitor 不使用主动轮询，而是按需触发
        # 因此 run() 方法不执行任何操作
        # 但为了保持 QThread 的完整性，我们需要启动事件循环

        # 启动定时器保持线程活跃（不执行任何操作）
        timer = QTimer(self)
        timer.timeout.connect(lambda: None)  # 空操作
        timer.start(60000)  # 每 60 秒触发一次（仅保持线程活跃）

        # 启动事件循环
        self.exec()

        logger.info("ChromeMonitor thread stopped gracefully")

    def check_history(self, app_name: str, window_title: str) -> None:
        """
        检查 Chrome 历史（由外部调用）。

        只读取最近 30 秒内访问的 URL，避免误判历史记录。

        Args:
            app_name: 应用程序名称
            window_title: 窗口标题
        """
        if not self._running:
            return

        if not self._history_path:
            return

        # 检查是否为浏览器窗口
        app_lower = app_name.lower()
        title_lower = window_title.lower()

        is_browser = any(keyword in app_lower or keyword in title_lower
                         for keyword in BROWSER_KEYWORDS)

        if not is_browser:
            return

        try:
            # 读取最近的 URL（只读取最近 3 秒内访问的，避免误判历史记录）
            history = read_chrome_history(
                self._history_path,
                limit=1,
                time_threshold_seconds=3  # 缩短到3秒，只检测当前正在浏览的页面
            )
            if not history:
                logger.debug("No recent Chrome history found (within 3 seconds)")
                return

            current_url = history["url"]

            # 新增：URL 验证优先于窗口标题验证
            # 只有真正访问 bilibili.com 才触发检测
            if "bilibili.com" in current_url.lower():
                # 真正的 Bilibili 访问 - 触发检测
                if current_url != self._last_url:
                    self.activity_detected.emit(app_name, window_title, current_url)
                    self._last_url = current_url
                    logger.debug(f"Chrome history detected: {current_url[:80]}...")
            elif "bilibili" in title_lower:
                # 窗口标题包含 "Bilibili" 但 URL 不包含 bilibili.com
                # 例如：GitHub Copilot 相关的页面标题含有 "Bilibili"
                logger.debug(f"Window title contains 'Bilibili' but URL is {current_url[:80]}, ignoring")
                # 不触发检测
            else:
                # 正常检测其他 URL
                if current_url != self._last_url:
                    self.activity_detected.emit(app_name, window_title, current_url)
                    self._last_url = current_url
                    logger.debug(f"Chrome history detected: {current_url[:80]}...")

        except Exception as e:
            logger.warning(f"ChromeMonitor error: {e}", exc_info=True)

    def stop(self) -> None:
        """
        停止监控。
        """
        super().stop()
        self.quit()  # 退出事件循环
