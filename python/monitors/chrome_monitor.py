"""
Chrome/Edge 浏览历史监控器

作用：
1. 读取Chrome/Edge浏览历史记录
2. 获取最近访问的URL和页面标题
3. 定期更新历史记录
"""

import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import tempfile


@dataclass
class BrowserActivity:
    """浏览器活动数据模型"""
    url: str
    title: str
    visit_time: datetime
    browser: str  # 'chrome', 'edge'


class BrowserMonitor:
    """浏览器监控器类"""

    def __init__(self):
        self.last_timestamp = 0
        self.cached_urls = set()

    def get_chrome_history_path(self) -> Optional[str]:
        """获取Chrome History文件路径"""
        user_profile = os.environ.get('USERPROFILE')
        if not user_profile:
            return None

        possible_paths = [
            os.path.join(user_profile, 'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'History'),
            os.path.join(user_profile, 'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Profile 1', 'History'),
            os.path.join(user_profile, 'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Profile 2', 'History'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def get_edge_history_path(self) -> Optional[str]:
        """获取Edge History文件路径"""
        user_profile = os.environ.get('USERPROFILE')
        if not user_profile:
            return None

        possible_paths = [
            os.path.join(user_profile, 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data', 'Default', 'History'),
            os.path.join(user_profile, 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data', 'Profile 1', 'History'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def read_history_file(self, history_path: str) -> List[Dict[str, Any]]:
        """
        读取浏览器历史文件

        Args:
            history_path: History文件路径

        Returns:
            历史记录列表
        """
        if not os.path.exists(history_path):
            return []

        # 复制到临时文件（Chrome/Edge可能正在使用）
        temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
        try:
            os.close(temp_fd)
            shutil.copy2(history_path, temp_path)

            # 读取历史
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()

            # 查询最近5分钟的访问记录
            # Chrome时间戳是微秒，从1601-01-01开始
            five_minutes_ago = int((datetime.now() - timedelta(minutes=5)).timestamp() * 1000000) + 11644473600000000

            query = """
                SELECT url, title, last_visit_time
                FROM urls
                WHERE last_visit_time > ?
                ORDER BY last_visit_time DESC
                LIMIT 50
            """

            cursor.execute(query, (five_minutes_ago,))
            rows = cursor.fetchall()

            conn.close()

            results = []
            for row in rows:
                url, title, last_visit_time = row

                # 过滤掉非HTTP协议和内部页面
                if not self.is_valid_url(url):
                    continue

                # 转换时间戳
                visit_time = self.chrome_time_to_datetime(last_visit_time)

                results.append({
                    'url': url,
                    'title': title or url,
                    'visit_time': visit_time
                })

            return results

        except Exception as e:
            print(f'[BrowserMonitor] 读取历史失败: {e}')
            return []
        finally:
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass

    def is_valid_url(self, url: str) -> bool:
        """判断URL是否有效（过滤内部页面）"""
        if not url or not isinstance(url, str):
            return False

        # 只允许HTTP和HTTPS协议
        if not (url.startswith('http://') or url.startswith('https://')):
            return False

        # 过滤内部页面
        blocked_prefixes = [
            'chrome://',
            'chrome-extension://',
            'edge://',
            'extension://',
            'about:',
        ]

        for prefix in blocked_prefixes:
            if url.startswith(prefix):
                return False

        return True

    def chrome_time_to_datetime(self, chrome_time: int) -> datetime:
        """
        Chrome时间戳转datetime

        Chrome时间戳：从1601-01-01 00:00:00开始的微秒数
        """
        # 减去Chrome基准时间（1601-01-01到1970-01-01的微秒数）
        windows_epoch = 11644473600000000
        microseconds_since_chrome_epoch = chrome_time - windows_epoch

        # 转换为秒
        seconds_since_unix_epoch = microseconds_since_chrome_epoch / 1000000

        return datetime.fromtimestamp(seconds_since_unix_epoch)

    def get_recent_chrome_history(self, limit: int = 10) -> List[BrowserActivity]:
        """获取Chrome最近历史"""
        history_path = self.get_chrome_history_path()
        if not history_path:
            return []

        records = self.read_history_file(history_path)

        activities = []
        for record in records[:limit]:
            # 去重
            if record['url'] in self.cached_urls:
                continue

            self.cached_urls.add(record['url'])

            activities.append(BrowserActivity(
                url=record['url'],
                title=record['title'],
                visit_time=record['visit_time'],
                browser='chrome'
            ))

        return activities

    def get_recent_edge_history(self, limit: int = 10) -> List[BrowserActivity]:
        """获取Edge最近历史"""
        history_path = self.get_edge_history_path()
        if not history_path:
            return []

        records = self.read_history_file(history_path)

        activities = []
        for record in records[:limit]:
            # 去重
            if record['url'] in self.cached_urls:
                continue

            self.cached_urls.add(record['url'])

            activities.append(BrowserActivity(
                url=record['url'],
                title=record['title'],
                visit_time=record['visit_time'],
                browser='edge'
            ))

        return activities

    def get_all_browser_history(self, limit: int = 20) -> List[BrowserActivity]:
        """获取所有浏览器历史"""
        activities = []

        # 获取Chrome历史
        chrome_history = self.get_recent_chrome_history(limit)
        activities.extend(chrome_history)

        # 获取Edge历史
        edge_history = self.get_recent_edge_history(limit)
        activities.extend(edge_history)

        # 按时间排序
        activities.sort(key=lambda x: x.visit_time, reverse=True)

        return activities[:limit]

    def clear_cache(self):
        """清空URL缓存"""
        self.cached_urls.clear()


# 单例
browser_monitor = BrowserMonitor()


# 测试代码
if __name__ == '__main__':
    print("测试浏览器历史监控...\n")

    # 获取Chrome历史
    print("Chrome历史:")
    chrome_history = browser_monitor.get_recent_chrome_history(limit=10)
    for activity in chrome_history:
        print(f"  [{activity.visit_time.strftime('%H:%M:%S')}] {activity.title}")
        print(f"    {activity.url[:80]}...")

    print()

    # 获取Edge历史
    print("Edge历史:")
    edge_history = browser_monitor.get_recent_edge_history(limit=10)
    for activity in edge_history:
        print(f"  [{activity.visit_time.strftime('%H:%M:%S')}] {activity.title}")
        print(f"    {activity.url[:80]}...")

    print(f"\n总计: {len(chrome_history) + len(edge_history)} 条记录")
