"""
FocusGuard v3.0 - Recovery Detector Module

检测用户是否从分心状态回归工作（Recovery 状态检测）。

使用多因素判断系统：
1. 最近 2 分钟内有关闭事件 (USER_CLOSED_TAB/WINDOW/MINIMIZED)
2. 当前应用是工作相关应用
3. 当前窗口不匹配已关闭的分心内容
4. 距离关闭 > 30 秒（宽限期，防止误判）
"""
from __future__ import annotations

import logging
from datetime import datetime

from ..storage.database import get_last_close_event, get_recent_episodic_events

logger = logging.getLogger(__name__)


# 工作相关关键词（用于判断当前窗口是否是工作上下文）
WORK_KEYWORDS = [
    # 编程相关
    "code", "python", "javascript", "typescript", "java", "cpp", "c++",
    "github", "gitlab", "bitbucket",
    "documentation", "docs", "api",
    "stack overflow", "stackoverflow",
    "terminal", "console", "powershell", "bash",
    "vscode", "intellij", "eclipse", "idea", "pycharm",
    "notepad++", "sublime", "atom", "vim",

    # 设计相关
    "figma", "sketch", "photoshop", "illustrator",
    "design", "prototype", "wireframe",

    # 写作相关
    "docs", "document", "report", "paper",
    "word", "excel", "powerpoint", "powerpoint",

    # AI 助手（现代编程工具）
    "claude", "chatgpt", "gemini", "copilot", "cursor",
]

# 分心网站关键词
DISTRACTION_KEYWORDS = [
    "bilibili", "youtube", "tiktok", "douyin",
    "netflix", "hulu", "disney",
    "twitter", "weibo", "instagram", "facebook",
    "reddit", "tieba",
    "game", "steam", "epic", "origin",
    "novel", "comic", "manga",
]


