/**
 * 腾讯混元LLM适配器
 */

import {
  ILLMAdapter,
  ChatMessage,
  ChatResponse,
  ChatChunk,
  ChatOptions,
  JudgmentResult,
  DialogResult
} from './adapter';

// 导入腾讯云SDK
// eslint-disable-next-line @typescript-eslint/no-var-requires
const tencentcloud = require('tencentcloud-sdk-nodejs');

/**
 * 腾讯混元适配器配置
 */
export interface HunyuanConfig {
  /** 腾讯云SecretId */
  secretId: string;
  /** 腾讯云SecretKey */
  secretKey: string;
  /** API端点（可选） */
  endpoint?: string;
  /** 区域（可选） */
  region?: string;
}

/**
 * 腾讯混元适配器实现
 */
export class HunyuanAdapter implements ILLMAdapter {
  private client: any;
  private config: HunyuanConfig;

  // 支持的模型列表
  private static readonly MODELS = [
    'hunyuan-lite',    // 轻量级模型（免费）
    'hunyuan-standard', // 标准模型
    'hunyuan-pro',     // 专业模型
    'hunyuan-embedding' // 嵌入模型
  ];

  constructor(config: HunyuanConfig) {
    this.config = config;

    // 导入混元服务客户端
    const HunyuanClient = tencentcloud.hunyuan.v20230901.Client;

    // 初始化腾讯云SDK客户端
    const credential = new tencentcloud.common.Credential(
      config.secretId,
      config.secretKey
    );

    const clientConfig = {
      credential,
      region: config.region || 'ap-guangzhou',
      profile: {
        httpProfile: {
          endpoint: config.endpoint || 'hunyuan.tencentcloudapi.com'
        }
      }
    };

    this.client = new HunyuanClient(clientConfig);
  }

  getName(): string {
    return '腾讯混元';
  }

  getModels(): string[] {
    return HunyuanAdapter.MODELS;
  }

  async chat(messages: ChatMessage[], options?: ChatOptions): Promise<ChatResponse> {
    const model = options?.model || 'hunyuan-lite';

    try {
      // 转换消息格式
      const sdkMessages = messages.map(msg => ({
        Role: msg.role.toUpperCase(),
        Content: msg.content
      }));

      // 构建请求参数
      const params = {
        Model: model,
        Messages: sdkMessages,
        Temperature: options?.temperature ?? 0.7,
        TopP: options?.topP ?? 0.9,
        Stream: false
      };

      // 调用API
      const response = await this.client.ChatCompletions(params);

      return {
        content: response.Response.Choices[0].Message.Content,
        model,
        usage: {
          promptTokens: response.Response.Usage.PromptTokens,
          completionTokens: response.Response.Usage.CompletionTokens,
          totalTokens: response.Response.Usage.TotalTokens
        },
        finishReason: response.Response.Choices[0].FinishReason?.toLowerCase() as any
      };
    } catch (error) {
      console.error('腾讯混元API调用失败:', error);
      throw new Error(`腾讯混元API调用失败: ${error}`);
    }
  }

  async *streamChat(
    messages: ChatMessage[],
    options?: ChatOptions,
    onChunk?: (chunk: ChatChunk) => void
  ): AsyncIterable<ChatChunk> {
    const model = options?.model || 'hunyuan-lite';

    try {
      const sdkMessages = messages.map(msg => ({
        Role: msg.role.toUpperCase(),
        Content: msg.content
      }));

      const params = {
        Model: model,
        Messages: sdkMessages,
        Temperature: options?.temperature ?? 0.7,
        TopP: options?.topP ?? 0.9,
        Stream: true
      };

      // 调用流式API
      const response = await this.client.ChatCompletions(params);

      // 处理流式响应
      // 注意：实际实现需要根据SDK的流式响应处理方式调整
      for await (const chunk of response) {
        const content = chunk.Choices?.[0]?.Delta?.Content || '';
        const done = chunk.Choices?.[0]?.FinishReason === 'stop';

        const chatChunk: ChatChunk = {
          content,
          done
        };

        if (onChunk) {
          onChunk(chatChunk);
        }

        yield chatChunk;

        if (done) {
          break;
        }
      }
    } catch (error) {
      console.error('腾讯混元流式API调用失败:', error);
      throw new Error(`腾讯混元流式API调用失败: ${error}`);
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      const response = await this.chat([
        {
          role: 'user',
          content: '测试连接'
        }
      ]);

      return response.content.length > 0;
    } catch {
      return false;
    }
  }

  /**
   * 判断活动是否分心
   */
  async evaluateActivity(
    activity: any,
    focusGoals: any[]
  ): Promise<JudgmentResult> {
    const systemPrompt = this.buildSystemPrompt(focusGoals);

    const userPrompt = this.buildEvaluationPrompt(activity);

    try {
      const response = await this.chat([
        {
          role: 'system',
          content: systemPrompt
        },
        {
          role: 'user',
          content: userPrompt
        }
      ]);

      // 解析AI响应
      return this.parseJudgmentResponse(response.content);
    } catch (error) {
      console.error('AI评估失败:', error);
      // 返回默认结果
      return {
        isDistracted: false,
        confidence: 0,
        action: 'allow',
        reason: 'AI评估失败，默认放行'
      };
    }
  }

