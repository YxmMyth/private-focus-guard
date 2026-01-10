"""
测试监控功能
"""
import sys
import os
import io
from datetime import datetime

# 修复编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from monitors.windows_monitor import windows_monitor
from storage.database import db_manager
from storage.activity_repository import activity_repository

print("=" * 60)
print("监控功能测试")
print("=" * 60)

# 初始化数据库
db_manager.initialize()

print("\n[测试] 开始5次活动检测...")
print("提示：请在检测期间切换不同的窗口\n")

for i in range(5):
    activity = windows_monitor.get_active_window()
    if activity:
        print(f"\n检测 #{i+1}:")
        print(f"  应用: {activity.app_name}")
        print(f"  窗口: {activity.window_title[:50]}...")
        print(f"  PID: {activity.process_id}")
        print(f"  时间: {datetime.now().strftime('%H:%M:%S')}")

        # 保存到数据库
        activity_repository.save_activity(
            activity_type='application',
            timestamp=int(datetime.now().timestamp() * 1000),
            duration=0,
            data={
                'appName': activity.app_name,
                'windowTitle': activity.window_title,
                'processId': activity.process_id,
                'executablePath': activity.executable_path
            }
        )
        print(f"  状态: 已保存到数据库")
    else:
        print(f"\n检测 #{i+1}: 未获取到活动")

    if i < 4:
        print("  等待3秒...")
        import time
        time.sleep(3)

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

# 显示保存的记录
print("\n[检查] 最近保存的记录:")
recent = activity_repository.get_recent_activities(limit=6)
for act in recent[:5]:
    ts = datetime.fromtimestamp(act['timestamp'] / 1000).strftime('%H:%M:%S')
    print(f"  [{ts}] {act['type']}")

print(f"\n总计: {len(recent)} 条记录")
