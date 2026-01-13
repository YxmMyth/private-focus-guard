"""
FocusGuard v2.0 - Audit Service Module

交互审计层 - 使用 LLM 检测用户说辞与实际行为的一致性。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer

if TYPE_CHECKING:
    from collections.abc import Callable

from storage.database import (
    ensure_initialized,
    record_audit,
    get_approval_rate,
)

logger = logging.getLogger(__name__)

# 审计结果类型
AUDIT_RESULT_APPROVED = "APPROVED"
AUDIT_RESULT_REJECTED = "REJECTED"
AUDIT_RESULT_PRICE_ADJUSTED = "PRICE_ADJUSTED"


class AuditWorker(QThread):
    """
    审计工作线程 - 在后台执行 LLM 审计调用（v3.0: 注入 session_blocks 上下文）。

    Signal:
        - audit_completed: 审计完成 (action_type, audit_result, original_cost, final_cost, audit_reason)
    """

    audit_completed = pyqtSignal(str, str, int, int, str)  # (action_type, result, original_cost, final_cost, reason)

    def __init__(
        self,
        llm_service,
        user_action_type: str,
        user_reason: Optional[str],
        current_context: dict,
        original_cost: int,
        session_blocks: Optional[list[dict]] = None,  # v3.0: 添加 session_blocks
        parent: Optional[QObject] = None,
    ):
        """
        初始化审计工作线程（v3.0: 接收 session_blocks 上下文）。

        Args:
            llm_service: LLM 服务实例
            user_action_type: 用户选择的动作类型
            user_reason: 用户提供的理由（如果有）
            current_context: 当前上下文（app_name, window_title, url）
            original_cost: 原始价格
            session_blocks: 最近2小时的 session_blocks（L2 数据）
            parent: 父 QObject
        """
        super().__init__(parent)
        self._llm_service = llm_service
        self._user_action_type = user_action_type
        self._user_reason = user_reason
        self._current_context = current_context
        self._original_cost = original_cost
        self._session_blocks = session_blocks or []

    def run(self) -> None:
        """
        执行审计（在后台线程中）。
        """
        try:
            # 构建审计 Prompt
            audit_prompt = self._build_audit_prompt()

            # 调用 LLM 进行审计
            consistency_score, audit_reason = self._call_llm_for_audit(audit_prompt)

            # 根据一致性分数决定审计结果
            audit_result, final_cost = self._determine_result(consistency_score)

            logger.info(
                f"Audit completed: {self._user_action_type} -> {audit_result} "
                f"(consistency: {consistency_score:.2f}, cost: {self._original_cost} -> {final_cost})"
            )

            # 发出完成信号
            self.audit_completed.emit(
                self._user_action_type,
                audit_result,
                self._original_cost,
                final_cost,
                audit_reason,
            )

        except Exception as e:
            logger.exception(f"Audit error: {e}")
            # 审计失败时默认通过
            self.audit_completed.emit(
                self._user_action_type,
                AUDIT_RESULT_APPROVED,
                self._original_cost,
                self._original_cost,
                f"审计失败，已自动通过: {str(e)}",
            )

    def _build_audit_prompt(self) -> str:
        """
        构建审计 Prompt（v3.0: 添加 session_blocks 上下文和 Few-Shot 示例）。

        Returns:
            str: 审计 Prompt
        """
        app_name = self._current_context.get("app_name", "Unknown")
        window_title = self._current_context.get("window_title", "")
        url = self._current_context.get("url", "")

        # v3.0: 格式化 session_blocks 上下文
        session_blocks_summary = self._format_session_blocks()

        prompt = f"""你是 FocusGuard v3.0 的交互审计员。你的职责是验证用户声称是否可信，防止滥用白名单机制。

## 用户声称
- Action: {self._user_action_type}
- Reason: {self._user_reason or "（无）"}
- Current App: {app_name}
- Window Title: {window_title}
- URL: {url or "（无）"}

## 用户最近2小时状态
{session_blocks_summary}

## 审计准则

### 1. 一致性检查
用户当前行为是否与最近2小时的状态一致？
- **高专注密度(>0.8) + 偶尔浏览技术视频** → 一致性高 (0.9-1.0)
- **低专注密度(<0.4) + 频繁切换应用** → 一致性低 (0.0-0.5)

### 2. 应用上下文分析
window_title 是否包含学习关键词？
- **技术关键词**: "react", "vue", "python", "教程", "框架", "编程" → 可能是学习
- **娱乐关键词**: "游戏", "番剧", "娱乐", "搞笑" → 可能是分心
- **模糊关键词**: "学习", "资料" → 需要结合上下文判断

### 3. 历史模式匹配
- 如果用户在观看技术视频时，dominant_apps 包含 [code.exe, python.exe, msedge.exe] → 提高一致性分数
- 如果用户在观看娱乐内容，且最近专注密度低 → 降低一致性分数

## Few-Shot 示例

