"""
异步判决 Worker

在后台线程中处理 LLM 调用，避免阻塞监控和UI
Phase 2: The Judge - 异步处理层
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, Any, Optional
from collections import deque
from datetime import datetime
import time

from services.supervision_service import JudgmentResult, supervision_service


class JudgmentTask:
    """判决任务"""
    def __init__(self, activity_data: Dict[str, Any], session_id: Optional[int] = None):
        self.activity_data = activity_data
        self.session_id = session_id
        self.timestamp = datetime.now()

    def __repr__(self):
        return f"JudgmentTask(app={self.activity_data.get('app_name')}, time={self.timestamp.strftime('%H:%M:%S')})"


class JudgmentWorker(QThread):
    """异步判决 Worker - 在后台处理 LLM 调用"""

    # 信号定义
    judgment_completed = pyqtSignal(dict)  # 判决完成：{activity_data, result, timestamp}

    def __init__(self):
        super().__init__()
        self.task_queue = deque()
        self.is_running = False
        self.is_paused = False
        self.current_task = None
        self.processed_count = 0  # 已处理任务数

    def add_task(self, task: JudgmentTask):
        """添加任务到队列"""
        if not self.is_paused:
            self.task_queue.append(task)
            print(f"[JudgmentWorker] 任务已添加: {task} (队列大小: {len(self.task_queue)})")

    def pause(self):
        """暂停处理（但处理完当前任务）"""
        self.is_paused = True
        print("[JudgmentWorker] Worker 已暂停")

    def resume(self):
        """恢复处理"""
        self.is_paused = False
        print("[JudgmentWorker] Worker 已恢复")

    def stop(self):
        """停止 Worker"""
        print(f"[JudgmentWorker] 正在停止 Worker... (已处理: {self.processed_count} 个任务)")
        self.is_running = False
        self.wait()
        print(f"[JudgmentWorker] Worker 已停止")

    def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return len(self.task_queue)

    def clear_queue(self):
        """清空任务队列"""
        cleared_count = len(self.task_queue)
        self.task_queue.clear()
        print(f"[JudgmentWorker] 已清空队列 (清除了 {cleared_count} 个任务)")

    def run(self):
        """运行 Worker 线程"""
        self.is_running = True
        print("[JudgmentWorker] Worker 已启动")

        # 初始化监督服务（包括 LLM）
        supervision_service.initialize_llm()

        while self.is_running:
            try:
                # 如果队列为空或已暂停，等待 100ms
                if not self.task_queue or self.is_paused:
                    self.msleep(100)
                    continue

                # 获取任务
                task = self.task_queue.popleft()
                self.current_task = task

                print(f"[JudgmentWorker] 开始处理任务: {task}")

                # 执行判决
                result = supervision_service.llm_judgment(
                    task.activity_data,
                    {}  # session info (会从 activity_data 中获取)
                )

                print(f"[JudgmentWorker] 判决完成: {result.rule_used} | "
                      f"{'分心' if result.is_distracted else '正常'} | "
                      f"分数: {result.score}/10")

                # 发出信号
                self.judgment_completed.emit({
                    'activity_data': task.activity_data,
                    'result': result,
                    'timestamp': task.timestamp.isoformat()
                })

                self.processed_count += 1
                self.current_task = None

                # 避免过度消耗资源，每个任务之间暂停 500ms
                self.msleep(500)

            except Exception as e:
                print(f"[JudgmentWorker] 处理任务失败: {e}")
                import traceback
                traceback.print_exc()
                self.current_task = None

        print(f"[JudgmentWorker] Worker 已停止 (总计处理: {self.processed_count} 个任务)")


# 全局单例
judgment_worker = JudgmentWorker()


# 测试代码
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QCoreApplication

    # 创建 Qt 应用
    app = QCoreApplication(sys.argv)

    print("测试异步判决 Worker...\n")

    # 创建并启动 Worker
    worker = JudgmentWorker()
    worker.judgment_completed.connect(lambda data: print(
        f"\n[主线程] 收到判决结果:\n"
        f"  活动: {data['activity_data'].get('app_name')}\n"
        f"  判决: {'分心' if data['result'].is_distracted else '正常'}\n"
        f"  分数: {data['result'].score}/10\n"
        f"  理由: {data['result'].reason}\n"
    ))

    worker.start()

    # 添加测试任务
    test_tasks = [
        JudgmentTask({'app_name': 'code.exe', 'window_title': 'main.py - VSCode'}),
        JudgmentTask({'app_name': 'chrome.exe', 'url': 'https://www.youtube.com/watch?v=test'}),
        JudgmentTask({'app_name': 'idea64.exe', 'window_title': 'FocusGuard - IntelliJ IDEA'}),
    ]

    print("\n添加测试任务...")
    for task in test_tasks:
        worker.add_task(task)

    print(f"\n队列大小: {worker.get_queue_size()}")

    # 等待处理完成
    print("\n等待处理完成...")
    def check_done():
        if worker.get_queue_size() == 0 and not worker.current_task:
            print("\n所有任务已完成！")
            worker.stop()
            app.quit()
        else:
            QCoreApplication.instance().startTimer(1000, check_done)

    QCoreApplication.instance().startTimer(1000, check_done)

    # 运行事件循环
    sys.exit(app.exec())
