"""
专注监督服务

负责判断用户活动是否符合目标，计算分心值
Phase 2: The Judge - 三层次判决系统
"""

import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

from services.zhipuai_adapter import create_zhipuai_adapter, ChatMessage
from storage.session_repository import session_repository


@dataclass
class JudgmentResult:
    """判决结果"""
    is_distracted: bool
    score: float  # 0-10, 10=完全分心
    reason: str
    confidence: float  # 0-1
    rule_used: str  # 'rule', 'llm', 'fallback'
    timestamp: datetime


class SupervisionService:
    """专注监督服务"""

    def __init__(self):
        self.llm_adapter = None
        self.distraction_history = deque(maxlen=100)  # 最近100次判决
        self.cache = {}  # 判决结果缓存
        self.cache_ttl = timedelta(minutes=5)

    def initialize_llm(self):
        """初始化 LLM 适配器"""
        if self.llm_adapter is None:
            try:
                # 从环境变量读取密钥
                import os
                api_key = os.getenv('ZHIPUAI_API_KEY')

                if api_key:
                    self.llm_adapter = create_zhipuai_adapter(api_key)
                    print("[SupervisionService] 智谱AI LLM 适配器初始化成功")
                else:
                    print("[SupervisionService] 未配置 LLM 密钥，仅使用规则判决")
            except Exception as e:
                print(f"[SupervisionService] LLM 初始化失败: {e}")

    def judge_activity(
        self,
        activity_data: Dict[str, Any],
        session_id: Optional[int] = None
    ) -> JudgmentResult:
        """
        判断活动是否分心

        Args:
            activity_data: 活动数据 {app_name, window_title, url, ...}
            session_id: 会话 ID

        Returns:
            JudgmentResult: 判决结果
        """
        # 获取会话信息
        session = None
        if session_id:
            session = session_repository.get_session_by_id(session_id)
        else:
            session = session_repository.get_active_session()

        if not session:
            # 没有活跃会话，使用保守策略
            return JudgmentResult(
                is_distracted=False,
                score=0.0,
                reason="无活跃会话，不进行判断",
                confidence=1.0,
                rule_used='fallback',
                timestamp=datetime.now()
            )

        # 层次1: 规则快速判断
        rule_result = self._rule_based_judgment(activity_data, session)
        if rule_result is not None:
            self.distraction_history.append(rule_result)
            return rule_result

        # 层次2: LLM 语义判断（异步）
        # 注意：这里应该调用异步 worker，见 judgment_worker.py
        # 暂时返回保守结果
        fallback_result = self._fallback_judgment(activity_data, session)
        self.distraction_history.append(fallback_result)
        return fallback_result

    def _rule_based_judgment(
        self,
        activity_data: Dict[str, Any],
        session: Dict[str, Any]
    ) -> Optional[JudgmentResult]:
        """基于规则的快速判断"""
        goal = session.get('goal', '').lower()
        scope = session.get('scope', '').lower()
        app_name = activity_data.get('app_name', '').lower()
        window_title = activity_data.get('window_title', '').lower()
        url = activity_data.get('url', '').lower()

        # 调试输出
        if url:
            print(f"[Judgment] 检测到URL: {url[:60]}...")
        print(f"[Judgment] 窗口标题: {window_title[:60]}...")

        # 规则1: 允许的应用白名单
        if scope:
            allowed_apps = [app.strip().lower() for app in scope.split(',')]
            if any(allowed_app in app_name for allowed_app in allowed_apps):
                print(f"[Judgment] 白名单匹配: {app_name} 在 {scope} 中")
                return JudgmentResult(
                    is_distracted=False,
                    score=0.0,
                    reason=f"在允许范围内: {app_name}",
                    confidence=1.0,
                    rule_used='rule',
                    timestamp=datetime.now()
                )

        # 规则2: 窗口标题关键词匹配（新！更可靠）
        distraction_keywords = ['youtube', 'bilibili', 'netflix', 'tiktok', 'douyin', '抖音', '爱奇艺', '优酷', '腾讯视频']
        for keyword in distraction_keywords:
            if keyword in window_title:
                print(f"[Judgment] 窗口标题匹配: {keyword} 在 {window_title[:40]}...")
                return JudgmentResult(
                    is_distracted=True,
                    score=8.0,
                    reason=f"窗口标题包含分心关键词: {keyword}",
                    confidence=1.0,
                    rule_used='rule',
                    timestamp=datetime.now()
                )

        # 规则3: URL 关键词匹配
        if url:
            distraction_keywords = ['watch', 'video', 'game', 'entertainment', '娱乐', 'bilibili', 'youtube']
            for keyword in distraction_keywords:
                if keyword in url:
                    print(f"[Judgment] URL关键词匹配: {keyword} in {url[:40]}...")
                    return JudgmentResult(
                        is_distracted=True,
                        score=7.0,
                        reason=f"URL包含分心关键词: {url[:50]}",
                        confidence=0.8,
                        rule_used='rule',
                        timestamp=datetime.now()
                    )

        # 规则4: 编程相关工具（通常不认为是分心）
        dev_tools = ['code', 'idea', 'pycharm', 'visual studio', 'terminal', 'cmd', 'powershell']
        if any(tool in app_name for tool in dev_tools):
            return JudgmentResult(
                is_distracted=False,
                score=0.0,
                reason=f"开发工具: {app_name}",
                confidence=0.9,
                rule_used='rule',
                timestamp=datetime.now()
            )

        # 规则无法判断，返回 None，使用 LLM
        return None

    def llm_judgment(
        self,
        activity_data: Dict[str, Any],
        session: Dict[str, Any]
    ) -> JudgmentResult:
        """基于 LLM 的语义判断"""
        if not self.llm_adapter:
            return self._fallback_judgment(activity_data, session)

        try:
            # 构建 Prompt
            system_prompt = self._build_judgment_prompt(session)
            user_prompt = self._build_activity_prompt(activity_data)

            # 调用 LLM
            messages = [
                ChatMessage(role='system', content=system_prompt),
                ChatMessage(role='user', content=user_prompt)
            ]
            response = self.llm_adapter.chat(messages, temperature=0.3)

            # 解析结果
            result = self._parse_llm_response(response.content)

            # 记录到历史
            self.distraction_history.append(result)

            return result

        except Exception as e:
            print(f"[SupervisionService] LLM 判断失败: {e}")
            return self._fallback_judgment(activity_data, session)

    def _build_judgment_prompt(self, session: Dict[str, Any]) -> str:
        """构建判决系统提示词"""
        goal = session.get('goal', '')
        scope = session.get('scope', '')

        return f"""你是一个专注度裁判。你的任务是判断用户当前行为是否符合其专注目标。

用户的专注目标：{goal}

允许的范围：{scope if scope else "未明确指定"}

判断标准：
1. 行为是否直接服务于目标（如编程时访问StackOverflow）
2. 行为是否是必要的工具使用（如打开终端、文档）
3. 行为是否明显偏离目标（如看娱乐视频、社交媒体）

输出格式（JSON）：
{{
  "is_distracted": true/false,
  "score": 0.0-10.0,
  "reason": "判断理由（简短明确）",
  "confidence": 0.0-1.0
}}

评分标准：
- 0-3分：明确符合目标
- 4-6分：工具性使用（不确定是否分心）
- 7-10分：明确偏离目标

请严格但公正地判断。"""

    def _build_activity_prompt(self, activity_data: Dict[str, Any]) -> str:
        """构建活动描述"""
        app_name = activity_data.get('app_name', '')
        # 支持两种命名方式：window_title 和 windowTitle
        window_title = activity_data.get('window_title', activity_data.get('windowTitle', ''))
        url = activity_data.get('url', '')

        if url:
            return f"""用户正在使用浏览器：
- 应用：{app_name}
- 网页标题：{window_title}
- URL：{url}

请判断这是否服务于用户的目标。"""
        else:
            return f"""用户正在使用应用：
- 应用：{app_name}
- 窗口标题：{window_title}

请判断这是否服务于用户的目标。"""

    def _parse_llm_response(self, response: str) -> JudgmentResult:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError("未找到 JSON 响应")

            result = json.loads(json_match.group(0))

            return JudgmentResult(
                is_distracted=result.get('is_distracted', False),
                score=float(result.get('score', 0)),
                reason=result.get('reason', ''),
                confidence=float(result.get('confidence', 0.5)),
                rule_used='llm',
                timestamp=datetime.now()
            )
        except Exception as e:
            print(f"[SupervisionService] 解析 LLM 响应失败: {e}")
            # 返回保守结果
            return JudgmentResult(
                is_distracted=False,
                score=0.0,
                reason="LLM响应解析失败，默认允许",
                confidence=0.0,
                rule_used='fallback',
                timestamp=datetime.now()
            )

    def _fallback_judgment(
        self,
        activity_data: Dict[str, Any],
        session: Dict[str, Any]
    ) -> JudgmentResult:
        """保守策略：默认允许"""
        return JudgmentResult(
            is_distracted=False,
            score=0.0,
            reason="无法明确判断，默认允许",
            confidence=0.5,
            rule_used='fallback',
            timestamp=datetime.now()
        )

    def get_distraction_score(self, window_size: int = 10) -> float:
        """
        计算滑动窗口内的平均分心值

        Args:
            window_size: 窗口大小（最近N次判决）

        Returns:
            平均分心值 (0-10)
        """
        if not self.distraction_history:
            return 0.0

        recent = list(self.distraction_history)[-window_size:]
        if not recent:
            return 0.0

        total = sum(judgment.score for judgment in recent)
        return total / len(recent)

    def clear_history(self):
        """清空判决历史"""
        self.distraction_history.clear()


# 全局单例
supervision_service = SupervisionService()


# 测试代码
if __name__ == '__main__':
    print("测试专注监督服务...\n")

    # 初始化 LLM（需要设置环境变量）
    supervision_service.initialize_llm()

    # 模拟一个会话
    test_session = {
        'id': 1,
        'goal': '完成 Python 项目开发',
        'scope': 'VSCode, Chrome, GitHub'
    }

    # 测试规则判断
    print("测试规则判断:")
    test_activities = [
        {'app_name': 'code.exe', 'window_title': 'main.py - Visual Studio Code'},
        {'app_name': 'chrome.exe', 'url': 'https://www.youtube.com/watch?v=test'},
        {'app_name': 'idea64.exe', 'window_title': 'FocusGuard - IntelliJ IDEA'},
    ]

    for activity in test_activities:
        result = supervision_service.judge_activity(activity, 1)
        print(f"\n活动: {activity['app_name']}")
        print(f"判决: {'分心' if result.is_distracted else '正常'}")
        print(f"分数: {result.score}/10")
        print(f"理由: {result.reason}")
        print(f"规则: {result.rule_used}")

    print(f"\n平均分心值: {supervision_service.get_distraction_score():.2f}/10")
