"""
FocusGuard v2.0 - LLM Service Module

集成 LLM API（OpenAI 兼容接口），提供基于信任分的智能判断。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Type Definitions（确保 Nuitka 兼容性）
class LLMOption(dict):
    """LLM 返回的选项结构（TypedDict 替代方案）。"""
    def __init__(
        self,
        label: str,
        action_type: str,
        payload: dict,
        trust_impact: int,
        style: str,
        disabled: bool,
        disabled_reason: Optional[str] = None,
        cost: int = 0,
        affordable: bool = True,
    ):
        super().__init__(
            label=label,
            action_type=action_type,
            payload=payload,
            trust_impact=trust_impact,
            style=style,
            disabled=disabled,
            disabled_reason=disabled_reason,
            cost=cost,
            affordable=affordable,
        )


class LLMResponse(dict):
    """LLM 返回的完整响应结构（v3.0: 添加 thought_trace, status, force_cease_fire）。"""
    def __init__(
        self,
        is_distracted: bool,
        confidence: int,
        analysis_summary: str,
        options: list[LLMOption],
        thought_trace: Optional[list[str]] = None,
        status: Optional[str] = None,
        force_cease_fire: Optional[bool] = None,
    ):
        super().__init__(
            is_distracted=is_distracted,
            confidence=confidence,
            analysis_summary=analysis_summary,
            options=options,
            thought_trace=thought_trace or [],
            status=status or "FOCUSED",
            force_cease_fire=force_cease_fire or False,
        )


# The Master System Prompt (v3.0: System 2 Thinking + Context Augmentation)
SYSTEM_PROMPT = """你是 FocusGuard v3.0 智能监督 Agent。你的职责是帮助用户保持专注，同时尊重用户的自主权。

## System 2 Thinking: 三步推理协议

**Step 1: Context Analysis（上下文分析）**
- 检查最近2小时的 session_blocks 状态
- 识别用户当前能量等级和专注密度
- 检查历史审计记录的一致性

**Step 2: Pattern Matching（模式匹配）**
- 匹配 Few-Shot 示例（见下文）
- 识别应用组合（浏览器+IDE=学习？浏览器+Steam=游戏？）
- 考虑时间因素（工作时间 vs 深夜）

**Step 3: Confidence Calibration（置信度校准）**
- 根据匹配的示例调整 confidence
- 高专注密度(>0.8) → 降低 confidence 10-20%
- 低专注密度(<0.4) → 提高 confidence 10-20%

## Few-Shot Exemplars（示例库）

**示例 1: 专注后休息（正确判断 - IGNORE）**
上下文:
- 用户专注工作 3 小时（focus_density=0.92）
- 刚打开 B站观看游戏视频
- 能量等级: Deep Flow (energy_level=0.3)
- 活跃应用: [code.exe, msedge.exe]

推理过程:
1. 用户已连续专注3小时，专注密度很高
2. 打开B站可能是疲劳休息，合理行为
3. 不需要干预

判断结果: is_distracted=false, confidence=30, DISMISS

---

**示例 2: 开始即分心（需干预 - INTERVENE）**
上下文:
- 用户刚开始工作 10 分钟
- focus_density=0.3，已切换 8 个应用
- 打开 Steam 浏览游戏
- 能量等级: High/Anxious (energy_level=0.8)

推理过程:
1. 用户刚开始工作就打开游戏
2. 专注密度极低，频繁切换应用
3. 明显分心行为，需要干预

判断结果: is_distracted=true, confidence=85, CLOSE_WINDOW

---

**示例 3: 精确关闭标签页（CLOSE_TAB）**
上下文:
- 用户在浏览器，有多个标签页
- 其中一个标签页是 Bilibili（分心）
- 其他标签页是技术文档（有用）

判断结果:
{{{{
  "is_distracted": true,
  "confidence": 75,
  "analysis_summary": "检测到 Bilibili 分心，但浏览器有其他有用标签页",
  "status": "DISTRACTED",
  "options": [
    {{{{
      "label": "关闭 Bilibili 标签页",
      "action_type": "CLOSE_TAB",
      "payload": {{"keyword": "Bilibili", "return_to_app": "VSCode"}},
      "trust_impact": 3,
      "style": "primary",
      "disabled": false,
      "disabled_reason": null,
      "cost": 5,
      "affordable": true
    }}}}
  ]
}}}}