  /**
   * 与用户对话
   */
  async converse(
    conversationHistory: ChatMessage[],
    activity: any,
    focusGoals: any[]
  ): Promise<DialogResult> {
    const systemPrompt = this.buildDialogPrompt(focusGoals);

    try {
      const response = await this.chat(
        [
          {
            role: 'system',
            content: systemPrompt
          },
          ...conversationHistory
        ],
        {
          temperature: 0.8, // 对话时使用更高的温度
          maxTokens: 500
        }
      );

      return this.parseDialogResponse(response.content);
    } catch (error) {
      console.error('AI对话失败:', error);
      return {
        isFinal: true,
        decision: 'allow',
        message: '抱歉，AI服务出现错误，允许您继续访问'
      };
    }
  }

  /**
   * 构建系统提示词（评估模式）
   */
  private buildSystemPrompt(focusGoals: any[]): string {
    const goalsText = focusGoals
      .map(g => `- ${g.name}: ${g.description}`)
      .join('\n');

    return `你是一个专注力助手，帮助用户保持专注。

用户的专注目标：
${goalsText || '用户没有设置明确的专注目标'}

你的任务是分析用户的活动是否与专注目标冲突。

响应格式（JSON）：
{
  "is_distracted": true/false,
  "confidence": 0.0-1.0,
  "distraction_level": 1-10,
  "action": "allow" | "warn" | "block" | "dialog",
  "reason": "简要说明判断原因",
  "message_to_user": "对用户说的话",
  "requires_dialog": true/false,
  "questions": ["问题1", "问题2"]
}

判断原则：
1. 考虑用户的长期目标
2. 考虑当前活动是否必要（工作相关、休息、学习等）
3. 适当的灵活性（允许必要的休息）
4. 如果不确定，选择对话而不是强制阻止`;
  }

  /**
   * 构建评估提示词
   */
  private buildEvaluationPrompt(activity: any): string {
    const activityText = activity.type === 'browser'
      ? `正在访问网站：${activity.data.url}\n页面标题：${activity.data.title}`
      : `正在使用应用：${activity.data.appName}\n窗口标题：${activity.data.windowTitle}`;

    return `请分析以下用户活动：

${activityText}

请判断这是否是分心活动，并决定应该采取什么行动。`;
  }

  /**
   * 构建对话模式提示词
   */
  private buildDialogPrompt(focusGoals: any[]): string {
    const goalsText = focusGoals
      .map(g => `- ${g.name}: ${g.description}`)
      .join('\n');

    return `你是一个友善但坚定的专注力助手。用户正在访问可能分散注意力的内容。

用户的专注目标：
${goalsText || '用户没有设置明确的专注目标'}

你的任务是：
1. 了解用户的真实意图
2. 如果用户有充分的理由，允许他们继续
3. 如果理由不充分，友善地劝说他们回到专注任务
4. 最多进行3-5轮对话

响应格式（JSON）：
{
  "is_final": true/false,
  "decision": "allow" | "block",
  "message": "对用户说的话",
  "questions": ["继续问的问题"],
  "learned_preference": "学到的用户偏好"
}

保持友善、理解和专业的语气。`;
  }

  /**
   * 解析判断响应
   */
  private parseJudgmentResponse(content: string): JudgmentResult {
    try {
      // 尝试提取JSON
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('未找到JSON响应');
      }

      const result = JSON.parse(jsonMatch[0]);

      return {
        isDistracted: result.is_distracted || false,
        confidence: result.confidence || 0,
        distractionLevel: result.distraction_level,
        action: result.action || 'allow',
        reason: result.reason || '',
        messageToUser: result.message_to_user,
        requiresDialog: result.requires_dialog || false,
        questions: result.questions || []
      };
    } catch (error) {
      console.error('解析AI响应失败:', error);
      // 返回保守的默认值
      return {
        isDistracted: false,
        confidence: 0,
        action: 'allow',
        reason: '无法解析AI响应'
      };
    }
  }

  /**
   * 解析对话响应
   */
  private parseDialogResponse(content: string): DialogResult {
    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('未找到JSON响应');
      }

      const result = JSON.parse(jsonMatch[0]);

      return {
        isFinal: result.is_final !== false, // 默认为最终决定
        decision: result.decision || 'allow',
        message: result.message || content,
        questions: result.questions || [],
        learnedPreference: result.learned_preference
      };
    } catch (error) {
      console.error('解析对话响应失败:', error);
      return {
        isFinal: true,
        decision: 'allow',
        message: content
      };
    }
  }
}

/**
 * 创建腾讯混元适配器实例
 */
export function createHunyuanAdapter(config: HunyuanConfig): HunyuanAdapter {
  return new HunyuanAdapter(config);
}
