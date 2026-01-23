"""
FocusGuard v2.0 - Configuration Module

从环境变量或 .env 文件加载配置。

支持三层配置系统：
1. 内置配置层（打包进exe的bundled_config.env）
2. 用户配置层（~/.focusguard/user_settings.json）
3. 环境变量层（开发环境兼容性）
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """
    配置管理类 - 单例模式。

    支持从环境变量或 .env 文件加载配置。
    """

    _instance: Optional[Config] = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # === 三层配置系统 ===

        # 1. 加载内置配置（从打包资源或开发环境）
        bundled_env_path = self._get_bundled_env_path()
        if bundled_env_path and bundled_env_path.exists():
            load_dotenv(bundled_env_path)
            logger.info(f"Loaded bundled config from {bundled_env_path}")

        # 2. 加载用户自定义配置（可选）
        user_config_path = Path.home() / ".focusguard" / "user_settings.json"
        if user_config_path.exists():
            self._load_user_config(user_config_path)

        # 3. 环境变量覆盖（开发环境兼容性，最低优先级）
        # 注意：这一步只是为了兼容开发环境，生产环境不应该依赖环境变量

        # 数据库配置
        self.db_path: str = os.getenv(
            "FOCUSGUARD_DB_PATH",
            str(Path.home() / ".focusguard" / "focusguard.db")
        )

        # LLM API 配置
        self.llm_api_key: str = os.getenv("FOCUSGUARD_LLM_API_KEY", "")
        user_provided_llm_key = bool(self.llm_api_key)
        self.llm_base_url: str = os.getenv(
            "FOCUSGUARD_LLM_BASE_URL",
            "https://api.openai.com/v1"
        )
        self.llm_model: str = os.getenv("FOCUSGUARD_LLM_MODEL", "gpt-4o-mini")
        self.llm_timeout: int = int(os.getenv("FOCUSGUARD_LLM_TIMEOUT", "30"))

        # 监控间隔配置
        self.windows_monitor_interval: int = int(os.getenv(
            "FOCUSGUARD_WINDOWS_MONITOR_INTERVAL",
            "3"
        ))
        self.supervision_check_interval: int = int(os.getenv(
            "FOCUSGUARD_SUPERVISION_CHECK_INTERVAL",
            "30"
        ))

        # 信任分阈值
        self.trust_strict_threshold: int = int(os.getenv(
            "FOCUSGUARD_TRUST_STRICT_THRESHOLD",
            "60"
        ))
        self.trust_whitelist_threshold: int = int(os.getenv(
            "FOCUSGUARD_TRUST_WHITELIST_THRESHOLD",
            "70"
        ))
        self.trust_trust_threshold: int = int(os.getenv(
            "FOCUSGUARD_TRUST_TRUST_THRESHOLD",
            "90"
        ))

        # 数据清理配置
        self.data_retention_hours: int = int(os.getenv(
            "FOCUSGUARD_DATA_RETENTION_HOURS",
            "1"
        ))
        self.cleanup_interval_seconds: int = int(os.getenv(
            "FOCUSGUARD_CLEANUP_INTERVAL_SECONDS",
            "60"
        ))

        # 日志配置
        self.log_level: str = os.getenv("FOCUSGUARD_LOG_LEVEL", "INFO")
        self.log_file: Optional[str] = os.getenv("FOCUSGUARD_LOG_FILE")

        # UI 配置
        self.dialog_auto_close: bool = os.getenv(
            "FOCUSGUARD_DIALOG_AUTO_CLOSE",
            "false"
        ).lower() == "true"

        # 专注货币系统配置
        self.mining_rate: int = int(os.getenv(
            "FOCUSGUARD_MINING_RATE",
            "1"
        ))
        self.bankruptcy_threshold: int = int(os.getenv(
            "FOCUSGUARD_BANKRUPTCY_THRESHOLD",
            "-50"
        ))

        # 数据新陈代谢配置
        self.l1_to_l2_interval: int = int(os.getenv(
            "FOCUSGUARD_L1_TO_L2_INTERVAL",
            "30"
        ))
        self.l2_to_l3_interval: int = int(os.getenv(
            "FOCUSGUARD_L2_TO_L3_INTERVAL",
            "24"
        ))

        # 交互审计配置
        self.consistency_threshold: float = float(os.getenv(
            "FOCUSGUARD_CONSISTENCY_THRESHOLD",
            "0.5"
        ))

        # 强制执行层配置
        self.enforcement_enabled: bool = os.getenv(
            "FOCUSGUARD_ENFORCEMENT_ENABLED",
            "true"
        ).lower() == "true"
        self.follow_up_interval: int = int(os.getenv(
            "FOCUSGUARD_FOLLOW_UP_INTERVAL",
            "30"
        ))
        self.allow_process_termination: bool = os.getenv(
            "FOCUSGUARD_ALLOW_PROCESS_TERMINATION",
            "false"
        ).lower() == "true"

        # v3.0: Memory 系统配置（Recovery 检测）
        self.recovery_grace_period: int = int(os.getenv(
            "FOCUSGUARD_RECOVERY_GRACE_PERIOD",
            "30"  # 宽限期（秒），关闭后多久才开始检测 Recovery
        ))
        self.recovery_cooldown: int = int(os.getenv(
            "FOCUSGUARD_RECOVERY_COOLDOWN",
            "180"  # 冷却时间（秒），Recovery 后不干预的时间
        ))
        self.episodic_retention_hours: int = int(os.getenv(
            "FOCUSGUARD_EPISODIC_RETENTION_HOURS",
            "24"  # episodic 事件保留时间（小时）
        ))

        # === 强制保护：API密钥始终使用内置值 ===
        # 防止用户通过user_settings.json或环境变量覆盖API密钥
        if not self.llm_api_key and bundled_env_path and bundled_env_path.exists():
            self.llm_api_key = self._get_bundled_api_key()
            logger.info("API key loaded from bundled config (fallback)")

        # Log which key source is active (masked, no secrets).
        if user_provided_llm_key:
            logger.info("API key source: user environment/.env")
        elif self.llm_api_key:
            logger.info("API key source: bundled_config.env")
        else:
            logger.warning("API key source: missing")

        self._initialized = True
        logger.info("Configuration loaded")

    def _get_bundled_env_path(self) -> Optional[Path]:
        """
        获取打包后的内置.env路径。

        Returns:
            Optional[Path]: 配置文件路径，如果不存在则返回None
        """
        if getattr(sys, 'frozen', False):
            # 打包后：.env 在 sys._MEIPASS 根目录（PyInstaller 解压位置）
            meipass_env = Path(sys._MEIPASS) / ".env"
            if meipass_env.exists():
                return meipass_env
            # 回退：在 exe 所在目录查找
            return Path(sys.executable).parent / "bundled_config.env"
        else:
            # 开发环境：优先查找 focusguard 目录下的 .env
            # 然后查找项目根目录的 .env
            focusguard_env = Path(__file__).parent / ".env"
            if focusguard_env.exists():
                return focusguard_env
            return Path(__file__).parent.parent / ".env"

    def _get_bundled_api_key(self) -> str:
        """
        从内置配置获取API密钥（强制保护）。

        Returns:
            str: API密钥
        """
        bundled_env = self._get_bundled_env_path()
        if bundled_env and bundled_env.exists():
            try:
                with open(bundled_env, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('FOCUSGUARD_LLM_API_KEY='):
                            return line.split('=', 1)[1].strip()
            except Exception as e:
                logger.warning(f"Failed to read bundled API key: {e}")
        return os.getenv("FOCUSGUARD_LLM_API_KEY", "")

    def _load_user_config(self, config_path: Path) -> None:
        """
        加载用户自定义配置（仅限安全参数）。

        Args:
            config_path: 用户配置文件路径
        """
        import json
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)

            # 仅允许修改白名单内的参数
            ALLOWED_USER_KEYS = [
                'FOCUSGUARD_WINDOWS_MONITOR_INTERVAL',
                'FOCUSGUARD_SUPERVISION_CHECK_INTERVAL',
                'FOCUSGUARD_DB_PATH',
                'FOCUSGUARD_LOG_LEVEL',
                'FOCUSGUARD_LOG_FILE',
            ]

            for key, value in user_config.items():
                if key in ALLOWED_USER_KEYS:
                    # 将环境变量名转换为属性名
                    attr_name = key.lower().replace('focusguard_', '')
                    if hasattr(self, attr_name):
                        setattr(self, attr_name, value)
                        logger.info(f"User config loaded: {key} = {value}")
        except Exception as e:
            logger.warning(f"Failed to load user config: {e}")

    def save_user_config(self, **kwargs) -> None:
        """
        保存用户配置到user_settings.json。

        Args:
            **kwargs: 配置键值对
        """
        user_config_path = Path.home() / ".focusguard" / "user_settings.json"
        user_config_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取现有配置
        import json
        existing_config = {}
        if user_config_path.exists():
            try:
                with open(user_config_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read existing user config: {e}")

        # 更新允许的参数
        ALLOWED_USER_KEYS = [
            'FOCUSGUARD_WINDOWS_MONITOR_INTERVAL',
            'FOCUSGUARD_SUPERVISION_CHECK_INTERVAL',
            'FOCUSGUARD_DB_PATH',
            'FOCUSGUARD_LOG_LEVEL',
            'FOCUSGUARD_LOG_FILE',
        ]

        for key, value in kwargs.items():
            if key in ALLOWED_USER_KEYS:
                existing_config[key] = value

        # 保存
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)

        logger.info(f"User config saved to {user_config_path}")

    def validate(self) -> bool:
        """
        验证配置是否有效。

        Returns:
            bool: 配置是否有效
        """
        if not self.llm_api_key:
            logger.error("LLM API key is missing. Please set FOCUSGUARD_LLM_API_KEY.")
            return False

        if self.windows_monitor_interval < 1:
            logger.error("Windows monitor interval must be at least 1 second")
            return False

        if self.supervision_check_interval < 5:
            logger.error("Supervision check interval must be at least 5 seconds")
            return False

        return True

    def get_trust_level(self, trust_score: int) -> str:
        """
        根据信任分返回级别描述。

        Args:
            trust_score: 信任分（0-100）

        Returns:
            str: 级别描述（"strict"/"standard"/"trust"）
        """
        if trust_score < self.trust_strict_threshold:
            return "strict"
        elif trust_score > self.trust_trust_threshold:
            return "trust"
        else:
            return "standard"


# 全局配置实例
config = Config()


def setup_logging() -> None:
    """
    配置日志系统。
    """
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    logger.info(f"Logging configured at {config.log_level} level")
