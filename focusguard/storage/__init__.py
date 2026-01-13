"""
FocusGuard v2.0 - Storage Package

数据层：负责数据持久化和清理。
"""

from .database import (
    get_connection,
    get_db_connection,
    ensure_initialized,
    initialize_schema,
    log_activity,
    get_activity_summary,
    get_trust_score,
    update_trust_score,
    create_focus_session,
    get_active_session,
    end_focus_session,
    record_learning,
    cleanup_old_logs,
    DEFAULT_DB_PATH,
)
# Import the new class name, but provide alias for backward compatibility
from .cleaner import DataMetabolismCleaner as DataCleaner

__all__ = [
    "get_connection",
    "get_db_connection",
    "ensure_initialized",
    "initialize_schema",
    "log_activity",
    "get_activity_summary",
    "get_trust_score",
    "update_trust_score",
    "create_focus_session",
    "get_active_session",
    "end_focus_session",
    "record_learning",
    "cleanup_old_logs",
    "DataCleaner",  # Alias for DataMetabolismCleaner
    "DataMetabolismCleaner",  # New name (for reference)
    "DEFAULT_DB_PATH",
]
