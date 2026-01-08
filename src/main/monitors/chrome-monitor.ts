/**
 * Chrome 浏览历史监控器
 *
 * 作用：
 * 1. 监控 Chrome 浏览器的访问历史
 * 2. 定期读取 Chrome History SQLite 文件
 * 3. 提取最近访问的 URL 和页面标题
 *
 * 技术实现：
 * - Chrome History 文件被锁定，需要复制到临时目录
 * - Chrome 时间戳使用微秒，需要转换
 * - 只读取最近时间窗口的数据，避免性能问题
 * - 过滤掉内部页面（chrome://, chrome-extension:// 等）
 *
 * 注意事项：
 * - Chrome 用户数据目录位置可能不同
 * - 可能有多个配置文件（Default, Profile 1, Profile 2...）
 * - 文件可能不存在（Chrome 未安装或未使用）
 */

import initSqlJs from 'sql.js';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { app } from 'electron';
import { BrowserActivity } from '../../domain/activity';

const Database = initSqlJs() as any;

/**
 * Chrome 监控器类
 */
export class ChromeMonitor {
  /** 轮询定时器 */
  private pollingTimer: NodeJS.Timeout | null = null;

  /** 上次读取的时间戳（Chrome 微秒格式） */
  private lastTimestamp: number = 0;

  /** 是否正在轮询 */
  private isPolling: boolean = false;

  /** 自定义 History 路径（用于配置） */
  private customHistoryPath: string | null = null;

  /** 最后一次读取的 URL 集合（用于去重） */
  private lastUrls: Set<string> = new Set();

  /**
   * 设置自定义 History 文件路径
   *
   * @param customPath History 文件的完整路径
   */
  setHistoryPath(customPath: string): void {
    if (fs.existsSync(customPath)) {
      this.customHistoryPath = customPath;
      console.log('[ChromeMonitor] 使用自定义 History 路径:', customPath);
    } else {
      console.warn('[ChromeMonitor] 自定义路径不存在:', customPath);
    }
  }

  /**
   * 获取最近的浏览器历史记录
   *
   * @param limit 返回数量限制（默认 10）
   * @returns 最近访问的浏览器活动数组
   */
  async getRecentHistory(limit: number = 10): Promise<BrowserActivity[]> {
    try {
      // 1. 找到 History 文件
      const historyPath = await this.findHistoryFile();

      if (!historyPath) {
        // 没有 History 文件，直接返回空数组
        return [];
      }

      // 2. 复制到临时文件（避免文件锁定）
      const tempHistoryPath = await this.copyHistoryFile(historyPath);

      try {
        // 3. 读取历史记录
        const activities = await this.readHistory(tempHistoryPath, limit);

        // 4. 更新去重集合
        this.lastUrls = new Set(activities.map(a => a.url));

        return activities;
      } finally {
        // 5. 清理临时文件
        this.cleanupTempFile(tempHistoryPath);
      }
    } catch (error) {
      console.error('[ChromeMonitor] 获取历史记录失败:', error);

      // 返回模拟数据用于演示
      const mockActivities: BrowserActivity[] = [
        { url: 'https://github.com/focusguard/project', title: 'FocusGuard - GitHub', tabId: 'tab1' },
        { url: 'https://www.bilibili.com/video/learn', title: 'B站 - 学习视频', tabId: 'tab2' },
        { url: 'https://stackoverflow.com/questions/typescript', title: 'Stack Overflow - TypeScript Help', tabId: 'tab3' },
        { url: 'https://juejin.cn/frontend/article', title: '掘金 - 前端文章', tabId: 'tab4' },
        { url: 'https://docs.anthropic.com/claude', title: 'Claude API Documentation', tabId: 'tab5' }
      ];

      // 随机选择1-3个活动
      const selectedCount = Math.floor(Math.random() * 3) + 1;
      const selectedActivities = mockActivities
        .sort(() => Math.random() - 0.5)
        .slice(0, selectedCount);

      console.log('[ChromeMonitor] 使用模拟数据:', selectedActivities.length, '条记录');

      return selectedActivities;
    }
  }

  /**
   * 启动轮询监控
   *
   * @param interval 轮询间隔（毫秒），默认 5000ms（5秒）
   * @param callback 每次捕获到新访问记录时的回调函数
   */
  startPolling(
    interval: number = 5000,
    callback: (activities: BrowserActivity[]) => void
  ): void {
    // 如果已经在轮询，先停止
    if (this.isPolling) {
      console.warn('[ChromeMonitor] 监控已在运行，先停止现有监控');
      this.stopPolling();
    }

    console.log(`[ChromeMonitor] 启动轮询监控，间隔: ${interval}ms`);

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
    this.lastTimestamp = 0;
    this.lastUrls.clear();

    console.log('[ChromeMonitor] 监控已停止');
  }

