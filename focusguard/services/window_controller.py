"""
FocusGuard v3.0 - Window Controller Module

窗口控制工具类，用于精确关闭特定标签页。
使用策略：Focus + Hotkey（强制置顶 + 发送快捷键）
"""
from __future__ import annotations

import logging
import time
from typing import Optional

try:
    import win32gui
    import win32con
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logging.warning("pywin32 not available, window control features disabled")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available, hotkey simulation disabled")

logger = logging.getLogger(__name__)


class WindowController:
    """
    窗口控制器 - 用于精确关闭分心标签页。

    功能：
        - 根据标题关键词查找窗口
        - 强制将窗口置顶（绕过 Windows 限制）
        - 发送快捷键关闭当前标签页
        - 安全检查防止误关
    """

    @staticmethod
    def find_window_by_title_keyword(keyword: str) -> int:
        """
        遍历所有窗口，返回标题包含 keyword 的窗口句柄 (hwnd)。

        Args:
            keyword: 窗口标题关键词（如 "Bilibili"）

        Returns:
            int: 窗口句柄，没找到返回 0
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot find window: pywin32 not available")
            return 0

        def enum_handler(hwnd, ctx):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and keyword.lower() in title.lower():
                        # 找到匹配的窗口
                        windows.append(hwnd)
            except Exception as e:
                logger.debug(f"Error enumerating window: {e}")
            return True

        windows = []
        win32gui.EnumWindows(enum_handler, None)

        if windows:
            # 返回第一个匹配的窗口
            logger.info(f"Found {len(windows)} window(s) containing '{keyword}'")
            return windows[0]

        logger.warning(f"No window found containing '{keyword}'")
        return 0

    @staticmethod
    def force_focus_window(hwnd: int) -> bool:
        """
        强制将窗口置顶。

        关键步骤：
        1. 获取当前前台窗口线程ID (current_tid) 和目标窗口线程ID (target_tid)
        2. 使用 AttachThreadInput 绑定输入
        3. SetForegroundWindow 和 BringWindowToTop
        4. 解绑 AttachThreadInput

        Args:
            hwnd: 目标窗口句柄

        Returns:
            bool: 是否成功置顶
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot force focus window: pywin32 not available")
            return False

        try:
            # 获取当前前台窗口的线程ID
            foreground_hwnd = win32gui.GetForegroundWindow()
            current_tid, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)

            # 获取目标窗口的线程ID
            target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

            # 如果线程ID相同，直接设置前台窗口
            if current_tid == target_tid:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                logger.info(f"Window {hwnd} set to foreground (same thread)")
                return True

            # 绑定输入（伪造权限）
            win32process.AttachThreadInput(current_tid, target_tid, True)

            # 强制置顶
            if win32gui.IsIconic(hwnd):
                # 如果窗口最小化了，先恢复
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)

            # 解绑输入
            win32process.AttachThreadInput(current_tid, target_tid, False)

            logger.info(f"Window {hwnd} forced to foreground successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to force focus window {hwnd}: {e}")
            return False

    @staticmethod
    def close_current_tab_safely(
        target_title_keyword: str,
        return_to_hwnd: Optional[int] = None
    ) -> bool:
        """
        组合拳逻辑：查找窗口 -> 强制置顶 -> 双重检查 -> 发送快捷键 -> 恢复焦点

        Args:
            target_title_keyword: 目标窗口标题关键词（如 "Bilibili"）
            return_to_hwnd: 执行完成后要返回的窗口句柄（可选）

        Returns:
            bool: 是否成功关闭
        """
        if not WIN32_AVAILABLE:
            logger.error("Cannot close tab: pywin32 not available")
            return False

        if not PYAUTOGUI_AVAILABLE:
            logger.error("Cannot close tab: pyautogui not available")
            return False

        # 步骤 1: 查找目标窗口
        target_hwnd = WindowController.find_window_by_title_keyword(target_title_keyword)
        if not target_hwnd:
            logger.error(f"Target window '{target_title_keyword}' not found")
            return False

        # 记录当前活动窗口（用于后续恢复焦点）
        current_active_hwnd = win32gui.GetForegroundWindow()

        # 步骤 2: 强制置顶
        logger.info(f"Force focusing window with keyword: {target_title_keyword}")
        if not WindowController.force_focus_window(target_hwnd):
            logger.error("Failed to force focus target window")
            return False

        # 步骤 3: 等待动画完成
        time.sleep(0.2)

        # 步骤 4: 双重检查（防止误关）
        actual_title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        if target_title_keyword.lower() not in actual_title.lower():
            logger.error(f"Focus lost! Expected '{target_title_keyword}', got '{actual_title}'")
            logger.error("ABORTING: Closing tab to prevent accident")
            return False

        # 步骤 5: 发送 Ctrl+W 关闭标签页
        logger.info(f"Sending Ctrl+W to close tab in '{actual_title}'")
        try:
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(0.1)  # 等待快捷键生效
        except Exception as e:
            logger.error(f"Failed to send Ctrl+W: {e}")
            return False

        # 步骤 6: 恢复到之前的工作窗口
        if return_to_hwnd:
            logger.info("Returning focus to previous working window")
            WindowController.force_focus_window(return_to_hwnd)
        elif current_active_hwnd != target_hwnd:
            # 如果没有指定 return_to_hwnd，尝试回到之前的窗口
            logger.info("Returning focus to previous active window")
            WindowController.force_focus_window(current_active_hwnd)

        logger.info(f"Successfully closed tab with keyword '{target_title_keyword}'")
        return True
