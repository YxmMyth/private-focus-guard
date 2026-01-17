"""
FocusGuard v2.0 - Database Module

负责数据持久化、连接管理（WAL 模式）和线程安全的信任分更新。
"""
from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = Path.home() / ".focusguard" / "focusguard.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    获取 SQLite 数据库连接，启用 WAL 模式提升并发性能。

    Args:
        db_path: 数据库文件路径

    Returns:
        sqlite3.Connection: 配置好的数据库连接
    """
    # 确保父目录存在
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,  # 允许多线程使用（但实际使用时需要外部同步）
    )
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging，提升并发读写性能
    conn.execute("PRAGMA busy_timeout=5000")  # 锁等待超时 5 秒
    conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全
    conn.row_factory = sqlite3.Row  # 返回 dict-like 的行

    return conn


# 全局连接锁（用于写操作同步）
_db_lock = threading.Lock()


@contextlib.contextmanager
def get_db_connection(db_path: str | Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    上下文管理器：自动关闭数据库连接。

    Args:
        db_path: 数据库文件路径

    Yields:
        sqlite3.Connection: 数据库连接
    """
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def initialize_schema(conn: sqlite3.Connection) -> None:
    """
    初始化数据库表结构。

    Args:
        conn: 数据库连接
    """
    # Table: activity_logs - 原始活动流
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            app_name TEXT,
            window_title TEXT,
            url TEXT,
            duration INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON activity_logs(timestamp)")

    # Table: focus_sessions - 用户目标跟踪
    conn.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_text TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'abandoned'))
        )
    """)

    # Table: user_profile - 长期记忆（信任分等）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
    """)

    # 初始化信任分为 80
    conn.execute("""
        INSERT OR IGNORE INTO user_profile (key, value)
        VALUES ('trust_score', '80')
    """)

    # Table: learning_history - 用户选择学习
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            context_summary TEXT,
            user_choice TEXT,
            was_correct INTEGER
        )
    """)

    # ============ 专注货币系统表（Focus Currency）============
    # Table: focus_wallet - 专注货币钱包
    conn.execute("""
        CREATE TABLE IF NOT EXISTS focus_wallet (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_balance INTEGER NOT NULL DEFAULT 0,
            total_earned INTEGER NOT NULL DEFAULT 0,
            total_spent INTEGER NOT NULL DEFAULT 0,
            last_earned_at TEXT,
            last_spent_at TEXT,
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
    """)

    # 初始化钱包（仅首次）
    conn.execute("""
        INSERT OR IGNORE INTO focus_wallet (id, current_balance, total_earned, total_spent)
        VALUES (1, 0, 0, 0)
    """)

    # Table: wallet_transactions - 交易历史
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL CHECK(transaction_type IN ('EARN', 'SPEND', 'PENALTY', 'BONUS')),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            reason TEXT NOT NULL,
            metadata TEXT,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON wallet_transactions(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON wallet_transactions(transaction_type)")

    # ============ 交互审计层表（Interaction Auditor）============
    # Table: interaction_audits - 用户交互审计记录
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interaction_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_action_type TEXT NOT NULL,
            user_reason TEXT,
            current_app TEXT,
            current_window_title TEXT,
            current_url TEXT,
            audit_result TEXT NOT NULL CHECK(audit_result IN ('APPROVED', 'REJECTED', 'PRICE_ADJUSTED')),
            consistency_score REAL,
            audit_reason TEXT,
            original_cost INTEGER,
            final_cost INTEGER,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audits_timestamp ON interaction_audits(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audits_result ON interaction_audits(audit_result)")

    # ============ 数据新陈代谢系统表（Data Metabolism）============
    # Table: session_blocks - 会话砖块（L2 数据）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            focus_density REAL DEFAULT 0.0,
            distraction_count INTEGER DEFAULT 0,
            dominant_apps TEXT,
            energy_level REAL DEFAULT 0.0,
            activity_switches INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES focus_sessions(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_session ON session_blocks(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_time ON session_blocks(start_time)")

    # Table: user_insights - 用户洞察（L3 数据）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_type TEXT NOT NULL CHECK(insight_type IN ('PEAK_HOURS', 'DISTRACTION_PATTERNS', 'APP_PREFERENCES', 'FATIGUE_SIGNALS')),
            data TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            sample_size INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_insights_type ON user_insights(insight_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_insights_time ON user_insights(created_at)")

    # 迁移信任分到专注货币（仅首次）
    _migrate_trust_score_to_currency(conn)

    conn.commit()
    logger.info("Database schema initialized successfully")


def log_activity(
    conn: sqlite3.Connection,
    app_name: str,
    window_title: str,
    url: Optional[str] = None,
    duration: int = 0,
) -> int:
    """
    记录用户活动日志。

    Args:
        conn: 数据库连接
        app_name: 应用程序名称
        window_title: 窗口标题
        url: URL（如果有，如 Chrome）
        duration: 持续时间（秒）

    Returns:
        int: 新插入记录的 ID
    """
    cursor = conn.execute(
        """
        INSERT INTO activity_logs (app_name, window_title, url, duration)
        VALUES (?, ?, ?, ?)
        """,
        (app_name, window_title, url, duration),
    )
    conn.commit()
    return cursor.lastrowid


def get_activity_summary(
    conn: sqlite3.Connection,
    seconds: int,
) -> list[dict]:
    """
    获取最近 N 秒内的活动摘要（用于 LLM 上下文）。

    改进：
    1. 按 app_name 和 url 分组（如果 URL 存在）
    2. 增加窗口标题显示长度（40 → 60 字符）
    3. 按最新活动时间排序（当前活跃窗口优先）

    Args:
        conn: 数据库连接
        seconds: 时间范围（秒）

    Returns:
        list[dict]: 活动摘要列表，每个元素包含应用名、URL（如果有）、窗口数量、窗口标题列表
    """
    # 按 app_name 和 url 分组，统计窗口数量和窗口标题列表
    # 如果 url 为 NULL，则只按 app_name 分组
    cursor = conn.execute(
        """
        SELECT
            app_name,
            url,
            COUNT(DISTINCT window_title) as window_count,
            GROUP_CONCAT(SUBSTR(window_title, 1, 60), ' | ') as windows
        FROM activity_logs
        WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-{} seconds')
        GROUP BY app_name, url
        ORDER BY MAX(timestamp) DESC
        LIMIT 10
        """.format(seconds)
    )

    summary = []
    for row in cursor.fetchall():
        app_name = row[0]
        url = row[1]
        window_count = row[2]
        windows = row[3]

        # 格式化显示（包含 URL 信息）
        if url:
            format_str = f"{app_name} ({url[:50]}... - {window_count} 个窗口)"
        else:
            format_str = f"{app_name} ({window_count} 个窗口)"

        summary.append({
            "app_name": app_name,
            "url": url,  # 新增 URL 字段
            "window_count": window_count,
            "windows": windows,
            "format": format_str
        })

    return summary


def get_trust_score(conn: sqlite3.Connection) -> int:
    """
    获取当前信任分。

    Args:
        conn: 数据库连接

    Returns:
        int: 信任分（0-100）
    """
    cursor = conn.execute(
        "SELECT CAST(value AS INTEGER) as score FROM user_profile WHERE key = 'trust_score'"
    )
    row = cursor.fetchone()
    return row["score"] if row else 80


def update_trust_score(
    conn: sqlite3.Connection,
    delta: int,
) -> int:
    """
    线程安全地更新信任分（使用事务 + 乐观锁）。

    Args:
        conn: 数据库连接
        delta: 增量（可正可负）

    Returns:
        int: 更新后的信任分（0-100 之间）
    """
    with _db_lock:
        # 使用 SQL 的 MAX/MIN 确保值在 0-100 之间
        cursor = conn.execute(
            """
            UPDATE user_profile
            SET value = CAST(MAX(0, MIN(100, CAST(value AS INTEGER) + ?)) AS TEXT),
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            WHERE key = 'trust_score'
            RETURNING CAST(value AS INTEGER) as new_score
            """,
            (delta,),
        )
        # 移除 conn.commit() - 让外部 context manager 处理事务（修复嵌套事务错误）
        row = cursor.fetchone()
        new_score = row["new_score"] if row else 80

        logger.info(f"Trust score updated by {delta:+d}, new score: {new_score}")
        return new_score


def create_focus_session(
    conn: sqlite3.Connection,
    goal_text: str,
) -> int:
    """
    创建新的专注会话。

    Args:
        conn: 数据库连接
        goal_text: 用户目标描述

    Returns:
        int: 新会话 ID
    """
    cursor = conn.execute(
        """
        INSERT INTO focus_sessions (goal_text, start_time)
        VALUES (?, strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        """,
        (goal_text,),
    )
    conn.commit()
    return cursor.lastrowid


def get_active_session(conn: sqlite3.Connection) -> Optional[dict]:
    """
    获取当前活跃的专注会话。

    Args:
        conn: 数据库连接

    Returns:
        Optional[dict]: 会话信息，如果没有活跃会话则返回 None
    """
    cursor = conn.execute(
        """
        SELECT id, goal_text, start_time
        FROM focus_sessions
        WHERE status = 'active'
        ORDER BY start_time DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def end_focus_session(
    conn: sqlite3.Connection,
    session_id: int,
    status: str = "completed",
) -> None:
    """
    结束专注会话。

    Args:
        conn: 数据库连接
        session_id: 会话 ID
        status: 结束状态（completed/abandoned）
    """
    conn.execute(
        """
        UPDATE focus_sessions
        SET end_time = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'),
            status = ?
        WHERE id = ?
        """,
        (status, session_id),
    )
    conn.commit()


def record_learning(
    conn: sqlite3.Connection,
    context_summary: str,
    user_choice: str,
) -> int:
    """
    记录用户选择（用于后续学习用户偏好）。

    Args:
        conn: 数据库连接
        context_summary: 上下文摘要
        user_choice: 用户选择的 action_type

    Returns:
        int: 新记录 ID
    """
    cursor = conn.execute(
        """
        INSERT INTO learning_history (timestamp, context_summary, user_choice)
        VALUES (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'), ?, ?)
        """,
        (context_summary, user_choice),
    )
    conn.commit()
    return cursor.lastrowid


def cleanup_old_logs(
    conn: sqlite3.Connection,
    hours: int = 1,
) -> int:
    """
    清理超过指定小时数的活动日志。

    Args:
        conn: 数据库连接
        hours: 保留时间（小时）

    Returns:
        int: 删除的行数
    """
    cursor = conn.execute(
        """
        DELETE FROM activity_logs
        WHERE timestamp < strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-{} hours')
        """.format(hours)
    )
    conn.commit()
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old activity logs")
    return deleted_count


# 初始化数据库（首次导入时执行）
@contextlib.contextmanager
def ensure_initialized(db_path: str | Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    确保数据库已初始化的上下文管理器。

    Args:
        db_path: 数据库路径

    Yields:
        sqlite3.Connection: 初始化后的数据库连接
    """
    conn = get_connection(db_path)

    # 检查是否已初始化（通过检查表是否存在）
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_logs'"
    )
    if cursor.fetchone() is None:
        initialize_schema(conn)

    try:
        yield conn
    finally:
        conn.close()

# ============ 专注货币系统相关函数 ============


def _migrate_trust_score_to_currency(conn: sqlite3.Connection) -> None:
    """
    迁移信任分到专注货币（仅执行一次）。

    转换公式：initial_balance = trust_score * 1.25
    - Trust Score 80 -> Balance 100 Coins
    - Trust Score < 60 -> Balance 50 Coins
    - Trust Score > 90 -> Balance 150 Coins

    Args:
        conn: 数据库连接
    """
    import json

    # 检查是否已迁移（通过检查钱包是否有余额）
    cursor = conn.execute("SELECT current_balance FROM focus_wallet WHERE id = 1")
    row = cursor.fetchone()

    if row and row[0] != 0:
        # 已有余额，跳过迁移
        logger.info("Focus wallet already has balance, skipping migration")
        return

    # 读取信任分
    trust_score = get_trust_score(conn)

    # 转换公式
    initial_balance = int(trust_score * 1.25)

    # 更新钱包
    conn.execute("""
        UPDATE focus_wallet
        SET current_balance = ?,
            total_earned = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
        WHERE id = 1
    """, (initial_balance, initial_balance))

    # 记录迁移交易
    conn.execute("""
        INSERT INTO wallet_transactions (
            transaction_type, amount, balance_after, reason, metadata
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        "BONUS",
        initial_balance,
        initial_balance,
        "信任分迁移",
        '{"from": "trust_score", "original_value": ' + str(trust_score) + '}'
    ))

    conn.commit()
    logger.info(f"Migrated trust score {trust_score} to balance {initial_balance} Coins")


def get_wallet_balance(conn: sqlite3.Connection) -> int:
    """
    获取当前钱包余额。

    Args:
        conn: 数据库连接

    Returns:
        int: 当前余额（Coins）
    """
    cursor = conn.execute("SELECT current_balance FROM focus_wallet WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else 0


def update_wallet_balance(
    conn: sqlite3.Connection,
    delta: int,
    reason: str,
    transaction_type: str = "EARN",
    metadata: Optional[dict] = None,
) -> int:
    """
    更新钱包余额（线程安全）。

    Args:
        conn: 数据库连接
        delta: 变化量（正数=收入，负数=支出）
        reason: 原因说明
        transaction_type: 交易类型（EARN/SPEND/PENALTY/BONUS）
        metadata: 额外元数据（JSON 格式）

    Returns:
        int: 更新后的余额
    """
    import json

    with _db_lock:
        # 更新钱包
        cursor = conn.execute("""
            UPDATE focus_wallet
            SET current_balance = current_balance + ?,
                total_earned = total_earned + CASE WHEN ? > 0 THEN ? ELSE 0 END,
                total_spent = total_spent + CASE WHEN ? < 0 THEN ABS(?) ELSE 0 END,
                last_earned_at = CASE WHEN ? > 0 THEN strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime') ELSE last_earned_at END,
                last_spent_at = CASE WHEN ? < 0 THEN strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime') ELSE last_spent_at END,
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            WHERE id = 1
            RETURNING current_balance
        """, (delta, delta, delta, delta, delta, delta, delta))

        new_balance = cursor.fetchone()[0]

        # 记录交易历史
        conn.execute("""
            INSERT INTO wallet_transactions (
                transaction_type, amount, balance_after, reason, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            transaction_type,
            delta,
            new_balance,
            reason,
            json.dumps(metadata, ensure_ascii=False) if metadata else None
        ))

        conn.commit()

        logger.info(f"Wallet {transaction_type}: {delta:+d} Coins, new balance: {new_balance}")
        return new_balance


def is_bankrupt(conn: sqlite3.Connection, threshold: int = -50) -> bool:
    """
    检查是否破产。

    Args:
        conn: 数据库连接
        threshold: 破产阈值（默认 -50）

    Returns:
        bool: 是否破产
    """
    balance = get_wallet_balance(conn)
    return balance < threshold

# ============ 交互审计层相关函数 ============


def record_audit(
    conn: sqlite3.Connection,
    user_action_type: str,
    audit_result: str,
    consistency_score: float,
    audit_reason: str,
    current_app: Optional[str] = None,
    current_window_title: Optional[str] = None,
    current_url: Optional[str] = None,
    user_reason: Optional[str] = None,
    original_cost: int = 0,
    final_cost: int = 0,
) -> int:
    """
    记录交互审计结果。

    Args:
        conn: 数据库连接
        user_action_type: 用户选择的动作类型
        audit_result: 审计结果（APPROVED/REJECTED/PRICE_ADJUSTED）
        consistency_score: 一致性分数（0.0-1.0）
        audit_reason: 审计原因说明
        current_app: 当前应用名称
        current_window_title: 当前窗口标题
        current_url: 当前 URL（如果有）
        user_reason: 用户提供的理由（如果有）
        original_cost: 原始价格
        final_cost: 最终价格（调整后）

    Returns:
        int: 新记录 ID
    """
    cursor = conn.execute(
        """
        INSERT INTO interaction_audits (
            user_action_type, user_reason, current_app, current_window_title,
            current_url, audit_result, consistency_score, audit_reason,
            original_cost, final_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_action_type,
            user_reason,
            current_app,
            current_window_title,
            current_url,
            audit_result,
            consistency_score,
            audit_reason,
            original_cost,
            final_cost,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_recent_audits(
    conn: sqlite3.Connection,
    limit: int = 10,
) -> list[dict]:
    """
    获取最近的审计记录。

    Args:
        conn: 数据库连接
        limit: 返回记录数量

    Returns:
        list[dict]: 审计记录列表
    """
    cursor = conn.execute(
        """
        SELECT * FROM interaction_audits
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_approval_rate(
    conn: sqlite3.Connection,
    hours: int = 24,
) -> float:
    """
    获取指定时间内的审批通过率。

    Args:
        conn: 数据库连接
        hours: 时间范围（小时）

    Returns:
        float: 审批通过率（0.0-1.0）
    """
    cursor = conn.execute(
        """
        SELECT
            COUNT(CASE WHEN audit_result = 'APPROVED' THEN 1 END) * 1.0 / COUNT(*) as rate
        FROM interaction_audits
        WHERE timestamp >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-{} hours')
        """.format(hours)
    )
    row = cursor.fetchone()
    return row["rate"] if row and row["rate"] is not None else 0.0

# ============ 数据新陈代谢系统相关函数 ============


def create_session_block(
    conn: sqlite3.Connection,
    session_id: Optional[int],
    start_time: str,
    end_time: str,
    duration_minutes: int,
    focus_density: float = 0.0,
    distraction_count: int = 0,
    dominant_apps: Optional[str] = None,
    energy_level: float = 0.0,
    activity_switches: int = 0,
) -> int:
    """
    创建会话砖块（L2 数据压缩）。

    Args:
        conn: 数据库连接
        session_id: 关联的会话 ID
        start_time: 开始时间
        end_time: 结束时间
        duration_minutes: 持续时间（分钟）
        focus_density: 专注密度（0.0-1.0）
        distraction_count: 分心次数
        dominant_apps: 主要应用（JSON 字符串）
        energy_level: 能量等级（0.0-1.0）
        activity_switches: 活动切换次数

    Returns:
        int: 新记录 ID
    """
    import json

    cursor = conn.execute(
        """
        INSERT INTO session_blocks (
            session_id, start_time, end_time, duration_minutes,
            focus_density, distraction_count, dominant_apps,
            energy_level, activity_switches
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            start_time,
            end_time,
            duration_minutes,
            focus_density,
            distraction_count,
            json.dumps(dominant_apps, ensure_ascii=False) if isinstance(dominant_apps, list) else dominant_apps,
            energy_level,
            activity_switches,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_recent_session_blocks(
    conn: sqlite3.Connection,
    limit: int = 10,
) -> list[dict]:
    """
    获取最近的会话砖块。

    Args:
        conn: 数据库连接
        limit: 返回记录数量

    Returns:
        list[dict]: 会话砖块列表
    """
    cursor = conn.execute(
        """
        SELECT * FROM session_blocks
        ORDER BY start_time DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def create_user_insight(
    conn: sqlite3.Connection,
    insight_type: str,
    data: dict,
    period_start: str,
    period_end: str,
    sample_size: int = 0,
    confidence: float = 1.0,
) -> int:
    """
    创建用户洞察（L3 数据）。

    Args:
        conn: 数据库连接
        insight_type: 洞察类型（PEAK_HOURS/DISTRACTION_PATTERNS/APP_PREFERENCES/FATIGUE_SIGNALS）
        data: 洞察数据（字典）
        period_start: 统计周期开始时间
        period_end: 统计周期结束时间
        sample_size: 样本大小
        confidence: 置信度（0.0-1.0）

    Returns:
        int: 新记录 ID
    """
    import json

    cursor = conn.execute(
        """
        INSERT INTO user_insights (
            insight_type, data, period_start, period_end, sample_size, confidence
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            insight_type,
            json.dumps(data, ensure_ascii=False),
            period_start,
            period_end,
            sample_size,
            confidence,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_latest_insight(
    conn: sqlite3.Connection,
    insight_type: str,
) -> Optional[dict]:
    """
    获取最新的用户洞察。

    Args:
        conn: 数据库连接
        insight_type: 洞察类型

    Returns:
        Optional[dict]: 洞察数据，如果没有则返回 None
    """
    import json

    cursor = conn.execute(
        """
        SELECT * FROM user_insights
        WHERE insight_type = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (insight_type,),
    )
    row = cursor.fetchone()

    if row:
        result = dict(row)
        # 解析 JSON 数据
        if result.get("data"):
            result["data"] = json.loads(result["data"])
        return result

    return None


def get_all_latest_insights(
    conn: sqlite3.Connection,
) -> dict[str, dict]:
    """
    获取所有类型的最新洞察。

    Args:
        conn: 数据库连接

    Returns:
        dict[str, dict]: 洞察类型到洞察数据的映射
    """
    insight_types = ["PEAK_HOURS", "DISTRACTION_PATTERNS", "APP_PREFERENCES", "FATIGUE_SIGNALS"]
    insights = {}

    for insight_type in insight_types:
        insight = get_latest_insight(conn, insight_type)
        if insight:
            insights[insight_type] = insight

    return insights

