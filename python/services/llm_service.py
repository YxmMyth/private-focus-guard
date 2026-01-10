"""
腾讯混元LLM适配器

作用：
1. 调用腾讯混元API进行活动判断
2. 与用户进行对话
3. 管理对话历史
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from tencentcloud.common import credential
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # 'user', 'assistant', 'system'
    content: str


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


@dataclass
class JudgmentResult:
    """判断结果"""
    is_distracted: bool
    confidence: float
    action: str  # 'allow', 'warn', 'block', 'dialog'
    reason: str
    message_to_user: Optional[str] = None
    distraction_level: Optional[int] = None
    requires_dialog: bool = False
    questions: List[str] = None

    def __post_init__(self):
        if self.questions is None:
            self.questions = []


@dataclass
class DialogResult:
    """对话结果"""
    is_final: bool
    decision: str  # 'allow', 'block'
    message: str
    questions: List[str] = None
    learned_preference: Optional[str] = None

    def __post_init__(self):
        if self.questions is None:
            self.questions = []


class HunyuanAdapter:
    """腾讯混元适配器"""

    # 支持的模型
    MODELS = [
        'hunyuan-lite',  # 轻量级模型（免费）
        'hunyuan-standard',  # 标准模型
        'hunyuan-pro',  # 专业模型
    ]

    def __init__(self, secret_id: str, secret_key: str, region: str = 'ap-guangzhou'):
        """
        初始化腾讯混元适配器

        Args:
            secret_id: 腾讯云SecretId
            secret_key: 腾讯云SecretKey
            region: 区域，默认 ap-guangzhou
        """
        # 创建认证对象
        cred = credential.Credential(secret_id, secret_key)

        # 创建HTTP配置
        from tencentcloud.common.profile.http_profile import HttpProfile
        httpProfile = HttpProfile()
        httpProfile.endpoint = "hunyuan.tencentcloudapi.com"
        httpProfile.protocol = "https"

        # 创建客户端配置
        from tencentcloud.common.profile.client_profile import ClientProfile
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile

        # 初始化客户端（正确的传参方式）
        self.client = hunyuan_client.HunyuanClient(cred, region, clientProfile)
        self.default_model = 'hunyuan-turbo'  # 使用turbo而不是lite

    def get_name(self) -> str:
        """获取适配器名称"""
        return '腾讯混元'

    def get_models(self) -> List[str]:
        """获取支持的模型列表"""
        return self.MODELS

    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> ChatResponse:
        """
        发起聊天请求

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            top_p: top_p参数

        Returns:
            聊天响应
        """
        if model is None:
            model = self.default_model

        try:
            # 转换消息格式（注意：Role必须是小写：user, assistant, system）
            sdk_messages = [
                {
                    'Role': msg.role.lower(),  # 小写！
                    'Content': msg.content
                }
                for msg in messages
            ]

            # 调试：打印消息格式
            print(f"[DEBUG] 发送消息到腾讯混元API:")
            print(f"  模型: {model}")
            print(f"  消息数量: {len(sdk_messages)}")
            for i, msg in enumerate(sdk_messages):
                print(f"  消息{i+1}: Role={msg['Role']}, Content={msg['Content'][:30]}...")

            # 构建请求参数（注意：这些属性使用大驼峰，是SDK的要求）
            req = models.ChatCompletionsRequest()
            req.Model = model
            req.Messages = sdk_messages
            req.Temperature = temperature
            req.TopP = top_p

            # 调用API
            resp = self.client.ChatCompletions(req)

            # 解析响应（注意：响应对象直接包含Choices，不需要.Response）
            return ChatResponse(
                content=resp.Choices[0].Message.Content,
                model=model,
                usage={
                    'prompt_tokens': resp.Usage.PromptTokens,
                    'completion_tokens': resp.Usage.CompletionTokens,
                    'total_tokens': resp.Usage.TotalTokens
                },
                finish_reason=resp.Choices[0].FinishReason.lower()
            )

        except Exception as error:
            print(f'❌ 腾讯混元API调用失败: {error}')
            raise Exception(f'腾讯混元API调用失败: {error}')

    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            response = self.chat([
                ChatMessage(
                    role='user',
                    content='测试连接'
                )
            ])
            return len(response.content) > 0
        except Exception as error:
            print(f'API连接测试失败: {error}')
            return False

    def evaluate_activity(
        self,
        activity: Dict[str, Any],
        focus_goals: List[Dict[str, Any]]
    ) -> JudgmentResult:
        """
        判断活动是否分心

        Args:
            activity: 活动数据
            focus_goals: 专注目标列表

        Returns:
            判断结果
        """
        system_prompt = self._build_system_prompt(focus_goals)
        user_prompt = self._build_evaluation_prompt(activity)

        try:
            response = self.chat([
                ChatMessage(role='system', content=system_prompt),
                ChatMessage(role='user', content=user_prompt)
            ])

            # 解析AI响应
            return self._parse_judgment_response(response.content)

        except Exception as error:
            print(f'❌ AI评估失败: {error}')
            # 返回默认结果
            return JudgmentResult(
                is_distracted=False,
                confidence=0.0,
                action='allow',
                reason='AI评估失败，默认放行'
            )

    def converse(
        self,
        conversation_history: List[ChatMessage],
        activity: Dict[str, Any],
        focus_goals: List[Dict[str, Any]]
    ) -> DialogResult:
        """
        与用户对话

        Args:
            conversation_history: 对话历史
            activity: 活动数据
            focus_goals: 专注目标列表

        Returns:
            对话结果
        """
        system_prompt = self._build_dialog_prompt(focus_goals)

        try:
            messages = [
                ChatMessage(role='system', content=system_prompt),
                *conversation_history
            ]

            response = self.chat(
                messages=messages,
                temperature=0.8  # 对话时使用更高的温度
            )

            return self._parse_dialog_response(response.content)

        except Exception as error:
            print(f'❌ AI对话失败: {error}')
            return DialogResult(
                is_final=True,
                decision='allow',
                message='抱歉，AI服务出现错误，允许您继续访问'
            )

    def _build_system_prompt(self, focus_goals: List[Dict[str, Any]]) -> str:
        """构建系统提示词（评估模式）"""
        goals_text = '\n'.join([
            f"- {goal.get('name', '')}: {goal.get('description', '')}"
            for goal in focus_goals
        ])

        return f"""你是一个专注力助手，帮助用户保持专注。

