"""
FocusGuard v2.0 - Main Entry Point

核心监控循环 + 应用程序入口。
"""
from __future__ import annotations

import logging
import sys
import time as time_module
from pathlib import Path
from typing import Optional

# 添加项目根目录到 sys.path
if getattr(sys, 'frozen', False):
    # 打包后：资源在 sys.executable 的目录
    project_root = Path(sys.executable).parent
else:
    # 开发环境：项目根目录是 focusguard 的父目录
    project_root = Path(__file__).parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

# 导入项目模块
from focusguard.config import config, setup_logging
from focusguard.storage.database import (
    ensure_initialized,
    get_trust_score,
    get_activity_summary,
    get_active_session,
    update_trust_score,
    log_activity,
    DEFAULT_DB_PATH,
)
from focusguard.storage.cleaner import DataMetabolismCleaner
from focusguard.monitors.windows_monitor import WindowsMonitor
from focusguard.monitors.chrome_monitor import ChromeMonitor
from focusguard.services.llm_service import LLMService
from focusguard.services.action_manager import ActionManager
from focusguard.services.economy_service import EconomyService
from focusguard.services.audit_service import AuditService
from focusguard.services.data_transformer import DataTransformer
from focusguard.services.enforcement_service import EnforcementService
from focusguard.ui.dialogs.intervention_dialog import InterventionDialog
from focusguard.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class SupervisionEngine(QThread):
    """
    核心监控引擎 - 主循环。

    职责：
    1. 从数据库读取活动摘要
    2. 应用规则过滤（白名单、严格模式）
    3. 调用 LLM 服务进行判断
    4. 如果检测到分心，触发干预对话框
    5. 处理用户选择
    """

    # Signal: 检测到活动（用于日志记录）
    activity_detected = pyqtSignal(str, str)

    # Signal: 需要显示干预对话框 (analysis, options, balance, thought_trace, current_app, current_window_title)
    show_dialog_requested = pyqtSignal(str, list, int, list, str, str)

    def __init__(
        self,
        llm_service: LLMService,
        action_manager: ActionManager,
        dialog: InterventionDialog,
        economy_service: EconomyService,
        data_transformer: DataTransformer,
        parent: Optional[QThread] = None,
    ) -> None:
        """
        初始化监控引擎。

        Args:
            llm_service: LLM 服务实例
            action_manager: 动作管理器实例
            dialog: 干预对话框实例
            economy_service: 专注货币服务实例
            data_transformer: 数据转化器实例
            parent: 父 QThread
        """
        super().__init__(parent)

        self._llm_service = llm_service
        self._action_manager = action_manager
        self._dialog = dialog
        self._economy_service = economy_service
        self._data_transformer = data_transformer

        self._running = False
        self._check_interval = config.supervision_check_interval  # 默认 30 秒

        # 连接 Signal
        self._dialog.action_chosen.connect(self._on_user_choice)
        self._action_manager.snooze_expired.connect(self._on_snooze_expired)

        # 获取数据库连接（在线程运行时初始化）
        self._db_path = config.db_path

        logger.info("SupervisionEngine initialized")

    def run(self) -> None:
        """
        主监控循环。

        逻辑：
        1. 读取活动摘要（30s/5m/20m）
        2. 检查白名单和严格模式
        3. 调用 LLM 进行判断
        4. 如果分心，显示对话框
        """
        self._running = True
        logger.info("SupervisionEngine thread started")

        # 初始化数据库连接
        with ensure_initialized(self._db_path) as init_conn:
            pass  # 确保数据库已初始化

        while self._running:
            logger.debug("SupervisionEngine check cycle started")

            # 检查是否在 SNOOZE 状态
            if self._action_manager.is_snoozed():
                logger.debug("SNOOZE active, skipping supervision check")
                self._wait_next_check()
                continue

            try:
                # 步骤 1: 读取活动摘要
                with ensure_initialized(self._db_path) as conn:
                    instant_log = get_activity_summary(conn, seconds=30)
                    short_trend = get_activity_summary(conn, seconds=300)
                    context_trend = get_activity_summary(conn, seconds=1200)

                    # 获取信任分和当前目标
                    trust_score = get_trust_score(conn)
                    active_session = get_active_session(conn)
                    goal = active_session["goal_text"] if active_session else "未设置目标"

                    # v3.0: 获取最近2小时的 session_blocks（L2 数据）
                    from storage.database import get_recent_session_blocks
                    session_blocks = get_recent_session_blocks(conn, limit=4)  # 最近2小时（4个30分钟块）

                # 如果没有活动记录，跳过本次检查
                if not instant_log and not short_trend:
                    logger.debug("No activity detected, skipping LLM call")
                    self._wait_next_check()
                    continue

                # 步骤 2: 应用规则过滤
                # 检查是否在白名单中
                if instant_log:
                    latest_app = instant_log[0].get("app_name", "")
                    if self._action_manager.is_whitelisted(latest_app):
                        logger.debug(f"App {latest_app} is whitelisted, skipping")
                        self._wait_next_check()
                        continue

                # 检查是否在严格模式中（如果是，则增加检查频率）
                if self._action_manager.is_in_strict_mode():
                    self._check_interval = 10  # 严格模式：每 10 秒检查
                else:
                    self._check_interval = config.supervision_check_interval

                # 步骤 3: 调用 LLM 进行判断（同步调用）
                # 获取当前余额和用户上下文传递给 LLM
                balance = self._economy_service.get_balance()
                user_context = self._data_transformer.get_user_context()

                response = self._llm_service.analyze_activity(
                    instant_log=instant_log,
                    short_trend=short_trend,
                    context_trend=context_trend,
                    trust_score=trust_score,
                    goal=goal,
                    balance=balance,
                    user_streak=None,  # TODO: 从数据库读取用户连续性数据
                    user_context=user_context,
                    session_blocks=session_blocks,  # v3.0: 注入 session_blocks 上下文
                )

                if response is None:
                    logger.warning("LLM service returned None, using fallback")
                    self._wait_next_check()
                    continue

                # 步骤 4: 处理 LLM 响应
                if response.get("is_distracted", False):
                    confidence = response.get("confidence", 0)

                    # 只有置信度 > 60% 时才触发干预
                    if confidence >= 60:
                        logger.info(
                            f"Distracted behavior detected (confidence: {confidence}%)"
                        )
                        self._show_intervention_dialog(response)
                        logger.debug("Intervention dialog shown, waiting for next check")
                    else:
                        logger.debug(
                            f"Low confidence ({confidence}%), skipping intervention"
                        )
                else:
                    logger.debug("User is focused, continuing monitoring")

            except Exception as e:
                # 监控异常不应导致线程退出
                logger.exception(f"SupervisionEngine error (will retry): {e}")

            # 等待下一次检查
            logger.debug("Starting wait for next check...")
            self._wait_next_check()
            logger.debug("Wait completed, starting next cycle")

        logger.info("SupervisionEngine thread stopped gracefully")

    def _wait_next_check(self) -> None:
        """
        等待下一次检查（可中断）。
        """
        remaining = self._check_interval
        while remaining > 0 and self._running:
            sleep_time = min(1.0, float(remaining))
            time_module.sleep(sleep_time)  # 使用Python的time.sleep而不是QThread.sleep
            remaining -= sleep_time

    def _show_intervention_dialog(self, response: dict) -> None:
        """
        显示干预对话框（v3.0: 添加 thought_trace 传递）。

        Args:
            response: LLM 返回的完整响应
        """
        analysis = response.get("analysis_summary", "检测到分心行为")
        options = response.get("options", [])
        balance = self._economy_service.get_balance()
        thought_trace = response.get("thought_trace", [])

        # 获取当前窗口信息
        current_app = ""
        current_window_title = ""
        try:
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            current_window_title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            import psutil
            try:
                process = psutil.Process(pid)
                current_app = process.name()
            except:
                pass
        except:
            pass

        # 使用Signal显示对话框（线程安全，v3.0: 传递完整参数）
        self.show_dialog_requested.emit(analysis, options, balance, thought_trace, current_app, current_window_title)

    def _on_user_choice(self, action_type: str, payload: dict, trust_impact: int) -> None:
        """
        处理用户选择。

        Args:
            action_type: 动作类型
            payload: 动作参数
            trust_impact: 信任分影响
        """
        # 更新信任分
        with ensure_initialized(self._db_path) as conn:
            new_score = update_trust_score(conn, trust_impact)

        logger.info(f"Trust score updated: {new_score}")

        # 分发给 ActionManager
        self._action_manager.handle_action(
            action_type=action_type,
            payload=payload,
            trust_impact=trust_impact,
            update_trust_fn=lambda delta: update_trust_score(
                ensure_initialized(self._db_path).__enter__(), delta
            ),
        )

    def _on_snooze_expired(self) -> None:
        """
        处理 Snooze 到期（由 ActionManager 触发）。
        """
        logger.info("Snooze expired, resuming supervision")
        # ActionManager 会自动触发干预对话框

    def stop(self) -> None:
        """
        停止监控引擎。
        """
        logger.info("SupervisionEngine stop requested")
        self._running = False

        # 等待线程结束（最多 5 秒）
        self.wait(5000)
        if self.isRunning():
            logger.warning("SupervisionEngine did not stop within timeout")