---

**示例 5: AI 助手工作场景（应识别为工作）**
上下文:
- 用户在 Claude/ChatGPT/Gemini 对话
- 窗口标题不包含明确的编程关键词
- 用户目标是学习编程

推理过程:
1. AI助手是现代编程的重要工具（vibe coding）
2. 即使窗口标题不包含"代码"、"编程"等关键词，使用AI助手也应视为工作状态
3. 不需要干预

判断结果: is_distracted=false, confidence=20, DISMISS

---

**示例 6: Recovery 状态（用户回归工作）**
上下文:
- 最近 30 秒：用户在 Gemini（AI 助手），窗口标题包含"金融分析"
- 最近 5 分钟：用户在 Bilibili 观看视频（分心记录）
- 用户目标："学习量化交易"

推理过程:
1. 优先级检查：最近 30 秒显示用户在 Gemini
2. 窗口标题包含"金融分析"，与目标高度相关
3. 虽然 5 分钟前有分心记录，但当前已回归工作
4. 判定为 RECOVERY 状态，立即停止所有干预

判断结果:
{{{{
  "is_distracted": false,
  "confidence": 10,
  "analysis_summary": "用户已回归工作（Gemini - 金融分析），停止报警",
  "status": "RECOVERY",
  "force_cease_fire": true,
  "thought_trace": [
    "检查最近 30 秒：用户在 Gemini（AI 助手）",
    "窗口标题包含 '金融分析'，与目标相关",
    "虽然 5 分钟前有分心记录，但当前已回归工作",
    "判定为 RECOVERY，立即停止所有干预"
  ],
  "options": []
}}}}

---

## 当前上下文
- 用户目标：{goal}
- 专注货币余额：{balance} Coins
- 破产状态：{bankruptcy_status}
- 当前时间：{current_time}
{user_streak_info}
{user_context_info}

## 用户活动记录
【最近 30 秒】
{instant_log}

【最近 5 分钟趋势】
{short_trend}

【最近 20 分钟趋势】
{context_trend}

## 用户最近状态（Session Blocks - L2 数据）
{session_blocks_summary}

## 数据格式说明
- 活动记录按应用聚合显示，例如："msedge.exe (5 个窗口)"
- 同一应用打开多个窗口/标签页是正常学习行为
- 例如用户在浏览器中查阅 5 个学习资料，会显示为 "msedge.exe (5 个窗口)"
- "活动切换" 表示使用了多少个不同的应用，而非窗口数量

## 学习场景识别
以下应用组合通常表示学习状态，应该降低怀疑度：
- 浏览器（msedge.exe/chrome.exe）+ 代码编辑器 + 终端 = 正在开发
- 浏览器 + PDF 阅读器（wps.exe/acrobat.exe）+ 笔记软件 = 正在查资料
- Python/Node.js + 浏览器 + IDE = 正在编程学习
- 浏览器 + Office 办公软件 = 正在办公
- **AI助手单独使用** = 也可能是工作（vibe coding 是现代编程方式）
  - Claude, ChatGPT, Gemini, DeepSeek 等 AI 助手即使没有明确编程关键词，也应视为潜在工作状态
  - 除非明确是娱乐聊天（如"讲个笑话"、"推荐电影"），否则不要轻易判定为分心

## 优先级层次判断准则（Priority Hierarchy）

**Priority 0: Current Activity（当前活动 - 绝对最高优先级）**
- **首先检查【最近 10 秒】的当前窗口**
- **URL 验证优先于窗口标题验证**：
  * 如果 URL 包含 bilibili.com、youtube.com 等视频网站 → 确认为分心
  * 如果只是窗口标题包含"Bilibili"但 URL 不包含 bilibili.com → 不判断为分心
  * 例如：窗口标题"Bilibili - GitHub Copilot"的 URL 是 github.com，应视为工作
