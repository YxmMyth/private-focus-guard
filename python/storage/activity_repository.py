"""
活动数据仓库

作用：
1. 管理活动记录的CRUD操作
2. 提供查询统计功能
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .database import db_manager


class ActivityRepository:
    """活动数据仓库"""

    def __init__(self):
        self.db = db_manager

    def save_activity(
        self,
        activity_type: str,
        timestamp: int,
        duration: int,
        data: Dict[str, Any]
    ) -> int:
        """
        保存活动记录

        Args:
            activity_type: 活动类型 (application/browser)
            timestamp: 时间戳（毫秒）
            duration: 持续时间（毫秒）
            data: 活动数据（字典）

        Returns:
            新记录的ID
        """
        conn = self.db.get_connection()

        cursor = conn.execute('''
            INSERT INTO activities (type, timestamp, duration, data)
            VALUES (?, ?, ?, ?)
        ''', (
            activity_type,
            timestamp,
            duration,
            json.dumps(data, ensure_ascii=False)
        ))

        conn.commit()
        return cursor.lastrowid

    def get_recent_activities(
        self,
        limit: int = 100,
        activity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最近的活动记录

        Args:
            limit: 返回数量限制
            activity_type: 活动类型过滤（可选）

        Returns:
            活动记录列表
        """
        conn = self.db.get_connection()

        if activity_type:
            cursor = conn.execute('''
                SELECT * FROM activities
                WHERE type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (activity_type, limit))
        else:
            cursor = conn.execute('''
                SELECT * FROM activities
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_activities_by_timerange(
        self,
        start_time: int,
        end_time: int,
        activity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定时间范围内的活动记录

        Args:
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            activity_type: 活动类型过滤（可选）

        Returns:
            活动记录列表
        """
        conn = self.db.get_connection()

        if activity_type:
            cursor = conn.execute('''
                SELECT * FROM activities
                WHERE type = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            ''', (activity_type, start_time, end_time))
        else:
            cursor = conn.execute('''
                SELECT * FROM activities
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            ''', (start_time, end_time))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_total_duration(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        activity_type: Optional[str] = None
    ) -> int:
        """
        获取总持续时间

        Args:
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            activity_type: 活动类型过滤（可选）

        Returns:
            总持续时间（毫秒）
        """
        conn = self.db.get_connection()

        if start_time and end_time:
            if activity_type:
                cursor = conn.execute('''
                    SELECT SUM(duration) as total
                    FROM activities
                    WHERE type = ? AND timestamp >= ? AND timestamp <= ?
                ''', (activity_type, start_time, end_time))
            else:
                cursor = conn.execute('''
                    SELECT SUM(duration) as total
                    FROM activities
                    WHERE timestamp >= ? AND timestamp <= ?
                ''', (start_time, end_time))
        else:
            if activity_type:
                cursor = conn.execute('''
                    SELECT SUM(duration) as total
                    FROM activities
                    WHERE type = ?
                ''', (activity_type,))
            else:
                cursor = conn.execute('''
                    SELECT SUM(duration) as total
                    FROM activities
                ''')

        result = cursor.fetchone()
        return result['total'] or 0

    def get_activity_count(
        self,
        activity_type: Optional[str] = None
    ) -> int:
        """
        获取活动记录总数

        Args:
            activity_type: 活动类型过滤（可选）

        Returns:
            活动记录数量
        """
        conn = self.db.get_connection()

        if activity_type:
            cursor = conn.execute('''
                SELECT COUNT(*) as count
                FROM activities
                WHERE type = ?
            ''', (activity_type,))
        else:
            cursor = conn.execute('''
                SELECT COUNT(*) as count
                FROM activities
            ''')

        result = cursor.fetchone()
        return result['count']

    def get_top_apps(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取使用时间最长的应用

        Args:
            hours: 统计最近多少小时
            limit: 返回数量限制

        Returns:
            应用使用统计列表
        """
        conn = self.db.get_connection()

        # 计算时间范围
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (hours * 3600 * 1000)

        cursor = conn.execute('''
            SELECT
                json_extract(data, '$.app_name') as app_name,
                SUM(duration) as total_duration,
                COUNT(*) as activity_count
            FROM activities
            WHERE type = 'application'
            AND timestamp >= ? AND timestamp <= ?
            GROUP BY app_name
            ORDER BY total_duration DESC
            LIMIT ?
        ''', (start_time, end_time, limit))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def delete_old_activities(self, days: int = 30):
        """
        删除旧的活动记录

        Args:
            days: 保留最近多少天的数据
        """
        conn = self.db.get_connection()

        cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        conn.execute('''
            DELETE FROM activities
            WHERE timestamp < ?
        ''', (cutoff_time,))

        conn.commit()
        print(f'已删除 {days} 天前的活动记录')


# 全局活动仓库实例
activity_repository = ActivityRepository()
