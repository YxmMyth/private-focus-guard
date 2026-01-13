"""
Session 数据仓库

负责 focus_sessions 表的 CRUD 操作
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .database import db_manager


class SessionRepository:
    """Session 数据仓库"""

    def __init__(self):
        self.db = db_manager

    def create_session(self, goal: str, scope: str = "") -> int:
        """
        创建新的专注会话

        Args:
            goal: 专注目标
            scope: 允许的范围（应用/网站列表）

        Returns:
            新创建的 session_id
        """
        conn = self.db.get_connection()

        cursor = conn.execute('''
            INSERT INTO focus_sessions (goal, scope, start_time, status)
            VALUES (?, ?, ?, 'active')
        ''', (
            goal,
            scope,
            int(datetime.now().timestamp() * 1000)
        ))

        conn.commit()
        print(f'[SessionRepository] 创建会话 #{cursor.lastrowid}: {goal[:30]}...')
        return cursor.lastrowid

    def end_session(self, session_id: int) -> bool:
        """结束会话"""
        conn = self.db.get_connection()

        cursor = conn.execute('''
            UPDATE focus_sessions
            SET end_time = ?, status = 'completed'
            WHERE id = ?
        ''', (
            int(datetime.now().timestamp() * 1000),
            session_id
        ))

        conn.commit()
        success = cursor.rowcount > 0
        if success:
            print(f'[SessionRepository] 结束会话 #{session_id}')
        return success

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """获取当前活跃的会话"""
        conn = self.db.get_connection()

        cursor = conn.execute('''
            SELECT * FROM focus_sessions
            WHERE status = 'active'
            ORDER BY start_time DESC
            LIMIT 1
        ''')

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取会话"""
        conn = self.db.get_connection()

        cursor = conn.execute('''
            SELECT * FROM focus_sessions
            WHERE id = ?
        ''', (session_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def update_session_stats(self, session_id: int,
                           activities_count: int = 0,
                           distractions_count: int = 0,
                           duration: int = 0) -> bool:
        """更新会话统计信息"""
        conn = self.db.get_connection()

        updates = []
        params = []

        if activities_count:
            updates.append("activities_count = activities_count + ?")
            params.append(activities_count)

        if distractions_count:
            updates.append("distractions_count = distractions_count + ?")
            params.append(distractions_count)

        if duration:
            updates.append("total_duration = total_duration + ?")
            params.append(duration)

        if not updates:
            return False

        params.append(session_id)

        cursor = conn.execute(f'''
            UPDATE focus_sessions
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)

        conn.commit()
        return cursor.rowcount > 0

    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取所有会话（最近优先）"""
        conn = self.db.get_connection()

        cursor = conn.execute('''
            SELECT * FROM focus_sessions
            ORDER BY start_time DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_session_activities(self, session_id: int) -> List[Dict[str, Any]]:
        """获取会话关联的所有活动"""
        conn = self.db.get_connection()

        cursor = conn.execute('''
            SELECT * FROM activities
            WHERE session_id = ?
            ORDER BY timestamp DESC
        ''', (session_id,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_session_statistics(self, session_id: int) -> Dict[str, Any]:
        """获取会话统计信息"""
        conn = self.db.get_connection()

        # 获取会话基本信息
        session = self.get_session_by_id(session_id)
        if not session:
            return {}

        # 获取活动统计
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total_activities,
                SUM(duration) as total_duration
            FROM activities
            WHERE session_id = ?
        ''', (session_id,))

        activity_stats = cursor.fetchone()

        return {
            'session_id': session_id,
            'goal': session['goal'],
            'scope': session['scope'],
            'start_time': session['start_time'],
            'end_time': session['end_time'],
            'status': session['status'],
            'total_activities': activity_stats['total_activities'] if activity_stats else 0,
            'total_duration': activity_stats['total_duration'] if activity_stats else 0,
            'activities_count': session['activities_count'],
            'distractions_count': session['distractions_count']
        }


# 全局单例
session_repository = SessionRepository()


# 测试代码
if __name__ == '__main__':
    # 测试数据库初始化
    db_manager.initialize()

    # 测试创建会话
    session_id = session_repository.create_session(
        goal="完成 Python 项目开发",
        scope="VSCode, Chrome, GitHub"
    )
    print(f'创建会话: #{session_id}')

    # 测试获取活跃会话
    active = session_repository.get_active_session()
    print(f'活跃会话: {active}')

    # 测试更新统计
    session_repository.update_session_stats(
        session_id,
        activities_count=5,
        distractions_count=1,
        duration=300000
    )

    # 测试获取统计
    stats = session_repository.get_session_statistics(session_id)
    print(f'会话统计: {stats}')

    # 测试结束会话
    session_repository.end_session(session_id)

    # 测试获取所有会话
    all_sessions = session_repository.get_all_sessions()
    print(f'所有会话: {len(all_sessions)} 个')