- **当前窗口优先于历史记录**：
  * 如果当前窗口标题包含编程/技术关键词 → 视为工作
  * 如果当前窗口是 AI 助手（Claude/ChatGPT/Gemini） → 视为工作（vibe coding）
  * 即使历史记录（30秒/5分钟）显示有分心记录，也要优先相信当前窗口
- **裁决**：忽略所有历史记录，只看当前窗口


**Priority 1: Instant Alignment（当下对齐 - 最高优先级）**
- 首先检查【最近 30 秒】的活动
- 如果当前窗口标题与目标在语义上高度相关：
  * 编程工具：VSCode, PyCharm, IntelliJ, Code
  * AI 助手：Gemini, ChatGPT, Claude, DeepSeek（标题包含工作关键词）
  * 文档工具：Notion, Obsidian, Markdown（标题包含技术/学习关键词）
  * 终端：Terminal, PowerShell, cmd
- **裁决**：忽略过去 5 分钟的任何分心记录
- **判断结果**: is_distracted=false, confidence=10, status="RECOVERY"
- **理由**: "User has returned to work context. Cease fire."

**Priority 2: Ambiguity Check（通用工具审查）**
- 如果当前是通用工具（Browser, AI Chat），检查窗口标题：
  * 标题是 "New Tab", "Home", "空白页" → 结合 Trust Score 判断
  * 标题包含编程/技术关键词 → 视为工作
  * 标题包含娱乐关键词 → 视为分心

**Priority 3: Historical Trend（历史惯性 - 最低优先级）**
- 只有在 Priority 1 和 2 无法确定时，才参考【最近 5 分钟】数据
- 用于识别持续的分心行为（如连续 10 分钟在娱乐网站）

## Recovery 状态识别

**定义**: 用户从分心状态回归工作

**判断条件**:
1. 【最近 30 秒】显示工作工具（VSCode, Gemini, Terminal 等）
2. 【最近 5 分钟】显示有分心记录（B站, YouTube 等）
3. 能量等级显示 "High" 或 "Anxious"（用户正在努力工作）

**输出格式**:
```json
{{{{
  "is_distracted": false,
  "confidence": 10,
  "analysis_summary": "用户已回归工作（Gemini - 金融分析），停止报警",
  "status": "RECOVERY",
  "force_cease_fire": true,
  "thought_trace": [
    "检查最近 30 秒：用户在 Gemini（AI 助手）",
    "窗口标题包含 '金融分析'，与目标相关",
    "虽然 5 分钟前有分心记录，但当前已回归工作",
    "判定为 RECOVERY，立即停止所有干预"
  ],
  "options": []
}}}}
```

**force_cease_fire 字段说明**:
- 如果为 true，前端立即关闭所有已存在的干预对话框
- 实现方式：发送信号给 InterventionDialog，调用 close()

## 传统判断准则（用于 Priority 3）
1. **优先考虑应用类型**，而非窗口数量
   - 如果看到浏览器有多个窗口，优先判断为"查阅资料"，而非"频繁切换"
   - 同一应用的多窗口不算分心

2. **活动切换次数容忍度**：
   - 活动切换 < 3 个应用：正常，不弹窗
   - 活动切换 3-5 个应用：轻微分心，置信度 60-70%
   - 活动切换 > 5 个应用：明显分心，置信度 > 80%

3. **学习场景特殊处理**：
   - 看到学习相关应用组合，降低怀疑度（-20%）
   - 看到娱乐应用（游戏、视频网站），增加怀疑度（+20%）

## 你的任务
1. 分析用户当前行为是否偏离目标（考虑学习场景）
2. 考虑货币余额调整判断严格程度：
   - 余额充足（> 100）：正常定价，鼓励专注挖矿
   - 余额偏低（< 50）：降低价格，给予更多自主空间
   - 破产状态（< 0）：启用破产保护，大幅降低价格
3. 结合用户历史洞察调整判断策略：
   - 疲劳时段：建议休息，减少干预
   - 高效时段：鼓励专注，适当严格
   - 惯性堕落：增加监督力度
4. 生成 3-5 个交互选项供用户选择，并为每个选项定价
5. **优先考虑学习场景**：如果判断为"查阅资料"，提供 DISMISS 或降低置信度

