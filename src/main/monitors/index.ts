/**
 * 监控服务管理器
 *
 * 作用：
 * 1. 协调 Windows 和 Chrome 监控器
 * 2. 统一管理监控的启动和停止
 * 3. 存储活动数据到数据库
 * 4. 提供事件订阅机制
 *
 * 设计原则：
 * - 错误容忍：单个监控器失败不影响整体
 * - 数据合并：统一处理来自不同监控器的活动数据
 * - 事件驱动：通过回调通知活动变化
 */

import { Activity, ActivityType, ApplicationActivity, BrowserActivity } from '../../domain/activity';
import { ActivityRepository } from '../../storage/repositories';
import { DatabaseManager } from '../../storage/database';
import { windowsMonitor } from './windows-monitor';
import { chromeMonitor } from './chrome-monitor';

/**
 * 监控服务配置接口
 */
export interface MonitorServiceConfig {
  /** 轮询间隔（毫秒），默认 5000ms */
  interval?: number;

  /** 是否启用 Windows 监控，默认 true */
  enableWindows?: boolean;

  /** 是否启用 Chrome 监控，默认 true */
  enableChrome?: boolean;
}

/**
 * 监控服务管理器类
 */
export class MonitorService {
  /** 是否正在运行 */
  private isRunning: boolean = false;

  /** 活动事件订阅者 */
  private activityCallbacks: ((activity: Activity) => void)[] = [];

  /** 活动数据仓储（可能为null，如果数据库不可用） */
  private activityRepo: ActivityRepository | null = null;

  /** 监控配置 */
  private config: MonitorServiceConfig = {};

  /** 活动缓冲区（用于批量写入） */
  private activityBuffer: Activity[] = [];

  /** 缓冲区刷新定时器 */
  private bufferFlushTimer: NodeJS.Timeout | null = null;

  /** 缓冲区最大大小 */
  private readonly BUFFER_MAX_SIZE = 50;

  /** 缓冲区刷新间隔（毫秒） */
  private readonly BUFFER_FLUSH_INTERVAL = 10000; // 10秒

  constructor() {
    // 尝试初始化数据库仓储（如果数据库可用）
    try {
      const db = DatabaseManager.getInstance();
      this.activityRepo = new ActivityRepository(db);
    } catch (error) {
      console.warn('[MonitorService] 数据库不可用，使用内存存储');
      // 数据库不可用时，活动将只存储在缓冲区中
      this.activityRepo = null;
    }

    // 启动缓冲区刷新定时器
    this.startBufferFlushTimer();
  }

  /**
   * 启动监控服务
   *
   * @param config 监控配置
   */
  start(config: MonitorServiceConfig = {}): void {
    // 如果已经在运行，先停止
    if (this.isRunning) {
      console.warn('[MonitorService] 监控服务已在运行，先停止现有服务');
      this.stop();
    }

    console.log('[MonitorService] 启动监控服务');

    // 保存配置
    this.config = {
      interval: config.interval || 5000,
      enableWindows: config.enableWindows !== false,
      enableChrome: config.enableChrome !== false
    };

    // 启动 Windows 监控
    if (this.config.enableWindows) {
      try {
        windowsMonitor.startPolling(this.config.interval, (appActivity) => {
          this.handleApplicationActivity(appActivity);
        });
        console.log('[MonitorService] Windows 监控已启动');
      } catch (error) {
        console.error('[MonitorService] Windows 监控启动失败:', error);
      }
    }

    // 启动 Chrome 监控
    if (this.config.enableChrome) {
      try {
        chromeMonitor.startPolling(this.config.interval, (browserActivities) => {
          // Chrome 监控器返回的是数组（可能有多个新访问的网站）
          for (const browserActivity of browserActivities) {
            this.handleBrowserActivity(browserActivity);
          }
        });
        console.log('[MonitorService] Chrome 监控已启动');
      } catch (error) {
        console.error('[MonitorService] Chrome 监控启动失败:', error);
      }
    }

    this.isRunning = true;
    console.log('[MonitorService] 监控服务启动完成');
  }

  /**
   * 停止监控服务
   */
  stop(): void {
    if (!this.isRunning) {
      console.warn('[MonitorService] 监控服务未运行');
      return;
    }

    console.log('[MonitorService] 停止监控服务');

    // 停止所有监控器
    try {
      windowsMonitor.stopPolling();
    } catch (error) {
      console.error('[MonitorService] Windows 监控停止失败:', error);
    }

    try {
      chromeMonitor.stopPolling();
    } catch (error) {
      console.error('[MonitorService] Chrome 监控停止失败:', error);
    }

    // 刷新缓冲区
    this.flushBuffer();

    this.isRunning = false;
    console.log('[MonitorService] 监控服务已停止');
  }

  /**
   * 获取当前活动
   *
   * 从数据库读取最近的活动记录
   *
   * @returns 当前活动或 null
   */
  getCurrentActivity(): Activity | null {
    try {
      if (!this.activityRepo) {
        // 如果没有数据库，从缓冲区返回最近的活动
        return this.activityBuffer.length > 0 ? this.activityBuffer[this.activityBuffer.length - 1] : null;
      }
      const recentActivities = this.activityRepo.findRecent(1);
      return recentActivities.length > 0 ? recentActivities[0] : null;
    } catch (error) {
      console.error('[MonitorService] 获取当前活动失败:', error);
      return null;
    }
  }

