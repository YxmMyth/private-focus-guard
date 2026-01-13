"""
诊断YouTube检测问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitors.windows_monitor import windows_monitor
from monitors.chrome_monitor import browser_monitor

print("=" * 60)
print("正在诊断YouTube检测...")
print("=" * 60)
print()

# 获取当前活动窗口
print("1. 获取当前活动窗口...")
activity = windows_monitor.get_active_window()

if activity:
    print(f"   应用: {activity.app_name}")
    print(f"   标题: {activity.window_title}")
    print()

    # 检查是否是浏览器
    app_name_lower = activity.app_name.lower()
    if 'chrome' in app_name_lower or 'msedge' in app_name_lower or 'edge' in app_name_lower:
        print("2. 检测到浏览器，尝试获取URL...")
        try:
            browser_history = browser_monitor.get_all_browser_history(limit=3)
            if browser_history:
                print(f"   成功获取 {len(browser_history)} 条历史记录")
                print()
                for i, item in enumerate(browser_history):
                    print(f"   记录{i+1}:")
                    print(f"     URL: {item.url}")
                    print(f"     标题: {item.title}")
                    print(f"     时间: {item.visit_time}")
                    print()
            else:
                print("   ❌ 没有获取到浏览器历史记录")
                print()
                print("   可能原因:")
                print("   - 浏览器历史数据库被锁定")
                print("   - Chrome/Edge正在运行，数据库被占用")
        except Exception as e:
            print(f"   ❌ 获取URL失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("2. 当前不是浏览器")
else:
    print("   ❌ 无法获取活动窗口")

print()
print("=" * 60)
print("请现在打开浏览器访问YouTube，然后运行此脚本")
print("=" * 60)
