"""
FocusGuard v2.0 - 对话框测试脚本

演示干预对话框的功能。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from ui.dialogs.intervention_dialog import InterventionDialog


def test_dialog():
    """测试干预对话框的各种场景。"""

    app = QApplication(sys.argv)

    # 创建对话框
    dialog = InterventionDialog()

    # 场景 1: 检测到 Bilibili 视频网站
    bilibili_response = {
        "is_distracted": True,
        "confidence": 92,
        "analysis_summary": "检测到您正在观看 Bilibili 视频，当前目标是「学习 Python」，已偏离目标 15 分钟",
        "options": [
            {
                "label": "再看 5 分钟",
                "action_type": "SNOOZE",
                "payload": {"duration_minutes": 5},
                "trust_impact": -5,
                "style": "warning",
                "disabled": False,
                "disabled_reason": None
            },
            {
                "label": "这是学习教程视频",
                "action_type": "DISMISS",
                "payload": {},
                "trust_impact": 2,
                "style": "normal",
                "disabled": False,
                "disabled_reason": None
            },
            {
                "label": "我管不住自己，请强制监督",
                "action_type": "STRICT_MODE",
                "payload": {"duration_minutes": 30},
                "trust_impact": 5,
                "style": "primary",
                "disabled": False,
                "disabled_reason": None
            },
        ]
    }

    # 场景 2: 检测到社交媒体
    social_media_response = {
        "is_distracted": True,
        "confidence": 88,
        "analysis_summary": "您正在使用微信聊天，与当前工作目标不符",
        "options": [
            {
                "label": "聊完这最后一句",
                "action_type": "SNOOZE",
                "payload": {"duration_minutes": 3},
                "trust_impact": -2,
                "style": "warning",
                "disabled": False,
                "disabled_reason": None
            },
            {
                "label": "这是工作相关沟通",
                "action_type": "DISMISS",
                "payload": {},
                "trust_impact": 3,
                "style": "normal",
                "disabled": False,
                "disabled_reason": None
            },
            {
                "label": "我确实在摸鱼...",
                "action_type": "STRICT_MODE",
                "payload": {"duration_minutes": 20},
                "trust_impact": 8,
                "style": "primary",
                "disabled": False,
                "disabled_reason": None
            },
        ]
    }

    # 场景 3: 信任分过低 - 禁用部分选项
    low_trust_response = {
        "is_distracted": True,
        "confidence": 95,
        "analysis_summary": "您的信任分较低 (45/100)，建议立即回到专注状态",
        "options": [
            {
                "label": "休息 3 分钟",
                "action_type": "SNOOZE",
                "payload": {"duration_minutes": 3},
                "trust_impact": -2,
                "style": "warning",
                "disabled": False,
                "disabled_reason": None
            },
            {
                "label": "休息 10 分钟",
                "action_type": "SNOOZE",
                "payload": {"duration_minutes": 10},
                "trust_impact": -8,
                "style": "warning",
                "disabled": True,
                "disabled_reason": "信任分低于 60 时不可用"
            },
            {
                "label": "加入白名单 1 小时",
                "action_type": "WHITELIST_TEMP",
                "payload": {"app": "chrome.exe", "duration_hours": 1},
                "trust_impact": 0,
                "style": "normal",
                "disabled": True,
                "disabled_reason": "信任分低于 70 时不可用"
            },
            {
                "label": "我知错了，立即工作",
                "action_type": "DISMISS",
                "payload": {},
                "trust_impact": 5,
                "style": "primary",
                "disabled": False,
                "disabled_reason": None
            },
        ]
    }

    # 连接信号
    def on_action_chosen(action_type: str, payload: dict, trust_impact: int):
        print(f"\n{'='*50}")
        print(f"用户选择了: {action_type}")
        print(f"参数: {payload}")
        print(f"信任分影响: {trust_impact:+d}")
        print(f"{'='*50}\n")

        # 关闭对话框
        dialog.close()

        # 3 秒后显示下一个测试场景
        QTimer.singleShot(3000, lambda: show_scene(social_media_response))

    dialog.action_chosen.connect(on_action_chosen)

    # 显示第一个场景
    def show_scene(response):
        dialog.show_with_options(
            analysis_summary=response["analysis_summary"],
            options=response["options"]
        )

    # 延迟 1 秒后显示第一个场景（让应用先完全启动）
    QTimer.singleShot(1000, lambda: show_scene(bilibili_response))

    # 运行应用
    print("="*50)
    print("FocusGuard 对话框测试程序")
    print("="*50)
    print("\n将依次展示 3 个测试场景：")
    print("1. Bilibili 视频检测")
    print("2. 社交媒体检测")
    print("3. 低信任分状态")
    print("\n请点击对话框中的按钮进行测试...\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    test_dialog()
