"""
快速测试干预功能 - 降低触发阈值
运行此脚本后，打开2次分心网站就会弹窗
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.tolerance_service import TOLERANCE_LEVELS

# 临时修改容忍度配置（仅用于测试）
print("=" * 60)
print("🔧 测试模式：已降低触发阈值")
print("=" * 60)
print()

# 将级别3（默认）改为更容易触发
TOLERANCE_LEVELS[3] = {
    'name': '测试模式',
    'threshold': 15,      # 原来是40，改为15（2次分心就触发）
    'strike_limit': 2,   # 原来是5，改为2（2次就触发）
    'decay_minutes': 10
}

print("新配置（级别3 - 测试模式）：")
print(f"  - 触发阈值：{TOLERANCE_LEVELS[3]['threshold']}分")
print(f"  - Strike上限：{TOLERANCE_LEVELS[3]['strike_limit']}次")
print()
print("现在打开2次分心网站就会触发干预！")
print()
print("启动GUI测试：")
print("  python ui/main_window.py")
print()
print("步骤：")
print("  1. 填写专注目标：'测试'")
print("  2. 点击'开始专注会话'")
print("  3. 点击'启动监控'")
print("  4. 打开2次YouTube/Bilibili")
print("  5. 应该立即弹窗！")
print()
print("=" * 60)
