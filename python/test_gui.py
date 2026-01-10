"""
简单的GUI测试脚本
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

if sys.platform == 'win32':
    import os
    os.system('chcp 65001 >nul 2>&1')

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试窗口")
        self.setGeometry(100, 100, 400, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        title = QLabel("✅ PyQt6 工作正常！")
        title.setFont(QFont("", 16))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        btn = QPushButton("点击测试")
        btn.clicked.connect(self.on_click)
        layout.addWidget(btn)

        self.statusBar().showMessage("应用已启动")

    def on_click(self):
        self.statusBar().showMessage("按钮被点击了！")
        print("✅ 按钮点击成功！")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    print("✅ 测试窗口已显示")
    sys.exit(app.exec())