class RecoveryDetector:
    """
    Recovery 状态检测器。

    检测用户是否从分心状态回归工作，使用多因素评分系统。
    """

    def __init__(
        self,
        grace_period_seconds: int = 30,
        detection_window_seconds: int = 120,
        confidence_threshold: float = 0.7,
    ):
        """
        初始化 Recovery 检测器。

        Args:
            grace_period_seconds: 宽限期（秒），关闭后多久才开始检测
            detection_window_seconds: 检测窗口（秒），查找多久内的关闭事件
            confidence_threshold: 置信度阈值，达到此值才判定为 Recovery
        """
        self._grace_period = grace_period_seconds
        self._detection_window = detection_window_seconds
        self._confidence_threshold = confidence_threshold

    def detect_recovery(
        self,
        conn,
        current_app: str,
        current_title: str,
        current_url: str | None = None,
    ) -> tuple[bool, str, float]:
        """
        检测用户是否处于 Recovery 状态（已回归工作）。

        Args:
            conn: 数据库连接
            current_app: 当前应用名称
            current_title: 当前窗口标题
            current_url: 当前 URL（如果有）

        Returns:
            tuple: (is_recovery, reason, confidence)
                - is_recovery: 是否处于 Recovery 状态
                - reason: 判断原因说明
                - confidence: 置信度 (0.0-1.0)
        """
        # Step 1: 检查是否有最近的关闭事件
        last_close = get_last_close_event(
            conn,
            within_seconds=self._detection_window,
        )

        if not last_close:
            return False, "No recent close events", 0.0

        # Step 2: 计算时间差
        close_time_str = last_close["timestamp"]
        try:
            close_time = datetime.fromisoformat(close_time_str)
            time_since_close = (datetime.now() - close_time).total_seconds()
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp format: {close_time_str}")
            return False, "Invalid close event timestamp", 0.0

        # Step 3: 检查宽限期（必须 > 30s 才开始检测）
        if time_since_close < self._grace_period:
            return False, f"Still in grace period ({time_since_close:.0f}s < {self._grace_period}s)", 0.0

        # Step 4: 检查当前窗口是否仍匹配已关闭的分心内容
        closed_keyword = last_close.get("metadata", {}).get("keyword", "")
        closed_title = last_close.get("window_title", "")

        current_title_lower = current_title.lower() if current_title else ""
        closed_keyword_lower = closed_keyword.lower() if closed_keyword else ""

        # 如果当前窗口仍包含已关闭的关键词，说明用户可能还在同一类内容
        if closed_keyword_lower and closed_keyword_lower in current_title_lower:
            return False, f"Still on closed distraction (keyword: {closed_keyword})", 0.0

        # Step 5: 检查当前 URL 是否是分心网站
        if current_url:
            url_lower = current_url.lower()
            for kw in DISTRACTION_KEYWORDS:
                if kw in url_lower:
                    return False, f"Still on distraction site (URL contains: {kw})", 0.0

        # Step 6: 检查当前标题是否是分心内容
        current_title_lower = current_title.lower() if current_title else ""
        for kw in DISTRACTION_KEYWORDS:
            if kw in current_title_lower:
                return False, f"Still on distraction (title contains: {kw})", 0.0

        # Step 7: 计算置信度（多因素评分）
        confidence = 0.0
        reasons = []

        # 因素 1: 时间因素（关闭后 30-120 秒内）
        if self._grace_period <= time_since_close <= self._detection_window:
            time_score = 0.3
            confidence += time_score
            reasons.append(f"Closed {time_since_close:.0f}s ago (in detection window)")

        # 因素 2: 用户主动关闭分心（加分）
        event_type = last_close["event_type"]
        if event_type in ["USER_CLOSED_TAB", "USER_CLOSED_WINDOW"]:
            confidence += 0.3
            reasons.append("User actively closed distraction")
        elif event_type == "USER_MINIMIZED":
            confidence += 0.15
            reasons.append("User minimized distraction")
        elif event_type == "USER_DISMISSED":
            confidence += 0.1
            reasons.append("User dismissed intervention")

        # 因素 3: 当前应用是工作相关应用
        current_app_lower = current_app.lower() if current_app else ""
        if self._is_work_app(current_app_lower):
            confidence += 0.25
            reasons.append(f"Current app '{current_app}' is work-related")
        elif self._is_browser(current_app_lower) and current_url:
            # 浏览器需要检查 URL
            if not self._is_distraction_url(current_url):
                confidence += 0.15
                reasons.append("Browser on non-distraction site")

        # 因素 4: 当前窗口标题包含工作关键词
        if self._has_work_context(current_title):
            confidence += 0.2
            reasons.append("Current window has work context")

        # 因素 5: 检查是否有连续的分心行为（如果有，降低置信度）
        recent_events = get_recent_episodic_events(
            conn,
            seconds=self._detection_window,
            event_types=["DISTRACTION_DETECTED", "INTERVENTION_SHOWN"],
            limit=5,
        )
        distraction_count = len([e for e in recent_events if e["event_type"] in ["DISTRACTION_DETECTED", "INTERVENTION_SHOWN"]])

        if distraction_count >= 3:
            confidence -= 0.2
            reasons.append(f"Multiple recent distractions ({distraction_count}) - lower confidence")

        # 确保置信度在 0-1 范围内
        confidence = max(0.0, min(1.0, confidence))

        is_recovery = confidence >= self._confidence_threshold
        reason = ", ".join(reasons) if reasons else "Insufficient evidence"

        if is_recovery:
            logger.info(f"Recovery state detected: {reason} (confidence: {confidence:.2f})")
        else:
            logger.debug(f"Recovery not detected: {reason} (confidence: {confidence:.2f})")

        return is_recovery, reason, confidence

    def _is_work_app(self, app_name: str) -> bool:
        """检查应用是否是工作相关应用"""
        if not app_name:
            return False

        # IDE 和代码编辑器
        work_apps = [
            "code", "vscode", "intellij", "pycharm", "idea",
            "eclipse", "netbeans", "xcode", "android studio",
            "vim", "nvim", "emacs",
            "notepad++", "sublime", "atom",
        ]

        app_lower = app_name.lower()
        for work_app in work_apps:
            if work_app in app_lower:
                return True

        return False

    def _is_browser(self, app_name: str) -> bool:
        """检查应用是否是浏览器"""
        if not app_name:
            return False

        browsers = ["chrome", "edge", "firefox", "brave", "safari", "opera"]
        app_lower = app_name.lower()
        return any(browser in app_lower for browser in browsers)

    def _is_distraction_url(self, url: str) -> bool:
        """检查 URL 是否是分心网站"""
        if not url:
            return False

        url_lower = url.lower()
        for kw in DISTRACTION_KEYWORDS:
            if kw in url_lower:
                return True
        return False

    def _has_work_context(self, window_title: str) -> bool:
        """检查窗口标题是否包含工作上下文"""
        if not window_title:
            return False

        title_lower = window_title.lower()
        for kw in WORK_KEYWORDS:
            if kw in title_lower:
                return True
        return False
