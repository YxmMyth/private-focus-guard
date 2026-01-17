"""
对话管理服务

Phase 4: The Intervention - 苏格拉底式对话机制
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from services.zhipuai_adapter import create_zhipuai_adapter, ChatMessage
from storage.session_repository import session_repository
from storage.database import db_manager


class UserAction(Enum):
    """用户可选择的行为"""
    CLOSE_APP = "close_app"  # 关闭分心应用
    REQUEST_EXEMPTION = "request_exemption"  # 请求豁免
    ADJUST_GOAL = "adjust_goal"  # 调整目标
    IGNORE = "ignore"  # 忽略警告


@dataclass
class ConversationMessage:
    """对话消息"""
    role: str  # 'system', 'assistant', 'user'
    content: str
    timestamp: datetime
    action: Optional[str] = None  # 用户选择的行动


@dataclass
class InterventionResult:
    """干预结果"""
    should_continue: bool  # 是否继续监控
    user_action: Optional[UserAction]  # 用户选择的行动
    resolution: str  # 解决方案描述
    exemption_granted: bool  # 是否给予豁免
    new_goal: Optional[str]  # 新目标（如果调整）


class ConversationService:
    """对话管理服务 - 苏格拉底式教练"""

    def __init__(self):
        self.llm_adapter = None
        self.conversation_history: Dict[int, List[ConversationMessage]] = {}

    def initialize_llm(self):
        """初始化LLM"""
        if self.llm_adapter is None:
            try:
                import os
                api_key = os.getenv('ZHIPUAI_API_KEY')

                if api_key:
                    self.llm_adapter = create_zhipuai_adapter(api_key)
                    print("[ConversationService] 智谱AI LLM 适配器初始化成功")
                else:
                    print("[ConversationService] 未配置 LLM 密钥")
            except Exception as e:
                print(f"[ConversationService] LLM 初始化失败: {e}")

    def start_intervention(
        self,
        session_id: int,
        distraction_app: str,
        distraction_reason: str,
        tolerance_status: Any
    ) -> str:
        """
        开始干预对话

        Args:
            session_id: 会话ID
            distraction_app: 分心应用名称
            distraction_reason: 分心原因
            tolerance_status: 容忍度状态

        Returns:
            初始干预消息
        """
        # 获取会话信息
        session = session_repository.get_session_by_id(session_id)
        if not session:
            return "会话不存在"

        goal = session.get('goal', '')
        strikes_count = tolerance_status.strikes_count
        strike_limit = tolerance_status.strike_limit

        # 构建初始干预消息
        initial_message = self._build_intervention_message(
            goal=goal,
            app=distraction_app,
            reason=distraction_reason,
            strikes=strikes_count,
            limit=strike_limit
        )

        # 初始化对话历史
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []

        # 记录系统消息
        self.conversation_history[session_id].append(ConversationMessage(
            role='system',
            content=initial_message,
            timestamp=datetime.now()
        ))

        # 保存到数据库
        self._save_conversation_to_db(session_id, 'system', initial_message)

        return initial_message

    def _build_intervention_message(
        self,
        goal: str,
        app: str,
        reason: str,
        strikes: int,
        limit: int
    ) -> str:
        """构建干预消息"""
        if strikes >= limit:
            return f"""🚨 警告：已达到容忍度上限！

你的专注目标：{goal}

检测到分心活动：
• 应用：{app}
• 原因：{reason}
• 击打次数：{striks}/{limit}（已达上限）

你已经连续多次偏离目标。为了保持专注，我需要与你对话：

请告诉我：你现在正在使用 {app} 做什么？这与你的目标"{goal}"有何关系？

你可以：
1. 承认分心并关闭应用
2. 解释为什么需要使用这个应用
3. 调整你的专注目标"""

        else:
            return f"""⚡ 提醒：检测到分心活动

你的专注目标：{goal}

检测到分心活动：
• 应用：{app}
• 原因：{reason}
• 累计次数：{striks}/{limit}

请告诉我：你真的需要现在使用 {app} 吗？这对你的目标"{goal}"有何帮助？

