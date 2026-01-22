"""
FocusGuard v2.0 - Action Manager Module

负责 Signal 分发、动作处理和 Snooze 强制回调循环。
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class ActionManager(QObject):
    """
    动作管理器 - 处理用户选择并分发相应动作。

    Signals:
        - snooze_expired: Snooze 定时器到期
        - trust_updated: 信任分更新
        - intervention_requested: 请求用户干预（强制回调或 AI 判断）
    """

    # Signal 定义（类型安全）
    snooze_expired = pyqtSignal()  # 无参数
    trust_updated = pyqtSignal(int)  # 新的 trust_score
    intervention_requested = pyqtSignal(dict)  # LLM 返回的完整 JSON
    force_cease_fire = pyqtSignal()  # 强制停止所有干预（Recovery 状态）

    def __init__(self, enforcement_service: Optional["EnforcementService"] = None, parent: Optional[QObject] = None) -> None:
        """
        初始化动作管理器。

        Args:
            enforcement_service: 强制执行服务实例（可选）
            parent: 父 QObject
        """
        super().__init__(parent)

        self._enforcement = enforcement_service

        self._snooze_timer: Optional[QTimer] = None
        self._temp_whitelist: set[str] = set()  # 临时白名单（应用名称）
        self._strict_mode_until: Optional[float] = None  # 严格模式结束时间（timestamp）

        # 新增：刚关闭的关键词列表，防止误报
        self._recently_closed_keywords: dict[str, float] = {}  # {keyword: timestamp}

        # v3.0: Memory 系统 - 数据库路径（用于记录 episodic 事件）
        self._db_path = None  # 将在运行时设置

        logger.info("ActionManager initialized")

    def set_db_path(self, db_path: str) -> None:
        """
        设置数据库路径（用于记录 episodic 事件）。

        Args:
            db_path: 数据库文件路径
        """
        self._db_path = db_path

    def _record_episodic_event(
        self,
        event_type: str,
        app_name: str | None = None,
        window_title: str | None = None,
        url: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        记录情景记忆事件（Episodic Memory）。

        Args:
            event_type: 事件类型
            app_name: 应用名称
            window_title: 窗口标题
            url: URL
            metadata: 额外元数据
        """
        if not self._db_path:
            return

        try:
            from ..storage.database import ensure_initialized, record_episodic_event

            with ensure_initialized(self._db_path) as conn:
                record_episodic_event(
                    conn=conn,
                    event_type=event_type,
                    app_name=app_name,
                    window_title=window_title,
                    url=url,
                    metadata=metadata,
                )
        except Exception as e:
            logger.warning(f"Failed to record episodic event: {e}")

    def handle_action(
        self,
        action_type: str,
        payload: dict,
        trust_impact: int,
        update_trust_fn: Callable[[int], int],
    ) -> None:
        """
        处理用户选择的动作。

        Args:
            action_type: 动作类型（SNOOZE/DISMISS/WHITELIST_TEMP/STRICT_MODE/CLOSE_WINDOW/MINIMIZE_WINDOW/BLOCK_APP）
            payload: 动作参数
            trust_impact: 信任分影响
            update_trust_fn: 更新信任分的函数（签名为 (delta) -> new_score）
        """
        # 更新信任分
        if trust_impact != 0:
            new_score = update_trust_fn(trust_impact)
            self.trust_updated.emit(new_score)

        # 分发到增强版处理器
        if action_type == "DISMISS":
            self._handle_dismiss(payload)

        elif action_type == "SNOOZE":
            self._handle_snooze_enhanced(payload)

        elif action_type == "WHITELIST_TEMP":
            self._handle_whitelist_temp(payload)

        elif action_type == "STRICT_MODE":
            self._handle_strict_mode_enhanced(payload)

        elif action_type == "CLOSE_WINDOW":
            self._handle_close_window(payload)

        elif action_type == "MINIMIZE_WINDOW":
            self._handle_minimize_window(payload)

        elif action_type == "BLOCK_APP":
            self._handle_block_app(payload)

        elif action_type == "FORCE_CEASE_FIRE":
            self._handle_force_cease_fire(payload)

        elif action_type == "CLOSE_TAB":
            self._handle_close_tab(payload)

        else:
            logger.warning(f"Unknown action type: {action_type}")

    def _handle_snooze(self, payload: dict) -> None:
        """
        处理 SNOOZE 动作 - 暂停监控 X 分钟。

        关键：启动强制回调定时器。

        Args:
            payload: {"duration": int} 或 {"duration_minutes": int}
        """
        # 兼容两种键名：LLM 可能返回 "duration" 或 "duration_minutes"
        duration_minutes = payload.get("duration_minutes") or payload.get("duration", 5)
        if isinstance(duration_minutes, str):
            duration_minutes = int(duration_minutes)

        logger.info(f"Action: SNOOZE - Pausing for {duration_minutes} minutes")

        # 创建并启动定时器
        if self._snooze_timer is None:
            self._snooze_timer = QTimer(self)
            self._snooze_timer.setSingleShot(True)
            self._snooze_timer.timeout.connect(self._on_snooze_expired)

        # 启动定时器（毫秒）
        self._snooze_timer.start(duration_minutes * 60 * 1000)

    def _handle_snooze_enhanced(self, payload: dict) -> None:
        """
        增强版 SNOOZE - 最小化当前窗口 + 暂停监控。

        Args:
            payload: {"duration_minutes": int, "current_app": str, "current_window_title": str}
        """
        duration_minutes = payload.get("duration_minutes") or payload.get("duration", 5)
        if isinstance(duration_minutes, str):
            duration_minutes = int(duration_minutes)

        # v3.0: Memory 系统 - 记录 episodic 事件
        self._record_episodic_event(
            event_type="USER_SNOOZED",
            app_name=payload.get("current_app", ""),
            window_title=payload.get("current_window_title", ""),
            metadata={"duration_minutes": duration_minutes},
        )

        # 如果有 EnforcementService，最小化当前窗口
        if self._enforcement:
            current_app = payload.get("current_app", "")
            current_title = payload.get("current_window_title", "")

            if current_app:
                self._enforcement.minimize_window(current_app, current_title)
                logger.info(f"Minimized window for {current_app} during snooze")

        # 启动定时器
        self._handle_snooze(payload)

    def _on_snooze_expired(self) -> None:
        """
        Snooze 定时器到期 - 强制回调。

        跳过 AI 判断，直接强制弹窗。
        """
        logger.info("Snooze expired - Forcing callback")

        self.snooze_expired.emit()

        # 发出强制干预请求
        forced_response = {
            "is_distracted": True,
            "confidence": 100,
            "analysis_summary": "休息时间结束，请确认当前状态",
            "options": [
                {
                    "label": "继续工作",
                    "action_type": "DISMISS",
                    "payload": {},
                    "trust_impact": 3,
                    "style": "primary",
                    "disabled": False,
                    "disabled_reason": None,
                },
                {
                    "label": "再休息 5 分钟",
                    "action_type": "SNOOZE",
                    "payload": {"duration_minutes": 5},
                    "trust_impact": -5,
                    "style": "warning",
                    "disabled": False,
                    "disabled_reason": None,
                },
            ],
            "_forced_callback": True,  # 内部标记
        }

        self.intervention_requested.emit(forced_response)

    def _handle_whitelist_temp(self, payload: dict) -> None:
        """
        处理 WHITELIST_TEMP 动作 - 临时白名单。

        Args:
            payload: {"app": str, "duration_hours": int}
        """
        app_name = payload.get("app", "")
        duration_hours = payload.get("duration_hours", 1)

        if app_name:
            self._temp_whitelist.add(app_name)
            logger.info(f"Action: WHITELIST_TEMP - Added {app_name} for {duration_hours}h")

            # TODO: 可以使用 QTimer 在 duration_hours 后自动移除
            # 这里简化处理，只在内存中存储，不持久化

    def _handle_strict_mode(self, payload: dict) -> None:
        """
        处理 STRICT_MODE 动作 - 高频监控。

        Args:
            payload: {"duration": int} 或 {"duration_minutes": int}
        """
        import time

        # 兼容两种键名：LLM 可能返回 "duration" 或 "duration_minutes"
        duration_minutes = payload.get("duration_minutes") or payload.get("duration", 30)
        if isinstance(duration_minutes, str):
            duration_minutes = int(duration_minutes)

        self._strict_mode_until = time.time() + duration_minutes * 60

        logger.info(f"Action: STRICT_MODE - Enabled for {duration_minutes} minutes")

    def _handle_dismiss(self, payload: dict) -> None:
        """
        增强版 DISMISS - 支持关闭窗口选项。

        Args:
            payload: {"dismiss_action": str, "app": str, "window_title": str}
        """
        # v3.0: Memory 系统 - 记录 episodic 事件
        self._record_episodic_event(
            event_type="USER_DISMISSED",
            app_name=payload.get("app", ""),
            window_title=payload.get("window_title", ""),
            metadata=payload,
        )

        action = payload.get("dismiss_action", "none")  # none, close, minimize
        target_app = payload.get("app", "")
        target_title = payload.get("window_title", "")

        if action == "close" and target_app and self._enforcement:
            success = self._enforcement.close_window(target_app, target_title)
            if success:
                logger.info(f"Closed window: {target_app} - {target_title}")
        elif action == "minimize" and target_app and self._enforcement:
            self._enforcement.minimize_window(target_app, target_title)
            logger.info(f"Minimized window: {target_app} - {target_title}")
        else:
            logger.info("Action: DISMISS - Dialog dismissed")

    def _handle_strict_mode_enhanced(self, payload: dict) -> None:
        """
        增强版 STRICT_MODE - 启用主动拦截。

        Args:
            payload: {"duration_minutes": int, "current_app": str}
        """
        duration_minutes = payload.get("duration_minutes") or payload.get("duration", 30)
        if isinstance(duration_minutes, str):
            duration_minutes = int(duration_minutes)

        # 设置严格模式标记
        self._handle_strict_mode(payload)

        # 如果有 EnforcementService，启用严格监控
        if self._enforcement:
            self._enforcement.enable_strict_monitoring(duration_minutes)
            logger.info(f"Enabled strict monitoring for {duration_minutes} minutes")

    def _handle_close_window(self, payload: dict) -> None:
        """
        关闭指定窗口。

        Args:
            payload: {"app": str, "current_window_title": str} 或 {"keyword": str, "current_app": str}
        """
        # v3.0: Memory 系统 - 记录 episodic 事件
        self._record_episodic_event(
            event_type="USER_CLOSED_WINDOW",
            app_name=payload.get("app", "") or payload.get("current_app", ""),
            window_title=payload.get("current_window_title", ""),
            metadata={"keyword": payload.get("keyword", "")},
        )

        if not self._enforcement:
            logger.warning("EnforcementService not available, cannot close window")
            return

        # 兼容两种格式：直接指定 app 或通过 keyword 推断
        app = payload.get("app", "") or payload.get("current_app", "")
        title = payload.get("current_window_title", "")

        # 如果没有指定 app，尝试使用 WindowController 根据 keyword 关闭窗口
        keyword = payload.get("keyword", "")
        if keyword and not app:
            try:
                from .window_controller import WindowController
                success = WindowController.close_current_tab_safely(
                    target_title_keyword=keyword,
                    return_to_hwnd=None
                )
                if success:
                    logger.info(f"Action: CLOSE_WINDOW - Closed window with keyword '{keyword}'")
                else:
                    logger.error(f"Action: CLOSE_WINDOW - Failed to close window with keyword '{keyword}'")
                return
            except ImportError:
                logger.error("WindowController not available")
                return

        if app:
            self._enforcement.close_window(app, title)
            logger.info(f"Action: CLOSE_WINDOW - {app} - {title}")

    def _handle_minimize_window(self, payload: dict) -> None:
        """
        最小化指定窗口 + 暂停监控（修复：需要启动 SNOOZE 定时器）。

        Args:
            payload: {"app": str, "current_window_title": str, "duration_minutes": int} 或 {"keyword": str, "current_app": str}
        """
        # v3.0: Memory 系统 - 记录 episodic 事件
        self._record_episodic_event(
            event_type="USER_MINIMIZED",
            app_name=payload.get("app", "") or payload.get("current_app", ""),
            window_title=payload.get("current_window_title", ""),
            metadata={"keyword": payload.get("keyword", ""), "duration_minutes": payload.get("duration_minutes", 10)},
        )

        if not self._enforcement:
            logger.warning("EnforcementService not available, cannot minimize window")
            return

        # 兼容两种格式：直接指定 app 或通过 keyword 推断
        app = payload.get("app", "") or payload.get("current_app", "")
        title = payload.get("current_window_title", "")

        # 获取暂停时长（默认 10 分钟）
        duration_minutes = payload.get("duration_minutes", payload.get("duration", 10))
        if isinstance(duration_minutes, str):
            duration_minutes = int(duration_minutes)

        # 如果没有指定 app，尝试使用 EnforcementService 根据 keyword 查找并最小化窗口
        keyword = payload.get("keyword", "")
        if keyword and not app:
            # 尝试从 keyword 推断应用名称（简化处理）
            # 对于浏览器，我们可以直接使用 msedge.exe 或 chrome.exe
            if "bilibili" in keyword.lower() or "youtube" in keyword.lower():
                app = "msedge.exe"  # 默认使用 Edge
                # TODO: 可以进一步根据 keyword 判断是 Chrome 还是 Edge

        if app:
            self._enforcement.minimize_window(app, title)
            logger.info(f"Minimized window: {app} - {title}")

        # 关键修复：启动 SNOOZE 定时器暂停监控
        logger.info(f"Action: MINIMIZE_WINDOW - Also starting SNOOZE for {duration_minutes} minutes")
        self._handle_snooze({"duration_minutes": duration_minutes})


    def _handle_block_app(self, payload: dict) -> None:
        """
        阻止指定应用。

        Args:
            payload: {"app": str, "duration_minutes": int}
        """
        if not self._enforcement:
            logger.warning("EnforcementService not available, cannot block app")
            return

        app = payload.get("app", "")
        duration = payload.get("duration_minutes", 60)

        if isinstance(duration, str):
            duration = int(duration)

        if app:
            self._enforcement.block_app(app, duration)
            logger.info(f"Action: BLOCK_APP - {app} for {duration} minutes")

    def is_in_strict_mode(self) -> bool:
        """
        检查是否处于严格模式。

        Returns:
            bool: 是否在严格模式中
        """
        if self._strict_mode_until is None:
            return False

        import time

        if time.time() > self._strict_mode_until:
            # 严格模式已过期
            self._strict_mode_until = None
            return False

        return True

    def is_whitelisted(self, app_name: str) -> bool:
        """
        检查应用是否在临时白名单中。

        Args:
            app_name: 应用程序名称

        Returns:
            bool: 是否在白名单中
        """
        return app_name in self._temp_whitelist

    def cancel_snooze(self) -> None:
        """
        取消当前的 Snooze 定时器（用于重置监控）。
        """
        if self._snooze_timer and self._snooze_timer.isActive():
            self._snooze_timer.stop()
            logger.info("Snooze timer cancelled")

    def clear_whitelist(self) -> None:
        """
        清空临时白名单。
        """
        self._temp_whitelist.clear()
        logger.info("Temporary whitelist cleared")

    def exit_strict_mode(self) -> None:
        """
        退出严格模式。
        """
        self._strict_mode_until = None
        logger.info("Strict mode exited")

    def is_snoozed(self) -> bool:
        """
        检查是否在 SNOOZE 状态。

        Returns:
            bool: 是否在 SNOOZE 状态（定时器是否激活）
        """
        return (self._snooze_timer is not None and
                self._snooze_timer.isActive())

    def _handle_force_cease_fire(self, payload: dict) -> None:
        """
        处理强制停止干预请求（Recovery 状态）。

        当检测到用户回归工作后，立即关闭所有干预对话框。

        Args:
            payload: 空字典 {}
        """
        logger.info("Action: FORCE_CEASE_FIRE - User returned to work, stopping interventions")

        # 发送信号关闭对话框
        self.force_cease_fire.emit()

    def _handle_close_tab(self, payload: dict) -> None:
        """
        关闭特定标签页（使用强制置顶 + 快捷键）。

        Args:
            payload: {"keyword": str, "return_to_app": str}
        """
        try:
            from .window_controller import WindowController
        except ImportError:
            logger.error("WindowController not available, cannot close tab")
            return

        keyword = payload.get("keyword", "")
        return_to_app = payload.get("return_to_app", "")

        if not keyword:
            logger.warning("CLOSE_TAB action missing 'keyword' in payload")
            return

        # 查找要返回的工作窗口（如果找不到就不返回）
        return_to_hwnd = 0
        if return_to_app:
            return_to_hwnd = WindowController.find_window_by_title_keyword(return_to_app)
            if not return_to_hwnd:
                logger.info(f"Could not find window with keyword '{return_to_app}', will not return after closing tab")

        # 执行关闭操作
        success = WindowController.close_current_tab_safely(
            target_title_keyword=keyword,
            return_to_hwnd=return_to_hwnd if return_to_hwnd else None
        )

        if success:
            logger.info(f"Action: CLOSE_TAB - Closed tab with keyword '{keyword}'")

            # v3.0: Memory 系统 - 记录 episodic 事件
            self._record_episodic_event(
                event_type="USER_CLOSED_TAB",
                window_title=keyword,
                metadata={"keyword": keyword, "return_to_app": return_to_app},
            )

            # 关键修复：添加到忽略列表，防止5分钟内重复检测
            import time
            self._recently_closed_keywords[keyword.lower()] = time.time()
            logger.info(f"Added '{keyword}' to ignore list for 5 minutes to prevent false positives")

            # v3.0: 新增 - 将 URL 模式添加到 ChromeMonitor 的关闭列表
            # 这样可以防止 Chrome History 中的旧 URL 触发误报
            try:
                from ..monitors.chrome_monitor import ChromeMonitor
                # 添加 URL 模式到忽略列表（5分钟冷却）
                ChromeMonitor.add_closed_url(keyword, cooldown_seconds=300)
                logger.info(f"Added '{keyword}' to ChromeMonitor closed URL list")
            except ImportError:
                logger.warning("ChromeMonitor not available, cannot add URL to closed list")

            # 新增：从数据库中删除最近的活动记录，防止LLM误判
            try:
                from ..storage.database import ensure_initialized
                import sqlite3
                from focusguard.config import config

                with ensure_initialized(config.db_path) as conn:
                    # 删除最近5分钟内包含该关键词的活动记录
                    conn.execute(
                        """
                        DELETE FROM activity_logs
                        WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-5 minutes')
                        AND (
                            lower(window_title) LIKE lower(?)
                            OR lower(url) LIKE lower(?)
                        )
                        """,
                        (f"%{keyword}%", f"%{keyword}%")
                    )
                    conn.commit()
                    logger.info(f"Deleted recent activity logs containing '{keyword}' from database (last 5 minutes)")
            except Exception as e:
                logger.warning(f"Failed to delete activity logs: {e}")
        else:
            logger.error(f"Action: CLOSE_TAB - Failed to close tab with keyword '{keyword}'")

    def is_keyword_recently_closed(self, keyword: str) -> bool:
        """
        检查某个关键词是否在最近被关闭过（在5分钟冷却期内）。

        Args:
            keyword: 要检查的关键词

        Returns:
            bool: 如果在冷却期内返回True，否则返回False
        """
        import time

        # 清理过期的忽略项
        current_time = time.time()
        expired_keywords = [
            kw for kw, timestamp in self._recently_closed_keywords.items()
            if current_time - timestamp > 300  # 5分钟冷却期 (300秒)
        ]
        for kw in expired_keywords:
            del self._recently_closed_keywords[kw]

        # 检查当前关键词是否在忽略列表中
        keyword_lower = keyword.lower()
        # 检查是否包含任意忽略的关键词
        for ignored_keyword in self._recently_closed_keywords:
            if ignored_keyword in keyword_lower or keyword_lower in ignored_keyword:
                logger.info(f"Keyword '{keyword}' is in ignore list (matches '{ignored_keyword}'), skipping detection")
                return True

        return False