## 专注货币系统说明
- 用户每专注工作 1 分钟挖矿 1 Coin
- 购买休息选项需要支付货币
- 严格模式是自律行为，会奖励货币
- 破产保护：余额不足时自动降低价格

## 强制执行选项
FocusGuard 可以直接帮助您停止分心：
- **帮我关闭**：自动关闭当前分心窗口（温和关闭，允许保存）
- **最小化并稍后提醒**：最小化窗口，稍后继续提醒
- **阻止此应用**：阻止该应用运行一段时间（会立即终止现有实例）

## 输出要求
你必须且只能输出以下 JSON 格式，不要包含任何其他文字：

```json
{{
  "is_distracted": boolean,
  "confidence": number (0-100),
  "analysis_summary": "一句话分析，不超过 30 字",
  "status": "FOCUSED" | "DISTRACTED" | "RECOVERY",
  "force_cease_fire": boolean,
  "thought_trace": ["推理步骤1", "推理步骤2", "推理步骤3"],
  "options": [
    {{
      "label": "按钮文字",
      "action_type": "SNOOZE" | "DISMISS" | "WHITELIST_TEMP" | "STRICT_MODE" | "CLOSE_WINDOW" | "MINIMIZE_WINDOW" | "BLOCK_APP" | "CLOSE_TAB",
      "payload": {{}},
      "trust_impact": number,
      "style": "normal" | "warning" | "primary",
      "disabled": boolean,
      "disabled_reason": "string 或 null",
      "cost": number,
      "affordable": boolean
    }}
  ]
}}
```

**字段说明**:
- `status`: 当前状态
  - "FOCUSED": 专注中（默认）
  - "DISTRACTED": 分心中
  - "RECOVERY": 用户已回归工作（立即停止干预）
- `force_cease_fire`: 是否强制关闭所有干预对话框（仅在 status="RECOVERY" 时为 true）

## 动作类型说明

**重要**: analysis_summary 必须明确指出是哪个网站/标签页，例如："检测到Bilibili娱乐视频"而不是"检测到娱乐网页"

1. **CLOSE_TAB**：关闭当前分心标签页（cost=5，仅适用于浏览器，精确关闭单个标签页）
   - **必须包含字段**: payload 中必须包含 "keyword" 字段（从窗口标题或URL中提取的关键词）
   - **示例**: {{"label": "关闭 Bilibili 标签页", "action_type": "CLOSE_TAB", "payload": {{"keyword": "Bilibili", "return_to_app": "VSCode"}}, "cost": 5}}
   - keyword 必须是能识别该标签页的唯一词（如 "Bilibili", "YouTube", "知乎"）

2. **CLOSE_WINDOW**：关闭整个应用窗口（cost=5，适用于非浏览器或需要关闭整个应用）
3. **MINIMIZE_WINDOW**：最小化窗口并稍后提醒（cost=2，温和方式）
4. **SNOOZE**：暂停监控 X 分钟（cost=5-10，按时长定价）
5. **DISMISS**：关闭对话框，不操作（cost=0，误报或学习时使用）
6. **WHITELIST_TEMP**：临时加入白名单（cost=20，仅当余额充足时可用）
7. **STRICT_MODE**：进入高频监控（cost=-10，奖励自律行为）
8. **BLOCK_APP**：阻止应用运行（cost=15，严厉措施）

