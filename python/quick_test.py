"""
快速测试监控功能
"""
import sys
import io

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from monitors.windows_monitor import windows_monitor

def test_callback(activity):
    """回调函数"""
    print(f"\n{'='*60}")
    print(f"检测到窗口切换！")
    print(f"应用名称: {activity.app_name}")
    print(f"窗口标题: {activity.window_title}")
    print(f"进程PID: {activity.process_id}")
    print(f"可执行文件: {activity.executable_path}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    print("启动监控（每3秒检查一次）...")
    print("请切换到不同的应用程序窗口（Chrome、VSCode等）")
    print("按 Ctrl+C 停止\n")

    windows_monitor.start_polling(interval=3, callback=test_callback)

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止监控...")
        windows_monitor.stop_polling()
        print("监控已停止")
