"""测试表格显示"""
import sys
import os
import io
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 修复编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from storage.database import db_manager
from storage.activity_repository import activity_repository
import json

class TableTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表格显示测试")
        self.setGeometry(100, 100, 1000, 600)

        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        layout = QVBoxLayout(central_widget)

        # 标题
        title = QLabel("最近活动记录（表格测试）")
        title.setFont(QFont("", 14))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["时间", "应用", "窗口标题/网页", "URL", "PID"])

        # 设置表格样式
        self.table.setStyleSheet("""
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
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # 加载数据
        self.load_data()

        print("[DEBUG] 表格创建完成")
        self.statusBar().showMessage("表格已创建")

    def load_data(self):
        """加载活动记录"""
        try:
            print("[DEBUG] 开始加载数据...")
            db_manager.initialize()
            recent = activity_repository.get_recent_activities(limit=20)
            print(f"[DEBUG] 获取到 {len(recent)} 条记录")

            self.table.setRowCount(len(recent))

            for row, activity in enumerate(recent):
                # 时间
                timestamp = activity.get('timestamp', 0)
                time_str = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')
                self.table.setItem(row, 0, QTableWidgetItem(time_str))

                # 应用和标题
                data_str = activity.get('data', '{}')
                data = json.loads(data_str) if isinstance(data_str, str) else data_str
                app_name = data.get('appName', 'Unknown')
                window_title = data.get('windowTitle', '')
                page_title = data.get('pageTitle', '')
                url = data.get('url', '')

                # 显示应用名称
                self.table.setItem(row, 1, QTableWidgetItem(app_name))

                # 显示标题
                if url:
                    display_title = page_title if page_title else window_title
                    self.table.setItem(row, 2, QTableWidgetItem(display_title[:50]))
                    self.table.setItem(row, 3, QTableWidgetItem(url[:60]))
                else:
                    self.table.setItem(row, 2, QTableWidgetItem(window_title[:50]))
                    self.table.setItem(row, 3, QTableWidgetItem(""))

                # PID
                pid = str(data.get('processId', ''))
                self.table.setItem(row, 4, QTableWidgetItem(pid))

            print(f"[DEBUG] 数据加载完成，表格行数: {self.table.rowCount()}")
            self.statusBar().showMessage(f"已加载 {len(recent)} 条记录")

        except Exception as e:
            print(f"[ERROR] 加载失败: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"加载失败: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TableTestWindow()
    window.show()
    print("[INFO] 测试窗口已显示")
    sys.exit(app.exec())
