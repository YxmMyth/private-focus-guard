"""
Windows 窗口监控器

作用：
1. 监控 Windows 系统的活动窗口
2. 获取当前活动窗口的信息（应用名、窗口标题、进程ID等）
3. 提供轮询机制，定期检查窗口切换

技术实现：
- 使用 win32gui 获取活动窗口
- 使用 psutil 获取进程详细信息
- 提供防抖机制，避免重复记录相同窗口
"""

import win32gui
import win32process
import psutil
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import threading
import time


@dataclass
class ApplicationActivity:
    """应用活动数据模型"""
    app_name: str
    window_title: str
    process_id: int
    executable_path: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class WindowsMonitor:
    """Windows 监控器类"""

    def __init__(self):
        self.polling_timer = None
        self.last_activity = None
        self.is_polling = False
        self.polling_thread = None
        self.stop_event = threading.Event()

    def get_active_window(self) -> Optional[ApplicationActivity]:
        """
        获取当前活动窗口

        Returns:
            当前活动窗口的信息，如果获取失败返回 None
        """
        try:
            # 获取前台窗口句柄
            hwnd = win32gui.GetForegroundWindow()

            if not hwnd:
                print('[WindowsMonitor] 未检测到活动窗口')
                return None

            # 获取窗口标题（过滤不可打印字符）
            window_title = win32gui.GetWindowText(hwnd)
            # 清理零宽字符和其他不可打印字符
            window_title = ''.join(c for c in window_title if c.isprintable() or c.isspace())

            # 获取进程ID
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)

            # 获取进程信息
            try:
                process = psutil.Process(process_id)
                app_name = process.name()
                executable_path = process.exeecutable() if hasattr(process, 'exeecutable') else ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # 如果无法获取进程信息，使用基本信息
                app_name = f"Process_{process_id}"
                executable_path = ""

            activity = ApplicationActivity(
                app_name=app_name,
                window_title=window_title or "Untitled Window",
                process_id=process_id,
                executable_path=executable_path
            )

            print(f'[WindowsMonitor] 捕获活动窗口: {activity.app_name} - {activity.window_title}')

            return activity

        except Exception as error:
            print(f'[WindowsMonitor] 获取活动窗口失败: {error}')
            return None

    def is_different_activity(self, activity: ApplicationActivity) -> bool:
        """
        判断活动窗口是否发生变化

        Args:
            activity: 当前活动

        Returns:
            是否发生变化
        """
        if not self.last_activity:
            return True

        return (
            activity.app_name != self.last_activity.app_name or
            activity.window_title != self.last_activity.window_title
        )

    def start_polling(self, interval: int = 5, callback=None):
        """
        启动轮询监控

        Args:
            interval: 轮询间隔（秒），默认 5秒
            callback: 每次捕获到新窗口时的回调函数
        """
        if self.is_polling:
            print('[WindowsMonitor] 监控已在运行，先停止现有监控')
            self.stop_polling()

        print(f'[WindowsMonitor] 启动轮询监控，间隔: {interval}秒')

        self.is_polling = True
        self.stop_event.clear()
        self.callback = callback

        # 创建轮询线程
        self.polling_thread = threading.Thread(
            target=self._polling_loop,
            args=(interval,),
            daemon=True
        )
        self.polling_thread.start()

        # 立即执行一次
        self._poll_once()

    def _polling_loop(self, interval: int):
        """轮询循环（在独立线程中运行）"""
        while not self.stop_event.is_set():
            time.sleep(interval)
            if not self.stop_event.is_set():
                self._poll_once()

    def _poll_once(self):
        """单次轮询"""
        try:
            activity = self.get_active_window()

            if activity and self.is_different_activity(activity):
                self.last_activity = activity

                if self.callback:
                    try:
                        self.callback(activity)
                    except Exception as error:
                        print(f'[WindowsMonitor] 回调执行失败: {error}')

        except Exception as error:
            print(f'[WindowsMonitor] 轮询执行失败: {error}')

    def stop_polling(self):
        """停止轮询监控"""
        if not self.is_polling:
            return

        print('[WindowsMonitor] 停止监控')
        self.stop_event.set()
        self.is_polling = False
        self.last_activity = None

        if self.polling_thread:
            self.polling_thread.join(timeout=2)
            self.polling_thread = None

    def is_active(self) -> bool:
        """获取监控状态"""
        return self.is_polling


# 单例
windows_monitor = WindowsMonitor()


# 测试代码
if __name__ == '__main__':
    def test_callback(activity: ApplicationActivity):
        print(f"窗口切换: {activity.app_name} - {activity.window_title}")

    monitor = WindowsMonitor()
    monitor.start_polling(interval=2, callback=test_callback)

    print("监控运行中... 按 Ctrl+C 停止")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop_polling()
        print("监控已停止")
