"""
测试浏览器监控能否获取URL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from monitors.chrome_monitor import browser_monitor

print("=" * 60)
print("测试浏览器监控...")
print("=" * 60)
print()

try:
    print("正在获取浏览器历史...")
    history = browser_monitor.get_all_browser_history(limit=5)

    if history:
        print(f"[OK] 成功获取 {len(history)} 条记录")
        print()
        for i, item in enumerate(history[:3]):
            print(f"记录 {i+1}:")
            print(f"  URL: {item.url}")
            print(f"  标题: {item.title}")
            print(f"  时间: {item.visit_time}")
            print()

        # 检查是否有YouTube
        youtube_found = False
        for item in history:
            if 'youtube.com' in item.url.lower():
                print("[OK] 找到YouTube访问记录!")
                print(f"   URL: {item.url}")
                youtube_found = True
                break

        if not youtube_found:
            print("[WARN] 没有找到YouTube访问记录")
            print()
            print("请先在浏览器中访问YouTube，然后再运行此脚本")
    else:
        print("[ERROR] 没有获取到任何浏览器历史")
        print()
        print("可能原因:")
        print("1. Chrome/Edge没有访问记录")
        print("2. 浏览器历史数据库路径不正确")
        print("3. 数据库被锁定（浏览器正在运行）")

except Exception as e:
    print(f"[ERROR] 错误: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
