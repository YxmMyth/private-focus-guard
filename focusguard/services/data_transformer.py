"""
FocusGuard v2.0 - Data Transformer Module

数据新陈代谢系统 - 实现短期记忆到长期洞察的转化（L1→L2→L3）。
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from collections.abc import Callable

from storage.database import (
    ensure_initialized,
    create_session_block,
    create_user_insight,
    get_activity_summary,
    get_recent_session_blocks,
    get_all_latest_insights,
    get_active_session,
)

logger = logging.getLogger(__name__)


class DataTransformer(QObject):
    """
    数据转化器 - 将原始活动日志压缩为会话砖块和用户洞察。

    Signals:
        - block_created: 会话砖块创建 (block_id)
        - insight_updated: 用户洞察更新 (insight_type, data)

    核心功能:
        - L1→L2: 每 30 分钟压缩活动日志为 session_blocks
        - L2→L3: 每天基于 blocks 生成 user_insights
        - 提供用户上下文供 LLM 使用
    """

    # Signal 定义
    block_created = pyqtSignal(int)  # (block_id)
    insight_updated = pyqtSignal(str, dict)  # (insight_type, data)

    def __init__(
        self,
        db_path: str | Path,
        l1_to_l2_interval_minutes: int = 30,
        l2_to_l3_interval_hours: int = 24,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        初始化数据转化器。

        Args:
            db_path: 数据库文件路径
            l1_to_l2_interval_minutes: L1→L2 压缩间隔（分钟）
            l2_to_l3_interval_hours: L2→L3 转化间隔（小时）
            parent: 父 QObject
        """
        super().__init__(parent)

        self._db_path = Path(db_path)
        self._l1_to_l2_interval = timedelta(minutes=l1_to_l2_interval_minutes)
        self._l2_to_l3_interval = timedelta(hours=l2_to_l3_interval_hours)

        logger.info(
            f"DataTransformer initialized "
            f"(L1→L2: {l1_to_l2_interval_minutes}min, L2→L3: {l2_to_l3_interval_hours}h)"
        )

    def compress_logs_to_block(
        self,
        session_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        将活动日志压缩为会话砖块（L1→L2 转化）。

        Args:
            session_id: 关联的会话 ID（可选）

        Returns:
            Optional[int]: 新创建的砖块 ID，如果没有数据则返回 None
        """
        try:
            with ensure_initialized(self._db_path) as conn:
                # 获取最近的活动日志（基于压缩间隔）
                seconds = int(self._l1_to_l2_interval.total_seconds())
                logs = get_activity_summary(conn, seconds=seconds)

                if not logs:
                    logger.debug("No activity logs to compress")
                    return None

                # 计算砖块指标
                now = datetime.now()
                start_time = now - self._l1_to_l2_interval

                # 计算专注密度（基于应用类型）
                focus_density = self._calculate_focus_density(logs)

                # 计算分心次数（切换到分心应用的次数）
                distraction_count = self._count_distractions(logs)

                # 获取主要应用
                dominant_apps = self._get_dominant_apps(logs)

                # 计算能量等级（基于活动频率）
                energy_level = self._calculate_energy_level(logs)

                # 计算活动切换次数
                activity_switches = len(logs)

                # 创建砖块
                block_id = create_session_block(
                    conn=conn,
                    session_id=session_id,
                    start_time=start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    end_time=now.strftime("%Y-%m-%dT%H:%M:%S"),
                    duration_minutes=int(self._l1_to_l2_interval.total_seconds() / 60),
                    focus_density=focus_density,
                    distraction_count=distraction_count,
                    dominant_apps=dominant_apps,
                    energy_level=energy_level,
                    activity_switches=activity_switches,
                )

                logger.info(
                    f"Created session block #{block_id}: "
                    f"focus={focus_density:.2f}, distractions={distraction_count}, "
                    f"energy={energy_level:.2f}"
                )

                # 发出信号
                self.block_created.emit(block_id)

                return block_id

        except Exception as e:
            logger.exception(f"Failed to compress logs to block: {e}")
            return None

    def generate_insights(
        self,
    ) -> dict[str, dict]:
        """
        基于会话砖块生成用户洞察（L2→L3 转化）。

        Returns:
            dict[str, dict]: 生成的洞察映射
        """
        insights = {}

        try:
            with ensure_initialized(self._db_path) as conn:
                # 获取最近的会话砖块
                blocks = get_recent_session_blocks(conn, limit=100)  # 获取足够多的样本

                if not blocks:
                    logger.debug("No session blocks to analyze")
                    return insights

                # 生成各类洞察
                now = datetime.now()
                period_end = now.strftime("%Y-%m-%dT%H:%M:%S")
                period_start = (now - self._l2_to_l3_interval).strftime("%Y-%m-%dT%H:%M:%S")

                # 1. 高效时段洞察
                peak_hours_insight = self._generate_peak_hours_insight(blocks)
                if peak_hours_insight:
                    insight_id = create_user_insight(
                        conn=conn,
                        insight_type="PEAK_HOURS",
                        data=peak_hours_insight,
                        period_start=period_start,
                        period_end=period_end,
                        sample_size=len(blocks),
                    )
                    insights["PEAK_HOURS"] = peak_hours_insight
                    self.insight_updated.emit("PEAK_HOURS", peak_hours_insight)

                # 2. 分心模式洞察
                distraction_insight = self._generate_distraction_insight(blocks)
                if distraction_insight:
                    insight_id = create_user_insight(
                        conn=conn,
                        insight_type="DISTRACTION_PATTERNS",
                        data=distraction_insight,
                        period_start=period_start,
                        period_end=period_end,
                        sample_size=len(blocks),
                    )
                    insights["DISTRACTION_PATTERNS"] = distraction_insight
                    self.insight_updated.emit("DISTRACTION_PATTERNS", distraction_insight)

                # 3. 应用偏好洞察
                app_insight = self._generate_app_insight(blocks)
                if app_insight:
                    insight_id = create_user_insight(
                        conn=conn,
                        insight_type="APP_PREFERENCES",
                        data=app_insight,
                        period_start=period_start,
                        period_end=period_end,
                        sample_size=len(blocks),
                    )
                    insights["APP_PREFERENCES"] = app_insight
                    self.insight_updated.emit("APP_PREFERENCES", app_insight)

                # 4. 疲劳信号洞察
                fatigue_insight = self._generate_fatigue_insight(blocks)
                if fatigue_insight:
                    insight_id = create_user_insight(
                        conn=conn,
                        insight_type="FATIGUE_SIGNALS",
                        data=fatigue_insight,
                        period_start=period_start,
                        period_end=period_end,
                        sample_size=len(blocks),
                    )
                    insights["FATIGUE_SIGNALS"] = fatigue_insight
                    self.insight_updated.emit("FATIGUE_SIGNALS", fatigue_insight)

                logger.info(f"Generated {len(insights)} insights from {len(blocks)} blocks")
                return insights

        except Exception as e:
            logger.exception(f"Failed to generate insights: {e}")
            return insights

    def get_user_context(
        self,
    ) -> dict:
        """
        获取用户上下文供 LLM 使用。

        Returns:
            dict: 用户上下文（包含洞察数据）
        """
        try:
            with ensure_initialized(self._db_path) as conn:
                insights = get_all_latest_insights(conn)

                context = {
                    "has_insights": len(insights) > 0,
                    "insights": insights,
                }

                # 提取关键信息供 LLM 使用
                if "PEAK_HOURS" in insights:
                    peak_hours = insights["PEAK_HOURS"]["data"]
                    context["peak_hours_summary"] = f"高效时段: {peak_hours.get('description', '未知')}"

                if "FATIGUE_SIGNALS" in insights:
                    fatigue = insights["FATIGUE_SIGNALS"]["data"]
                    context["fatigue_summary"] = fatigue.get("description", "未知")

                return context

        except Exception as e:
            logger.exception(f"Failed to get user context: {e}")
            return {"has_insights": False, "insights": {}}

    def _calculate_focus_density(self, logs: list[dict]) -> float:
        """
        计算专注密度。

        Args:
            logs: 活动日志列表

        Returns:
            float: 专注密度（0.0-1.0）
        """
        if not logs:
            return 0.0

        # 定义专注应用和分心应用
        focus_apps = {
            "code", "python", "vscode", "intellij", "idea", "terminal",
            "word", "excel", "powerpoint", "powerpnt", "notepad",
            "pdf", "adobe", "latex", "markdown",
        }
        distraction_apps = {
            "bilibili", "youtube", "netflix", "tiktok", "douyin",
            "game", "steam", "epic", "origin", "uplay",
            "twitter", "facebook", "instagram", "weibo",
            "zhihu", "reddit", "discord",
        }

        focus_duration = 0
        total_duration = 0

        for log in logs:
            app_name = log.get("app_name", "").lower()
            duration = log.get("total_duration", 0)

            total_duration += duration

            # 判断是否为专注应用
            if any(keyword in app_name for keyword in focus_apps):
                focus_duration += duration
            elif any(keyword in app_name for keyword in distraction_apps):
                # 分心应用不增加专注时长
                pass
            else:
                # 其他应用按 0.5 权重计算
                focus_duration += duration * 0.5

        if total_duration == 0:
            return 0.0

        return min(1.0, focus_duration / total_duration)

    def _count_distractions(self, logs: list[dict]) -> int:
        """
        计算分心次数。

        Args:
            logs: 活动日志列表

        Returns:
            int: 分心次数
        """
        distraction_keywords = ["bilibili", "youtube", "game", "steam", "twitter", "reddit"]
        count = 0

        for log in logs:
            app_name = log.get("app_name", "").lower()
            if any(keyword in app_name for keyword in distraction_keywords):
                count += 1

        return count

    def _get_dominant_apps(self, logs: list[dict]) -> list[str]:
        """
        获取主要应用。

        Args:
            logs: 活动日志列表

        Returns:
            list[str]: 主要应用列表（按使用时长排序）
        """
        app_durations = {}

        for log in logs:
            app_name = log.get("app_name", "Unknown")
            duration = log.get("total_duration", 0)
            app_durations[app_name] = app_durations.get(app_name, 0) + duration

        # 按时长排序，取前 5
        sorted_apps = sorted(app_durations.items(), key=lambda x: x[1], reverse=True)[:5]
        return [app for app, _ in sorted_apps]

    def _calculate_energy_level(self, logs: list[dict]) -> float:
        """
        计算能量等级（基于活动频率和切换次数）。

        Args:
            logs: 活动日志列表

        Returns:
            float: 能量等级（0.0-1.0）
        """
        if not logs:
            return 0.0

        # 活动切换次数
        switches = len(logs)

        # 归一化：假设 10 次切换为正常能量水平
        energy = min(1.0, switches / 10.0)

        return energy

    def _generate_peak_hours_insight(self, blocks: list[dict]) -> Optional[dict]:
        """
        生成高效时段洞察。

        Args:
            blocks: 会话砖块列表

        Returns:
            Optional[dict]: 洞察数据
        """
        if not blocks:
            return None

        # 按小时分组计算平均专注密度
        hour_density = {}

        for block in blocks:
            try:
                start_time = datetime.fromisoformat(block["start_time"])
                hour = start_time.hour
                density = block.get("focus_density", 0.0)

                if hour not in hour_density:
                    hour_density[hour] = []
                hour_density[hour].append(density)
            except Exception as e:
                logger.warning(f"Failed to parse block time: {e}")
                continue

        # 计算每小时的平均专注密度
        hourly_avg = {}
        for hour, densities in hour_density.items():
            hourly_avg[hour] = sum(densities) / len(densities)

        if not hourly_avg:
            return None

        # 找出高峰时段
        peak_hour = max(hourly_avg.items(), key=lambda x: x[1])
        peak_hours = [h for h, d in hourly_avg.items() if d > 0.7]

        return {
            "peak_hour": peak_hour[0],
            "peak_density": float(peak_hour[1]),
            "high_productivity_hours": sorted(peak_hours),
            "hourly_average": {str(k): float(v) for k, v in hourly_avg.items()},
            "description": f"最佳时段: {peak_hour[0]}:00-{peak_hour[0]+1}:00（专注度 {peak_hour[1]:.1%}）",
        }

    def _generate_distraction_insight(self, blocks: list[dict]) -> Optional[dict]:
        """
        生成分心模式洞察。

        Args:
            blocks: 会话砖块列表

        Returns:
            Optional[dict]: 洞察数据
        """
        if not blocks:
            return None

        total_distractions = sum(b.get("distraction_count", 0) for b in blocks)
        avg_distraction = total_distractions / len(blocks)

        # 分析分心趋势
        recent_blocks = blocks[:10]  # 最近 10 个砖块
        recent_avg = sum(b.get("distraction_count", 0) for b in recent_blocks) / len(recent_blocks)

        trend = "stable"
        if recent_avg > avg_distraction * 1.2:
            trend = "increasing"
        elif recent_avg < avg_distraction * 0.8:
            trend = "decreasing"

        return {
            "average_distractions_per_block": float(avg_distraction),
            "recent_average": float(recent_avg),
            "trend": trend,
            "total_blocks_analyzed": len(blocks),
            "description": f"平均分心: {avg_distraction:.1f} 次/30分钟（趋势: {trend}）",
        }

    def _generate_app_insight(self, blocks: list[dict]) -> Optional[dict]:
        """
        生成应用偏好洞察。

        Args:
            blocks: 会话砖块列表

        Returns:
            Optional[dict]: 洞察数据
        """
        import json

        if not blocks:
            return None

        # 统计所有主要应用
        all_apps = []

        for block in blocks:
            try:
                dominant_apps_str = block.get("dominant_apps", "[]")
                dominant_apps = json.loads(dominant_apps_str) if isinstance(dominant_apps_str, str) else dominant_apps_str
                all_apps.extend(dominant_apps)
            except json.JSONDecodeError:
                continue

        if not all_apps:
            return None

        # 统计应用频率
        app_counter = Counter(all_apps)
        top_apps = app_counter.most_common(10)

        return {
            "top_apps": [{"name": app, "count": count} for app, count in top_apps],
            "total_mentions": len(all_apps),
            "diversity_score": len(app_counter) / max(1, len(all_apps)),  # 应用多样性
            "description": f"最常用: {top_apps[0][0] if top_apps else 'N/A'}（{top_apps[0][1] if top_apps else 0} 次）",
        }

    def _generate_fatigue_insight(self, blocks: list[dict]) -> Optional[dict]:
        """
        生成疲劳信号洞察。

        Args:
            blocks: 会话砖块列表

        Returns:
            Optional[dict]: 洞察数据
        """
        if not blocks:
            return None

        # 分析能量等级趋势
        energy_levels = [b.get("energy_level", 0.0) for b in blocks]

        if not energy_levels:
            return None

        avg_energy = sum(energy_levels) / len(energy_levels)
        recent_energy = energy_levels[:5]  # 最近 5 个砖块
        recent_avg = sum(recent_energy) / len(recent_energy)

        # 判断疲劳状态
        fatigue_level = "normal"
        if recent_avg < avg_energy * 0.6:
            fatigue_level = "high"
        elif recent_avg < avg_energy * 0.8:
            fatigue_level = "moderate"

        return {
            "average_energy_level": float(avg_energy),
            "recent_energy_level": float(recent_avg),
            "fatigue_level": fatigue_level,
            "energy_decline": float(avg_energy - recent_avg),
            "description": f"疲劳程度: {fatigue_level}（能量下降 {avg_energy - recent_avg:.1%}）",
        }
