"""
SQLite数据库管理

作用：
1. 管理SQLite数据库连接
2. 初始化所有表结构
3. 提供数据库统计信息
"""

import sqlite3
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class DatabaseManager:
    """数据库管理器单例类"""

    _instance = None
    _db_path: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.conn: Optional[sqlite3.Connection] = None

    def initialize(self, db_path: Optional[str] = None) -> sqlite3.Connection:
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径

        Returns:
            数据库连接对象
        """
        if self.conn:
            return self.conn

        try:
            # 确定数据库路径
            if db_path is None:
                # 使用用户数据目录
                home_dir = Path.home()
                data_dir = home_dir / '.focusguard' / 'data'
                data_dir.mkdir(parents=True, exist_ok=True)
                db_path = str(data_dir / 'focusguard.db')

            self._db_path = db_path

            # 创建数据库连接
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 使用字典式访问

            # 启用外键约束
            self.conn.execute('PRAGMA foreign_keys = ON')

            # 初始化表结构
            self._initialize_tables()

            print(f'[OK] SQLite数据库已初始化: {db_path}')

            return self.conn

        except Exception as error:
            print(f'[ERROR] 数据库初始化失败: {error}')
            raise

    def _initialize_tables(self):
        """初始化所有表"""
        if not self.conn:
            raise RuntimeError('数据库未初始化')

        # 活动记录表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                duration INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 创建索引
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_activities_timestamp
            ON activities(timestamp)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_activities_type
            ON activities(type)
        ''')

        # 专注目标表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS focus_goals (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                schedule TEXT,
                blocked_sites TEXT,
                allowed_sites TEXT,
                blocked_apps TEXT,
                allowed_apps TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 规则表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                conditions TEXT NOT NULL,
                action TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 判断历史表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS judgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER,
                is_distracted INTEGER,
                confidence REAL,
                action TEXT,
                reason TEXT,
                llm_provider TEXT,
                llm_model TEXT,
                rule_id TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                FOREIGN KEY (activity_id) REFERENCES activities(id)
            )
        ''')

        # 创建索引
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_judgments_activity
            ON judgments(activity_id)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_judgments_timestamp
            ON judgments(created_at)
        ''')

        # 对话历史表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                judgment_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                FOREIGN KEY (judgment_id) REFERENCES judgments(id)
            )
        ''')

        # ============ NEW: focus_sessions table ============
        # 专注会话表 - 记录用户的专注会话（Phase 1: The Contract）
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                scope TEXT,
                start_time INTEGER NOT NULL,
                end_time INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                activities_count INTEGER DEFAULT 0,
                distractions_count INTEGER DEFAULT 0,
                total_duration INTEGER DEFAULT 0,
                tolerance_level INTEGER DEFAULT 1,  # 测试模式：1次就触发
                strikes_count INTEGER DEFAULT 0,
                distraction_score_total REAL DEFAULT 0.0,
                intervention_triggered INTEGER DEFAULT 0,
                interventions_count INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 创建索引
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON focus_sessions(status)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_start_time
            ON focus_sessions(start_time)
        ''')
        # ============ END: focus_sessions table ============

        # 尝试给 activities 表添加 session_id 外键（如果不存在）
        try:
            self.conn.execute('''
                ALTER TABLE activities
                ADD COLUMN session_id INTEGER REFERENCES focus_sessions(id)
            ''')
            print('[OK] activities 表已添加 session_id 字段')
        except sqlite3.OperationalError:
            # 列可能已存在，忽略错误
            pass

        # 尝试给 focus_sessions 表添加容忍度字段（Phase 3: The Tolerance）
        tolerance_columns = [
            ('tolerance_level', 'INTEGER DEFAULT 1'),  # 测试模式
            ('strikes_count', 'INTEGER DEFAULT 0'),
            ('distraction_score_total', 'REAL DEFAULT 0.0'),
            ('intervention_triggered', 'INTEGER DEFAULT 0'),
            ('interventions_count', 'INTEGER DEFAULT 0')
        ]

        for column_name, column_def in tolerance_columns:
            try:
                self.conn.execute(f'''
                    ALTER TABLE focus_sessions
                    ADD COLUMN {column_name} {column_def}
                ''')
                print(f'[OK] focus_sessions 表已添加 {column_name} 字段')
            except sqlite3.OperationalError:
                # 列可能已存在，忽略错误
                pass

        # 系统配置表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 用户偏好表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                url_pattern TEXT,
                app_name TEXT,
                decision TEXT NOT NULL,
                reason TEXT,
                confidence INTEGER DEFAULT 50,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        ''')

        # 创建索引
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_preferences_type
            ON user_preferences(activity_type)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_preferences_decision
            ON user_preferences(decision)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_preferences_confidence
            ON user_preferences(confidence)
        ''')

        # 提交所有更改
        self.conn.commit()

        # 插入默认配置
        cursor = self.conn.execute('SELECT COUNT(*) as count FROM config')
        config_count = cursor.fetchone()['count']

        if config_count == 0:
            default_config = [
                ('llm_provider', 'hunyuan'),
                ('llm_model', 'hunyuan-lite'),
                ('monitoring_enabled', '0'),
                ('monitoring_interval', '3000'),
                ('auto_start', '0')
            ]
            self.conn.executemany(
                'INSERT INTO config (key, value) VALUES (?, ?)',
                default_config
            )
            self.conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            数据库连接对象

        Raises:
            RuntimeError: 如果数据库未初始化
        """
        if not self.conn:
            raise RuntimeError('数据库未初始化，请先调用 initialize()')
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            print('数据库连接已关闭')

    def clear_all_data(self):
        """清空所有数据（谨慎使用）"""
        if not self.conn:
            raise RuntimeError('数据库未初始化')

        self.conn.execute('DELETE FROM activities')
        self.conn.execute('DELETE FROM focus_goals')
        self.conn.execute('DELETE FROM rules')
        self.conn.execute('DELETE FROM judgments')
        self.conn.execute('DELETE FROM conversations')
        self.conn.execute('DELETE FROM config')
        self.conn.execute('DELETE FROM user_preferences')
        self.conn.execute('DELETE FROM focus_sessions')  # NEW: 清空专注会话

        # 重新插入默认配置
        default_config = [
            ('llm_provider', 'hunyuan'),
            ('llm_model', 'hunyuan-lite'),
            ('monitoring_enabled', '0'),
            ('monitoring_interval', '3000'),
            ('auto_start', '0')
        ]
        self.conn.executemany(
            'INSERT INTO config (key, value) VALUES (?, ?)',
            default_config
        )

        self.conn.commit()
        print('所有数据已清空')

    def get_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            包含统计信息的字典
        """
        if not self.conn:
            raise RuntimeError('数据库未初始化')

        stats = {}

        # 统计各表的记录数
        tables = ['activities', 'focus_goals', 'rules', 'judgments',
                  'conversations', 'user_preferences', 'focus_sessions']  # NEW: 添加 focus_sessions

        for table in tables:
            cursor = self.conn.execute(f'SELECT COUNT(*) as count FROM {table}')
            stats[table] = cursor.fetchone()['count']

        # 获取数据库文件大小
        if self._db_path and os.path.exists(self._db_path):
            stats['dbSize'] = os.path.getsize(self._db_path)
        else:
            stats['dbSize'] = 0

        return stats

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        执行SQL语句

        Args:
            sql: SQL语句
            params: 参数元组

        Returns:
            游标对象
        """
        if not self.conn:
            raise RuntimeError('数据库未初始化')
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """
        批量执行SQL语句

        Args:
            sql: SQL语句
            params_list: 参数列表

        Returns:
            游标对象
        """
        if not self.conn:
            raise RuntimeError('数据库未初始化')
        return self.conn.executemany(sql, params_list)

    def commit(self):
        """提交事务"""
        if self.conn:
            self.conn.commit()

    def rollback(self):
        """回滚事务"""
        if self.conn:
            self.conn.rollback()


# 全局数据库实例
db_manager = DatabaseManager()


# 测试代码
if __name__ == '__main__':
    # 测试数据库初始化
    db = db_manager.initialize()

    # 测试插入数据
    db.execute('''
        INSERT INTO activities (type, timestamp, duration, data)
        VALUES (?, ?, ?, ?)
    ''', ('application', int(datetime.now().timestamp() * 1000), 60000,
          json.dumps({'app_name': 'TestApp', 'title': 'Test Window'})))

    db.commit()

    # 测试查询数据
    cursor = db.execute('SELECT * FROM activities')
    print('活动记录:')
    for row in cursor.fetchall():
        print(dict(row))

    # 测试统计信息
    stats = db_manager.get_stats()
    print('\n数据库统计:')
    for key, value in stats.items():
        print(f'  {key}: {value}')

    # 关闭数据库
    db_manager.close()