class FocusGuardApp(QApplication):
    """
    FocusGuard 应用程序主类。

    负责初始化所有组件并协调运行。
    """

    def __init__(self, argv: list[str]) -> None:
        """
        初始化应用程序。

        Args:
            argv: 命令行参数
        """
        super().__init__(argv)

        # 防止关闭对话框后程序退出
        self.setQuitOnLastWindowClosed(False)

        # 验证配置
        if not config.validate():
            logger.error("Invalid configuration, exiting")
            sys.exit(1)

        # 初始化数据库
        with ensure_initialized(config.db_path) as conn:
            logger.info(f"Database initialized at {config.db_path}")

        # 初始化组件
        self._llm_service = LLMService(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            model=config.llm_model,
            timeout=config.llm_timeout,
        )

        # 初始化强制执行服务
        self._enforcement_service = EnforcementService()

        self._action_manager = ActionManager(enforcement_service=self._enforcement_service)

        # 初始化专注货币服务
        self._economy_service = EconomyService(
            db_path=config.db_path,
            mining_rate=config.mining_rate,  # 每分钟 1 Coin
            bankruptcy_threshold=config.bankruptcy_threshold,
        )

        # 初始化数据转化器
        self._data_transformer = DataTransformer(
            db_path=config.db_path,
            l1_to_l2_interval_minutes=config.l1_to_l2_interval,
            l2_to_l3_interval_hours=config.l2_to_l3_interval,
        )

        # 初始化审计服务
        self._audit_service = AuditService(
            db_path=config.db_path,
            llm_service=self._llm_service,
            consistency_threshold=config.consistency_threshold,
        )

        self._dialog = InterventionDialog()

        # 初始化主窗口（v3.0: 添加主控界面）
        self._main_window = MainWindow()
        self._main_window.monitoring_toggled.connect(self._on_monitoring_toggled)
        self._main_window.goal_updated.connect(self._on_goal_updated)

        self._windows_monitor = WindowsMonitor(
            poll_interval=config.windows_monitor_interval
        )
        self._chrome_monitor = ChromeMonitor()

        self._cleaner = DataMetabolismCleaner(
            db_path=config.db_path,
            data_transformer=self._data_transformer,
        )

        self._engine = SupervisionEngine(
            llm_service=self._llm_service,
            action_manager=self._action_manager,
            dialog=self._dialog,
            economy_service=self._economy_service,
            data_transformer=self._data_transformer,
        )

        # 连接 Signal
        self._windows_monitor.activity_detected.connect(self._on_activity_detected)
        self._chrome_monitor.activity_detected.connect(self._on_activity_detected)
        self._engine.show_dialog_requested.connect(self._on_show_dialog_requested)
        # 暂时不连接 action_chosen 信号，改用直接回调
        # self._dialog.action_chosen.connect(self._on_user_action_chosen)
        self._dialog._action_callback = self._on_user_action_chosen  # 直接设置回调
        self._economy_service.balance_updated.connect(self._on_balance_updated)
        self._audit_service.audit_completed.connect(self._on_audit_completed)
        self._audit_service.audit_rejected.connect(self._on_audit_rejected)

        # 连接 EnforcementService 信号
        self._enforcement_service.intervention_requested.connect(self._on_enforcement_intervention)

        # 连接 ActionManager 的 force_cease_fire 信号（用于 Recovery 状态）
        self._action_manager.force_cease_fire.connect(self._on_force_cease_fire)

        logger.info("Signal connections established")

        # 设置自定义原因回调
        self._dialog._custom_reason_callback = self._on_custom_reason

        # 防止无限递归的标志
        self._processing_activity = False

        logger.info("FocusGuard application initialized")

    def _on_activity_detected(self, app_name: str, window_title: str, url: Optional[str]) -> None:
        """
        处理检测到的活动。

        Args:
            app_name: 应用程序名称
            window_title: 窗口标题
            url: URL（如果有）
        """
        # 防止无限递归：如果已经在处理中，直接返回
        if self._processing_activity:
            return

        self._processing_activity = True

        try:
            # 记录到数据库
            with ensure_initialized(config.db_path) as conn:
                log_activity(
                    conn,
                    app_name=app_name,
                    window_title=window_title,
                    url=url,
                    duration=0,  # TODO: 计算实际持续时间
                )

            logger.debug(f"Activity logged: {app_name} - {window_title[:50]}")

            # 如果是浏览器且没有 URL，触发 Chrome 监控器检查历史
            # 只有当 URL 为空时才触发检查，避免重复
            is_browser = any(keyword in app_name.lower() for keyword in ["chrome", "edge", "chromium"])
            if is_browser and url is None:
                self._chrome_monitor.check_history(app_name, window_title)
        finally:
            self._processing_activity = False

    def _on_show_dialog_requested(self, analysis: str, options: list, balance: int, thought_trace: list, current_app: str, current_window_title: str) -> None:
        """
        处理显示对话框请求（从 SupervisionEngine 发出）（v3.0: 接收 thought_trace）。

        Args:
            analysis: AI 分析摘要
            options: 选项列表
            balance: 当前余额
            thought_trace: AI 推理过程
            current_app: 当前应用
            current_window_title: 当前窗口标题
        """
        self._dialog.show_with_options(analysis, options, balance, current_app, current_window_title, thought_trace)

    def _on_enforcement_intervention(self, response: dict) -> None:
        """
        处理强制执行服务触发的干预请求（如后续监控）（v3.0: 添加 thought_trace 传递）。

        Args:
            response: 完整的 LLM 响应字典
        """
        analysis = response.get("analysis_summary", "检测到持续分心")
        options = response.get("options", [])
        balance = self._economy_service.get_balance()
        thought_trace = response.get("thought_trace", [])

        # 获取当前窗口信息
        current_app = ""
        current_window_title = ""
        try:
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            current_window_title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            import psutil
            try:
                process = psutil.Process(pid)
                current_app = process.name()
            except:
                pass
        except:
            pass

        self._dialog.show_with_options(analysis, options, balance, current_app, current_window_title, thought_trace)

    def _on_custom_reason(self, reason: str) -> None:
        """
        处理用户输入的自定义原因。

        Args:
            reason: 用户输入的原因
        """
        logger.info(f"User explained: {reason}")

        # 临时降低监控频率（1 分钟内不检测）
        original_interval = self._engine._check_interval
        self._engine._check_interval = 60

        # 1 分钟后恢复原始检测间隔
        QTimer.singleShot(60000, lambda: setattr(self._engine, '_check_interval', original_interval))

        # 记录到数据库作为学习数据
        try:
            from storage.database import log_activity
            with ensure_initialized(config.db_path) as conn:
                log_activity(
                    conn,
                    app_name="FocusGuard",
                    window_title=f"用户说明: {reason}",
                    url=None,
                    duration=0,
                )
        except Exception as e:
            logger.warning(f"Failed to log user reason: {e}")

        logger.info(f"Supervision relaxed for 1 minute due to user explanation")

    def _on_balance_updated(self, new_balance: int, transaction_info: dict) -> None:
        """
        处理余额更新事件（v3.0: 同步更新主窗口）。

        Args:
            new_balance: 新余额
            transaction_info: 交易信息
        """
        logger.info(f"Balance updated: {new_balance} Coins ({transaction_info['type']}: {transaction_info['amount']:+d})")
        # 如果对话框当前显示中，更新其余额显示
        if self._dialog.isVisible():
            self._dialog._current_balance = new_balance
            self._dialog._balance_label.setText(f"{new_balance} Coins")

        # v3.0: 同步更新主窗口的余额显示
        self._main_window.update_balance(new_balance)

    def _on_audit_completed(
        self,
        action_type: str,
        audit_result: str,
        original_cost: int,
        final_cost: int,
        audit_reason: str,
    ) -> None:
        """
        处理审计完成事件。

        Args:
            action_type: 动作类型
            audit_result: 审计结果 (APPROVED/REJECTED/PRICE_ADJUSTED)
            original_cost: 原始价格
            final_cost: 最终价格
            audit_reason: 审计原因
        """
        logger.info(
            f"Audit completed: {action_type} -> {audit_result} "
            f"(cost: {original_cost} -> {final_cost}, reason: {audit_reason})"
        )

        # 如果对话框仍然显示，显示审计结果
        if self._dialog.isVisible():
            self._dialog.show_audit_result(audit_result, audit_reason)
            # 短暂延迟后关闭对话框
            QTimer.singleShot(2000, self._dialog.close)

    def _on_audit_rejected(self, action_type: str, reason: str) -> None:
        """
        处理审计拒绝事件。

        Args:
            action_type: 动作类型
            reason: 拒绝原因
        """
        logger.warning(f"Audit rejected: {action_type} - {reason}")

        # 如果对话框仍然显示，显示拒绝信息
        if self._dialog.isVisible():
            self._dialog.show_audit_result("REJECTED", reason)
            # 延迟后关闭对话框
            QTimer.singleShot(3000, self._dialog.close)

    def _on_force_cease_fire(self) -> None:
        """
        处理强制停止干预事件（Recovery 状态）。

        当检测到用户回归工作后，立即关闭所有干预对话框。
        """
        logger.info("Force cease fire triggered - closing all intervention dialogs")
        self._dialog.force_close()

    def _on_user_action_chosen(self, action_type: str, payload: dict, trust_impact: int) -> None:
        """
        处理用户在对话框中的选择（v3.0: 启用审计并传递 session_blocks）。

        Args:
            action_type: 动作类型（SNOOZE/DISMISS/WHITELIST_TEMP/STRICT_MODE）
            payload: 动作参数（包含 cost 等信息）
            trust_impact: 信任分影响
        """
        logger.info(f"_on_user_action_chosen called: {action_type}, payload={payload}, trust_impact={trust_impact}")
        try:
            # 提取 cost（从 payload 中获取）
            cost = payload.get("cost", 0)

            # v3.0: 对于需要付费的动作（SNOOZE, WHITELIST_TEMP），触发审计
            if cost > 0 and action_type in ["SNOOZE", "WHITELIST_TEMP"]:
                logger.info(f"Triggering audit for {action_type} (cost: {cost})")

                # 显示审计状态
                self._dialog.show_audit_status("正在验证...")

                # 获取当前上下文
                current_context = {
                    "app_name": payload.get("current_app", ""),
                    "window_title": payload.get("current_window_title", ""),
                    "url": payload.get("url", ""),
                }

                # v3.0: 获取 session_blocks
                from storage.database import get_recent_session_blocks
                with ensure_initialized(config.db_path) as conn:
                    session_blocks = get_recent_session_blocks(conn, limit=4)

                # 触发审计（传递 session_blocks）
                self._audit_service.audit_user_choice(
                    user_action_type=action_type,
                    current_context=current_context,
                    original_cost=cost,
                    user_reason=payload.get("reason", ""),
                    session_blocks=session_blocks,  # v3.0: 传递 session_blocks
                    callback=self._process_action_after_audit,
                )
                return

            # 对于不需要审计的动作，直接处理
            self._process_action(action_type, payload, trust_impact, cost)
            # 处理完成后只隐藏对话框（不删除，可以复用）
            self._dialog.hide()

        except Exception as e:
            logger.exception(f"Error processing user action: {e}")
            # 出错时隐藏对话框
            self._dialog.hide()

    def _process_action_after_audit(
        self,
        action_type: str,
        audit_result: str,
        original_cost: int,
        final_cost: int,
        audit_reason: str,
    ) -> None:
        """
        审计完成后处理动作。

        Args:
            action_type: 动作类型
            audit_result: 审计结果
            original_cost: 原始价格
            final_cost: 最终价格
            audit_reason: 审计原因
        """
        try:
            if audit_result == "REJECTED":
                # 审计被拒绝，不执行动作
                logger.warning(f"Action {action_type} rejected by audit: {audit_reason}")
                # 显示拒绝消息后隐藏对话框
                self._dialog.show_audit_result("REJECTED", audit_reason)
                QTimer.singleShot(2500, self._dialog.hide)
                return

            # 使用最终价格（可能已调整）
            payload = {"cost": final_cost}

            # 信任分影响：根据审计结果调整
            # 如果价格被调整，给予额外的信任分惩罚
            trust_impact = -2 if audit_result == "PRICE_ADJUSTED" else 0

            self._process_action(action_type, payload, trust_impact, final_cost)
            # 处理完成后隐藏对话框
            self._dialog.hide()

        except Exception as e:
            logger.exception(f"Error in _process_action_after_audit: {e}")
            # 出错时隐藏对话框
            self._dialog.hide()

    def _process_action(self, action_type: str, payload: dict, trust_impact: int, cost: int) -> None:
        """
        处理动作（支付 + 执行）。

        Args:
            action_type: 动作类型
            payload: 动作参数
            trust_impact: 信任分影响
            cost: 价格
        """
        try:
            # 如果有费用，尝试支付
            if cost > 0:
                success, new_balance, error_msg = self._economy_service.spend(
                    amount=cost,
                    reason=f"购买选项: {action_type}",
                    metadata={"action_type": action_type},
                )
                if not success:
                    logger.warning(f"Payment failed: {error_msg}")
                    # 即使支付失败，仍然执行动作（但记录警告）
                else:
                    logger.info(f"Payment successful: {cost} Coins, new balance: {new_balance}")
            elif cost < 0:
                # 奖励货币（如 STRICT_MODE）
                self._economy_service.earn(
                    amount=abs(cost),
                    reason=f"奖励选项: {action_type}",
                    metadata={"action_type": action_type},
                )

            # 定义更新信任分的函数（保留用于向后兼容）
            def update_trust(delta: int) -> int:
                logger.info(f"update_trust called with delta={delta}")
                with ensure_initialized(config.db_path) as conn:
                    result = update_trust_score(conn, delta)
                    logger.info(f"update_trust result: {result}")
                    return result

            logger.info("Calling handle_action...")
            # 调用 ActionManager 处理动作
            self._action_manager.handle_action(
                action_type=action_type,
                payload=payload,
                trust_impact=trust_impact,
                update_trust_fn=update_trust,
            )

            logger.info(f"Action processed: {action_type}, trust impact: {trust_impact:+d}")
        except Exception as e:
            logger.exception(f"Error processing action: {e}")

    def start(self) -> None:
        """
        启动应用程序（显示主窗口，等待用户点击开始监控）。
        """
        logger.info("Starting FocusGuard...")

        # v3.0: 只显示主窗口，不自动启动监控
        # 用户需要点击主窗口的"开始监控"按钮才会启动监控线程
        self._main_window.show()

        logger.info("Main window shown, waiting for user to start monitoring")

    def stop(self) -> None:
        """
        停止应用程序（优雅关闭）。
        """
        logger.info("Stopping FocusGuard...")

        # 先停止监控（如果正在运行）
        if self._main_window.is_monitoring():
            self._stop_monitoring()

        # 清理强制执行服务
        if hasattr(self, '_enforcement_service'):
            self._enforcement_service.cleanup()

        logger.info("FocusGuard stopped")

    def _on_monitoring_toggled(self, is_monitoring: bool) -> None:
        """
        处理主窗口的监控切换事件。

        Args:
            is_monitoring: 是否开始监控
        """
        if is_monitoring:
            self._start_monitoring()
        else:
            self._stop_monitoring()

    def _on_goal_updated(self, new_goal: str) -> None:
        """
        处理目标更新事件。

        Args:
            new_goal: 新的目标描述
        """
        logger.info(f"Saving goal to database: {new_goal}")

        # 保存目标到 user_profile 表
        with ensure_initialized(config.db_path) as conn:
            # 使用 INSERT OR REPLACE 来更新或插入当前目标
            conn.execute("""
                INSERT INTO user_profile (key, value, updated_at)
                VALUES ('current_goal', ?, strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (new_goal,))
            conn.commit()

        logger.info(f"Goal saved successfully: {new_goal}")

    def _start_monitoring(self) -> None:
        """启动所有监控线程。"""
        logger.info("Starting all monitoring threads...")

        # 启动监控线程
        self._windows_monitor.start()
        self._chrome_monitor.start()
        self._cleaner.start()
        self._engine.start()

        logger.info("All monitors started")

        # 更新主窗口的初始状态
        initial_balance = self._economy_service.get_balance()
        with ensure_initialized(config.db_path) as conn:
            trust_score = get_trust_score(conn)

            # 优先从 user_profile 读取 current_goal，如果没有则从 focus_sessions 读取
            cursor = conn.execute("SELECT value FROM user_profile WHERE key = 'current_goal'")
            row = cursor.fetchone()
            if row and row[0]:
                goal = row[0]
                logger.info(f"Loaded goal from user_profile: {goal}")
            else:
                active_session = get_active_session(conn)
                goal = active_session["goal_text"] if active_session else "未设置目标"
                logger.info(f"Loaded goal from focus_sessions: {goal}")

        self._main_window.update_balance(initial_balance)
        self._main_window.update_trust_score(trust_score)
        self._main_window.update_goal(goal)

    def _stop_monitoring(self) -> None:
        """停止所有监控线程。"""
        logger.info("Stopping all monitoring threads...")

        # 停止所有线程
        if self._engine.isRunning():
            self._engine.stop()
        self._windows_monitor.stop()
        self._chrome_monitor.stop()
        self._cleaner.stop()

        logger.info("All monitors stopped")


def main() -> int:
    """
    应用程序入口点。
    """
    # 配置日志
    setup_logging()

    logger.info("=" * 60)
    logger.info("FocusGuard v2.0 Ultimate starting...")
    logger.info("=" * 60)

    # 创建应用程序
    app = FocusGuardApp(sys.argv)

    # 启动监控
    app.start()

    # 运行事件循环
    ret = app.exec()

    # 清理
    app.stop()

    logger.info("FocusGuard exited cleanly")
    return ret


if __name__ == "__main__":
    sys.exit(main())
