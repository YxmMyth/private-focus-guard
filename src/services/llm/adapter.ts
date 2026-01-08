/**
 * LLM适配器接口定义
 */

/**
 * 聊天消息角色
 */
export type MessageRole = 'system' | 'user' | 'assistant';

/**
 * 聊天消息
 */
export interface ChatMessage {
  role: MessageRole;
  content: string;
}

/**
 * 聊天响应
 */
export interface ChatResponse {
  /** 响应内容 */
  content: string;
  /** 使用的模型 */
  model: string;
  /** Token使用情况 */
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  /** 是否结束 */
  finishReason?: 'stop' | 'length' | 'content_filter';
}

/**
 * 流式响应块
 */
export interface ChatChunk {
  /** 内容片段 */
  content: string;
  /** 是否结束 */
  done: boolean;
}

/**
 * LLM适配器接口
 */
export interface ILLMAdapter {
  /**
   * 获取适配器名称
   */
  getName(): string;

  /**
   * 获取支持的模型列表
   */
  getModels(): string[];

  /**
   * 聊天接口（非流式）
   */
  chat(messages: ChatMessage[], options?: ChatOptions): Promise<ChatResponse>;

  /**
   * 聊天接口（流式）
   */
  streamChat(
    messages: ChatMessage[],
    options?: ChatOptions,
    onChunk?: (chunk: ChatChunk) => void
  ): AsyncIterable<ChatChunk>;

  /**
   * 测试连接
   */
  testConnection(): Promise<boolean>;
}

/**
 * 聊天选项
 */
export interface ChatOptions {
  /** 模型名称 */
  model?: string;
  /** 温度 (0-1) */
  temperature?: number;
  /** 最大Token数 */
  maxTokens?: number;
  /** Top-P采样 */
  topP?: number;
  /** 停止序列 */
  stopSequences?: string[];
}

/**
 * 判断结果
 */
export interface JudgmentResult {
  /** 是否分心 */
  isDistracted: boolean;
  /** 置信度 (0-1) */
  confidence: number;
  /** 分心等级 (1-10) */
  distractionLevel?: number;
  /** 动作 */
  action: 'allow' | 'warn' | 'block' | 'dialog';
  /** 原因说明 */
  reason: string;
  /** 给用户的消息 */
  messageToUser?: string;
  /** 是否需要对话 */
  requiresDialog?: boolean;
  /** 需要询问的问题 */
  questions?: string[];
}

/**
 * 对话结果
 */
export interface DialogResult {
  /** 是否最终决定 */
  isFinal: boolean;
  /** 决定 */
  decision: 'allow' | 'block';
  /** 消息 */
  message: string;
  /** 需要继续问的问题 */
  questions?: string[];
  /** 学到的用户偏好 */
  learnedPreference?: string;
}