用户的专注目标：
{goals_text or '用户没有设置明确的专注目标'}

你的任务是分析用户的活动是否与专注目标冲突。

响应格式（JSON）：
{{
  "is_distracted": true/false,
  "confidence": 0.0-1.0,
  "distraction_level": 1-10,
  "action": "allow" | "warn" | "block" | "dialog",
  "reason": "简要说明判断原因",
  "message_to_user": "对用户说的话",
  "requires_dialog": true/false,
  "questions": ["问题1", "问题2"]
}}

判断原则：
1. 考虑用户的长期目标
2. 考虑当前活动是否必要（工作相关、休息、学习等）
3. 适当的灵活性（允许必要的休息）
4. 如果不确定，选择对话而不是强制阻止"""

    def _build_evaluation_prompt(self, activity: Dict[str, Any]) -> str:
        """构建评估提示词"""
        activity_type = activity.get('type', '')
        data = activity.get('data', {})

        if activity_type == 'browser':
            activity_text = f"""正在访问网站：{data.get('url', '未知')}
页面标题：{data.get('title', '未知')}"""
        else:
            activity_text = f"""正在使用应用: {data.get('appName', '未知')}
窗口标题: {data.get('windowTitle', '未知')}"""

        return f"""请分析以下用户活动：

{activity_text}

请判断这是否是分心活动，并决定应该采取什么行动。"""

    def _build_dialog_prompt(self, focus_goals: List[Dict[str, Any]]) -> str:
        """构建对话模式提示词"""
        goals_text = '\n'.join([
            f"- {goal.get('name', '')}: {goal.get('description', '')}"
            for goal in focus_goals
        ])

        return f"""你是一个友善但坚定的专注力助手。用户正在访问可能分散注意力的内容。