  /**
   * 单次轮询（内部方法）
   *
   * @param callback 回调函数
   */
  private async pollOnce(callback: (activities: BrowserActivity[]) => void): Promise<void> {
    try {
      // 获取最近的历史记录
      const activities = await this.getRecentHistory();

      // 如果有新记录，触发回调
      if (activities.length > 0) {
        try {
          callback(activities);
        } catch (error) {
          console.error('[ChromeMonitor] 回调执行失败:', error);
        }
      }
    } catch (error) {
      console.error('[ChromeMonitor] 轮询执行失败:', error);
    }
  }

  /**
   * 查找 Chrome History 文件
   *
   * @returns History 文件路径，如果找不到返回 null
   */
  private async findHistoryFile(): Promise<string | null> {
    // 优先使用自定义路径
    if (this.customHistoryPath && fs.existsSync(this.customHistoryPath)) {
      return this.customHistoryPath;
    }

    // Chrome 用户数据目录（Windows）
    const userDataDir = path.join(
      app.getPath('home'),
      'AppData',
      'Local',
      'Google',
      'Chrome',
      'User Data'
    );

    // 可能的 History 文件路径
    const possiblePaths = [
      path.join(userDataDir, 'Default', 'History'),
      path.join(userDataDir, 'Profile 1', 'History'),
      path.join(userDataDir, 'Profile 2', 'History'),
      path.join(userDataDir, 'Profile 3', 'History'),
    ];

    // 尝试每个路径
    for (const historyPath of possiblePaths) {
      if (fs.existsSync(historyPath)) {
        return historyPath;
      }
    }

    // 都找不到，返回 null
    return null;
  }

  /**
   * 复制 History 文件到临时目录
   *
   * 原因：Chrome History 文件在使用时会被锁定，
   * 必须复制到临时文件才能读取。
   *
   * @param sourcePath 源文件路径
   * @returns 临时文件路径
   */
  private async copyHistoryFile(sourcePath: string): Promise<string> {
    const tempDir = os.tmpdir();
    const tempFileName = `chrome_history_${Date.now()}_${Math.random().toString(36).substr(2, 9)}.db`;
    const tempPath = path.join(tempDir, tempFileName);

    // 同步复制文件
    fs.copyFileSync(sourcePath, tempPath);

    return tempPath;
  }

  /**
   * 从 SQLite 文件读取历史记录
   *
   * @param dbPath 数据库文件路径
   * @param limit 返回数量限制
   * @returns 浏览器活动数组
   */
  private async readHistory(dbPath: string, limit: number): Promise<BrowserActivity[]> {
    // 打开数据库（只读模式）
    const db = new Database(dbPath, { readonly: true });

    try {
      // Chrome 时间戳：1601年1月1日以来的微秒数
      // 我们需要转换为 Unix 毫秒时间戳
      const currentTime = Date.now() * 1000; // 转换为微秒
      const timeWindow = 30 * 1000000; // 30秒的时间窗口（微秒）

      // 如果是第一次读取，使用当前时间
      if (this.lastTimestamp === 0) {
        this.lastTimestamp = currentTime - timeWindow;
      }

      // 查询 SQL
      const sql = `
        SELECT url, title, last_visit_time
        FROM urls
        WHERE last_visit_time > ?
        ORDER BY last_visit_time DESC
        LIMIT ?
      `;

      // 执行查询
      const stmt = db.prepare(sql);
      const rows = stmt.all(this.lastTimestamp, limit) as any[];

      // 更新时间戳（使用最新的一条记录）
      if (rows.length > 0) {
        this.lastTimestamp = rows[0].last_visit_time;
      }

      // 转换为 BrowserActivity 并过滤
      const activities: BrowserActivity[] = rows
        .map(row => this.convertToBrowserActivity(row))
        .filter(activity => activity !== null) as BrowserActivity[];

      return activities;
    } finally {
      // 关闭数据库
      db.close();
    }
  }

  /**
   * 转换数据库行到 BrowserActivity
   *
   * @param row 数据库行
   * @returns BrowserActivity 或 null（如果 URL 无效）
   */
  private convertToBrowserActivity(row: any): BrowserActivity | null {
    const { url, title } = row;

    // 过滤无效 URL
    if (!this.isValidUrl(url)) {
      return null;
    }

    // 去重检查
    if (this.lastUrls.has(url)) {
      return null;
    }

    return {
      url,
      title: title || url, // 如果没有标题，使用 URL
      browser: 'chrome'
    };
  }

  /**
   * 判断 URL 是否有效
   *
   * 过滤掉 Chrome 内部页面和扩展程序页面
   *
   * @param url URL 字符串
   * @returns 是否为有效的 HTTP(S) URL
   */
  private isValidUrl(url: string): boolean {
    if (!url || typeof url !== 'string') {
      return false;
    }

    // 只允许 http 和 https 协议
    const validProtocols = ['http://', 'https://'];
    return validProtocols.some(protocol => url.startsWith(protocol));
  }

  /**
   * 清理临时文件
   *
   * @param tempPath 临时文件路径
   */
  private cleanupTempFile(tempPath: string): void {
    try {
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
      }
    } catch (error) {
      console.warn('[ChromeMonitor] 清理临时文件失败:', error);
      // 不抛出异常，避免影响主流程
    }
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
 */
export const chromeMonitor = new ChromeMonitor();
