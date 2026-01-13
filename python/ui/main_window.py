"""
FocusGuard - PyQt6主窗口
"""
import sys
import os
from datetime import datetime, timedelta

# 加载环境变量（优先加载.env文件）
try:
    from dotenv import load_dotenv
    # 尝试加载项目根目录的.env文件
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)
    print(f"[ENV] 已加载环境变量文件: {env_path}")
except ImportError:
    print("[WARN] 未安装 python-dotenv，环境变量可能未加载")
except Exception as e:
    print(f"[WARN] 加载.env文件失败: {e}")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QStatusBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

# 设置UTF-8编码（修复Windows控制台emoji显示问题）
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加父目录到路径，以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from monitors.windows_monitor import windows_monitor
from monitors.chrome_monitor import browser_monitor
from storage.database import db_manager
from storage.activity_repository import activity_repository
from storage.session_repository import session_repository  # NEW: 导入 session_repository
from services.supervision_service import supervision_service  # NEW: 导入监督服务
from services.judgment_worker import JudgmentWorker, JudgmentTask  # NEW: 导入异步Worker
from services.tolerance_service import tolerance_service  # Phase 3: 容忍度服务
from services.conversation_service import conversation_service  # Phase 4: 对话服务
from ui.intervention_dialog import InterventionDialog  # Phase 4: 干预对话框
import json


