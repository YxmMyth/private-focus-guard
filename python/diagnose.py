"""
诊断脚本 - 检查GUI是否能正常显示
"""
import sys
import os

# 修复编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("=" * 50)
print("FocusGuard 诊断工具")
print("=" * 50)

# 1. 检查PyQt6
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    print("✅ PyQt6 导入成功")
except Exception as e:
    print(f"❌ PyQt6 导入失败: {e}")
    sys.exit(1)

# 2. 检查其他依赖
try:
    import pywin32
    print("✅ pywin32 已安装")
except:
    print("❌ pywin32 未安装")

try:
    import psutil
    print("✅ psutil 已安装")
except:
    print("❌ psutil 未安装")

# 3. 尝试创建简单窗口
print("\n尝试创建测试窗口...")
try:
    app = QApplication(sys.argv)
    print("✅ QApplication 创建成功")

    from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton

    class SimpleWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("FocusGuard 测试窗口")
            self.setGeometry(200, 200, 500, 300)
            self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)  # 置顶

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)

            label = QLabel("如果你能看到这个窗口，说明GUI工作正常！")
            label.setFont(QFont("", 12))
            label.setWordWrap(True)
            layout.addWidget(label)

            btn = QPushButton("点击关闭")
            btn.clicked.connect(app.quit)
            layout.addWidget(btn)

            print("✅ 窗口创建成功")

    window = SimpleWindow()
    window.show()
    print("✅ 窗口已显示")

    print("\n请检查屏幕上是否有窗口弹出")
    print("按 Ctrl+C 退出")

    sys.exit(app.exec())

except Exception as e:
    print(f"❌ 创建窗口失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