你可以：
1. 承认分心并关闭应用
2. 解释使用的原因
3. 调整你的专注目标"""

    def process_user_response(
        self,
        session_id: int,
        user_message: str
    ) -> InterventionResult:
        """
        处理用户回复

        Args:
            session_id: 会话ID
            user_message: 用户消息

        Returns:
            InterventionResult: 干预结果
        """
        # 记录用户消息
        self.conversation_history[session_id].append(ConversationMessage(
            role='user',
            content=user_message,
            timestamp=datetime.now()
        ))

        self._save_conversation_to_db(session_id, 'user', user_message)

        # 分析用户意图
        intent = self._analyze_user_intent(user_message)

        # 根据意图生成结果
        if intent == 'close_app':
            return InterventionResult(
                should_continue=True,
                user_action=UserAction.CLOSE_APP,
                resolution="好的，请关闭分心应用，回到专注状态。",
                exemption_granted=False,
                new_goal=None
            )

        elif intent == 'request_exemption':
            # 使用 LLM 判断是否给予豁免
            exemption_decision = self._evaluate_exemption_request(
                session_id,
                user_message
            )

            return InterventionResult(
                should_continue=exemption_decision['granted'],
                user_action=UserAction.REQUEST_EXEMPTION,
                resolution=exemption_decision['response'],
                exemption_granted=exemption_decision['granted'],
                new_goal=None
            )

        elif intent == 'adjust_goal':
            # 提取新目标
            new_goal = self._extract_new_goal(user_message)

            return InterventionResult(
                should_continue=True,
                user_action=UserAction.ADJUST_GOAL,
                resolution=f"好的，已将目标调整为：{new_goal}",
                exemption_granted=False,
                new_goal=new_goal
            )

        else:
            # 默认：使用 LLM 进行苏格拉底式对话
            response = self._socratic_dialogue(session_id, user_message)

            return InterventionResult(
                should_continue=False,  # 继续对话
                user_action=None,
                resolution=response,
                exemption_granted=False,
                new_goal=None
            )

    def _analyze_user_intent(self, message: str) -> str:
        """分析用户意图（基于关键词）"""
        message_lower = message.lower()

        # 关闭应用的关键词
        close_keywords = ['关闭', 'close', '退出', 'exit', '好的', 'ok', '知道了', '马上']
        if any(kw in message_lower for kw in close_keywords):
            return 'close_app'

        # 请求豁免的关键词
        exemption_keywords = ['需要', '工作', '学习', '研究', '查资料', '必要', '重要']
        if any(kw in message_lower for kw in exemption_keywords):
            return 'request_exemption'

        # 调整目标的关键词
        adjust_keywords = ['调整', '修改', '改变', '换成', '新目标']
        if any(kw in message_lower for kw in adjust_keywords):
            return 'adjust_goal'

        return 'dialogue'

    def _evaluate_exemption_request(
        self,
        session_id: int,
        user_message: str
    ) -> Dict[str, Any]:
        """评估豁免请求"""
        if not self.llm_adapter:
            # 没有 LLM，默认给予豁免
            return {
                'granted': True,
                'response': f"理解了。既然你说：{user_message}\n\n那我就允许你继续使用。但要记住尽快回到目标上！"
            }

        try:
            session = session_repository.get_session_by_id(session_id)
            goal = session.get('goal', '')

            system_prompt = f"""你是专注力教练。用户正在请求豁免（允许继续使用当前应用）。

用户的专注目标：{goal}

用户的请求：{user_message}

请判断这个请求是否合理。如果用户给出的理由与目标相关或确实必要，应该给予豁免。
但如果明显是借口或无关娱乐，应该拒绝。

输出JSON格式：
{{
  "granted": true/false,
  "reason": "判断理由",
  "response": "给用户的回复"
}}"""

            messages = [
                ChatMessage(role='system', content=system_prompt)
            ]

            response = self.llm_adapter.chat(messages, temperature=0.3)
            result = self._parse_llm_response(response.content)

            return result

        except Exception as e:
            print(f"[ConversationService] 评估豁免失败: {e}")
            return {
                'granted': True,
                'response': "理解了，我暂时允许你继续使用。但要记住尽快回到目标上！"
            }

    def _socratic_dialogue(self, session_id: int, user_message: str) -> str:
        """苏格拉底式对话"""
        if not self.llm_adapter:
            # 没有 LLM，使用预设回复
            responses = [
                "我理解你的想法。但请再次思考：这真的有助于你达成目标吗？",
                "你说得有道理。但你能解释得更详细一些吗？",
                "我明白。那么你打算何时回到你的目标上？"
            ]
            import random
            return random.choice(responses)

        try:
            session = session_repository.get_session_by_id(session_id)
            goal = session.get('goal', '')

            # 获取对话历史
            history = self.conversation_history.get(session_id, [])
            history_text = '\n'.join([
                f"{msg.role}: {msg.content}"
                for msg in history[-5:]  # 最近5轮
            ])

            system_prompt = f"""你是苏格拉底式的专注力教练。你的任务不是命令用户，而是通过提问引导用户自己思考。

用户的专注目标：{goal}

对话历史：
{history_text}

现在请回复用户。记住：
1. 用提问引导用户思考，而不是说教
2. 理解用户的观点，但挑战其合理性
3. 帮助用户自己认识到是否应该回到目标上
4. 保持友善但坚定的语气

回复不要太长，2-3句话即可。"""

            messages = [
                ChatMessage(role='system', content=system_prompt),
                ChatMessage(role='user', content=user_message)
            ]

            response = self.llm_adapter.chat(messages, temperature=0.7)
            return response.content

        except Exception as e:
            print(f"[ConversationService] 对话失败: {e}")
            return "我理解。那么你打算何时回到你的目标上？"

    def _extract_new_goal(self, message: str) -> str:
        """从用户消息中提取新目标"""
        # 简单提取：查找"目标"、"改成"等关键词后的内容
        import re

        patterns = [
            r'目标[是为的]*(.+?)[。，！？\n]',
            r'改成*(.+?)[。，！？\n]',
            r'调整[到为]*(.+?)[。，！？\n]',
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()

        return message  # 如果无法提取，返回原文

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                import json
                return json.loads(json_match.group(0))
        except:
            pass

        return {
            'granted': True,
            'reason': '无法解析，默认给予豁免',
            'response': response
        }

    def _save_conversation_to_db(self, session_id: int, role: str, content: str):
        """保存对话到数据库"""
        try:
            conn = db_manager.get_connection()

            conn.execute('''
                INSERT INTO conversations (judgment_id, role, content)
                VALUES (?, ?, ?)
            ''', (session_id, role, content))

            conn.commit()
        except Exception as e:
            print(f"[ConversationService] 保存对话失败: {e}")

    def clear_conversation(self, session_id: int):
        """清空对话历史"""
        if session_id in self.conversation_history:
            self.conversation_history[session_id].clear()


# 全局单例
conversation_service = ConversationService()
