/**
 * 全局类型声明
 *
 * 这个文件为渲染进程提供 TypeScript 类型支持
 * 使得 window.electronAPI 有完整的类型检查和自动补全
 */

// 类型定义（不导入，直接定义以避免循环依赖）
type Activity = {
  id?: number;
  type: 'browser' | 'application' | 'system';
  timestamp: number;
  duration?: number;
  data: any;
};

type JudgmentResult = {
  isDistracted: boolean;
  confidence: number;
  action: 'allow' | 'block' | 'warn';
  reason?: string;
};

/**
 * 监控服务接口
 */
interface MonitorAPI {
  /**
   * 启动监控服务
   * @param config 监控配置（可选）
   * @returns Promise<{ success: boolean }>
   */
  start: (config?: {
    interval?: number;
    enableWindows?: boolean;
    enableChrome?: boolean;
  }) => Promise<{ success: boolean }>;

  /**
   * 停止监控服务
   * @returns Promise<{ success: boolean }>
   */
  stop: () => Promise<{ success: boolean }>;

  /**
   * 获取当前活动
   * @returns Promise<Activity | null>
   */
  getCurrentActivity: () => Promise<Activity | null>;
}

/**
 * AI 判断接口
 */
interface AIAPI {
  /**
   * 评估活动是否分心
   * @param activity 要评估的活动对象
   * @returns Promise<JudgmentResult> 判断结果
   */
  evaluate: (activity: Activity) => Promise<JudgmentResult>;
}

/**
 * 配置管理接口
 */
interface ConfigAPI {
  /**
   * 获取配置值
   * @param key 配置键
   * @returns Promise<string | null> 配置值
   */
  get: (key: string) => Promise<string | null>;

  /**
   * 设置配置值
   * @param key 配置键
   * @param value 配置值
   * @returns Promise<boolean> 是否成功
   */
  set: (key: string, value: string) => Promise<boolean>;

  /**
   * 获取所有配置
   * @returns Promise<Record<string, string>> 所有配置的键值对
   */
  getAll: () => Promise<Record<string, string>>;
}

/**
 * 窗口控制接口
 */
interface WindowAPI {
  /**
   * 最小化窗口
   * @returns Promise<boolean> 是否成功
   */
  minimize: () => Promise<boolean>;

  /**
   * 最大化/还原窗口
   * @returns Promise<boolean> 是否成功
   */
  maximize: () => Promise<boolean>;

  /**
   * 关闭窗口
   * @returns Promise<boolean> 是否成功
   */
  close: () => Promise<boolean>;
}

/**
 * 活动记录接口
 */
interface ActivityAPI {
  /**
   * 插入活动记录
   * @param activity 活动对象
   * @returns Promise<number> 活动记录 ID
   */
  insert: (activity: Activity) => Promise<number>;

  /**
   * 查询活动记录
   * @param options 查询选项
   * @returns Promise<Activity[]> 活动记录数组
   */
  query: (options: {
    startTime?: number;
    endTime?: number;
    type?: string;
    limit?: number;
    offset?: number;
  }) => Promise<Activity[]>;

  /**
   * 获取最近的活动记录
   * @param limit 限制数量（默认 10）
   * @returns Promise<Activity[]> 最近的活动记录
   */
  recent: (limit?: number) => Promise<Activity[]>;
}

/**
 * 数据库操作接口
 */
interface DatabaseAPI {
  /**
   * 获取数据库统计信息
   * @returns Promise<DbStats> 统计信息
   */
  getStats: () => Promise<{
    totalActivities: number;
    browserActivities: number;
    applicationActivities: number;
    systemActivities: number;
    distractionCount: number;
    databaseSize: number;
  }>;

  /**
   * 清空所有数据
   * @returns Promise<boolean> 是否成功
   */
  clearAll: () => Promise<boolean>;
}

/**
 * 对话框控制接口
 */
interface DialogAPI {
  /**
   * 显示干预对话框
   * @param data 对话框数据
   * @returns Promise<{ success: boolean }>
   */
  showIntervention: (data: {
    activity: Activity;
    message: string;
  }) => Promise<{ success: boolean }>;

  /**
   * 关闭干预对话框
   * @returns Promise<{ success: boolean }>
   */
  closeIntervention: () => Promise<{ success: boolean }>;
}

/**
 * 事件监听接口
 */
interface EventListenerAPI {
  /**
   * 监听主进程发送的事件
   * @param channel 事件名称
   * @param callback 回调函数
   */
  on: (channel: string, callback: (...args: any[]) => void) => void;

  /**
   * 移除事件监听
   * @param channel 事件名称
   * @param callback 回调函数
   */
  off: (channel: string, callback: (...args: any[]) => void) => void;
}

/**
 * 暴露给渲染进程的完整 ElectronAPI 接口
 */
interface ElectronAPI {
  /** 监控服务 */
  monitor: MonitorAPI;

  /** AI 判断 */
  ai: AIAPI;

  /** 配置管理 */
  config: ConfigAPI;

  /** 窗口控制 */
  window: WindowAPI;

  /** 活动记录 */
  activity: ActivityAPI;

  /** 数据库操作 */
  db: DatabaseAPI;

  /** 对话框控制 */
  dialog: DialogAPI;

  /** 事件监听 */
  on: EventListenerAPI['on'];
  off: EventListenerAPI['off'];
}

/**
 * 扩展 Window 接口，添加 electronAPI 属性
 *
 * 这样在渲染进程中就可以通过 window.electronAPI 访问主进程功能，
 * 并且有完整的 TypeScript 类型支持。
 */
declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

/**
 * 导出空对象，使这个文件作为模块被识别
 */
export {};