## 注意事项
- **对于浏览器分心（Bilibili/YouTube等），优先使用 CLOSE_TAB 而不是 CLOSE_WINDOW**
- CLOSE_TAB 会精确关闭单个标签页，保留其他有用的标签页
- CLOSE_WINDOW 会关闭整个浏览器窗口（包括所有标签页）
- 如果用户在浏览器中有多个标签页（部分有用、部分分心），使用 CLOSE_TAB
- cost：该选项的价格（Coins）。强制执行选项通常 5-15 Coins
- affordable：用户余额是否足够支付该选项
- 破产状态下，大幅降低价格或提供免费选项（如 DISMISS）
- options 数组必须包含 3-5 个选项
- trust_impact 范围建议 -5 到 +5（仅用于记录，不影响货币）
- **thought_trace**: 必须提供推理过程，按照"三步推理协议"输出你的思考步骤
- **关键**：对于学习场景（浏览器多窗口 + 代码编辑器），优先提供 DISMISS，降低置信度
- 对于明显分心行为（游戏、视频网站且无其他应用），提供 CLOSE_WINDOW 选项"""


class LLMService:
    """
    LLM 服务类 - 处理 AI 判断和选项生成。

    功能：
    - 构建 Prompt（注入活动摘要、信任分、目标）
    - 调用 OpenAI 兼容 API
    - 解析 JSON 响应
    - 指数退避重试机制
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: int = 30,
    ):
        """
        初始化 LLM 服务。

        Args:
            api_key: API 密钥（腾讯混元格式：SecretId:SecretKey）
            base_url: API 基础 URL（默认 OpenAI，可替换为腾讯混元等）
            model: 模型名称
            timeout: 请求超时（秒）
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

        # 检测是否为腾讯混元（格式：SecretId:SecretKey）
        self._is_hunyuan = ":" in api_key
        if self._is_hunyuan:
            self._secret_id, self._secret_key = api_key.split(":", 1)
            # 腾讯混元使用不同的 endpoint
            self._hunyuan_endpoint = "hunyuan.tencentcloudapi.com"
            logger.info(f"LLMService initialized with Hunyuan model: {model}")
        else:
            logger.info(f"LLMService initialized with model: {model}")

    def _sign_hunyuan(
        self,
        params: dict,
    ) -> tuple[str, str, str, str]:
        """
        生成腾讯混元 API 签名（TC3-HMAC-SHA256）。

        按照腾讯云官方文档实现：
        https://cloud.tencent.com/document/product/213/41621

        Args:
            params: 请求参数

        Returns:
            tuple: (authorization_header, timestamp, date, body_str)
        """
        # 公共参数
        service = "hunyuan"
        version = "2023-09-01"
        algorithm = "TC3-HMAC-SHA256"
        region = "ap-guangzhou"  # 混元API使用的地域

        # 当前时间戳（UTC秒级）
        timestamp = int(time.time())
        # 使用UTC时间
        import time as time_module
        date = time_module.strftime("%Y-%m-%d", time_module.gmtime(timestamp))

        # 构造请求体（必须无空格、键排序，ensure_ascii=False处理中文）
        body_str = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        body = body_str

        # 1. 拼接规范请求串（Canonical Request）
        # 注意：canonical_headers 只包含 content-type 和 host，且按字母序排列
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""

        # 请求头按字母序排列：content-type 在前，host 在后
        canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{self._hunyuan_endpoint}\n"
        signed_headers = "content-type;host"

        hashed_request_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_request_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_request_payload}"
        )

        # 2. 拼接待签名字符串（String to Sign）
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()
        string_to_sign = (
            f"{algorithm}\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical_request}"
        )

        # 3. 计算签名（Signature）
        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac_sha256(
            ("TC3" + self._secret_key).encode("utf-8"), date
        )
        secret_service = _hmac_sha256(secret_date, service)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # 4. 拼接 Authorization
        authorization = (
            f"{algorithm} "
            f"Credential={self._secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return authorization, str(timestamp), date, body_str, region

    def _get_bankruptcy_status(self, balance: int) -> str:
        """
        根据余额返回破产状态描述。

        Args:
            balance: 当前余额（Coins）

        Returns:
            str: 状态描述
        """
        if balance < 0:
            return "已破产（启用保护）"
        elif balance < 50:
            return "余额偏低"
        elif balance > 100:
            return "余额充足"
        else:
            return "正常"

    def _format_session_blocks(self, blocks: Optional[list[dict]]) -> str:
        """
        格式化 session_blocks 为 LLM 可读的上下文（v3.0）。

        Args:
            blocks: session_blocks 列表

        Returns:
            str: 格式化的 session_blocks 上下文
        """
        if not blocks:
            return "（暂无历史数据）"

        # 计算汇总指标
        total_blocks = len(blocks)
        avg_focus_density = sum(b.get("focus_density", 0.0) for b in blocks) / max(1, total_blocks)
        avg_energy_level = sum(b.get("energy_level", 0.0) for b in blocks) / max(1, total_blocks)
        total_distractions = sum(b.get("distraction_count", 0) for b in blocks)

        # 格式化摘要
        summary = f"""最近 {total_blocks} 个 Session Block（最近 2 小时）:
