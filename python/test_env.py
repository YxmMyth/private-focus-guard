"""
测试环境变量加载
"""
import os
import sys
from dotenv import load_dotenv

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 加载.env文件
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

print(f"环境变量文件路径: {env_path}")
print(f"TENCENT_SECRET_ID: {'已设置' if os.getenv('TENCENT_SECRET_ID') else '未设置'}")
print(f"TENCENT_SECRET_KEY: {'已设置' if os.getenv('TENCENT_SECRET_KEY') else '未设置'}")

# 测试LLM服务初始化
try:
    from services.llm_service import create_hunyuan_adapter

    secret_id = os.getenv('TENCENT_SECRET_ID')
    secret_key = os.getenv('TENCENT_SECRET_KEY')

    if secret_id and secret_key:
        print("\n正在初始化LLM适配器...")
        adapter = create_hunyuan_adapter(secret_id, secret_key)
        print("[OK] LLM适配器初始化成功！")

        # 测试简单调用
        print("\n正在测试LLM调用...")
        from services.llm_service import ChatMessage

        # 测试多种消息格式
        test_cases = [
            # 测试1：简单问候
            ([ChatMessage(role='user', content='你好呀！')], "简单问候"),
            # 测试2：数学计算
            ([ChatMessage(role='user', content='1+1等于几？')], "数学计算"),
            # 测试3：自我介绍
            ([ChatMessage(role='user', content='请简单介绍下自己')], "自我介绍"),
        ]

        for messages, desc in test_cases:
            try:
                print(f"\n测试: {desc}")
                response = adapter.chat(messages, temperature=0.7)
                print(f"[OK] 成功！回复: {response.content[:100]}")
                break  # 如果成功就停止测试
            except Exception as e:
                print(f"[FAIL] 失败: {str(e)[:100]}...")
                continue
    else:
        print("[ERROR] 未设置API密钥，无法测试LLM")
except Exception as e:
    print(f"[ERROR] LLM测试失败: {e}")
    import traceback
    traceback.print_exc()
