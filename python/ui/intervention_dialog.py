"""
干预对话框

Phase 4: The Intervention - 用户交互界面
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGroupBox, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from typing import Optional, Callable

from services.conversation_service import conversation_service, InterventionResult
from services.tolerance_service import tolerance_service
from monitors.chrome_monitor import browser_monitor


class InterventionDialog(QDialog):
    """干预对话框"""

    # 信号：对话完成
    dialogue_finished = pyqtSignal(dict)  # {'should_continue': bool, 'action': str}

    def __init__(
        self,
        session_id: int,
        distraction_app: str,
        distraction_reason: str,
        tolerance_status,
        parent=None
    ):
        super().__init__(parent)
        self.session_id = session_id
        self.distraction_app = distraction_app
        self.distraction_reason = distraction_reason
        self.tolerance_status = tolerance_status

        self.init_ui()
        self.start_conversation()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🛡️ FocusGuard - 专注提醒")
        self.setMinimumSize(600, 500)
        self.setModal(True)  # 模态对话框，必须处理才能继续

        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("⚡ 专注力提醒")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 信息显示区域
        info_group = QGroupBox("📊 当前状态")
        info_layout = QVBoxLayout()

        goal_label = QLabel(f"专注目标: {self._get_session_goal()}")
        goal_label.setFont(QFont("", 11))
        goal_label.setWordWrap(True)
        info_layout.addWidget(goal_label)

        app_label = QLabel(f"分心应用: {self.distraction_app}")
        app_label.setFont(QFont("", 10))
        info_layout.addWidget(app_label)

        reason_label = QLabel(f"原因: {self.distraction_reason}")
        reason_label.setFont(QFont("", 10))
        reason_label.setWordWrap(True)
        info_layout.addWidget(reason_label)

        strikes_text = (f"击打次数: {self.tolerance_status.strikes_count}/"
                       f"{self.tolerance_status.strike_limit}")
        strikes_label = QLabel(strikes_text)
        strikes_label.setFont(QFont("", 10))

        # 根据严重程度设置颜色
        if self.tolerance_status.should_intervene:
            strikes_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            strikes_label.setStyleSheet("color: orange;")

        info_layout.addWidget(strikes_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 对话历史区域
        chat_group = QGroupBox("💬 对话")
        chat_layout = QVBoxLayout()

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setMinimumHeight(200)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        chat_layout.addWidget(self.chat_history)

        chat_group.setLayout(chat_layout)
        layout.addWidget(chat_group)

        # 用户输入区域
        input_group = QGroupBox("✍️ 你的回复")
        input_layout = QVBoxLayout()

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("请输入你的回复...")
        self.input_box.setMaximumHeight(80)
        self.input_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        input_layout.addWidget(self.input_box)

        # 快捷回复按钮
        quick_reply_layout = QHBoxLayout()

        self.close_app_btn = QPushButton("🔒 关闭应用")
        self.close_app_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.close_app_btn.clicked.connect(self.on_close_app)
        quick_reply_layout.addWidget(self.close_app_btn)

        self.exemption_btn = QPushButton("⚠️ 请求豁免")
        self.exemption_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.exemption_btn.clicked.connect(self.on_request_exemption)
        quick_reply_layout.addWidget(self.exemption_btn)

        self.adjust_goal_btn = QPushButton("🎯 调整目标")
        self.adjust_goal_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
        """)
        self.adjust_goal_btn.clicked.connect(self.on_adjust_goal)
        quick_reply_layout.addWidget(self.adjust_goal_btn)

        input_layout.addLayout(quick_reply_layout)

        # 发送按钮
        send_layout = QHBoxLayout()
        send_layout.addStretch()

        self.send_btn = QPushButton("📤 发送")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 10px 30px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.send_btn.clicked.connect(self.on_send_message)
        send_layout.addWidget(self.send_btn)

        input_layout.addLayout(send_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

    def _get_session_goal(self) -> str:
        """获取会话目标"""
        from storage.session_repository import session_repository
        session = session_repository.get_session_by_id(self.session_id)
        if session:
            return session.get('goal', '未知目标')
        return '未知目标'

    def start_conversation(self):
        """开始对话"""
        # 初始化LLM
        conversation_service.initialize_llm()

        # 获取初始干预消息
        initial_message = conversation_service.start_intervention(
            self.session_id,
            self.distraction_app,
            self.distraction_reason,
            self.tolerance_status
        )

        # 显示消息
        self.append_message('assistant', initial_message)

    def append_message(self, role: str, message: str):
        """添加消息到聊天历史"""
        self.chat_history.append(f"{role}: {message}")
        self.chat_history.moveCursor(QTextCursor.MoveOperation.End)

    def on_send_message(self):
        """发送消息"""
        user_message = self.input_box.toPlainText().strip()
        if not user_message:
            return

        # 显示用户消息
        self.append_message('你', user_message)
        self.input_box.clear()

        # 处理用户回复
        result = conversation_service.process_user_response(
            self.session_id,
            user_message
        )

        # 显示AI回复
        self.append_message('FocusGuard', result.resolution)

        # 根据结果决定下一步
        if result.should_continue:
            # 对话结束，用户采取了行动
            self.handle_intervention_result(result)

    def on_close_app(self):
        """关闭应用"""
        # 清理浏览器URL缓存，避免误判
        browser_monitor.clear_cache()
        self.input_box.setPlainText("好的，我马上关闭这个应用，回到专注状态。")
        self.on_send_message()

    def on_request_exemption(self):
        """请求豁免"""
        self.input_box.setPlainText("我需要继续使用这个应用，因为这对我的工作很重要。")
        self.on_send_message()

    def on_adjust_goal(self):
        """调整目标"""
        self.input_box.setPlainText("我想调整我的专注目标。")
        self.on_send_message()

    def handle_intervention_result(self, result: InterventionResult):
        """处理干预结果"""
        # 延迟关闭对话框，让用户看到最后的消息
        from PyQt6.QtCore import QTimer

        def close_dialog():
            # 发出信号
            self.dialogue_finished.emit({
                'should_continue': result.should_continue,
                'action': result.user_action.value if result.user_action else None,
                'exemption_granted': result.exemption_granted,
                'new_goal': result.new_goal
            })

            # 如果是豁免被拒绝，继续对话
            if result.user_action and result.user_action.value == 'request_exemption' and not result.exemption_granted:
                return

            # 否则关闭对话框
            self.accept()

        QTimer.singleShot(2000, close_dialog)

    def closeEvent(self, event):
        """关闭事件"""
        # 清空对话历史
        conversation_service.clear_conversation(self.session_id)
        event.accept()


# 测试代码
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    from services.tolerance_service import ToleranceStatus, StrikeEvent
    from datetime import datetime

    app = QApplication(sys.argv)

    # 创建模拟的容忍度状态
    tolerance_status = ToleranceStatus(
        session_id=1,
        tolerance_level=3,
        total_score=35.0,
        strikes_count=4,
        strike_limit=5,
        threshold=40.0,
        should_intervene=False,
        recent_strikes=[]
    )

    # 创建对话框
    dialog = InterventionDialog(
        session_id=1,
        distraction_app='chrome.exe',
        distraction_reason='访问 YouTube',
        tolerance_status=tolerance_status
    )

    dialog.dialogue_finished.connect(lambda result: print(f"对话结果: {result}"))
    dialog.exec()

    sys.exit(app.exec())