用户的专注目标：
{goals_text or '用户没有设置明确的专注目标'}

你的任务是：
1. 了解用户的真实意图
2. 如果用户有充分的理由，允许他们继续
3. 如果理由不充分，友善地劝说他们回到专注任务
4. 最多进行3-5轮对话

响应格式（JSON）：
{{
  "is_final": true/false,
  "decision": "allow" | "block",
  "message": "对用户说的话",
  "questions": ["继续问的问题"],
  "learned_preference": "学到的用户偏好"
}}

保持友善、理解和专业的语气。"""

    def _parse_judgment_response(self, content: str) -> JudgmentResult:
        """解析判断响应"""
        try:
            # 尝试提取JSON
            json_match = self._extract_json(content)
            if not json_match:
                raise ValueError('未找到JSON响应')

            result = json.loads(json_match)

            return JudgmentResult(
                is_distracted=result.get('is_distracted', False),
                confidence=result.get('confidence', 0.0),
                action=result.get('action', 'allow'),
                reason=result.get('reason', ''),
                message_to_user=result.get('message_to_user'),
                distraction_level=result.get('distraction_level'),
                requires_dialog=result.get('requires_dialog', False),
                questions=result.get('questions', [])
            )

        except Exception as error:
            print(f'❌ 解析AI响应失败: {error}')
            # 返回保守的默认值
            return JudgmentResult(
                is_distracted=False,
                confidence=0.0,
                action='allow',
                reason='无法解析AI响应'
            )

    def _parse_dialog_response(self, content: str) -> DialogResult:
        """解析对话响应"""
        try:
            json_match = self._extract_json(content)
            if not json_match:
                raise ValueError('未找到JSON响应')

            result = json.loads(json_match)

            return DialogResult(
                is_final=result.get('is_final', True),
                decision=result.get('decision', 'allow'),
                message=result.get('message', content),
                questions=result.get('questions', []),
                learned_preference=result.get('learned_preference')
            )

        except Exception as error:
            print(f'❌ 解析对话响应失败: {error}')
            return DialogResult(
                is_final=True,
                decision='allow',
                message=content
            )

    def _extract_json(self, content: str) -> Optional[str]:
        """从文本中提取JSON"""
        import re
        match = re.search(r'\{[\s\S]*\}', content)
        return match.group(0) if match else None


def create_hunyuan_adapter(
    secret_id: Optional[str] = None,
    secret_key: Optional[str] = None
) -> HunyuanAdapter:
    """
    创建腾讯混元适配器实例

    Args:
        secret_id: 腾讯云SecretId（如果为None则从环境变量读取）
        secret_key: 腾讯云SecretKey（如果为None则从环境变量读取）

    Returns:
        腾讯混元适配器实例
    """
    if secret_id is None:
        secret_id = os.getenv('TENCENT_SECRET_ID')
    if secret_key is None:
        secret_key = os.getenv('TENCENT_SECRET_KEY')

    if not secret_id or not secret_key:
        raise ValueError(
            '请提供腾讯云密钥，或设置环境变量 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY'
        )

    return HunyuanAdapter(secret_id, secret_key)


# 测试代码
if __name__ == '__main__':
    # 测试适配器（需要设置环境变量）
    import sys

    if len(sys.argv) < 3:
        print('用法: python llm_service.py <secret_id> <secret_key>')
        sys.exit(1)

    adapter = create_hunyuan_adapter(sys.argv[1], sys.argv[2])

    # 测试连接
    if adapter.test_connection():
        print('✅ API连接成功')

        # 测试活动评估
        activity = {
            'type': 'browser',
            'data': {
                'url': 'https://www.bilibili.com',
                'title': '哔哩哔哩'
            }
        }

        result = adapter.evaluate_activity(activity, [])
        print(f'判断结果: {result.action}')
        print(f'理由: {result.reason}')
    else:
        print('❌ API连接失败')
