/**
 * Preload 脚本 - 主进程和渲染进程之间的安全桥梁
 *
 * 作用：
 * 1. 使用 contextBridge 安全暴露 API 到渲染进程
 * 2. 提供 TypeScript 类型支持
 * 3. 实现 IPC 通信的封装
 */

import { contextBridge, ipcRenderer } from 'electron';

/**
 * 暴露给渲染进程的 API 接口
 *
 * 设计原则：
 * - 最小权限原则：只暴露必要的 API
 * - 类型安全：所有 API 都有完整的类型定义
 * - 错误处理：所有调用都返回 Promise，便于错误捕获
 */
const electronAPI = {
  // ===== 监控服务相关 =====

  /**
   * 启动监控服务
   * @param config 监控配置
   * @returns { success: boolean } 是否成功启动
   */
  monitor: {
    start: (config?: any) => ipcRenderer.invoke('monitor:start', config),

    /**
     * 停止监控服务
     * @returns { success: boolean } 是否成功停止
     */
    stop: () => ipcRenderer.invoke('monitor:stop'),

    /**
     * 获取当前活动
     * @returns 当前活动对象或 null
     */
    getCurrentActivity: () => ipcRenderer.invoke('monitor:getCurrentActivity')
  },

  // ===== AI 判断相关 =====

  /**
   * AI 评估活动是否分心
   * @param activity 要评估的活动
   * @returns 判断结果（isDistracted, confidence, action, reason）
   */
  ai: {
    evaluate: (activity: any) => ipcRenderer.invoke('ai:evaluate', activity)
  },

  // ===== 配置相关 =====

  /**
   * 配置管理
   */
  config: {
    /**
     * 获取配置值
     * @param key 配置键
     * @returns 配置值或 null
     */
    get: (key: string) => ipcRenderer.invoke('config:get', key),

    /**
     * 设置配置值
     * @param key 配置键
     * @param value 配置值
     * @returns 是否成功
     */
    set: (key: string, value: string) => ipcRenderer.invoke('config:set', key, value),

    /**
     * 获取所有配置
     * @returns 所有配置的键值对对象
     */
    getAll: () => ipcRenderer.invoke('config:getAll')
  },

  // ===== 窗口控制相关 =====

  /**
   * 窗口控制
   */
  window: {
    /**
     * 最小化窗口
     * @returns 是否成功
     */
    minimize: () => ipcRenderer.invoke('window:minimize'),

    /**
     * 最大化/还原窗口
     * @returns 是否成功
     */
    maximize: () => ipcRenderer.invoke('window:maximize'),

    /**
     * 关闭窗口
     * @returns 是否成功
     */
    close: () => ipcRenderer.invoke('window:close')
  },

  // ===== 活动记录相关 =====

  /**
   * 活动数据访问
   */
  activity: {
    /**
     * 插入活动记录
     * @param activity 活动对象
     * @returns 活动记录 ID
     */
    insert: (activity: any) => ipcRenderer.invoke('activity:insert', activity),

    /**
     * 查询活动记录
     * @param options 查询选项
     * @returns 活动记录数组
     */
    query: (options: any) => ipcRenderer.invoke('activity:query', options),

    /**
     * 获取最近的活动记录
     * @param limit 限制数量（默认 10）
     * @returns 最近的活动记录数组
     */
    recent: (limit?: number) => ipcRenderer.invoke('activity:recent', limit)
  },

  // ===== 数据库相关 =====

  /**
   * 数据库操作
   */
  db: {
    /**
     * 获取数据库统计信息
     * @returns 统计信息对象
     */
    getStats: () => ipcRenderer.invoke('db:getStats'),

    /**
     * 清空所有数据
     * @returns 是否成功
     */
    clearAll: () => ipcRenderer.invoke('db:clearAll')
  },

  // ===== 对话框相关 =====

  /**
   * 对话框控制
   */
  dialog: {
    /**
     * 显示干预对话框
     * @param data 对话框数据（activity 和 message）
     * @returns { success: boolean }
     */
    showIntervention: (data: { activity: any; message: string }) =>
      ipcRenderer.invoke('dialog:showIntervention', data),

    /**
     * 关闭干预对话框
     * @returns { success: boolean }
     */
    closeIntervention: () => ipcRenderer.invoke('dialog:closeIntervention')
  },

  // ===== 事件监听相关 =====

  /**
   * 监听主进程发送的事件
   * @param channel 事件名称
   * @param callback 回调函数
   */
  on: (channel: string, callback: (...args: any[]) => void) => {
    // 验证事件名称，防止安全风险
    const validChannels = [
      'show-intervention-dialog',
      'close-intervention-dialog',
      'monitor-error',
      'ai-response'
    ];

    if (validChannels.includes(channel)) {
      // 删除旧的监听器，防止重复
      ipcRenderer.removeAllListeners(channel);

      // 添加新的监听器
      ipcRenderer.on(channel, (_event, ...args) => callback(...args));
    }
  },

  /**
   * 移除事件监听
   * @param channel 事件名称
   * @param callback 回调函数
   */
  off: (channel: string, callback: (...args: any[]) => void) => {
    ipcRenderer.removeListener(channel, callback as any);
  }
};

/**
 * 使用 contextBridge 安全暴露 API
 *
 * contextBridge 是 Electron 提供的安全机制，
 * 用于在隔离的上下文中安全地暴露 API 给渲染进程。
 *
 * 优点：
 * 1. 渲染进程无法直接访问 Node.js API
 * 2. 只能调用我们明确暴露的 API
 * 3. 保持上下文隔离，提高安全性
 */
try {
  contextBridge.exposeInMainWorld('electronAPI', electronAPI);
} catch (error) {
  console.error('暴露 electronAPI 失败:', error);
}

/**
 * 类型声明补充
 *
 * 注意：完整的类型声明在 src/types/global.d.ts 中
 * 这个文件是为了 TypeScript 编译时的类型检查
 */
export type ElectronAPIType = typeof electronAPI;
