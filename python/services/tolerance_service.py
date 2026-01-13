"""
容忍度追踪服务

Phase 3: The Tolerance - 三振出局机制
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

from storage.session_repository import session_repository
from storage.database import db_manager


# 容忍度级别配置
TOLERANCE_LEVELS = {
    1: {'name': '测试模式（立即触发）', 'threshold': 1, 'strike_limit': 1, 'decay_minutes': 5},  # 测试用：1次就弹窗
    2: {'name': '较严', 'threshold': 30, 'strike_limit': 3, 'decay_minutes': 10},
    3: {'name': '默认', 'threshold': 40, 'strike_limit': 5, 'decay_minutes': 10},  # 原默认级别
    4: {'name': '宽松', 'threshold': 50, 'strike_limit': 5, 'decay_minutes': 15},
    5: {'name': '很宽松', 'threshold': 60, 'strike_limit': 7, 'decay_minutes': 20},
}


@dataclass
class StrikeEvent:
    """击打事件（分心事件）"""
    timestamp: datetime
    score: float
    reason: str
    app_name: str
    decayed: bool = False  # 是否已衰减


@dataclass
class ToleranceStatus:
    """容忍度状态"""
    session_id: int
    tolerance_level: int
    total_score: float  # 累积分心值
    strikes_count: int  # 当前击打数
    strike_limit: int  # 击打上限
    threshold: float  # 触发阈值
    should_intervene: bool  # 是否应该触发干预
    recent_strikes: List[StrikeEvent]  # 最近的击打事件


class ToleranceService:
    """容忍度追踪服务"""

    def __init__(self):
        self.session_strikes: Dict[int, deque] = {}  # session_id -> strikes queue
        self.last_update: Dict[int, datetime] = {}  # session_id -> last update time

    def record_judgment(
        self,
        session_id: int,
        is_distracted: bool,
        score: float,
        reason: str,
        app_name: str
    ) -> ToleranceStatus:
        """
        记录判决结果，更新容忍度状态

        Args:
            session_id: 会话ID
            is_distracted: 是否分心
            score: 分心值 (0-10)
            reason: 判决理由
            app_name: 应用名称

        Returns:
            ToleranceStatus: 更新后的容忍度状态
        """
        # 获取会话信息
        session = session_repository.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        tolerance_level = session.get('tolerance_level', 1)  # 默认使用测试模式（1次就触发）
        level_config = TOLERANCE_LEVELS[tolerance_level]

        # 初始化 strikes queue
        if session_id not in self.session_strikes:
            self.session_strikes[session_id] = deque(maxlen=level_config['strike_limit'] * 2)

        strikes_queue = self.session_strikes[session_id]

        # 衰减旧的击打事件
        self._decay_old_strikes(session_id, level_config['decay_minutes'])

        # 如果分心，记录击打
        if is_distracted and score >= 4.0:  # 只有分心值 >= 4.0 才算击打
            strike = StrikeEvent(
                timestamp=datetime.now(),
                score=score,
                reason=reason,
                app_name=app_name
            )
            strikes_queue.append(strike)

        # 计算当前状态
        total_score = sum(s.score for s in strikes_queue if not s.decayed)
        strikes_count = len([s for s in strikes_queue if not s.decayed])

        # 判断是否应该触发干预
        should_intervene = (
            total_score >= level_config['threshold'] or
            strikes_count >= level_config['strike_limit']
        )

        # 更新数据库
        self._update_session_tolerance(
            session_id,
            total_score,
            strikes_count
        )

        status = ToleranceStatus(
            session_id=session_id,
            tolerance_level=tolerance_level,
            total_score=total_score,
            strikes_count=strikes_count,
            strike_limit=level_config['strike_limit'],
            threshold=level_config['threshold'],
            should_intervene=should_intervene,
            recent_strikes=list(strikes_queue)[-5:]  # 最近5次
        )

        return status

    def _decay_old_strikes(self, session_id: int, decay_minutes: int):
        """衰减旧的击打事件"""
        if session_id not in self.session_strikes:
            return

        strikes_queue = self.session_strikes[session_id]
        cutoff_time = datetime.now() - timedelta(minutes=decay_minutes)

        # 标记超过时间窗口的击打为已衰减
        for strike in strikes_queue:
            if strike.timestamp < cutoff_time:
                strike.decayed = True

    def _update_session_tolerance(self, session_id: int, total_score: float, strikes_count: int):
        """更新数据库中的容忍度状态"""
        conn = db_manager.get_connection()

        conn.execute('''
            UPDATE focus_sessions
            SET distraction_score_total = ?,
                strikes_count = ?
            WHERE id = ?
        ''', (total_score, strikes_count, session_id))

        conn.commit()

    def get_tolerance_status(self, session_id: int) -> Optional[ToleranceStatus]:
        """获取当前容忍度状态"""
        session = session_repository.get_session_by_id(session_id)
        if not session:
            return None

        tolerance_level = session.get('tolerance_level', 1)  # 默认使用测试模式（1次就触发）
        level_config = TOLERANCE_LEVELS[tolerance_level]

        total_score = session.get('distraction_score_total', 0.0)
        strikes_count = session.get('strikes_count', 0)

        should_intervene = (
            total_score >= level_config['threshold'] or
            strikes_count >= level_config['strike_limit']
        )

        return ToleranceStatus(
            session_id=session_id,
            tolerance_level=tolerance_level,
            total_score=total_score,
            strikes_count=strikes_count,
            strike_limit=level_config['strike_limit'],
            threshold=level_config['threshold'],
            should_intervene=should_intervene,
            recent_strikes=[]
        )

    def reset_tolerance(self, session_id: int):
        """重置容忍度（例如用户同意回到专注状态）"""
        conn = db_manager.get_connection()

        conn.execute('''
            UPDATE focus_sessions
            SET distraction_score_total = 0,
                strikes_count = 0
            WHERE id = ?
        ''', (session_id,))

        conn.commit()

        # 清空内存中的队列
        if session_id in self.session_strikes:
            self.session_strikes[session_id].clear()

        print(f"[ToleranceService] 会话 #{session_id} 容忍度已重置")

    def increase_tolerance(self, session_id: int):
        """提高容忍度级别（用户可以选择更宽松的设置）"""
        session = session_repository.get_session_by_id(session_id)
        if not session:
            return

        current_level = session.get('tolerance_level', 3)
        new_level = min(current_level + 1, 5)  # 最高不超过5

        conn = db_manager.get_connection()
        conn.execute('''
            UPDATE focus_sessions
            SET tolerance_level = ?
            WHERE id = ?
        ''', (new_level, session_id))
        conn.commit()

        print(f"[ToleranceService] 会话 #{session_id} 容忍度级别: {current_level} -> {new_level}")

    def get_level_description(self, level: int) -> str:
        """获取容忍度级别描述"""
        if level in TOLERANCE_LEVELS:
            config = TOLERANCE_LEVELS[level]
            return (f"{config['name']} - "
                   f"阈值: {config['threshold']}, "
                   f"击打上限: {config['strike_limit']}, "
                   f"衰减: {config['decay_minutes']}分钟")
        return "未知级别"


# 全局单例
tolerance_service = ToleranceService()


# 测试代码
if __name__ == '__main__':
    print("测试容忍度服务...\n")

    # 初始化数据库
    db_manager.initialize()

    # 创建测试会话
    session_id = session_repository.create_session(
        goal="测试容忍度",
        scope="VSCode"
    )

    # 模拟一系列判决
    print("模拟分心事件:")
    distractions = [
        (True, 8.0, "YouTube", "chrome.exe"),
        (True, 7.0, "Bilibili", "chrome.exe"),
        (True, 6.0, "抖音", "edge.exe"),
        (True, 5.0, "微博", "chrome.exe"),
        (False, 0.0, "VSCode", "code.exe"),
    ]

    for is_distracted, score, reason, app in distractions:
        status = tolerance_service.record_judgment(
            session_id, is_distracted, score, reason, app
        )

        print(f"\n活动: {app} | {'分心' if is_distracted else '正常'} | {score}/10")
        print(f"容忍度状态: {tolerance_service.get_level_description(status.tolerance_level)}")
        print(f"累积分心值: {status.total_score:.1f}/{status.threshold}")
        print(f"击打数: {status.strikes_count}/{status.strike_limit}")
        print(f"是否触发干预: {'是' if status.should_intervene else '否'}")

        if status.should_intervene:
            print("\n🚨 触发干预！")
            break

    print(f"\n最终状态:")
    final_status = tolerance_service.get_tolerance_status(session_id)
    print(f"总分心值: {final_status.total_score:.1f}")
    print(f"总击打数: {final_status.strikes_count}")
