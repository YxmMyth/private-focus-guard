"""
FocusGuard - 主程序

作用：
1. 初始化所有服务
2. 启动监控
3. 测试核心功能
"""

import sys
import time
from datetime import datetime

# 设置UTF-8编码输出（解决Windows控制台编码问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from monitors.windows_monitor import windows_monitor, ApplicationActivity
from storage.database import db_manager
from storage.activity_repository import activity_repository


def on_activity_detected(activity: ApplicationActivity):
    """
    活动检测回调

    Args:
        activity: 检测到的活动
    """
    print(f"\n{'='*60}")
    print(f"🎯 检测到活动切换:")
    print(f"   应用: {activity.app_name}")
    print(f"   标题: {activity.window_title}")
    print(f"   进程ID: {activity.process_id}")
    print(f"   时间: {activity.timestamp.strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    # 保存到数据库
    try:
        activity_data = {
            'appName': activity.app_name,
            'windowTitle': activity.window_title,
            'processId': activity.process_id,
            'executablePath': activity.executable_path
        }

        timestamp = int(activity.timestamp.timestamp() * 1000)
        activity_repository.save_activity(
            activity_type='application',
            timestamp=timestamp,
            duration=0,  # 初始duration为0，后续会更新
            data=activity_data
        )

        print("✅ 活动已保存到数据库")

    except Exception as error:
        print(f"❌ 保存活动失败: {error}")


def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════╗
║         FocusGuard - AI专注力监督工具 v1.0            ║
║                                                        ║
║  监控你的电脑活动，帮助你保持专注                      ║
╚════════════════════════════════════════════════════════╝
""")

    try:
        # 1. 初始化数据库
        print("📦 初始化数据库...")
        db_manager.initialize()
        print("✅ 数据库初始化成功")

        # 显示数据库统计
        stats = db_manager.get_stats()
        print(f"\n📊 数据库统计:")
        print(f"   活动记录: {stats['activities']} 条")
        print(f"   数据库大小: {stats['dbSize'] / 1024:.2f} KB")

        # 2. 启动Windows监控
        print("\n🚀 启动Windows监控...")
        windows_monitor.start_polling(
            interval=3,  # 每3秒检查一次
            callback=on_activity_detected
        )
        print("✅ 监控已启动")

        print("\n" + "💡"*60)
        print("监控运行中... 切换到不同的窗口看看效果！")
        print("按 Ctrl+C 停止监控")
        print("💡"*60 + "\n")

        # 主循环
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n⏹️  收到停止信号...")

        # 停止监控
        print("🛑 停止监控...")
        windows_monitor.stop_polling()
        print("✅ 监控已停止")

        # 显示最终统计
        print("\n📊 最终统计:")
        stats = db_manager.get_stats()
        print(f"   活动记录: {stats['activities']} 条")

        # 关闭数据库
        print("\n🔒 关闭数据库...")
        db_manager.close()
        print("✅ 数据库已关闭")

        print("\n👋 再见！")
        sys.exit(0)

    except Exception as error:
        print(f"\n❌ 错误: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
