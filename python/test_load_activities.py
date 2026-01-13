"""测试加载活动记录"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from storage.database import db_manager
from storage.activity_repository import activity_repository
from datetime import datetime
import json

print("=" * 50)
print("测试加载活动记录")
print("=" * 50)

# 初始化数据库
db_manager.initialize()

# 获取活动记录
recent = activity_repository.get_recent_activities(limit=10)
print(f"\n获取到 {len(recent)} 条活动记录\n")

for i, activity in enumerate(recent[:5], 1):
    print(f"{i}. ID: {activity['id']}")
    print(f"   时间: {datetime.fromtimestamp(activity['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   类型: {activity['type']}")

    data = json.loads(activity['data'])
    print(f"   应用: {data.get('appName', 'Unknown')}")
    print(f"   标题: {data.get('windowTitle', '')[:50]}...")
    print()

print("=" * 50)
print("测试完成！")
print("=" * 50)
