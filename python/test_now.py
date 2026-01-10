"""
立即测试监控 - 不需要后台运行
"""
import sys
import os

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("="*60)
print("FocusGuard - 监控功能测试")
print("="*60)
print("\n正在测试获取当前活动窗口...\n")

try:
    from monitors.windows_monitor import windows_monitor

    # 获取当前活动窗口
    activity = windows_monitor.get_active_window()

    if activity:
        print("✅ 成功获取活动窗口！")
        print(f"\n检测到的活动信息:")
        print(f"  应用名称: {activity.app_name}")
        print(f"  窗口标题: {activity.window_title}")
        print(f"  进程PID: {activity.process_id}")
        print(f"  可执行文件: {activity.executable_path}")
        print(f"  时间戳: {activity.timestamp}")
        print("\n" + "="*60)
        print("监控功能正常工作！")
        print("="*60)
    else:
        print("❌ 未检测到活动窗口")

    # 测试数据库保存
    print("\n测试数据库保存...")
    from storage.database import db_manager
    from storage.activity_repository import activity_repository
    import json

    db_manager.initialize()

    activity_data = {
        'appName': activity.app_name,
        'windowTitle': activity.window_title,
        'processId': activity.process_id,
        'executablePath': activity.executable_path
    }

    timestamp = int(activity.timestamp.timestamp() * 1000)
    activity_id = activity_repository.save_activity(
        activity_type='application',
        timestamp=timestamp,
        duration=0,
        data=activity_data
    )

    print(f"✅ 活动已保存到数据库 (ID: {activity_id})")

    # 查询数据库统计
    stats = db_manager.get_stats()
    print(f"\n数据库统计:")
    print(f"  总活动记录: {stats['activities']} 条")
    print(f"  数据库大小: {stats['dbSize']} 字节")

    # 查询最近的活动
    print("\n最近的活动记录:")
    recent = activity_repository.get_recent_activities(limit=5)
    for act in recent:
        data = json.loads(act['data'])
        print(f"  - {data.get('appName')}: {data.get('windowTitle')}")

    db_manager.close()

    print("\n" + "="*60)
    print("✅ 所有测试通过！监控功能完全正常！")
    print("="*60)

except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

input("\n按Enter键退出...")