class MonitoringThread(QThread):
    """监控线程"""
    activity_detected = pyqtSignal(dict)  # 信号：检测到新活动
    judgment_completed = pyqtSignal(dict)  # NEW: 信号：判决完成
    intervention_triggered = pyqtSignal(dict)  # Phase 3/4: 信号：需要干预

    def __init__(self, interval=3, session_id=None):  # NEW: 添加 session_id 参数
        super().__init__()
        self.interval = interval
        self.session_id = session_id  # NEW: 存储 session_id
        self.running = False
        self.stopper = False
        self.last_intervention_time = None  # Phase 3: 上次干预时间（避免频繁触发）

    def run(self):
        """运行监控"""
        self.running = True
        last_activity = None

        # NEW: 初始化监督服务和 Worker
        supervision_service.initialize_llm()
        self.judgment_worker = JudgmentWorker()
        self.judgment_worker.judgment_completed.connect(self._on_judgment_completed)
        self.judgment_worker.start()

        while not self.stopper:
            try:
                activity = windows_monitor.get_active_window()

                if activity:
                    activity_data = {
                        'app_name': activity.app_name,
                        'window_title': activity.window_title,
                        'process_id': activity.process_id,
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }

                    # 如果是浏览器，尝试获取最近访问的URL
                    app_name_lower = activity.app_name.lower()
                    if 'chrome' in app_name_lower or 'msedge' in app_name_lower or 'edge' in app_name_lower:
                        try:
                            browser_history = browser_monitor.get_all_browser_history(limit=3)
                            if browser_history:
                                latest = browser_history[0]
                                activity_data['url'] = latest.url
                                activity_data['page_title'] = latest.title
                                activity_data['is_browser'] = True
                                print(f"[DEBUG] 浏览器URL: {latest.url[:60]}...")
                            else:
                                activity_data['is_browser'] = False
                                print(f"[DEBUG] 浏览器历史为空")
                        except Exception as e:
                            activity_data['is_browser'] = False
                            print(f"[DEBUG] 获取浏览器历史失败: {e}")
                    else:
                        activity_data['is_browser'] = False

                    # 检查是否为新活动（忽略时间戳）
                    is_new_activity = False
                    if last_activity is None:
                        is_new_activity = True
                    else:
                        # 比较关键字段
                        current_key = (activity_data['app_name'], activity_data['window_title'], activity_data.get('url'))
                        last_key = (last_activity['app_name'], last_activity['window_title'], last_activity.get('url'))
                        if current_key != last_key:
                            is_new_activity = True

                    if is_new_activity:
                        # 保存到数据库
                        activity_repo_data = {
                            'appName': activity.app_name,
                            'windowTitle': activity.window_title,
                            'processId': activity.process_id,
                            'executablePath': activity.executable_path
                        }

                        # 如果是浏览器，添加URL信息
                        if activity_data.get('is_browser') and 'url' in activity_data:
                            activity_repo_data['url'] = activity_data['url']
                            activity_repo_data['pageTitle'] = activity_data.get('page_title', '')

                        # NEW: 添加 session_id
                        if self.session_id:
                            activity_repo_data['session_id'] = self.session_id

                        timestamp = int(activity.timestamp.timestamp() * 1000)

                        try:
                            activity_repository.save_activity(
                                activity_type='browser' if activity_data.get('is_browser') else 'application',
                                timestamp=timestamp,
                                duration=0,
                                data=activity_repo_data
                            )
                            activity_data['_saved'] = True
                        except Exception as e:
                            print(f"保存活动失败: {e}")
                            activity_data['_saved'] = False

                        # ============ NEW: 提交判决任务 ============
                        # 快速规则判断
                        try:
                            quick_judgment = supervision_service.judge_activity(
                                activity_data,
                                self.session_id
                            )

                            # Phase 3: 如果有会话，记录容忍度
                            if self.session_id and quick_judgment.is_distracted:
                                tolerance_status = tolerance_service.record_judgment(
                                    self.session_id,
                                    quick_judgment.is_distracted,
                                    quick_judgment.score,
                                    quick_judgment.reason,
                                    activity_data.get('app_name', '')
                                )

                                # 检查是否需要触发干预
                                if tolerance_status.should_intervene:
                                    # 避免频繁触发（至少间隔30秒）
                                    now = datetime.now()
                                    if (self.last_intervention_time is None or
                                        now - self.last_intervention_time > timedelta(seconds=30)):
                                        # 发出干预信号
                                        self.intervention_triggered.emit({
                                            'activity_data': activity_data,
                                            'judgment_result': quick_judgment,
                                            'tolerance_status': tolerance_status
                                        })

                                        self.last_intervention_time = now

                            # 如果规则无法判断，提交给 LLM Worker
                            if quick_judgment.rule_used == 'fallback':
                                # 异步 LLM 判断
                                task = JudgmentTask(activity_data, self.session_id)
                                self.judgment_worker.add_task(task)
                            else:
                                # 规则判决完成，直接发出信号
                                self.judgment_completed.emit({
                                    'activity_data': activity_data,
                                    'result': quick_judgment,
                                    'timestamp': datetime.now().isoformat()
                                })
                        except Exception as e:
                            print(f"判决过程出错: {e}")
                        # ============ END: 提交判决任务 ============
                    else:
                        activity_data['_saved'] = False

                    # 发出信号（通知UI更新）
                    # 即使没有保存新记录，也更新UI显示（如时间戳），证明监控在运行
                    self.activity_detected.emit(activity_data)

                    last_activity = activity_data
            except Exception as e:
                print(f"监控错误: {e}")

            # 等待指定间隔
            for _ in range(self.interval * 10):
                if self.stopper:
                    break
                self.msleep(100)

        # NEW: 停止 Worker
        if hasattr(self, 'judgment_worker'):
            self.judgment_worker.stop()

        self.running = False

    def _on_judgment_completed(self, judgment_data: dict):
        """判决完成回调（从 Worker 接收结果）"""
        # 转发信号到主窗口
        self.judgment_completed.emit(judgment_data)

    def stop(self):
        """停止监控"""
        self.stopper = True
        self.wait()


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.monitoring_thread = None

        # NEW: Session 状态
        self.current_session = None  # 存储当前 session_id
        self.session_active = False
        self.session_goal = ""
        self.session_scope = ""

        self.init_ui()
        self.init_database()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("FocusGuard - AI专注力监督")
        self.setGeometry(100, 100, 1000, 800)  # 增加窗口大小

        # 强制窗口显示在前面
        self.raise_()
        self.activateWindow()
        self.showNormal()  # 如果最小化，恢复正常状态

        print("[GUI] 窗口已创建并显示")

        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 标题
        title_label = QLabel("🎯 FocusGuard - 实时活动监控")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # ============ NEW: Focus Session Setup Area ============
        session_group = QGroupBox("📝 专注会话设置")
        session_layout = QVBoxLayout()

        # Goal 输入
        goal_label = QLabel("🎯 本次专注目标:")
        self.goal_input = QTextEdit()
        self.goal_input.setPlaceholderText("例如：修复 Windows 监控 Bug，完成单元测试")
        self.goal_input.setMaximumHeight(60)

        # Scope 输入
        scope_label = QLabel("🔍 允许范围:")
        self.scope_input = QTextEdit()
        self.scope_input.setPlaceholderText("例如：VSCode, StackOverflow, GitHub, DeepSeek（可选，用逗号分隔）")
        self.scope_input.setMaximumHeight(50)

        # Session 按钮布局
        session_button_layout = QHBoxLayout()
        self.start_session_button = QPushButton("🚀 开始专注会话")
        self.start_session_button.setMinimumHeight(35)
        self.start_session_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_session_button.clicked.connect(self.start_focus_session)

        self.end_session_button = QPushButton("🏁 结束会话")
        self.end_session_button.setMinimumHeight(35)
        self.end_session_button.setEnabled(False)
        self.end_session_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.end_session_button.clicked.connect(self.end_focus_session)

        # Session 状态显示
        self.session_status_label = QLabel("📊 会话状态: 未设置")
        self.session_status_label.setFont(QFont("", 10))
        self.session_status_label.setStyleSheet("color: #666;")

        # 添加到布局
        session_layout.addWidget(goal_label)
        session_layout.addWidget(self.goal_input)
        session_layout.addWidget(scope_label)
        session_layout.addWidget(self.scope_input)
        session_button_layout.addWidget(self.start_session_button)
        session_button_layout.addWidget(self.end_session_button)
        session_layout.addLayout(session_button_layout)
        session_layout.addWidget(self.session_status_label)

        session_group.setLayout(session_layout)
        main_layout.addWidget(session_group)
        # ============ END: Focus Session Setup Area ============

        # 当前活动显示区域
        current_group = QGroupBox("📍 当前活动")
        current_group.setMaximumHeight(100)  # 设置最大高度
        current_layout = QVBoxLayout()

        self.current_activity_label = QLabel("未启动监控")
        self.current_activity_label.setFont(QFont("", 12))
        self.current_activity_label.setWordWrap(True)
        current_layout.addWidget(self.current_activity_label)

        current_group.setLayout(current_layout)
        main_layout.addWidget(current_group)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("▶️ 启动监控")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_button.clicked.connect(self.start_monitoring)

        self.stop_button = QPushButton("⏹️ 停止监控")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.stop_button.clicked.connect(self.stop_monitoring)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # 统计信息
        stats_group = QGroupBox("📊 统计信息")
        stats_layout = QHBoxLayout()

        self.stats_label = QLabel("总活动记录: 0 条")
        self.stats_label.setFont(QFont("", 10))
        stats_layout.addWidget(self.stats_label)

        stats_group.setLayout(stats_layout)
        main_layout.addWidget(stats_group)

        # 活动历史表格
        history_group = QGroupBox("📜 最近活动记录")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["时间", "应用", "窗口标题/网页", "URL", "PID"])
        self.history_table.setMinimumHeight(250)  # 设置最小高度

        # 设置表格样式
        self.history_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
            }
        """)

        # 调整列宽
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        main_layout.addWidget(history_group)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 定时刷新统计
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)  # 每5秒刷新一次统计

    def init_database(self):
        """初始化数据库"""
        try:
            print("[DEBUG] 正在初始化数据库...")
            db_manager.initialize()
            print("[DEBUG] 数据库初始化完成")
            self.update_stats()
            print("[DEBUG] 正在加载活动记录...")
            self.load_recent_activities()
            print("[DEBUG] 活动记录加载完成")
            self.status_bar.showMessage("数据库已连接")
        except Exception as e:
            print(f"[ERROR] 数据库初始化失败: {e}")
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"数据库连接失败: {e}")

    def start_monitoring(self):
        """启动监控"""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            return

        # NEW: 传入当前会话 ID
        self.monitoring_thread = MonitoringThread(
            interval=3,
            session_id=self.current_session
        )
        self.monitoring_thread.activity_detected.connect(self.on_activity_detected)
        self.monitoring_thread.judgment_completed.connect(self.on_judgment_completed)  # NEW: 连接判决信号
        self.monitoring_thread.intervention_triggered.connect(self.on_intervention_triggered)  # Phase 3/4: 连接干预信号
        self.monitoring_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_bar.showMessage("监控运行中...")

        # 启动监控后立即刷新活动记录，显示已有数据
        self.load_recent_activities()

    def stop_monitoring(self):
        """停止监控"""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop()
            self.monitoring_thread = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.showMessage("监控已停止")

        # 停止监控后刷新活动记录，显示最新数据
        self.load_recent_activities()
        self.update_stats()

    def start_focus_session(self):
        """开始专注会话"""
        goal = self.goal_input.toPlainText().strip()
        scope = self.scope_input.toPlainText().strip()

        # 验证输入
        if not goal:
            QMessageBox.warning(self, "输入错误", "请设置专注目标！")
            return

        # 保存会话到数据库
        try:
            session_id = session_repository.create_session(
                goal=goal,
                scope=scope
            )

            # 更新状态
            self.current_session = session_id
            self.session_goal = goal
            self.session_scope = scope
            self.session_active = True

            # 更新UI
            self.session_status_label.setText(f"📊 会话状态: 进行中 | Session ID: {session_id}")
            self.session_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_session_button.setEnabled(False)
            self.end_session_button.setEnabled(True)
            self.goal_input.setEnabled(False)
            self.scope_input.setEnabled(False)

            self.status_bar.showMessage(f"专注会话已开始！目标: {goal[:30]}...")
            print(f"[MainWindow] 专注会话 #{session_id} 已创建")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建会话失败: {e}")
            print(f"[MainWindow] 创建会话失败: {e}")

    def end_focus_session(self):
        """结束专注会话"""
        if not self.session_active:
            return

        try:
            session_repository.end_session(self.current_session)

            # 重置状态
            self.current_session = None
            self.session_active = False
            self.session_goal = ""
            self.session_scope = ""

            # 更新UI
            self.session_status_label.setText("📊 会话状态: 已结束")
            self.session_status_label.setStyleSheet("color: #666;")
            self.start_session_button.setEnabled(True)
            self.end_session_button.setEnabled(False)
            self.goal_input.setEnabled(True)
            self.scope_input.setEnabled(True)

            self.status_bar.showMessage("专注会话已结束")
            print(f"[MainWindow] 专注会话已结束")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"结束会话失败: {e}")
            print(f"[MainWindow] 结束会话失败: {e}")

    def on_activity_detected(self, activity):
        """处理检测到的活动"""
        # 更新当前活动显示
        app_name = activity['app_name']
        window_title = activity['window_title']
        timestamp = activity['timestamp']

        display_text = f"应用程序: {app_name}\n窗口标题: {window_title}\n检测时间: {timestamp}"

        # 如果是浏览器，显示URL
        if activity.get('is_browser') and 'url' in activity:
            url = activity['url']
            page_title = activity.get('page_title', '')
            display_text += f"\n\n🌐 访问网站:\n{url}"
            if page_title:
                display_text += f"\n网页标题: {page_title}"

        self.current_activity_label.setText(display_text)

        # 刷新活动历史（每次检测到活动时都刷新，确保实时显示）
        # 如果有新记录保存，标记需要完全刷新；否则也刷新以更新时间戳
        self.load_recent_activities()

    def on_judgment_completed(self, judgment_data: dict):
        """处理判决完成"""
        activity_data = judgment_data['activity_data']
        result = judgment_data['result']

        # 更新判断信息显示（在状态栏）
        app_name = activity_data.get('app_name', '')
        score = result.score
        reason = result.reason
        rule_used = result.rule_used

        if result.is_distracted and score >= 7.0:
            # 高分心值，显示警告
            self.status_bar.showMessage(
                f"⚠️ 检测到分心! {app_name} | 分心值: {score:.1f}/10 | {reason} ({rule_used})"
            )
            print(f"[Judgment] ⚠️ 分心: {app_name} | {score}/10 | {reason}")
        else:
            # 正常或低分心
            if score >= 4.0:
                self.status_bar.showMessage(
                    f"⚡ {app_name} | 分心值: {score:.1f}/10 | {reason} ({rule_used})"
                )
            else:
                self.status_bar.showMessage(
                    f"✅ {app_name} | 符合目标 | {reason} ({rule_used})"
                )
            print(f"[Judgment] ✅ 正常: {app_name} | {score}/10 | {reason}")

    def on_intervention_triggered(self, intervention_data: dict):
        """处理干预触发"""
        activity_data = intervention_data['activity_data']
        judgment_result = intervention_data['judgment_result']
        tolerance_status = intervention_data['tolerance_status']

        print(f"[Intervention] 触发干预！")
        print(f"  应用: {activity_data.get('app_name')}")
        print(f"  分心值: {judgment_result.score}/10")
        print(f"  击打数: {tolerance_status.strikes_count}/{tolerance_status.strike_limit}")

        # 暂停监控（避免重复触发）
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.judgment_worker.pause()

        # 显示干预对话框
        dialog = InterventionDialog(
            session_id=self.current_session,
            distraction_app=activity_data.get('app_name', 'Unknown'),
            distraction_reason=judgment_result.reason,
            tolerance_status=tolerance_status,
            parent=self
        )

        # 处理对话结果
        def handle_dialog_result(result):
            print(f"[Intervention] 对话结果: {result}")

            action = result.get('action')
            exemption_granted = result.get('exemption_granted', False)
            new_goal = result.get('new_goal')

            if action == 'close_app':
                # 用户同意关闭应用，重置容忍度
                tolerance_service.reset_tolerance(self.current_session)
                self.status_bar.showMessage("✅ 已回到专注状态，容忍度已重置")

            elif action == 'request_exemption':
                if exemption_granted:
                    # 豁免被批准，提高容忍度
                    tolerance_service.increase_tolerance(self.current_session)
                    self.status_bar.showMessage("⚠️ 豁免已批准，容忍度已提高")
                else:
                    # 豁免被拒绝，保持警告
                    self.status_bar.showMessage("❌ 豁免被拒绝，请尽快回到专注状态")

            elif action == 'adjust_goal':
                # 调整目标
                if new_goal:
                    self.goal_input.setText(new_goal)
                    self.status_bar.showMessage(f"🎯 目标已调整为: {new_goal}")

            # 恢复监控
            if self.monitoring_thread and self.monitoring_thread.isRunning():
                self.monitoring_thread.judgment_worker.resume()

        dialog.dialogue_finished.connect(handle_dialog_result)
        dialog.exec()

    def update_stats(self):
        """更新统计信息"""
        try:
            stats = db_manager.get_stats()
            self.stats_label.setText(f"总活动记录: {stats['activities']} 条 | 数据库大小: {stats['dbSize'] / 1024:.1f} KB")
        except Exception as e:
            print(f"更新统计失败: {e}")

    def load_recent_activities(self):
        """加载最近的活动记录"""
        try:
            print("[DEBUG] 开始加载活动记录...")
            recent = activity_repository.get_recent_activities(limit=20)
            print(f"[DEBUG] 获取到 {len(recent)} 条活动记录")

            self.history_table.setRowCount(len(recent))

            for row, activity in enumerate(recent):
                # 时间
                timestamp = activity.get('timestamp', 0)
                time_str = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')
                self.history_table.setItem(row, 0, QTableWidgetItem(time_str))

                # 应用和标题
                data_str = activity.get('data', '{}')
                data = json.loads(data_str) if isinstance(data_str, str) else data_str
                app_name = data.get('appName', 'Unknown')
                window_title = data.get('windowTitle', '')
                page_title = data.get('pageTitle', '')
                url = data.get('url', '')

                # 显示应用名称
                self.history_table.setItem(row, 1, QTableWidgetItem(app_name))

                # 如果是浏览器，显示网页标题，否则显示窗口标题
                if url:
                    display_title = page_title if page_title else window_title
                    self.history_table.setItem(row, 2, QTableWidgetItem(display_title[:50]))
                    # 显示URL
                    self.history_table.setItem(row, 3, QTableWidgetItem(url[:60]))
                else:
                    self.history_table.setItem(row, 2, QTableWidgetItem(window_title[:50]))
                    self.history_table.setItem(row, 3, QTableWidgetItem(""))

                # PID
                pid = str(data.get('processId', ''))
                self.history_table.setItem(row, 4, QTableWidgetItem(pid))

            print(f"[DEBUG] 活动记录加载完成，表格行数: {self.history_table.rowCount()}")

        except Exception as e:
            print(f"加载活动历史失败: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop()

        db_manager.close()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion样式

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
