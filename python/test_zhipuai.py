"""
智谱AI API连接测试脚本

测试内容：
1. API连接
2. 基本对话
3. 活动判断
"""

import os
import sys

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from services.zhipuai_adapter import create_zhipuai_adapter, ChatMessage

def test_connection():
    """测试API连接"""
    print("=" * 60)
    print("🧪 智谱AI API连接测试")
    print("=" * 60)

    # 从环境变量获取API密钥，如果没有则使用硬编码的密钥
    api_key = os.getenv('ZHIPUAI_API_KEY')

    if not api_key:
        # 使用提供的API密钥
        api_key = "1a9b343b6bb947bf939814b919a3c9fb.Nv1tf3ds7jltzywn"
        print("\n⚠️ 使用硬编码的API密钥")

    print(f"\n📝 API密钥: {api_key[:20]}...{api_key[-10:]}")

    try:
        # 创建适配器
        print("\n🔧 正在创建智谱AI适配器...")
        adapter = create_zhipuai_adapter(api_key)
        print("✅ 适配器创建成功")

        # 测试基本对话
        print("\n" + "=" * 60)
        print("📨 测试1: 基本对话")
        print("=" * 60)

        response = adapter.chat([
            ChatMessage(role='user', content='你好，请回复"连接成功"')
        ])

        print(f"\n📥 AI响应: {response.content}")
        print(f"📊 Token使用: {response.usage}")

        if '连接成功' in response.content or '你好' in response.content:
            print("✅ 基本对话测试通过")
        else:
            print("⚠️ 响应内容不符合预期")

        # 测试活动判断
        print("\n" + "=" * 60)
        print("🎯 测试2: 活动判断")
        print("=" * 60)

        activity = {
            'type': 'browser',
            'data': {
                'url': 'https://www.bilibili.com',
                'title': '哔哩哔哩 ( ゜- ゜)つロ 乾杯~'
            }
        }

        print(f"\n活动数据: {activity}")
        print("正在判断是否分心...")

        result = adapter.evaluate_activity(activity, [])

        print(f"\n判断结果:")
        print(f"  是否分心: {result.is_distracted}")
        print(f"  置信度: {result.confidence}")
        print(f"  行动: {result.action}")
        print(f"  理由: {result.reason}")

        if result.is_distracted:
            print("✅ 活动判断测试通过（正确识别分心）")
        else:
            print("⚠️ 判断结果：未识别为分心")

        # 测试多轮对话
        print("\n" + "=" * 60)
        print("💬 测试3: 多轮对话")
        print("=" * 60)

        conversation = [
            ChatMessage(role='user', content='我在学习Python编程'),
            ChatMessage(role='assistant', content='很好！学习编程很有用。'),
            ChatMessage(role='user', content='但是现在打开了Bilibili')
        ]

        print("\n对话历史:")
        for msg in conversation:
            print(f"  [{msg.role}]: {msg.content}")

        print("\n正在生成回复...")
        dialog_result = adapter.converse(conversation, activity, [])

        print(f"\nAI回复: {dialog_result.message}")
        print(f"是否最终: {dialog_result.is_final}")
        print(f"决策: {dialog_result.decision}")

        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)

        return True

    except ImportError as e:
        print(f"\n❌ 错误：缺少依赖包")
        print(f"   {e}")
        print("\n请运行: pip install zhipuai")
        return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)
