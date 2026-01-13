"""
FocusGuard v3.0 - Settings Dialog

设置对话框 - 允许用户自定义监控参数。
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QDialog,
)

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None) -> None:
        """
        初始化设置对话框。

        Args:
            parent: 父 QWidget
        """
        super().__init__(parent)
        self.setWindowTitle("FocusGuard 设置")
        self.setFixedSize(500, 450)
        self._init_ui()
        self._load_current_config()

    def _init_ui(self) -> None:
        """初始化UI组件"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 监控配置组 ===
        monitor_group = QGroupBox("监控配置")
        monitor_layout = QFormLayout()

        self.windows_interval_spin = QSpinBox()
        self.windows_interval_spin.setRange(1, 60)
        self.windows_interval_spin.setSuffix(" 秒")
        self.windows_interval_spin.setToolTip("窗口活动监控间隔（秒）")

        self.supervision_interval_spin = QSpinBox()
        self.supervision_interval_spin.setRange(5, 300)
        self.supervision_interval_spin.setSuffix(" 秒")
        self.supervision_interval_spin.setToolTip("监督检查间隔（秒）")

        monitor_layout.addRow("窗口监控间隔:", self.windows_interval_spin)
        monitor_layout.addRow("监控检查间隔:", self.supervision_interval_spin)
        monitor_group.setLayout(monitor_layout)

        # === 数据存储组 ===
        storage_group = QGroupBox("数据存储")
        storage_layout = QFormLayout()

        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_db_path)

        db_path_layout = QHBoxLayout()
        db_path_layout.addWidget(self.db_path_edit)
        db_path_layout.addWidget(browse_btn)

        storage_layout.addRow("数据库路径:", db_path_layout)
        storage_group.setLayout(storage_layout)

        # === 日志配置组 ===
        log_group = QGroupBox("日志配置")
        log_layout = QFormLayout()

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setToolTip("日志级别")

        self.log_file_edit = QLineEdit()
        self.log_file_edit.setToolTip("日志文件路径（可选）")

        log_layout.addRow("日志级别:", self.log_level_combo)
        log_layout.addRow("日志文件:", self.log_file_edit)
        log_group.setLayout(log_layout)

        # === API配置组（只读）===
        api_group = QGroupBox("API 配置 (只读)")
        api_layout = QFormLayout()

        from config import config

        # 脱敏显示API密钥
        api_key_masked = config.llm_api_key[:8] + "..." + config.llm_api_key[-6:]
        self.api_key_label = QLabel(api_key_masked)
        self.api_key_label.setStyleSheet("color: #666; font-family: monospace;")

        self.base_url_label = QLabel(config.llm_base_url)
        self.base_url_label.setStyleSheet("color: #666; font-family: monospace;")
        self.base_url_label.setWordWrap(True)

        self.model_label = QLabel(config.llm_model)
        self.model_label.setStyleSheet("color: #666; font-family: monospace;")

        api_layout.addRow("API 密钥:", self.api_key_label)
        api_layout.addRow("Base URL:", self.base_url_label)
        api_layout.addRow("Model:", self.model_label)
        api_group.setLayout(api_layout)

        # === 按钮 ===
        button_layout = QHBoxLayout()
        restore_btn = QPushButton("恢复默认")
        cancel_btn = QPushButton("取消")
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(
            "background-color: #4caf50; color: white; font-weight: 600; padding: 8px;"
        )

        restore_btn.clicked.connect(self._restore_defaults)
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._save_and_close)

        button_layout.addWidget(restore_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        # === 添加到主布局 ===
        layout.addWidget(monitor_group)
        layout.addWidget(storage_group)
        layout.addWidget(log_group)
        layout.addWidget(api_group)
        layout.addStretch()
        layout.addLayout(button_layout)

    def _load_current_config(self) -> None:
        """从config.py加载当前配置"""
        from config import config

        self.windows_interval_spin.setValue(config.windows_monitor_interval)
        self.supervision_interval_spin.setValue(config.supervision_check_interval)
        self.db_path_edit.setText(config.db_path)
        self.log_level_combo.setCurrentText(config.log_level)
        if config.log_file:
            self.log_file_edit.setText(config.log_file)

    def _browse_db_path(self) -> None:
        """浏览数据库路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择数据库路径",
            str(Path.home() / ".focusguard" / "focusguard.db"),
            "SQLite Database (*.db)",
        )
        if file_path:
            self.db_path_edit.setText(file_path)

    def _restore_defaults(self) -> None:
        """恢复默认值"""
        self.windows_interval_spin.setValue(3)
        self.supervision_interval_spin.setValue(30)
        self.db_path_edit.setText(str(Path.home() / ".focusguard" / "focusguard.db"))
        self.log_level_combo.setCurrentText("INFO")
        self.log_file_edit.setText("")

    def _save_and_close(self) -> None:
        """保存配置并关闭"""
        from config import config

        # 调用config.save_user_config()保存
        config.save_user_config(
            FOCUSGUARD_WINDOWS_MONITOR_INTERVAL=self.windows_interval_spin.value(),
            FOCUSGUARD_SUPERVISION_CHECK_INTERVAL=self.supervision_interval_spin.value(),
            FOCUSGUARD_DB_PATH=self.db_path_edit.text(),
            FOCUSGUARD_LOG_LEVEL=self.log_level_combo.currentText(),
            FOCUSGUARD_LOG_FILE=self.log_file_edit.text() or None,
        )

        QMessageBox.information(
            self,
            "设置已保存",
            "配置已保存。部分设置需要重启监控后生效。",
        )

        self.accept()
