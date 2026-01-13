"""
FocusGuard v2.0 - 诊断工具

检查数据库状态和活动记录。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from storage.database import get_connection, get_activity_summary, DEFAULT_DB_PATH
import sqlite3


def diagnose():
    """诊断数据库状态。"""

    print("=" * 60)
    print("FocusGuard Database Diagnostic Tool")
    print("=" * 60)

    # 连接数据库
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    conn.row_factory = sqlite3.Row

    print(f"\n[Database] Path: {DEFAULT_DB_PATH}")

    # 检查活动记录总数
    cursor = conn.execute("SELECT COUNT(*) as count FROM activity_logs")
    total_count = cursor.fetchone()["count"]
    print(f"[Records] Total activity count: {total_count}")

    if total_count > 0:
        # 查看最近 10 条记录
        cursor = conn.execute("""
            SELECT timestamp, app_name, window_title, url, duration
            FROM activity_logs
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        print("\n[Recent 10 records]:")
        print("-" * 60)
        for row in cursor.fetchall():
            print(f"[{row['timestamp']}]")
            print(f"  App: {row['app_name']}")
            print(f"  Title: {row['window_title'][:50]}")
            if row['url']:
                print(f"  URL: {row['url'][:50]}")
            print()

        # 检查时间戳格式
        cursor = conn.execute("SELECT datetime('now', 'localtime') as now")
        now = cursor.fetchone()["now"]
        print(f"[Current DB Time] {now}")

        # 测试查询 30 秒内的活动
        print("\n[Test Query] Activities in last 30 seconds:")
        cursor = conn.execute("""
            SELECT app_name, window_title, url, SUM(duration) as total_duration
            FROM activity_logs
            WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-30 seconds')
            GROUP BY app_name, window_title
            ORDER BY total_duration DESC
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"[OK] Found {len(rows)} activities")
            for row in rows:
                print(f"  - {row['app_name']}: {row['window_title'][:30]}")
        else:
            print("[ERROR] No activities found in last 30 seconds")

        # 测试查询 5 分钟内的活动
        print("\n[Test Query] Activities in last 5 minutes:")
        cursor = conn.execute("""
            SELECT app_name, window_title, url, SUM(duration) as total_duration
            FROM activity_logs
            WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-300 seconds')
            GROUP BY app_name, window_title
            ORDER BY total_duration DESC
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"[OK] Found {len(rows)} activities")
            for row in rows:
                print(f"  - {row['app_name']}: {row['window_title'][:30]}")
        else:
            print("[ERROR] No activities found in last 5 minutes")

    else:
        print("[WARNING] Database is empty, no activity records yet")
        print("[SUGGESTION] Make sure the main program is running")

    conn.close()

    print("\n" + "=" * 60)
    print("Diagnostic Complete")
    print("=" * 60)


if __name__ == "__main__":
    diagnose()
