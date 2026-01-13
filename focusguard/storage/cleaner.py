"""
FocusGuard v2.0 - Data Metabolism Cleaner Module

后台守护线程，负责数据新陈代谢：
- L1 清理：删除 1 小时前的活动日志
- L1→L2 压缩：每 30 分钟将日志压缩为会话砖块
- L2→L3 转化：每天生成用户洞察
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

# 相对导入
from .database import cleanup_old_logs, ensure_initialized, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class DataMetabolismCleaner(QThread):
    """
    数据新陈代谢清理线程 - 实现 L1→L2→L3 的数据流转。

    运行逻辑：
    - 每 60 秒检查一次
    - 删除 1 小时前的活动日志（L1 挥发）
    - 每 30 分钟压缩日志为会话砖块（L1→L2）
    - 每 24 小时生成用户洞察（L2→L3）
    - 异常不会导致线程退出
    """

    # Signal 定义
    cleanup_done = pyqtSignal(int)  # L1 清理完成（删除行数）
    block_created = pyqtSignal(int)  # L1→L2 压缩完成（砖块 ID）
    insight_generated = pyqtSignal(str, dict)  # L2→L3 转化完成（洞察类型, 数据）

    def __init__(
        self,
        db_path: Optional[str] = None,
        data_transformer=None,
        parent: Optional[QThread] = None,
    ) -> None:
        """
        初始化数据新陈代谢清理线程。

        Args:
            db_path: 数据库路径（默认使用 DEFAULT_DB_PATH）
            data_transformer: DataTransformer 实例（用于 L1→L2 和 L2→L3 转化）
            parent: 父 QThread
        """
        super().__init__(parent)

        self._db_path = db_path or DEFAULT_DB_PATH
        self._data_transformer = data_transformer
        self._stop_event = threading.Event()

        # 时间间隔配置
        self._check_interval = 60  # 检查间隔：60 秒
        self._retention_hours = 1  # L1 保留时长：1 小时
        self._l1_to_l2_interval = timedelta(minutes=30)  # L1→L2 压缩间隔：30 分钟
        self._l2_to_l3_interval = timedelta(hours=24)  # L2→L3 转化间隔：24 小时

        # 上次执行时间
        self._last_l1_to_l2_time: Optional[datetime] = None
        self._last_l2_to_l3_time: Optional[datetime] = None

        logger.info("DataMetabolismCleaner initialized")

    def run(self) -> None:
        """
        主循环：定期执行数据新陈代谢。

        线程安全：
        - 使用 _stop_event 进行优雅停止
        - 任何异常都不会退出循环，只记录日志
        """
        logger.info("DataMetabolismCleaner thread started")

        while not self._stop_event.is_set():
            try:
                now = datetime.now()

                # 1. L1 清理：删除过期日志（每次都执行）
                with ensure_initialized(self._db_path) as conn:
                    deleted_count = cleanup_old_logs(conn, hours=self._retention_hours)
                    if deleted_count > 0:
                        self.cleanup_done.emit(deleted_count)
                        logger.debug(f"L1 cleanup: deleted {deleted_count} old logs")

                # 2. L1→L2 压缩：检查是否需要压缩
                if self._should_compress_l1_to_l2(now):
                    self._compress_l1_to_l2(now)
                    self._last_l1_to_l2_time = now

                # 3. L2→L3 转化：检查是否需要生成洞察
                if self._should_transform_l2_to_l3(now):
                    self._transform_l2_to_l3(now)
                    self._last_l2_to_l3_time = now

            except Exception as e:
                # 失败不应导致线程退出
                logger.warning(f"MetabolismCleaner error (non-fatal): {e}", exc_info=True)

            # 等待下一次检查
            self._stop_event.wait(self._check_interval)

        logger.info("DataMetabolismCleaner thread stopped gracefully")

    def _should_compress_l1_to_l2(self, now: datetime) -> bool:
        """
        检查是否应该执行 L1→L2 压缩。

        Args:
            now: 当前时间

        Returns:
            bool: 是否应该压缩
        """
        if self._last_l1_to_l2_time is None:
            # 首次运行，检查是否已经过了首个间隔
            return True

        time_since_last = now - self._last_l1_to_l2_time
        return time_since_last >= self._l1_to_l2_interval

    def _should_transform_l2_to_l3(self, now: datetime) -> bool:
        """
        检查是否应该执行 L2→L3 转化。

        Args:
            now: 当前时间

        Returns:
            bool: 是否应该转化
        """
        if self._last_l2_to_l3_time is None:
            # 首次运行，不立即生成洞察（等待足够数据）
            return False

        time_since_last = now - self._last_l2_to_l3_time
        return time_since_last >= self._l2_to_l3_interval

    def _compress_l1_to_l2(self, now: datetime) -> None:
        """
        执行 L1→L2 压缩。

        Args:
            now: 当前时间
        """
        if self._data_transformer is None:
            logger.warning("DataTransformer not available, skipping L1→L2 compression")
            return

        try:
            block_id = self._data_transformer.compress_logs_to_block()
            if block_id:
                self.block_created.emit(block_id)
                logger.info(f"L1→L2 compression completed: block #{block_id}")
            else:
                logger.debug("L1→L2 compression: no data to compress")
        except Exception as e:
            logger.exception(f"L1→L2 compression failed: {e}")

    def _transform_l2_to_l3(self, now: datetime) -> None:
        """
        执行 L2→L3 转化。

        Args:
            now: 当前时间
        """
        if self._data_transformer is None:
            logger.warning("DataTransformer not available, skipping L2→L3 transformation")
            return

        try:
            insights = self._data_transformer.generate_insights()
            for insight_type, data in insights.items():
                self.insight_generated.emit(insight_type, data)
                logger.info(f"L2→L3 transformation completed: {insight_type}")
        except Exception as e:
            logger.exception(f"L2→L3 transformation failed: {e}")

    def stop(self) -> None:
        """
        请求停止清理线程（优雅关闭）。

        此方法设置 _stop_event，线程会在下一次循环迭代时退出。
        """
        logger.info("DataMetabolismCleaner stop requested")
        self._stop_event.set()

        # 如果线程正在等待，立即唤醒
        self.wait(5000)  # 等待最多 5 秒
        if self.isRunning():
            logger.warning("DataMetabolismCleaner did not stop within timeout")

    def set_check_interval(self, seconds: int) -> None:
        """
        设置检查间隔（用于调试或动态调整）。

        Args:
            seconds: 检查间隔（秒）
        """
        if seconds < 10:
            logger.warning(f"Check interval too short: {seconds}s, keeping 10s minimum")
            seconds = 10

        self._check_interval = seconds
        logger.info(f"Check interval set to {seconds}s")

    def set_retention_hours(self, hours: int) -> None:
        """
        设置 L1 数据保留时长（用于调试或动态调整）。

        Args:
            hours: 保留时长（小时）
        """
        if hours < 1:
            logger.warning(f"Retention too short: {hours}h, keeping 1h minimum")
            hours = 1

        self._retention_hours = hours
        logger.info(f"L1 data retention set to {hours}h")

    def set_l1_to_l2_interval(self, minutes: int) -> None:
        """
        设置 L1→L2 压缩间隔（用于调试或动态调整）。

        Args:
            minutes: 压缩间隔（分钟）
        """
        if minutes < 5:
            logger.warning(f"Compression interval too short: {minutes}min, keeping 5min minimum")
            minutes = 5

        self._l1_to_l2_interval = timedelta(minutes=minutes)
        logger.info(f"L1→L2 compression interval set to {minutes}min")

    def set_l2_to_l3_interval(self, hours: int) -> None:
        """
        设置 L2→L3 转化间隔（用于调试或动态调整）。

        Args:
            hours: 转化间隔（小时）
        """
        if hours < 1:
            logger.warning(f"Transformation interval too short: {hours}h, keeping 1h minimum")
            hours = 1

        self._l2_to_l3_interval = timedelta(hours=hours)
        logger.info(f"L2→L3 transformation interval set to {hours}h")