- 平均专注密度: {avg_focus_density:.2%}
- 平均能量等级: {avg_energy_level:.2f} (0=Deep Flow, 1=High Activity)
- 总分心次数: {total_distractions} 次
- 活跃应用: """

        # 收集所有主要应用
        import json
        all_apps = []
        for block in blocks:
            try:
                dominant_apps_str = block.get("dominant_apps", "[]")
                if isinstance(dominant_apps_str, str):
                    dominant_apps = json.loads(dominant_apps_str)
                else:
                    dominant_apps = dominant_apps_str
                all_apps.extend(dominant_apps)
            except (json.JSONDecodeError, TypeError):
                continue

        # 统计应用频率并取前5
        from collections import Counter
        app_counter = Counter(all_apps)
        top_apps = [app for app, _ in app_counter.most_common(5)]

        if top_apps:
            summary += ", ".join(top_apps)
        else:
            summary += "无"

        # 添加最近的 block 详情
        summary += "\n\n最近的 Session Block 详情:"
        for block in blocks[:3]:  # 只显示最近3个
            start_time = block.get("start_time", "")[11:16]  # HH:MM
            focus = block.get("focus_density", 0.0)
            energy = block.get("energy_level", 0.0)
            summary += f"\n  [{start_time}] 专注度={focus:.0%}, 能量={energy:.2f}"

        return summary

    def _build_prompt(
        self,
        instant_log: list[dict],
        short_trend: list[dict],
        context_trend: list[dict],
        trust_score: int,
        goal: str,
        balance: int = 100,
        user_streak: Optional[dict] = None,
        user_context: Optional[dict] = None,
        session_blocks: Optional[list[dict]] = None,
    ) -> str:
        """
        构建完整的 Prompt（v3.0: 添加 session_blocks 上下文注入）。

        Args:
            instant_log: 最近 30 秒活动
            short_trend: 最近 5 分钟活动
            context_trend: 最近 20 分钟活动
            trust_score: 信任分（已废弃，保留用于向后兼容）
            goal: 用户目标
            balance: 当前货币余额（Coins）
            user_streak: 用户连续性数据 {"consecutive_distractions": int, "consecutive_focus": int}
            user_context: 用户洞察数据（来自 DataTransformer）
            session_blocks: 最近2小时的 session_blocks 数据（L2 压缩数据）

        Returns:
            str: 完整的 Prompt
        """
        # 格式化活动日志
        def format_log(logs: list[dict]) -> str:
            """格式化活动日志为应用级聚合格式。"""
            if not logs:
                return "（无活动）"

            # 统计应用数量
            app_count = len(logs)

            # 格式化每个应用的活动
            formatted = []
            for row in logs:
                app_name = row.get('app_name', 'N/A')
                window_count = row.get('window_count', 0)
                windows = row.get('windows', 'N/A')

                # 格式：msedge.exe (5 个窗口): Gemini, DeepSeek, ...
                formatted.append(f"- {app_name} ({window_count} 个窗口): {windows}")

            # 添加应用切换统计
            result = "\n".join(formatted)
            result += f"\n\n活动切换: {app_count} 个应用"

            return result

        # 格式化用户连续性信息
        streak_info = ""
        if user_streak:
            consecutive_focus = user_streak.get("consecutive_focus", 0)
            consecutive_distractions = user_streak.get("consecutive_distractions", 0)

            if consecutive_focus > 0:
                streak_info = f"- 连续专注：{consecutive_focus} 次检测（享受折扣）\n"
            elif consecutive_distractions > 0:
                streak_info = f"- 连续分心：{consecutive_distractions} 次检测（价格上涨）\n"
            else:
                streak_info = ""

        # 格式化用户上下文信息（洞察数据）
        context_info = ""
        if user_context and user_context.get("has_insights"):
            insights = user_context.get("insights", {})

            context_parts = []
            if "peak_hours_summary" in insights:
                context_parts.append(f"- {insights['peak_hours_summary']}")

            if "fatigue_summary" in insights:
                context_parts.append(f"- {insights['fatigue_summary']}")

            # 添加应用偏好信息
            if "APP_PREFERENCES" in insights:
                app_data = insights["APP_PREFERENCES"]["data"]
                top_app = app_data.get("description", "")
                if top_app:
                    context_parts.append(f"- {top_app}")

            if context_parts:
                context_info = "\n".join(context_parts) + "\n"

        # 格式化 session_blocks（v3.0: L2 数据上下文注入）
        session_blocks_summary = self._format_session_blocks(session_blocks)

        return SYSTEM_PROMPT.format(
            goal=goal or "未设置目标",
            balance=balance,
            bankruptcy_status=self._get_bankruptcy_status(balance),
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_streak_info=streak_info,
            user_context_info=context_info,
            instant_log=format_log(instant_log),
            short_trend=format_log(short_trend),
            context_trend=format_log(context_trend),
            session_blocks_summary=session_blocks_summary,
        )

    def _call_api(self, prompt: str) -> str:
        """
        调用 LLM API（支持 OpenAI 和腾讯混元）。

        Args:
            prompt: 完整的 Prompt

        Returns:
            str: API 返回的原始文本

        Raises:
            requests.RequestException: 网络错误
            requests.Timeout: 超时
        """
        if self._is_hunyuan:
            # 腾讯混元 API 调用
            return self._call_hunyuan_api(prompt)
        else:
            # OpenAI 兼容 API 调用
            return self._call_openai_api(prompt)

    def _call_openai_api(self, prompt: str) -> str:
        """
        调用 OpenAI 兼容 API。

        Args:
            prompt: 完整的 Prompt

        Returns:
            str: API 返回的原始文本
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": prompt},  # 智谱AI要求以user角色开头
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        url = f"{self._base_url}/chat/completions"

        # Debug: Log request details
        logger.info(f"[DEBUG] Sending request to: {url}")
        logger.info(f"[DEBUG] Model: {self._model}")
        logger.info(f"[DEBUG] Prompt length: {len(prompt)} characters")
        logger.info(f"[DEBUG] Payload keys: {list(payload.keys())}")

        response = requests.post(url, json=payload, headers=headers, timeout=self._timeout)

        # Debug: Log response status
        logger.info(f"[DEBUG] Response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"[DEBUG] Response body: {response.text[:500]}")

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _call_hunyuan_api(self, prompt: str) -> str:
        """
        调用腾讯混元 API。

        Args:
            prompt: 完整的 Prompt

        Returns:
            str: API 返回的原始文本
        """
        # 构造请求参数（腾讯混元格式，键按字母顺序）
        # 注意：混元API使用 "user" 和 "assistant" 角色，不是 "system"
        params = {
            "Messages": [
                {"Role": "user", "Content": prompt},
            ],
            "Model": self._model,
            "Temperature": 0.7,
            "TopP": 1.0,
        }

        # 生成签名（同时获取body_str和region确保签名和请求体一致）
        authorization, timestamp, date, body_str, region = self._sign_hunyuan(params)

        # 构造请求头（腾讯云 API 需要特定的 header）
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self._hunyuan_endpoint,
            "X-TC-Action": "ChatCompletions",
            "X-TC-Version": "2023-09-01",
            "X-TC-Timestamp": timestamp,
            "X-TC-Region": region,
        }

        # 发送请求
        url = f"https://{self._hunyuan_endpoint}/"

        response = requests.post(
            url,
            data=body_str.encode("utf-8"),
            headers=headers,
            timeout=self._timeout
        )
        response.raise_for_status()

        # 先读取文本内容，避免 content type 问题
        text = response.text

        # 尝试解析 JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Hunyuan API response as JSON: {e}")
            logger.error(f"Response text: {text[:1000]}")
            raise

        # 记录完整响应结构用于调试
        logger.debug(f"Hunyuan API response structure: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")

        # 提取回复内容
        if "Response" in data:
            response_data = data["Response"]
            # 检查是否有错误
            if "Error" in response_data:
                error_msg = response_data["Error"].get("Message", "Unknown error")
                error_code = response_data["Error"].get("Code", "Unknown")
                raise ValueError(f"Hunyuan API error [{error_code}]: {error_msg}")

            # 尝试提取 Choices
            if "Choices" not in response_data:
                logger.error(f"Response missing 'Choices': {response_data}")
                raise ValueError(f"Hunyuan API response missing 'Choices' key")

            return response_data["Choices"][0]["Message"]["Content"]
        else:
            raise ValueError(f"Unexpected response format: {data}")

    def _parse_json_response(self, response_text: str) -> LLMResponse:
        """
        解析 LLM 返回的 JSON 响应。

        Args:
            response_text: API 返回的原始文本

        Returns:
            LLMResponse: 解析后的响应对象

        Raises:
            json.JSONDecodeError: JSON 解析失败
            KeyError: 缺少必需字段
        """
        # 尝试提取 JSON（有时 LLM 会添加 markdown 代码块）
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]  # 移除 ```json
        if text.startswith("```"):
            text = text[3:]  # 移除 ```
        if text.endswith("```"):
            text = text[:-3]  # 移除结尾的 ```

        text = text.strip()

        # 解析 JSON
        data = json.loads(text)

        # 验证必需字段
        required_fields = ["is_distracted", "confidence", "analysis_summary", "options"]
        for field in required_fields:
            if field not in data:
                raise KeyError(f"Missing required field: {field}")

        # 构建选项列表
        options = []
        for opt in data["options"]:
            option = LLMOption(
                label=opt["label"],
                action_type=opt["action_type"],
                payload=opt.get("payload", {}),
                trust_impact=opt.get("trust_impact", 0),
                style=opt.get("style", "normal"),
                disabled=opt.get("disabled", False),
                disabled_reason=opt.get("disabled_reason"),
                cost=opt.get("cost", 0),
                affordable=opt.get("affordable", True),
            )
            options.append(option)

        return LLMResponse(
            is_distracted=data["is_distracted"],
            confidence=data["confidence"],
            analysis_summary=data["analysis_summary"],
            options=options,
            thought_trace=data.get("thought_trace", []),
            status=data.get("status", "FOCUSED"),
            force_cease_fire=data.get("force_cease_fire", False),
        )

    def analyze_activity(
        self,
        instant_log: list[dict],
        short_trend: list[dict],
        context_trend: list[dict],
        trust_score: int,
        goal: str,
        balance: int = 100,
        user_streak: Optional[dict] = None,
        user_context: Optional[dict] = None,
        session_blocks: Optional[list[dict]] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> Optional[LLMResponse]:
        """
        分析用户活动（带重试机制）（v3.0: 添加 session_blocks 上下文）。

        Args:
            instant_log: 最近 30 秒活动
            short_trend: 最近 5 分钟活动
            context_trend: 最近 20 分钟活动
            trust_score: 信任分（已废弃，保留用于向后兼容）
            goal: 用户目标
            balance: 当前货币余额（Coins）
            user_streak: 用户连续性数据
            user_context: 用户洞察数据（来自 DataTransformer）
            session_blocks: 最近2小时的 session_blocks 数据（L2 压缩数据）
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒），用于指数退避

        Returns:
            Optional[LLMResponse]: LLM 判断结果，失败时返回 None
        """
        prompt = self._build_prompt(
            instant_log, short_trend, context_trend, trust_score, goal,
            balance=balance, user_streak=user_streak, user_context=user_context,
            session_blocks=session_blocks,
        )

        for attempt in range(max_retries):
            try:
                response_text = self._call_api(prompt)
                return self._parse_json_response(response_text)

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    f"JSON parse failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 指数退避: 1s, 2s, 4s
                    time.sleep(delay)

            except (requests.RequestException, requests.Timeout) as e:
                logger.error(
                    f"Network error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)

        logger.error("All LLM retry attempts failed")
        return None
