"""
直接测试腾讯混元API（参考官方示例）
"""
import os
import sys
from dotenv import load_dotenv

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

    # 从环境变量获取密钥
    secret_id = os.getenv('TENCENT_SECRET_ID')
    secret_key = os.getenv('TENCENT_SECRET_KEY')

    if not secret_id or not secret_key:
        print("[ERROR] 未设置API密钥")
        sys.exit(1)

    print("[OK] API密钥已加载")

    # 创建认证对象
    cred = credential.Credential(secret_id, secret_key)

    # 创建HTTP配置
    httpProfile = HttpProfile()
    httpProfile.endpoint = "hunyuan.tencentcloudapi.com"
    httpProfile.protocol = "https"

    # 创建客户端配置
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile

    # 初始化客户端
    print("\n正在初始化客户端...")
    client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", clientProfile)
    print("[OK] 客户端初始化成功")

    # 构建请求（参考官方示例10）
    print("\n正在发送请求...")
    req = models.ChatCompletionsRequest()
    req.Model = "hunyuan-turbo"
    req.Messages = [
        {
            "Role": "user",
            "Content": "你好呀！"
        }
    ]
    req.TopP = 0
    req.Stream = False
    req.Temperature = 0

    # 打印请求信息
    print(f"模型: {req.Model}")
    print(f"消息: {req.Messages}")
    print(f"TopP: {req.TopP}")
    print(f"Temperature: {req.Temperature}")

    # 发送请求
    resp = client.ChatCompletions(req)

    # 解析响应
    print("\n[OK] API调用成功！")
    print(f"回复: {resp.Choices[0].Message.Content}")
    print(f"Token使用: {resp.Usage.TotalTokens}")

except Exception as e:
    print(f"\n[ERROR] 调用失败: {e}")
    import traceback
    traceback.print_exc()
