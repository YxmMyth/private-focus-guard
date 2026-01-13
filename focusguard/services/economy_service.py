"""
FocusGuard v2.0 - Economy Service Module

专注货币系统 - 管理用户的专注货币挖矿、消费和破产保护。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from collections.abc import Callable

# Use absolute imports for direct execution
from storage.database import (
    ensure_initialized,
    get_wallet_balance,
    update_wallet_balance,
    is_bankrupt,
)

logger = logging.getLogger(__name__)


# 默认配置
DEFAULT_MINING_RATE = 1  # 每分钟挖矿 1 Coin
DEFAULT_BANKRUPTCY_THRESHOLD = -50  # 破产阈值
DEFAULT_BASE_PRICES = {
    "SNOOZE": 5,  # 稍后提醒的基础价格
    "DISMISS": 0,  # 忽略（通常是误报，不收费）
    "WHITELIST_TEMP": 20,  # 临时白名单价格较高
    "STRICT_MODE": -10,  # 严格模式是自律行为，奖励货币
}


class EconomyService(QObject):
    """
    专注货币服务 - 游戏化经济模型。

    Signals:
        - balance_updated: 余额更新 (new_balance, transaction_info)
        - bankruptcy_triggered: 破产触发（余额低于阈值）

    核心功能:
        - 挖矿：用户专注工作时每分钟获得 1 Coin
        - 消费：用户购买休息选项需要支付货币
        - 破产保护：余额不足时禁用付费选项
    """

    # Signal 定义
    balance_updated = pyqtSignal(int, dict)  # (new_balance, transaction_info)
    bankruptcy_triggered = pyqtSignal()  # 破产警告

    def __init__(
        self,
        db_path: str | Path,
        mining_rate: int = DEFAULT_MINING_RATE,
        bankruptcy_threshold: int = DEFAULT_BANKRUPTCY_THRESHOLD,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        初始化专注货币服务。

        Args:
            db_path: 数据库文件路径
            mining_rate: 挖矿速率（每分钟获得的 Coin 数）
            bankruptcy_threshold: 破产阈值（余额低于此值触发破产保护）
            parent: 父 QObject
        """
        super().__init__(parent)

        self._db_path = Path(db_path)
        self._mining_rate = mining_rate
        self._bankruptcy_threshold = bankruptcy_threshold

        # 缓存当前余额（避免频繁查询数据库）
        self._cached_balance: Optional[int] = None

        logger.info(
            f"EconomyService initialized (mining_rate={mining_rate}, "
            f"bankruptcy_threshold={bankruptcy_threshold})"
        )

    def get_balance(self) -> int:
        """
        获取当前钱包余额。

        Returns:
            int: 当前余额（Coins）
        """
        # 如果有缓存，直接返回
        if self._cached_balance is not None:
            return self._cached_balance

        # 否则从数据库读取
        with ensure_initialized(self._db_path) as conn:
            balance = get_wallet_balance(conn)
            self._cached_balance = balance
            return balance

    def earn(
        self,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        挖矿 - 增加余额。

        Args:
            amount: 增加的 Coin 数量
            reason: 原因说明（如"专注工作 10 分钟"）
            metadata: 额外元数据（如专注时长、应用名称等）

        Returns:
            int: 更新后的余额
        """
        with ensure_initialized(self._db_path) as conn:
            new_balance = update_wallet_balance(
                conn,
                delta=amount,
                reason=reason,
                transaction_type="EARN",
                metadata=metadata,
            )

        # 更新缓存
        self._cached_balance = new_balance

        # 发出 Signal
        transaction_info = {
            "type": "EARN",
            "amount": amount,
            "reason": reason,
            "metadata": metadata,
        }
        self.balance_updated.emit(new_balance, transaction_info)

        logger.info(f"Earned {amount} Coins, new balance: {new_balance}")
        return new_balance

    def spend(
        self,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> tuple[bool, int, str]:
        """
        消费 - 减少余额。

        Args:
            amount: 消费的 Coin 数量
            reason: 原因说明（如"购买 5 分钟休息"）
            metadata: 额外元数据

        Returns:
            tuple[bool, int, str]: (成功与否, 新余额, 错误消息)
        """
        # 检查余额是否足够
        current_balance = self.get_balance()
        if current_balance < amount:
            return (
                False,
                current_balance,
                f"余额不足（需要 {amount} Coins，当前 {current_balance} Coins）",
            )

        with ensure_initialized(self._db_path) as conn:
            new_balance = update_wallet_balance(
                conn,
                delta=-amount,  # 负数表示消费
                reason=reason,
                transaction_type="SPEND",
                metadata=metadata,
            )

        # 更新缓存
        self._cached_balance = new_balance

        # 发出 Signal
        transaction_info = {
            "type": "SPEND",
            "amount": -amount,
            "reason": reason,
            "metadata": metadata,
        }
        self.balance_updated.emit(new_balance, transaction_info)

        # 检查是否破产
        if new_balance < self._bankruptcy_threshold:
            self.bankruptcy_triggered.emit()
            logger.warning(f"Bankruptcy triggered! Balance: {new_balance}")

        logger.info(f"Spent {amount} Coins, new balance: {new_balance}")
        return True, new_balance, ""

    def is_bankrupt(self) -> bool:
        """
        检查是否破产。

        Returns:
            bool: 余额是否低于破产阈值
        """
        balance = self.get_balance()
        return balance < self._bankruptcy_threshold

    def can_afford(self, amount: int) -> bool:
        """
        检查是否能够支付指定金额。

        Args:
            amount: 需要支付的 Coin 数量

        Returns:
            bool: 余额是否足够
        """
        return self.get_balance() >= amount

    def calculate_price(
        self,
        action_type: str,
        severity: float = 1.0,
        user_streak: Optional[dict] = None,
    ) -> int:
        """
        计算动作的价格（基于动态定价）。

        定价策略:
            - 基础价格：从 DEFAULT_BASE_PRICES 获取
            - 严重度系数：severity (0.5-2.0)，越高越贵
            - 用户连续性：连续分心会加价，连续专注会降价
            - 破产保护：余额不足时降低价格（但不低于 1 Coin）

        Args:
            action_type: 动作类型（SNOOZE/DISMISS/WHITELIST_TEMP/STRICT_MODE）
            severity: 严重度系数（0.5-2.0），由 LLM 评估
            user_streak: 用户连续性数据 {"consecutive_distractions": int, "consecutive_focus": int}

        Returns:
            int: 最终价格（Coins）
        """
        # 获取基础价格
        base_price = DEFAULT_BASE_PRICES.get(action_type, 0)

        # 如果是奖励性动作（负价格），直接返回
        if base_price < 0:
            return base_price

        # 如果是免费动作，直接返回
        if base_price == 0:
            return 0

        # 应用严重度系数
        price = int(base_price * severity)

        # 应用用户连续性调整
        if user_streak:
            consecutive_distractions = user_streak.get("consecutive_distractions", 0)
            consecutive_focus = user_streak.get("consecutive_focus", 0)

            # 连续分心惩罚：每次 +20%
            if consecutive_distractions > 0:
                price = int(price * (1 + consecutive_distractions * 0.2))

            # 连续专注奖励：每次 -10%
            if consecutive_focus > 0:
                price = int(price * (1 - consecutive_focus * 0.1))

        # 破产保护：如果用户余额不足，降低价格
        current_balance = self.get_balance()
        if current_balance < price and price > 1:
            # 将价格降低到用户能支付的范围，但不低于 1 Coin
            affordable_price = max(1, current_balance)
            logger.info(
                f"Price adjusted from {price} to {affordable_price} (bankruptcy protection)"
            )
            price = affordable_price

        # 确保价格至少为 1 Coin（除非是免费动作）
        price = max(1, price)

        return price

    def award_bonus(
        self,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        奖励 - 增加余额（类似于 earn，但使用 BONUS 交易类型）。

        Args:
            amount: 奖励的 Coin 数量
            reason: 原因说明（如"完成 1 小时专注"）
            metadata: 额外元数据

        Returns:
            int: 更新后的余额
        """
        with ensure_initialized(self._db_path) as conn:
            new_balance = update_wallet_balance(
                conn,
                delta=amount,
                reason=reason,
                transaction_type="BONUS",
                metadata=metadata,
            )

        # 更新缓存
        self._cached_balance = new_balance

        # 发出 Signal
        transaction_info = {
            "type": "BONUS",
            "amount": amount,
            "reason": reason,
            "metadata": metadata,
        }
        self.balance_updated.emit(new_balance, transaction_info)

        logger.info(f"Awarded {amount} Coins as bonus, new balance: {new_balance}")
        return new_balance

    def apply_penalty(
        self,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        惩罚 - 减少余额（类似于 spend，但使用 PENALTY 交易类型）。

        Args:
            amount: 惩罚的 Coin 数量
            reason: 原因说明（如"检测到欺诈行为"）
            metadata: 额外元数据

        Returns:
            int: 更新后的余额
        """
        with ensure_initialized(self._db_path) as conn:
            new_balance = update_wallet_balance(
                conn,
                delta=-amount,
                reason=reason,
                transaction_type="PENALTY",
                metadata=metadata,
            )

        # 更新缓存
        self._cached_balance = new_balance

        # 发出 Signal
        transaction_info = {
            "type": "PENALTY",
            "amount": -amount,
            "reason": reason,
            "metadata": metadata,
        }
        self.balance_updated.emit(new_balance, transaction_info)

        # 检查是否破产
        if new_balance < self._bankruptcy_threshold:
            self.bankruptcy_triggered.emit()
            logger.warning(f"Bankruptcy triggered! Balance: {new_balance}")

        logger.info(f"Penalty applied: -{amount} Coins, new balance: {new_balance}")
        return new_balance

    def invalidate_cache(self) -> None:
        """
        使余额缓存失效（用于外部直接修改数据库后同步）。
        """
        self._cached_balance = None
        logger.debug("Balance cache invalidated")
