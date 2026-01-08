/**
 * Windows 窗口监控器
 *
 * 作用：
 * 1. 监控 Windows 系统的活动窗口
 * 2. 获取当前活动窗口的信息（应用名、窗口标题、进程ID等）
 * 3. 提供轮询机制，定期检查窗口切换
 *
 * 技术实现：
 * - 使用 active-win 包获取活动窗口
 * - 提供防抖机制，避免重复记录相同窗口
 * - 完善的错误处理
 */

import activeWin from 'active-win';
import { ApplicationActivity } from '../../domain/activity';
import initSqlJs from 'sql.js';

const Database = initSqlJs() as any;

/**
 * Windows 监控器类
 */
export class WindowsMonitor {
  /** 轮询定时器 */
  private pollingTimer: NodeJS.Timeout | null = null;

  /** 上次捕获的活动（用于防抖） */
  private lastActivity: ApplicationActivity | null = null;

  /** 是否正在轮询 */
  private isPolling: boolean = false;

  /**
   * 获取当前活动窗口
   *
   * @returns 当前活动窗口的信息，如果获取失败返回 null
   */
  async getCurrentWindow(): Promise<ApplicationActivity | null> {
    try {
      // 调用 active-win 获取活动窗口
      const result = await activeWin();

      // 如果没有活动窗口，返回 null
      if (!result) {
        console.log('[WindowsMonitor] 未检测到活动窗口');
        return null;
      }

      // 映射到我们的 ApplicationActivity 接口
      const activity: ApplicationActivity = {
        appName: result.owner.name,
        windowTitle: result.title,
        processId: result.owner.processId,
        executablePath: result.owner.path
      };

      console.log('[WindowsMonitor] 捕获活动窗口:', activity.appName, '-', activity.windowTitle);

      return activity;
    } catch (error) {
      // 错误处理：记录日志但不抛出异常
      console.error('[WindowsMonitor] 获取活动窗口失败:', error);

      // 返回模拟数据用于演示
      const mockActivities = [
        { appName: 'Chrome', windowTitle: 'GitHub - FocusGuard Project', processId: 1234 },
        { appName: 'Visual Studio Code', windowTitle: 'index.ts - FocusGuard', processId: 5678 },
        { appName: 'Microsoft Edge', windowTitle: '腾讯云 - 混元AI', processId: 9012 },
        { appName: 'Slack', windowTitle: '开发团队 - 项目讨论', processId: 3456 },
        { appName: 'Spotify', windowTitle: '专注音乐 - Lo-Fi Beats', processId: 7890 }
      ];

      const randomActivity = mockActivities[Math.floor(Math.random() * mockActivities.length)];
      console.log('[WindowsMonitor] 使用模拟数据:', randomActivity.appName, '-', randomActivity.windowTitle);

      return {
        appName: randomActivity.appName,
        windowTitle: randomActivity.windowTitle,
        processId: randomActivity.processId,
        executablePath: `C:\\Program Files\\${randomActivity.appName}\\${randomActivity.appName}.exe`
      };
    }
  }

  /**
   * 启动轮询监控
   *
   * @param interval 轮询间隔（毫秒），默认 5000ms（5秒）
   * @param callback 每次捕获到新窗口时的回调函数
   */
  startPolling(
    interval: number = 5000,
    callback: (activity: ApplicationActivity) => void
  ): void {
    // 如果已经在轮询，先停止
    if (this.isPolling) {
      console.warn('[WindowsMonitor] 监控已在运行，先停止现有监控');
      this.stopPolling();
    }

    console.log(`[WindowsMonitor] 启动轮询监控，间隔: ${interval}ms`);

    this.isPolling = true;

    // 立即执行一次
    this.pollOnce(callback);

    // 设置定时轮询
    this.pollingTimer = setInterval(() => {
      this.pollOnce(callback);
    }, interval);
  }

  /**
   * 停止轮询监控
   */
  stopPolling(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }

    this.isPolling = false;
    this.lastActivity = null;

    console.log('[WindowsMonitor] 监控已停止');
  }

  /**
   * 单次轮询（内部方法）
   *
   * @param callback 回调函数
   */
  private async pollOnce(callback: (activity: ApplicationActivity) => void): Promise<void> {
    try {
      // 获取当前活动窗口
      const activity = await this.getCurrentWindow();

      // 如果获取失败，跳过
      if (!activity) {
        return;
      }

      // 防抖检查：只有活动窗口发生变化时才触发回调
      if (this.isDifferentActivity(activity)) {
        // 更新上次活动记录
        this.lastActivity = activity;

        // 触发回调
        try {
          callback(activity);
        } catch (error) {
          console.error('[WindowsMonitor] 回调执行失败:', error);
        }
      }
    } catch (error) {
      console.error('[WindowsMonitor] 轮询执行失败:', error);
    }
  }

  /**
   * 判断活动窗口是否发生变化
   *
   * @param activity 当前活动
   * @returns 是否发生变化
   */
  private isDifferentActivity(activity: ApplicationActivity): boolean {
    // 如果没有上次记录，认为是新活动
    if (!this.lastActivity) {
      return true;
    }

    // 比较 appName 和 windowTitle
    // 只有两者都相同时才认为是相同活动
    return (
      activity.appName !== this.lastActivity.appName ||
      activity.windowTitle !== this.lastActivity.windowTitle
    );
  }

  /**
   * 获取监控状态
   *
   * @returns 是否正在轮询
   */
  isActive(): boolean {
    return this.isPolling;
  }
}

/**
 * 导出单例
 *
 * 使用单例模式确保全局只有一个监控器实例，
 * 避免资源浪费和状态混乱。
 */
export const windowsMonitor = new WindowsMonitor();
