"""
FocusGuard v2.0 - Enforcement Service Module

系统级强制执行服务 - 窗口管理、进程管理、持续监控。
"""
from __future__ import annotations

import logging
from typing import Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    import win32gui
    import win32con
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logging.warning("pywin32 not available, window management features disabled")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, process management features disabled")

logger = logging.getLogger(__name__)


class EnforcementService(QObject):
    """
    系统级强制执行服务。

    职责：
    - 窗口管理（关闭/最小化/隐藏）
    - 进程管理（终止/阻塞）
    - 持续监控与提醒
    """

    # Signals
    window_closed = pyqtSignal(str, str)  # (app_name, window_title)
    window_minimized = pyqtSignal(str, str)  # (app_name, window_title)
    process_terminated = pyqtSignal(str)  # (app_name)
    enforcement_failed = pyqtSignal(str, str)  # (action, error)
    app_blocked = pyqtSignal(str, int)  # (app_name, duration_minutes)
    app_unblocked = pyqtSignal(str)  # (app_name)

    # Signal for triggering intervention during follow-up monitoring
    intervention_requested = pyqtSignal(dict)  # LLM response dict

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """
        初始化强制执行服务。

        Args:
            parent: 父 QObject
        """
        super().__init__(parent)

        # 检查管理员权限
        try:
            import ctypes
            self._is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
            if not self._is_admin:
                logger.warning("Running without admin privileges - window management may be limited")
        except Exception:
            self._is_admin = False
            logger.warning("Could not check admin privileges")

        # 被阻止的应用列表 {app_name: (blocked_until_timestamp, timer)}
        self._blocked_apps: dict[str, tuple[float, QTimer]] = {}

        # 后续监控状态
        self._follow_up_timer: Optional[QTimer] = None
        self._follow_up_target: Optional[str] = None
        self._follow_up_active: bool = False

        # 严格模式监控
        self._strict_mode_timer: Optional[QTimer] = None
        self._strict_mode_active: bool = False

        logger.info("EnforcementService initialized")

    # ========== 窗口管理方法 ==========

    def close_window(self, app_name: str, window_title: str = "") -> bool:
        """
        关闭指定窗口（发送 WM_CLOSE 消息）。

        使用 SendMessage（同步）确保消息被窗口处理。

        Args:
            app_name: 应用程序名称（如 "chrome.exe"）
            window_title: 窗口标题（可选，用于更精确匹配）

        Returns:
            bool: 是否成功关闭至少一个窗口
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot close window: pywin32 not available")
            self.enforcement_failed.emit("close_window", "pywin32 not available")
            return False

        # 检查管理员权限
        if not self._is_admin:
            logger.warning(f"Attempting to close {app_name} without admin privileges")

        try:
            closed_count = 0

            def enum_handler(hwnd, ctx):
                nonlocal closed_count
                try:
                    # 跳过不可见窗口
                    if not win32gui.IsWindowVisible(hwnd):
                        return True

                    title = win32gui.GetWindowText(hwnd)
                    if not title:
                        return True

                    # 获取窗口所属进程
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except:
                        return True

                    # 匹配应用名称
                    if app_name.lower() not in process_name.lower():
                        return True

                    # 如果提供了窗口标题，也要匹配
                    if window_title and window_title.lower() not in title.lower():
                        return True

                    # 使用 SendMessage（同步）发送关闭消息
                    try:
                        result = win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                        closed_count += 1
                        logger.info(f"Successfully sent WM_CLOSE to: {process_name} - {title}")
                        self.window_closed.emit(process_name, title)
                    except Exception as send_error:
                        error_str = str(send_error).lower()
                        if "access is denied" in error_str or "error 5" in error_str:
                            logger.warning(f"Access denied when closing {process_name} - {title}: {send_error}")
                        else:
                            logger.error(f"Failed to send WM_CLOSE to {process_name} - {title}: {send_error}")

                except Exception as e:
                    logger.debug(f"Error in enum_handler: {e}")

                return True

            win32gui.EnumWindows(enum_handler, None)

            if closed_count > 0:
                logger.info(f"Successfully closed {closed_count} window(s) for {app_name}")
                return True
            else:
                logger.warning(f"No windows found for {app_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to close window: {e}")
            self.enforcement_failed.emit("close_window", str(e))
            return False

    def minimize_window(self, app_name: str, window_title: str = "") -> bool:
        """
        最小化指定窗口。

        Args:
            app_name: 应用程序名称
            window_title: 窗口标题（可选）

        Returns:
            bool: 是否成功最小化至少一个窗口
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot minimize window: pywin32 not available")
            self.enforcement_failed.emit("minimize_window", "pywin32 not available")
            return False

        try:
            minimized_count = 0

            def enum_handler(hwnd, ctx):
                nonlocal minimized_count
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True

                    title = win32gui.GetWindowText(hwnd)
                    if not title:
                        return True

                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except:
                        return True

                    if app_name.lower() not in process_name.lower():
                        return True

                    if window_title and window_title.lower() not in title.lower():
                        return True

                    # 最小化窗口
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    minimized_count += 1
                    logger.info(f"Minimized window: {process_name} - {title}")
                    self.window_minimized.emit(process_name, title)

                except Exception as e:
                    logger.debug(f"Error in enum_handler: {e}")

                return True

            win32gui.EnumWindows(enum_handler, None)

            if minimized_count > 0:
                logger.info(f"Successfully minimized {minimized_count} window(s) for {app_name}")
                return True
            else:
                logger.warning(f"No windows found for {app_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to minimize window: {e}")
            self.enforcement_failed.emit("minimize_window", str(e))
            return False

    def hide_window(self, app_name: str, window_title: str = "") -> bool:
        """
        隐藏指定窗口（不显示在任务栏）。

        Args:
            app_name: 应用程序名称
            window_title: 窗口标题（可选）

        Returns:
            bool: 是否成功
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot hide window: pywin32 not available")
            self.enforcement_failed.emit("hide_window", "pywin32 not available")
            return False

        try:
            hidden_count = 0

            def enum_handler(hwnd, ctx):
                nonlocal hidden_count
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return True

                    title = win32gui.GetWindowText(hwnd)
                    if not title:
                        return True

                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except:
                        return True

                    if app_name.lower() not in process_name.lower():
                        return True

                    if window_title and window_title.lower() not in title.lower():
                        return True

                    # 隐藏窗口
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    hidden_count += 1
                    logger.info(f"Hidden window: {process_name} - {title}")

                except Exception as e:
                    logger.debug(f"Error in enum_handler: {e}")

                return True

            win32gui.EnumWindows(enum_handler, None)

            if hidden_count > 0:
                logger.info(f"Successfully hid {hidden_count} window(s) for {app_name}")
                return True
            else:
                logger.warning(f"No windows found for {app_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to hide window: {e}")
            self.enforcement_failed.emit("hide_window", str(e))
            return False

    # ========== 进程管理方法 ==========

    def terminate_process(self, app_name: str) -> bool:
        """
        终止指定进程（温和方式，允许用户保存）。

        Args:
            app_name: 进程名称（如 "chrome.exe"）

        Returns:
            bool: 是否成功终止至少一个进程
        """
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot terminate process: psutil not available")
            self.enforcement_failed.emit("terminate_process", "psutil not available")
            return False

        try:
            terminated = False
            for proc in psutil.process_iter(['name']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        proc.terminate()  # 温和终止
                        terminated = True
                        logger.info(f"Terminated process: {proc.info['name']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            if terminated:
                self.process_terminated.emit(app_name)
                return True
            else:
                logger.warning(f"No processes found for {app_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to terminate process: {e}")
            self.enforcement_failed.emit("terminate_process", str(e))
            return False

    def block_app(self, app_name: str, duration_minutes: int = 60) -> None:
        """
        阻止指定应用运行一段时间。

        策略：定期检查进程列表，如果发现被阻止的应用，立即终止。

        Args:
            app_name: 应用名称（如 "chrome.exe"）
            duration_minutes: 阻止时长（分钟）
        """
        import time

        # 计算解除阻止的时间戳
        block_until = time.time() + duration_minutes * 60

        # 如果已经存在阻塞计时器，先停止
        if app_name in self._blocked_apps:
            old_timer = self._blocked_apps[app_name][1]
            if old_timer:
                old_timer.stop()
                old_timer.deleteLater()

        # 创建新的解除阻塞计时器
        unblock_timer = QTimer(self)
        unblock_timer.setSingleShot(True)
        unblock_timer.timeout.connect(lambda: self.unblock_app(app_name))
        unblock_timer.start(duration_minutes * 60 * 1000)

        # 保存到阻塞列表
        self._blocked_apps[app_name] = (block_until, unblock_timer)

        logger.info(f"Blocked {app_name} for {duration_minutes} minutes")
        self.app_blocked.emit(app_name, duration_minutes)

        # 立即终止现有实例
        self.terminate_process(app_name)

        # 启动持续监控（如果未启动）
        self._start_blocking_monitor()

    def unblock_app(self, app_name: str) -> None:
        """
        解除对指定应用的阻止。

        Args:
            app_name: 应用名称
        """
        if app_name in self._blocked_apps:
            # 停止计时器
            _, timer = self._blocked_apps[app_name]
            if timer:
                timer.stop()
                timer.deleteLater()

            # 从阻塞列表移除
            del self._blocked_apps[app_name]

            logger.info(f"Unblocked {app_name}")
            self.app_unblocked.emit(app_name)

            # 如果没有其他被阻止的应用，停止监控
            if not self._blocked_apps:
                self._stop_blocking_monitor()

    def is_app_blocked(self, app_name: str) -> bool:
        """
        检查应用是否被阻止。

        Args:
            app_name: 应用名称

        Returns:
            bool: 是否被阻止
        """
        return app_name in self._blocked_apps

    def _start_blocking_monitor(self) -> None:
        """启动阻塞监控循环。"""
        if self._blocked_apps and not hasattr(self, '_blocking_monitor_timer'):
            import time

            self._blocking_monitor_timer = QTimer(self)
            self._blocking_monitor_timer.timeout.connect(self._check_blocked_apps)
            # 每 5 秒检查一次
            self._blocking_monitor_timer.start(5000)
            logger.info("Started blocking monitor")

    def _stop_blocking_monitor(self) -> None:
        """停止阻塞监控循环。"""
        if hasattr(self, '_blocking_monitor_timer'):
            self._blocking_monitor_timer.stop()
            self._blocking_monitor_timer.deleteLater()
            delattr(self, '_blocking_monitor_timer')
            logger.info("Stopped blocking monitor")

    def _check_blocked_apps(self) -> None:
        """检查并终止被阻止应用的进程。"""
        if not PSUTIL_AVAILABLE:
            return

        import time

        # 清理过期的阻塞
        current_time = time.time()
        expired_apps = [
            app for app, (until, _) in self._blocked_apps.items()
            if current_time >= until
        ]
        for app in expired_apps:
            self.unblock_app(app)

        # 终止被阻止的应用
        for app_name in list(self._blocked_apps.keys()):
            if app_name not in expired_apps:
                self.terminate_process(app_name)

    # ========== 监控与提醒方法 ==========

    def start_follow_up_monitoring(self, target_app: str, interval_seconds: int = 30) -> None:
        """
        启动后续监控 - 检查用户是否真的关闭了分心应用。

        如果用户未行动，周期性触发干预对话框。

        Args:
            target_app: 目标应用名称
            interval_seconds: 检查间隔（默认 30 秒）
        """
        # 停止现有监控
        self.stop_follow_up_monitoring()

        self._follow_up_target = target_app
        self._follow_up_active = True

        self._follow_up_timer = QTimer(self)
        self._follow_up_timer.timeout.connect(
            lambda: self._check_user_action(target_app)
        )
        self._follow_up_timer.start(interval_seconds * 1000)

        logger.info(f"Started follow-up monitoring for {target_app} (interval: {interval_seconds}s)")

    def stop_follow_up_monitoring(self) -> None:
        """停止后续监控。"""
        if self._follow_up_timer:
            self._follow_up_timer.stop()
            self._follow_up_timer.deleteLater()
            self._follow_up_timer = None

        self._follow_up_target = None
        self._follow_up_active = False

        logger.info("Stopped follow-up monitoring")

    def _check_user_action(self, target_app: str) -> None:
        """检查用户是否仍在使用目标应用。"""
        if not WIN32_AVAILABLE:
            return

        try:
            # 获取当前活动窗口
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            try:
                process = psutil.Process(pid)
                current_app = process.name()
            except:
                return

            # 检查是否仍在使用目标应用
            if target_app.lower() in current_app.lower():
                # 用户仍在使用，触发干预
                logger.warning(f"User still on {target_app}, triggering intervention")

                # 获取窗口标题
                window_title = win32gui.GetWindowText(hwnd)

                self.intervention_requested.emit({
                    "is_distracted": True,
                    "confidence": 100,
                    "analysis_summary": f"检测到您仍在使用 {target_app}，请立即停止",
                    "options": [
                        {
                            "label": "立即关闭",
                            "action_type": "CLOSE_WINDOW",
                            "payload": {"app": current_app, "window_title": window_title},
                            "trust_impact": 0,
                            "style": "primary",
                            "disabled": False,
                            "disabled_reason": None,
                            "cost": 0,
                            "affordable": True,
                        },
                        {
                            "label": "我正在保存",
                            "action_type": "SNOOZE",
                            "payload": {"duration_minutes": 2},
                            "trust_impact": 0,
                            "style": "normal",
                            "disabled": False,
                            "disabled_reason": None,
                            "cost": 0,
                            "affordable": True,
                        }
                    ],
                    "_follow_up": True  # 标记为后续监控触发的干预
                })
            else:
                # 用户已切换到其他应用，停止监控
                logger.info(f"User switched away from {target_app}, stopping follow-up")
                self.stop_follow_up_monitoring()

        except Exception as e:
            logger.error(f"Error in follow-up check: {e}")

    # ========== 严格模式监控 ==========

    def enable_strict_monitoring(self, duration_minutes: int = 30) -> None:
        """
        启用严格模式监控。

        严格模式下，如果检测到分心应用，会自动关闭。

        Args:
            duration_minutes: 监控时长
        """
        import time

        # 停止现有严格模式监控
        self.disable_strict_monitoring()

        self._strict_mode_active = True

        # 创建监控计时器
        self._strict_mode_timer = QTimer(self)
        self._strict_mode_timer.timeout.connect(self._strict_mode_check)
        # 每 10 秒检查一次
        self._strict_mode_timer.start(10000)

        # 创建自动解除计时器
        strict_end_timer = QTimer(self)
        strict_end_timer.setSingleShot(True)
        strict_end_timer.timeout.connect(self.disable_strict_monitoring)
        strict_end_timer.start(duration_minutes * 60 * 1000)

        logger.info(f"Enabled strict monitoring for {duration_minutes} minutes")

    def disable_strict_monitoring(self) -> None:
        """禁用严格模式监控。"""
        if self._strict_mode_timer:
            self._strict_mode_timer.stop()
            self._strict_mode_timer.deleteLater()
            self._strict_mode_timer = None

        self._strict_mode_active = False
        logger.info("Disabled strict monitoring")

    def _strict_mode_check(self) -> None:
        """严格模式检查 - 需要与 SupervisionEngine 配合。"""
        # 这个方法会由 SupervisionEngine 的监控循环调用
        # EnforcementService 只提供状态查询
        pass

    def is_in_strict_mode(self) -> bool:
        """
        检查是否处于严格模式。

        Returns:
            bool: 是否在严格模式中
        """
        return self._strict_mode_active

    # ========== 清理方法 ==========

    def cleanup(self) -> None:
        """清理资源（停止所有监控和计时器）。"""
        logger.info("Cleaning up EnforcementService...")

        # 停止后续监控
        self.stop_follow_up_monitoring()

        # 停止严格模式监控
        self.disable_strict_monitoring()

        # 停止阻塞监控
        self._stop_blocking_monitor()

        # 解除所有应用阻塞
        for app_name in list(self._blocked_apps.keys()):
            self.unblock_app(app_name)

        logger.info("EnforcementService cleanup completed")