  /**
   * 订阅活动事件
   *
   * @param callback 活动变化时的回调函数
   */
  onActivity(callback: (activity: Activity) => void): void {
    this.activityCallbacks.push(callback);
  }

  /**
   * 取消订阅活动事件
   *
   * @param callback 要移除的回调函数
   */
  offActivity(callback: (activity: Activity) => void): void {
    const index = this.activityCallbacks.indexOf(callback);
    if (index !== -1) {
      this.activityCallbacks.splice(index, 1);
    }
  }

  /**
   * 处理应用程序活动
   *
   * @param appActivity 应用程序活动
   */
  private handleApplicationActivity(appActivity: ApplicationActivity): void {
    // 转换为统一的 Activity 接口
    const activity: Activity = {
      type: ActivityType.APPLICATION,
      timestamp: Date.now(),
      data: appActivity
    };

    this.handleNewActivity(activity);
  }

  /**
   * 处理浏览器活动
   *
   * @param browserActivity 浏览器活动
   */
  private handleBrowserActivity(browserActivity: BrowserActivity): void {
    // 转换为统一的 Activity 接口
    const activity: Activity = {
      type: ActivityType.BROWSER,
      timestamp: Date.now(),
      data: browserActivity
    };

    this.handleNewActivity(activity);
  }

  /**
   * 处理新活动
   *
   * 统一的活动处理逻辑：
   * 1. 存储到缓冲区
   * 2. 通知订阅者
   * 3. 错误处理
   *
   * @param activity 活动对象
   */
  private handleNewActivity(activity: Activity): void {
    try {
      // 1. 加入缓冲区
      this.activityBuffer.push(activity);

      // 如果缓冲区满了，立即刷新
      if (this.activityBuffer.length >= this.BUFFER_MAX_SIZE) {
        this.flushBuffer();
      }

      // 2. 通知订阅者
      this.notifyActivityCallbacks(activity);

      // 3. 日志记录
      const activityDesc = this.getActivityDescription(activity);
      console.log(`[MonitorService] 新活动: ${activityDesc}`);
    } catch (error) {
      console.error('[MonitorService] 处理新活动失败:', error);
    }
  }

  /**
   * 通知所有活动订阅者
   *
   * @param activity 活动对象
   */
  private notifyActivityCallbacks(activity: Activity): void {
    // 遍历所有订阅者，触发回调
    for (const callback of this.activityCallbacks) {
      try {
        callback(activity);
      } catch (error) {
        console.error('[MonitorService] 活动回调执行失败:', error);
        // 单个回调失败不影响其他回调
      }
    }
  }

  /**
   * 刷新缓冲区到数据库
   */
  private flushBuffer(): void {
    if (this.activityBuffer.length === 0) {
      return;
    }

    try {
      console.log(`[MonitorService] 刷新缓冲区，写入 ${this.activityBuffer.length} 条活动记录`);

      // 如果有数据库，批量插入数据库
      if (this.activityRepo) {
        this.activityRepo.insertBatch(this.activityBuffer);
      } else {
        console.log('[MonitorService] 数据库不可用，活动保留在内存中');
      }

      // 清空缓冲区
      this.activityBuffer = [];
    } catch (error) {
      console.error('[MonitorService] 刷新缓冲区失败:', error);
      // 如果写入失败，保留缓冲区数据，下次再试
      // 但需要限制缓冲区大小，防止内存溢出
      if (this.activityBuffer.length > this.BUFFER_MAX_SIZE * 2) {
        console.warn('[MonitorService] 缓冲区过大，丢弃旧数据');
        this.activityBuffer = this.activityBuffer.slice(-this.BUFFER_MAX_SIZE);
      }
    }
  }

  /**
   * 启动缓冲区刷新定时器
   */
  private startBufferFlushTimer(): void {
    this.bufferFlushTimer = setInterval(() => {
      this.flushBuffer();
    }, this.BUFFER_FLUSH_INTERVAL);
  }

  /**
   * 获取活动描述（用于日志）
   *
   * @param activity 活动对象
   * @returns 活动描述字符串
   */
  private getActivityDescription(activity: Activity): string {
    switch (activity.type) {
      case ActivityType.BROWSER:
        const browserActivity = activity.data as BrowserActivity;
        return `浏览器 - ${browserActivity.url}`;

      case ActivityType.APPLICATION:
        const appActivity = activity.data as ApplicationActivity;
        return `应用 - ${appActivity.appName}`;

      case ActivityType.SYSTEM:
        return `系统活动`;

      default:
        return `未知活动`;
    }
  }

  /**
   * 获取服务状态
   *
   * @returns 是否正在运行
   */
  isActive(): boolean {
    return this.isRunning;
  }

  /**
   * 获取缓冲区大小
   *
   * @returns 当前缓冲区的活动数量
   */
  getBufferSize(): number {
    return this.activityBuffer.length;
  }

  /**
   * 销毁服务
   *
   * 清理资源，停止定时器
   */
  destroy(): void {
    this.stop();

    if (this.bufferFlushTimer) {
      clearInterval(this.bufferFlushTimer);
      this.bufferFlushTimer = null;
    }

    this.activityCallbacks = [];
  }
}

/**
 * 导出单例
 */
export const monitorService = new MonitorService();

// 导出监控器类（供外部直接使用）
export { windowsMonitor, chromeMonitor };
export type { ApplicationActivity, BrowserActivity } from '../../domain/activity';