**示例 1: 高一致性（学习场景）**
上下文:
- focus_density=0.92, dominant_apps=[code.exe, python.exe, msedge.exe]
- window_title="react?vue 框架对比_哔哩哔哩"
- 用户选择"加入白名单"，理由"在学习前端框架"
判断: consistency_score=0.95, reason="高专注度+技术关键词+IDE组合，可信度高"

**示例 2: 中等一致性（模糊场景）**
上下文:
- focus_density=0.65, dominant_apps=[msedge.exe]
- window_title="如何提高工作效率 - 知乎"
- 用户选择"这是学习资料"，理由"查资料"
判断: consistency_score=0.60, reason="中等专注度+自我提升类内容，基本合理"

**示例 3: 低一致性（明显分心）**
上下文:
- focus_density=0.35, dominant_apps=[steam.exe, msedge.exe]
- window_title="Steam 特惠活动"
- 用户选择"加入白名单"，理由"查游戏开发资料"
判断: consistency_score=0.15, reason="低专注度+娱乐平台+理由牵强，明显分心"

## 输出要求
你必须且只能输出以下 JSON 格式，不要包含任何其他文字：

```json
{{
  "consistency_score": number (0.0-1.0),
  "audit_reason": "一句话审计说明，不超过 30 字"
}}
```

## 评分标准
- **0.9-1.0**: 完全一致（高专注度 + 技术关键词 + 合理应用组合）
- **0.7-0.9**: 基本合理（中等专注度 + 学习相关内容）
- **0.5-0.7**: 有些牵强（专注度一般 + 模糊内容）
- **0.3-0.5**: 可疑（低专注度 + 可能分心的内容）
- **0.0-0.3**: 明显撒谎（低专注度 + 娱乐平台 + 牵强理由）
"""
        return prompt

    def _format_session_blocks(self) -> str:
        """
        格式化 session_blocks 为审计上下文（v3.0）。

        Returns:
            str: 格式化的 session_blocks 摘要
        """
        if not self._session_blocks:
            return "（暂无历史数据，无法判断一致性）"

        from collections import Counter

        # 计算聚合指标
        total_blocks = len(self._session_blocks)
        avg_focus_density = sum(b.get("focus_density", 0.0) for b in self._session_blocks) / max(1, total_blocks)
        avg_energy_level = sum(b.get("energy_level", 0.0) for b in self._session_blocks) / max(1, total_blocks)
        total_distractions = sum(b.get("distraction_count", 0) for b in self._session_blocks)

        # 提取所有 dominant_apps
        all_apps = []
        for block in self._session_blocks:
            apps_json = block.get("dominant_apps", "[]")
            try:
                import json
                apps = json.loads(apps_json)
                all_apps.extend(apps)
            except:
                pass

        # 统计最常用应用
        app_counter = Counter(all_apps)
        top_apps = [app for app, _ in app_counter.most_common(5)]

        summary = f"""- 平均专注密度: {avg_focus_density:.2%}
- 平均能量等级: {avg_energy_level:.2f}
- 总分心次数: {total_distractions} 次
- 活跃应用: {", ".join(top_apps) if top_apps else "无"}

