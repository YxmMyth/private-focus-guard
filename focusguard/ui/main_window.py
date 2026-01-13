"""
FocusGuard v3.0 - Main Window Module

主窗口 - 提供主控按钮和状态显示。
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QGroupBox,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    FocusGuard 主窗口。

    Features:
        - 主控按钮（开始/停止监控）
        - 状态显示（余额、信任分、专注时长）
        - 目标设置
        - 最小化到系统托盘
    """

    # Signal 定义
    monitoring_toggled = pyqtSignal(bool)  # (is_monitoring: bool)
    goal_updated = pyqtSignal(str)  # (new_goal: str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        初始化主窗口。

        Args:
            parent: 父 QWidget
        """
        super().__init__(parent)

        self._is_monitoring = False
        self._current_balance = 100
        self._trust_score = 80
        self._current_goal = "未设置目标"
        self._focus_time_minutes = 0

        # 窗口设置（增加高度以显示所有内容）
        self.setWindowTitle("FocusGuard v3.0")
        self.setFixedSize(500, 650)

        # 初始化 UI
        self._init_ui()
        self._update_status_display()

        logger.info("MainWindow initialized")

    def _init_ui(self) -> None:
        """初始化 UI 组件。"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 20, 25, 20)

        # 标题
        title_label = QLabel("FocusGuard v3.0")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #2196f3;
                padding: 10px;
            }
        """)
        main_layout.addWidget(title_label)

        # === 主控按钮区域 ===
        control_group = QGroupBox("监控控制")
        control_layout = QVBoxLayout(control_group)

        self._toggle_button = QPushButton("开始监控")
        self._toggle_button.setFixedHeight(60)
        self._toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
                font-weight: 600;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        control_layout.addWidget(self._toggle_button)

        self._status_label = QLabel("监控已暂停")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 5px;
            }
        """)
        control_layout.addWidget(self._status_label)

        # 设置按钮
        settings_button = QPushButton("⚙️ 设置")
        settings_button.setFixedHeight(35)
        settings_button.setStyleSheet(
            """
            QPushButton {
                background-color: #607d8b;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #546e7a;
            }
            QPushButton:pressed {
                background-color: #455a64;
            }
        """
        )
        settings_button.clicked.connect(self._open_settings)
        control_layout.addWidget(settings_button)

        main_layout.addWidget(control_group)

        # === 状态信息区域 ===
        status_group = QGroupBox("当前状态")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(10)

        # 余额和信任分（横向排列）
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(20)

        # 余额
        balance_container = QWidget()
        balance_layout = QVBoxLayout(balance_container)
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(5)
        balance_label = QLabel("余额")
        balance_label.setStyleSheet("font-size: 14px; color: #333; font-weight: 600;")
        self._balance_value = QLabel("100 Coins")
        self._balance_value.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #2196f3;
            }
        """)
        balance_layout.addWidget(balance_label)
        balance_layout.addWidget(self._balance_value)
        metrics_layout.addWidget(balance_container)

        # 信任分
        trust_container = QWidget()
        trust_layout = QVBoxLayout(trust_container)
        trust_layout.setContentsMargins(0, 0, 0, 0)
        trust_layout.setSpacing(5)
        trust_label = QLabel("信任分")
        trust_label.setStyleSheet("font-size: 14px; color: #333; font-weight: 600;")
        self._trust_value = QLabel("80/100")
        self._trust_value.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #ff9800;
            }
        """)
        trust_layout.addWidget(trust_label)
        trust_layout.addWidget(self._trust_value)
        metrics_layout.addWidget(trust_container)

        status_layout.addLayout(metrics_layout)

        # 专注时长
        focus_time_label = QLabel("专注时长")
        focus_time_label.setStyleSheet("font-size: 14px; color: #333; font-weight: 600;")
        self._focus_time_value = QLabel("0 分钟")
        self._focus_time_value.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #4caf50;
            }
        """)
        status_layout.addWidget(focus_time_label)
        status_layout.addWidget(self._focus_time_value)

        main_layout.addWidget(status_group)

        # === 当前目标区域 ===
        goal_group = QGroupBox("当前目标")
        goal_layout = QVBoxLayout(goal_group)

        # 改为可编辑的文本框
        self._goal_input = QTextEdit()
        self._goal_input.setPlainText(self._current_goal)
        self._goal_input.setMaximumHeight(60)
        self._goal_input.setStyleSheet("""
            QTextEdit {
                font-size: 14px;
                color: #333;
                padding: 8px;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)
        goal_layout.addWidget(self._goal_input)

        # 添加"保存目标"按钮
        save_goal_button = QPushButton("保存目标")
        save_goal_button.setFixedHeight(35)
        save_goal_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
        save_goal_button.clicked.connect(self._on_save_goal)
        goal_layout.addWidget(save_goal_button)

        main_layout.addWidget(goal_group)

        # === 底部提示 ===
        tip_label = QLabel("💡 提示：监控运行时会最小化到系统托盘")
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #999;
                padding: 5px;
            }
        """)
        main_layout.addWidget(tip_label)

    def _on_toggle_clicked(self) -> None:
        """处理主控按钮点击。"""
        self._is_monitoring = not self._is_monitoring

        if self._is_monitoring:
            # 开始监控
            self._toggle_button.setText("停止监控")
            self._toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 20px;
                    font-weight: 600;
                    padding: 15px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
            self._status_label.setText("🟢 监控运行中...")
            self._status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #4caf50;
                    font-weight: 600;
                    padding: 5px;
                }
            """)
            logger.info("Monitoring started via main window")
        else:
            # 停止监控
            self._toggle_button.setText("开始监控")
            self._toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #4caf50;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 20px;
                    font-weight: 600;
                    padding: 15px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            self._status_label.setText("⚪ 监控已暂停")
            self._status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #999;
                    padding: 5px;
                }
            """)
            logger.info("Monitoring stopped via main window")

        # 发出信号
        self.monitoring_toggled.emit(self._is_monitoring)

    def _update_status_display(self) -> None:
        """更新状态显示。"""
        # 更新余额显示
        balance_color = "#2196f3" if self._current_balance >= 0 else "#f44336"
        self._balance_value.setText(f"{self._current_balance} Coins")
        self._balance_value.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: 700;
                color: {balance_color};
            }}
        """)

        # 更新信任分显示
        if self._trust_score >= 80:
            trust_color = "#4caf50"
        elif self._trust_score >= 60:
            trust_color = "#ff9800"
        else:
            trust_color = "#f44336"
        self._trust_value.setText(f"{self._trust_score}/100")
        self._trust_value.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: 700;
                color: {trust_color};
            }}
        """)

        # 更新专注时长
        hours = self._focus_time_minutes // 60
        minutes = self._focus_time_minutes % 60
        if hours > 0:
            time_text = f"{hours} 小时 {minutes} 分钟"
        else:
            time_text = f"{minutes} 分钟"
        self._focus_time_value.setText(time_text)

    def update_balance(self, balance: int) -> None:
        """
        更新余额。

        Args:
            balance: 新余额
        """
        self._current_balance = balance
        self._update_status_display()
        logger.info(f"Balance updated: {balance} Coins")

    def update_trust_score(self, score: int) -> None:
        """
        更新信任分。

        Args:
            score: 新信任分（0-100）
        """
        self._trust_score = score
        self._update_status_display()
        logger.info(f"Trust score updated: {score}/100")

    def update_focus_time(self, minutes: int) -> None:
        """
        更新专注时长。

        Args:
            minutes: 专注时长（分钟）
        """
        self._focus_time_minutes = minutes
        self._update_status_display()

    def update_goal(self, goal: str) -> None:
        """
        更新当前目标。

        Args:
            goal: 目标描述
        """
        self._current_goal = goal
        self._goal_input.setPlainText(goal)
        logger.info(f"Goal updated: {goal}")

    def _on_save_goal(self) -> None:
        """
        处理保存目标按钮点击。
        """
        new_goal = self._goal_input.toPlainText().strip()
        if new_goal:
            self._current_goal = new_goal
            self.goal_updated.emit(new_goal)
            logger.info(f"Goal saved: {new_goal}")

    def is_monitoring(self) -> bool:
        """
        检查是否正在监控。

        Returns:
            bool: 是否正在监控
        """
        return self._is_monitoring

    def set_monitoring_state(self, is_monitoring: bool) -> None:
        """
        设置监控状态（用于同步）。

        Args:
            is_monitoring: 是否正在监控
        """
        if self._is_monitoring != is_monitoring:
            self._on_toggle_clicked()

    def _open_settings(self) -> None:
        """打开设置对话框"""
        from ui.dialogs.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 配置已保存
            logger.info("Settings saved by user")
