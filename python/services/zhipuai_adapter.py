"""
智谱AI GLM-4 LLM适配器

作用：
1. 调用智谱AI GLM-4 API进行活动判断
2. 与用户进行对话
3. 管理对话历史
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

try:
    from zhipuai import ZhipuAI
    ZHIPUAI_AVAILABLE = True
except ImportError:
    ZHIPUAI_AVAILABLE = False
    print("⚠️ zhipuai 包未安装，请运行: pip install zhipuai")


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


class ZhipuAIAdapter:
    """智谱AI GLM-4适配器"""

    # 支持的模型
    MODELS = [
        'glm-4-flash',  # 快速模型（推荐）
        'glm-4',  # 标准模型
        'glm-4-plus',  # 增强模型
        'glm-4-air',  # 轻量模型
    ]

    def __init__(self, api_key: str, model: str = 'glm-4-flash'):
        """
        初始化智谱AI适配器

        Args:
            api_key: 智谱AI API密钥
            model: 模型名称，默认 glm-4-flash
        """
        if not ZHIPUAI_AVAILABLE:
            raise ImportError(
                'zhipuai 包未安装，请运行: pip install zhipuai'
            )

        self.client = ZhipuAI(api_key=api_key)
        self.default_model = model
        print(f"[ZhipuAI] 初始化成功，使用模型: {model}")

    def get_name(self) -> str:
        """获取适配器名称"""
        return '智谱AI GLM-4'

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
            # 转换消息格式
            api_messages = [
                {
                    'role': msg.role,
                    'content': msg.content
                }
                for msg in messages
            ]

            # 调试：打印消息格式
            print(f"[DEBUG] 发送消息到智谱AI API:")
            print(f"  模型: {model}")
            print(f"  消息数量: {len(api_messages)}")
            for i, msg in enumerate(api_messages):
                print(f"  消息{i+1}: Role={msg['role']}, Content={msg['content'][:30]}...")

            # 调用API
            response = self.client.chat.completions.create(
                model=model,
                messages=api_messages,
                temperature=temperature,
                top_p=top_p
            )

            # 解析响应
            return ChatResponse(
                content=response.choices[0].message.content,
                model=model,
                usage={
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                },
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as error:
            print(f'❌ 智谱AI API调用失败: {error}')
            raise Exception(f'智谱AI API调用失败: {error}')

    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            response = self.chat([
                ChatMessage(
                    role='user',
                    content='你好'
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


def create_zhipuai_adapter(
    api_key: Optional[str] = None,
    model: str = 'glm-4-flash'
) -> ZhipuAIAdapter:
    """
    创建智谱AI适配器实例

    Args:
        api_key: 智谱AI API密钥（如果为None则从环境变量读取）
        model: 模型名称

    Returns:
        智谱AI适配器实例
    """
    if api_key is None:
        api_key = os.getenv('ZHIPUAI_API_KEY')

    if not api_key:
        raise ValueError(
            '请提供智谱AI API密钥，或设置环境变量 ZHIPUAI_API_KEY'
        )

    return ZhipuAIAdapter(api_key, model)


# 测试代码
if __name__ == '__main__':
    # 测试适配器（需要设置环境变量）
    import sys

    # 从命令行参数或环境变量获取API密钥
    api_key = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        adapter = create_zhipuai_adapter(api_key)

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
    except Exception as e:
        print(f'❌ 错误: {e}')
        print('请确保设置了 ZHIPUAI_API_KEY 环境变量')
