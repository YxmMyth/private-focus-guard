/**
 * 简化的 IPC 处理器
 * 使用简单存储，无需数据库
 */

import { ipcMain } from 'electron';
import * as activeWin from 'active-win';
import { getMainWindow } from './index';
import { activityStorage, configStorage } from './simpleStorage';
import { Activity, validateActivity } from '@domain/activity';

/**
 * 注册所有IPC处理器
 */
export function registerHandlers(): void {
  // ===== 活动记录相关 =====

  ipcMain.handle('activity:insert', (_, activity: Activity) => {
    if (!validateActivity(activity)) {
      throw new Error('无效的活动数据');
    }

    return activityStorage.insert(activity);
  });

  ipcMain.handle('activity:query', (_, options) => {
    return activityStorage.query(options);
  });

  ipcMain.handle('activity:recent', (_, limit = 10) => {
    return activityStorage.findRecent(limit);
  });

  // ===== 配置相关 =====

  ipcMain.handle('config:get', (_, key: string) => {
    return configStorage.get(key);
  });

  ipcMain.handle('config:set', (_, key: string, value: string) => {
    configStorage.set(key, value);
    return true;
  });

  ipcMain.handle('config:getAll', () => {
    return configStorage.getAll();
  });

  // ===== 窗口控制相关 =====

  ipcMain.handle('window:minimize', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.minimize();
    }
    return true;
  });

  ipcMain.handle('window:maximize', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.maximize();
    }
    return true;
  });

  ipcMain.handle('window:close', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.close();
    }
    return true;
  });

  // ===== 监控相关 =====

  ipcMain.handle('monitor:getCurrentActivity', () => {
    const activity = activityStorage.findRecent(1);
    return activity || null;
  });

  // 简单监控实现
  const { app } = require('electron');
  let pollingTimer: NodeJS.Timeout | null = null;

  ipcMain.handle('monitor:start', (_, config) => {
    const { interval = 5000 } = config || {};

    if (pollingTimer) {
      clearInterval(pollingTimer);
    }

    const pollWindow = async () => {
      try {
        const result = await activeWin();
        if (result) {
          const mainWindow = getMainWindow();
          if (mainWindow) {
            mainWindow.webContents.send('monitor-update', result);
          }
        }
      } catch (error) {
        console.error('[Monitor] 获取窗口失败:', error);
      }
    };

    pollWindow();
    pollingTimer = setInterval(pollWindow, interval);

    configStorage.set('monitoring_enabled', '1');

    console.log('[IPC] 监控服务已启动');
    return { success: true };
  });

  ipcMain.handle('monitor:stop', () => {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }

    configStorage.set('monitoring_enabled', '0');

    console.log('[IPC] 监控服务已停止');
    return { success: true };
  });

  console.log('IPC 处理器已注册');
}