最近的 Session Block 详情:"""

        # 添加最近3个砖块的详情
        for block in self._session_blocks[:3]:
            start_time = block.get("start_time", "")[11:16] if block.get("start_time") else "??:??"
            focus = block.get("focus_density", 0.0)
            energy = block.get("energy_level", 0.0)
            distractions = block.get("distraction_count", 0)
            summary += f"\n  [{start_time}] 专注度={focus:.0%}, 能量={energy:.2f}, 分心={distractions}次"

        return summary

    def _call_llm_for_audit(self, prompt: str) -> tuple[float, str]:
        """
        调用 LLM 进行审计。

        Args:
            prompt: 审计 Prompt

        Returns:
            tuple[float, str]: (一致性分数, 审计原因)
        """
        import json

        try:
            # 调用 LLM API（复用现有的 analyze_activity 方法）
            response = self._llm_service._call_api(prompt)

            # 解析响应
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            data = json.loads(response_text)
            consistency_score = data.get("consistency_score", 0.5)
            audit_reason = data.get("audit_reason", "无说明")

            return float(consistency_score), audit_reason

        except Exception as e:
            logger.warning(f"LLM audit failed: {e}, using default score")
            return 0.5, f"审计失败: {str(e)}"

    def _determine_result(self, consistency_score: float) -> tuple[str, int]:
        """
        根据一致性分数决定审计结果和最终价格。

        Args:
            consistency_score: 一致性分数（0.0-1.0）

        Returns:
            tuple[str, int]: (审计结果, 最终价格)
        """
        if consistency_score >= 0.7:
            # 高一致性：通过
            return AUDIT_RESULT_APPROVED, self._original_cost
        elif consistency_score >= 0.4:
            # 中等一致性：价格调整（涨价 50%）
            adjusted_cost = int(self._original_cost * 1.5)
            return AUDIT_RESULT_PRICE_ADJUSTED, adjusted_cost
        else:
            # 低一致性：拒绝
            return AUDIT_RESULT_REJECTED, self._original_cost


class AuditService(QObject):
    """
    交互审计服务 - 防止用户欺诈，动态调价。

    Signals:
        - audit_completed: 审计完成 (action_type, audit_result, original_cost, final_cost, audit_reason)
        - audit_rejected: 审计拒绝 (action_type, reason)

    核心功能:
        - 检测用户说辞与实际行为的一致性
        - 一致性低时驳回或加价
        - 记录审计历史供后续分析
    """

    # Signal 定义
    audit_completed = pyqtSignal(str, str, int, int, str)  # (action_type, result, original_cost, final_cost, reason)
    audit_rejected = pyqtSignal(str, str)  # (action_type, reason)

    def __init__(
        self,
        db_path: str | Path,
        llm_service,
        consistency_threshold: float = 0.5,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        初始化审计服务。

        Args:
            db_path: 数据库文件路径
            llm_service: LLM 服务实例
            consistency_threshold: 一致性阈值（低于此值可能触发加价）
            parent: 父 QObject
        """
        super().__init__(parent)

        self._db_path = Path(db_path)
        self._llm_service = llm_service
        self._consistency_threshold = consistency_threshold

        # 当前正在运行的审计线程
        self._current_audit: Optional[AuditWorker] = None

        logger.info(f"AuditService initialized (threshold={consistency_threshold})")

    def audit_user_choice(
        self,
        user_action_type: str,
        current_context: dict,
        original_cost: int,
        user_reason: Optional[str] = None,
        session_blocks: Optional[list[dict]] = None,  # v3.0: 添加 session_blocks
        callback: Optional[Callable] = None,
    ) -> None:
        """
        异步审计用户选择（在后台线程中执行）（v3.0: 接收 session_blocks）。

        Args:
            user_action_type: 用户选择的动作类型
            current_context: 当前上下文（app_name, window_title, url）
            original_cost: 原始价格
            user_reason: 用户提供的理由（如果有）
            session_blocks: 最近2小时的 session_blocks（L2 数据）
            callback: 审计完成后的回调函数 (action_type, result, original_cost, final_cost, reason) -> None
        """
        # 如果已有审计在运行，先停止它
        if self._current_audit and self._current_audit.isRunning():
            logger.warning("Previous audit still running, will be replaced")

        # 创建审计工作线程（v3.0: 传递 session_blocks）
        self._current_audit = AuditWorker(
            llm_service=self._llm_service,
            user_action_type=user_action_type,
            user_reason=user_reason,
            current_context=current_context,
            original_cost=original_cost,
            session_blocks=session_blocks,  # v3.0: 传递 session_blocks
        )

        # 连接信号
        self._current_audit.audit_completed.connect(self._on_audit_completed)
        self._current_audit.audit_completed.connect(
            lambda act, res, orig, final, reason: (
                self._record_audit_in_db(act, res, orig, final, reason, current_context, user_reason),
                callback(act, res, orig, final, reason) if callback else None
            )
[-1]
        )

        # 启动审计
        self._current_audit.start()
        logger.info(f"Audit started for action: {user_action_type}")

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
            audit_result: 审计结果
            original_cost: 原始价格
            final_cost: 最终价格
            audit_reason: 审计原因
        """
        # 转发信号
        self.audit_completed.emit(action_type, audit_result, original_cost, final_cost, audit_reason)

        # 如果被拒绝，发出额外的拒绝信号
        if audit_result == AUDIT_RESULT_REJECTED:
            self.audit_rejected.emit(action_type, audit_reason)

        logger.info(
            f"Audit result: {action_type} -> {audit_result} "
            f"(cost: {original_cost} -> {final_cost}, reason: {audit_reason})"
        )

    def _record_audit_in_db(
        self,
        action_type: str,
        audit_result: str,
        original_cost: int,
        final_cost: int,
        audit_reason: str,
        current_context: dict,
        user_reason: Optional[str],
    ) -> None:
        """
        将审计结果记录到数据库。

        Args:
            action_type: 动作类型
            audit_result: 审计结果
            original_cost: 原始价格
            final_cost: 最终价格
            audit_reason: 审计原因
            current_context: 当前上下文
            user_reason: 用户理由
        """
        try:
            with ensure_initialized(self._db_path) as conn:
                record_audit(
                    conn=conn,
                    user_action_type=action_type,
                    audit_result=audit_result,
                    consistency_score=0.5,  # TODO: 从 AuditWorker 获取实际分数
                    audit_reason=audit_reason,
                    current_app=current_context.get("app_name"),
                    current_window_title=current_context.get("window_title"),
                    current_url=current_context.get("url"),
                    user_reason=user_reason,
                    original_cost=original_cost,
                    final_cost=final_cost,
                )
        except Exception as e:
            logger.exception(f"Failed to record audit: {e}")

    def get_approval_rate(self, hours: int = 24) -> float:
        """
        获取指定时间内的审批通过率。

        Args:
            hours: 时间范围（小时）

        Returns:
            float: 审批通过率（0.0-1.0）
        """
        with ensure_initialized(self._db_path) as conn:
            return get_approval_rate(conn, hours)
