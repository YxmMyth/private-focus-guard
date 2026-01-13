"""
FocusGuard v2.0 - Intervention Dialog Module

动态选项对话框 - Card Style 布局，根据 LLM 返回的选项生成按钮。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Callable

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QWidget,
    QFrame,
)
from PyQt6.QtGui import QFont

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# 按钮样式映射
STYLE_MAP = {
    "normal": """
        QPushButton {
            background-color: #f0f0f0;
            color: #333;
            border: 1px solid #ccc;
            border-radius: 6px;
            padding: 8px 15px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
        }
        QPushButton:pressed {
            background-color: #d0d0d0;
        }
    """,
    "warning": """
        QPushButton {
            background-color: #ff9800;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 15px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #f57c00;
        }
        QPushButton:pressed {
            background-color: #e65100;
        }
    """,
    "primary": """
        QPushButton {
            background-color: #2196f3;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 15px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #1976d2;
        }
        QPushButton:pressed {
            background-color: #0d47a1;
        }
    """,
    "disabled": """
        QPushButton {
            background-color: #e0e0e0;
            color: #888;
            border: 1px solid #ccc;
            border-radius: 6px;
            padding: 8px 15px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
        }
    """,
}


class InterventionDialog(QDialog):
    """
    干预对话框 - Card Style 布局。

    Signal:
        - action_chosen: 用户选择动作后发出 (action_type, payload, trust_impact)
    """

    action_chosen = pyqtSignal(str, dict, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        初始化干预对话框。

        Args:
            parent: 父 QWidget
        """
        super().__init__(parent)

        # 窗口设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置固定大小（增加高度以显示推理内容和按钮）
        self.setFixedSize(500, 500)

        # 当前余额
        self._current_balance = 0

        # 初始化 UI
        self._init_ui()

        logger.info("InterventionDialog initialized")

    def _init_ui(self) -> None:
        """初始化 UI 组件。"""
        # 主容器（卡片背景）
        self._card = QFrame(self)
        self._card.setGeometry(10, 10, 480, 480)
        self._card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.98);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)

        # 主布局
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 顶部容器（包含余额标签和分析摘要）
        top_container = QWidget(self._card)
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # 左侧：AI 分析摘要
        self._analysis_label = QLabel(top_container)
        self._analysis_label.setWordWrap(True)
        self._analysis_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 16px;
                font-weight: 600;
                padding: 10px;
                background-color: #f5f5f5;
                border-radius: 8px;
            }
        """)
        top_layout.addWidget(self._analysis_label, 1)  # stretch=1

        # 右侧：余额标签
        self._balance_label = QLabel(top_container)
        self._balance_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self._balance_label.setStyleSheet("""
            QLabel {
                color: #2196f3;
                font-size: 14px;
                font-weight: 700;
                padding: 8px 12px;
                background-color: #e3f2fd;
                border-radius: 6px;
            }
        """)
        self._balance_label.setText("0 Coins")
        top_layout.addWidget(self._balance_label)  # stretch=0

        layout.addWidget(top_container)

        # 中部：选项按钮容器
        self._buttons_container = QWidget(self._card)
        self._buttons_layout = QVBoxLayout(self._buttons_container)
        self._buttons_layout.setSpacing(10)
        layout.addWidget(self._buttons_container)

        # AI 推理过程标签（v3.0: 显示 thought_trace）
        self._reasoning_label = QLabel(self._card)
        self._reasoning_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._reasoning_label.setWordWrap(True)
        self._reasoning_label.setMinimumHeight(80)  # 设置最小高度以确保内容可见
        self._reasoning_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 13px;
                padding: 12px;
                background-color: #f0f7ff;
                border: 1px solid #b3d9ff;
                border-radius: 8px;
            }
        """)
        self._reasoning_label.setVisible(False)  # 默认隐藏，有 thought_trace 时显示
        layout.addWidget(self._reasoning_label)

        # 审计状态标签（隐藏，审计时显示）
        self._audit_status_label = QLabel(self._card)
        self._audit_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._audit_status_label.setStyleSheet("""
            QLabel {
                color: #ff9800;
                font-size: 13px;
                font-weight: 600;
                padding: 8px;
                background-color: #fff3e0;
                border-radius: 6px;
            }
        """)
        self._audit_status_label.setText("正在验证...")
        self._audit_status_label.setVisible(False)
        layout.addWidget(self._audit_status_label)

        # 底部：其他原因输入框 + 提交按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self._reason_input = QLineEdit(self._card)
        self._reason_input.setPlaceholderText("其他原因（可选）")
        self._reason_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 13px;
                background-color: white;
                color: #333;
            }
            QLineEdit:focus {
                border: 1px solid #2196f3;
            }
        """)

        self._submit_btn = QPushButton("提交", self._card)
        self._submit_btn.clicked.connect(self._on_custom_reason)
        self._submit_btn.setStyleSheet(STYLE_MAP["normal"])
        self._submit_btn.setFixedWidth(80)

        bottom_layout.addWidget(self._reason_input)
        bottom_layout.addWidget(self._submit_btn)
        layout.addLayout(bottom_layout)

    def show_with_options(
        self,
        analysis_summary: str,
        options: list[dict],
        balance: int = 0,
        current_app: str = "",
        current_window_title: str = "",
        thought_trace: Optional[list[str]] = None,
    ) -> None:
        """
        显示对话框并渲染动态选项（v3.0: 添加 thought_trace 显示）。

        Args:
            analysis_summary: AI 分析摘要
            options: 选项列表（从 LLM 返回）
            balance: 当前货币余额（Coins）
            current_app: 当前应用名称
            current_window_title: 当前窗口标题
            thought_trace: AI 推理过程（System 2 Thinking）
        """
        # 保存当前窗口信息
        self._current_app = current_app
        self._current_window_title = current_window_title

        # 更新余额
        self._current_balance = balance
        self._balance_label.setText(f"{balance} Coins")

        # 根据余额状态改变颜色
        if balance < 0:
            self._balance_label.setStyleSheet("""
                QLabel {
                    color: #d32f2f;
                    font-size: 14px;
                    font-weight: 700;
                    padding: 8px 12px;
                    background-color: #ffebee;
                    border-radius: 6px;
                }
            """)
        elif balance < 50:
            self._balance_label.setStyleSheet("""
                QLabel {
                    color: #f57c00;
                    font-size: 14px;
                    font-weight: 700;
                    padding: 8px 12px;
                    background-color: #fff3e0;
                    border-radius: 6px;
                }
            """)
        else:
            self._balance_label.setStyleSheet("""
                QLabel {
                    color: #2196f3;
                    font-size: 14px;
                    font-weight: 700;
                    padding: 8px 12px;
                    background-color: #e3f2fd;
                    border-radius: 6px;
                }
            """)

        # 设置分析摘要
        self._analysis_label.setText(analysis_summary)

        # v3.0: 显示 AI 推理过程（如果有）
        logger.info(f"show_with_options called with thought_trace: {thought_trace}")
        if thought_trace and len(thought_trace) > 0:
            trace_html = "<b>🧠 AI 推理过程:</b><ul>"
            for step in thought_trace:
                trace_html += f"<li>{step}</li>"
            trace_html += "</ul>"
            self._reasoning_label.setText(trace_html)
            self._reasoning_label.setVisible(True)
            logger.info(f"Reasoning label set with {len(thought_trace)} steps")
        else:
            self._reasoning_label.setVisible(False)
            logger.info("No thought_trace provided, hiding reasoning label")

        # 清空现有按钮
        for i in reversed(range(self._buttons_layout.count())):
            self._buttons_layout.itemAt(i).widget().deleteLater()

        # 渲染新按钮
        for opt in options:
            btn = self._create_option_button(opt)
            self._buttons_layout.addWidget(btn)

        # 显示对话框（先隐藏再显示，防止重复显示）
        self.hide()
        self.show()

        # 居中显示在屏幕
        if parent := self.parent():
            if isinstance(parent, QWidget):
                self.move(
                    parent.x() + (parent.width() - self.width()) // 2,
                    parent.y() + (parent.height() - self.height()) // 2,
                )

    def _create_option_button(self, option: dict) -> QPushButton:
        """
        创建选项按钮。

        Args:
            option: 选项字典（包含 cost, affordable 字段）

        Returns:
            QPushButton: 配置好的按钮
        """
        # 获取价格和负担能力
        cost = option.get("cost", 0)
        affordable = option.get("affordable", True)
        disabled = option.get("disabled", False)

        # 构建按钮文字（包含价格和 emoji）
        label = option["label"]
        if cost > 0:
            # 消费选项：显示扣除的价格
            btn_text = f"{label} 💰 -{cost}"
        elif cost < 0:
            # 奖励选项：显示获得的价格
            btn_text = f"{label} 💰 +{abs(cost)}"
        else:
            # 免费选项
            btn_text = label

        btn = QPushButton(btn_text, self._card)
        btn.setMinimumHeight(60)  # 增加最小高度以显示完整文字
        btn.setMinimumWidth(400)  # 增加最小宽度以显示 emoji 和价格
        # 设置字体大小以确保文字清晰
        font = btn.font()
        font.setPointSize(11)
        btn.setFont(font)

        # 应用样式
        style = option.get("style", "normal")

        # 检查是否应该禁用
        should_disable = disabled or (not affordable and cost > 0)

        if should_disable:
            btn.setStyleSheet(STYLE_MAP["disabled"])
            btn.setEnabled(False)

            # 显示禁用原因
            if not affordable and cost > 0:
                reason = f"余额不足（需要 {cost} Coins）"
            else:
                reason = option.get("disabled_reason", "不可用")
            btn.setToolTip(reason)
        else:
            btn.setStyleSheet(STYLE_MAP.get(style, STYLE_MAP["normal"]))
            btn.setEnabled(True)

            # 连接点击事件
            btn.clicked.connect(
                lambda checked, o=option: self._on_option_clicked(o)
            )

        return btn

    def _on_option_clicked(self, option: dict) -> None:
        """
        处理选项按钮点击。

        Args:
            option: 被点击的选项（包含 cost, affordable 等字段）
        """
        try:
            action_type = option["action_type"]
            payload = option.get("payload", {})
            trust_impact = option.get("trust_impact", 0)
            cost = option.get("cost", 0)

            # 添加当前窗口信息到 payload
            if hasattr(self, '_current_app') and hasattr(self, '_current_window_title'):
                payload["current_app"] = self._current_app
                payload["current_window_title"] = self._current_window_title

            # 将 cost 添加到 payload 中
            payload_with_cost = {**payload, "cost": cost}

            logger.info(f"User chose: {action_type} (trust impact: {trust_impact:+d}, cost: {cost} Coins)")
            logger.info("About to call action callback...")

            # 使用直接回调而不是信号
            try:
                if hasattr(self, '_action_callback') and self._action_callback is not None:
                    logger.info("Calling action callback directly")
                    self._action_callback(action_type, payload_with_cost, trust_impact)
                    logger.info("Action callback completed")
                else:
                    logger.warning("No action callback set, falling back to signal emission")
                    self.action_chosen.emit(action_type, payload_with_cost, trust_impact)
                    logger.info("Signal emitted successfully")
            except Exception as callback_error:
                logger.exception(f"Error during action callback: {callback_error}")
                raise
        except Exception as e:
            logger.exception(f"Error in _on_option_clicked: {e}")
            self.close()

    def show_audit_status(self, message: str = "正在验证...") -> None:
        """
        显示审计状态。

        Args:
            message: 状态消息
        """
        self._audit_status_label.setText(message)
        self._audit_status_label.setVisible(True)

        # 禁用所有按钮
        for i in range(self._buttons_layout.count()):
            widget = self._buttons_layout.itemAt(i).widget()
            if widget and isinstance(widget, QPushButton):
                widget.setEnabled(False)

    def hide_audit_status(self) -> None:
        """
        隐藏审计状态并恢复按钮。
        """
        self._audit_status_label.setVisible(False)

        # 恢复按钮状态（根据 affordable 重新设置）
        # 这里简化处理：对话框即将关闭，不需要恢复
        pass

    def show_audit_result(self, result: str, reason: str = "") -> None:
        """
        显示审计结果。

        Args:
            result: 审计结果 (APPROVED/REJECTED/PRICE_ADJUSTED)
            reason: 原因说明
        """
        if result == "APPROVED":
            self._audit_status_label.setStyleSheet("""
                QLabel {
                    color: #4caf50;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px;
                    background-color: #e8f5e9;
                    border-radius: 6px;
                }
            """)
            self._audit_status_label.setText("✓ 验证通过")
        elif result == "REJECTED":
            self._audit_status_label.setStyleSheet("""
                QLabel {
                    color: #d32f2f;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px;
                    background-color: #ffebee;
                    border-radius: 6px;
                }
            """)
            self._audit_status_label.setText(f"✗ 验证失败: {reason}")
        elif result == "PRICE_ADJUSTED":
            self._audit_status_label.setStyleSheet("""
                QLabel {
                    color: #ff9800;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px;
                    background-color: #fff3e0;
                    border-radius: 6px;
                }
            """)
            self._audit_status_label.setText(f"⚠ 价格已调整: {reason}")

        self._audit_status_label.setVisible(True)

    def _on_custom_reason(self) -> None:
        """
        处理自定义原因提交。
        """
        reason = self._reason_input.text().strip()
        if not reason:
            return

        logger.info(f"User provided custom reason: {reason}")

        # 调用回调处理用户说明
        if hasattr(self, '_custom_reason_callback') and self._custom_reason_callback is not None:
            self._custom_reason_callback(reason)

        self.close()

    def keyPressEvent(self, event) -> None:
        """
        禁用 ESC 关闭对话框（强制用户做出选择）。

        Args:
            event: 键盘事件
        """
        if event.key() == Qt.Key.Key_Escape:
            # 忽略 ESC 键
            pass
        else:
            super().keyPressEvent(event)

    def force_close(self) -> None:
        """
        强制关闭对话框（用于 force_cease_fire）。

        当检测到用户回归工作后，立即关闭所有干预对话框。
        """
        logger.info("Dialog force-closed due to RECOVERY status")
        self.close()
