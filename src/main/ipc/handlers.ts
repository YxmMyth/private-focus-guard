/**
 * IPC通信处理器
 */

import { ipcMain, BrowserWindow } from 'electron';
import { getMainWindow } from '../index';
import { activityStorage, configStorage, focusGoalStorage } from '../simpleStorage';
import { Activity, validateActivity } from '../../domain/activity';

// 临时类型声明（用于配置管理）
type AppConfig = {
  llmProvider: string;
  llmModel: string;
  monitoringInterval: number;
  autoStart: boolean;
};

/**
 * 注册所有IPC处理器
 */
export function registerIPCHandlers(): void {
  // ===== 数据库相关 =====

  // 获取数据库统计信息
  ipcMain.handle('db:getStats', () => {
    return activityStorage.getStats();
  });

  // 清空数据库
  ipcMain.handle('db:clearAll', () => {
    return activityStorage.clear();
  });

  // ===== 活动记录相关 =====

  // 插入活动记录
  ipcMain.handle('activity:insert', (_, activity: Activity) => {
    if (!validateActivity(activity)) {
      throw new Error('无效的活动数据');
    }

    return activityStorage.insert(activity);
  });

  // 查询活动记录
  ipcMain.handle('activity:query', (_, options) => {
    return activityStorage.query(options);
  });

  // 获取最近的活动
  ipcMain.handle('activity:recent', (_, limit = 10) => {
    return activityStorage.findRecent(limit);
  });

  // ===== 配置相关 =====

  // 获取配置值
  ipcMain.handle('config:get', (_, key: string) => {
    return configStorage.get(key);
  });

  // 设置配置值
  ipcMain.handle('config:set', (_, key: string, value: string) => {
    configStorage.set(key, value);
    return true;
  });

  // 获取完整配置
  ipcMain.handle('config:getAll', () => {
    return configStorage.getAll();
  });

  // 加载应用配置
  ipcMain.handle('config:loadAppConfig', () => {
    const config = configStorage.getAll();
    return config as AppConfig;
  });

  // 保存应用配置
  ipcMain.handle('config:saveAppConfig', (_, config: AppConfig) => {
    Object.entries(config).forEach(([key, value]) => {
      configStorage.set(key, String(value));
    });
    return true;
  });

  // ===== 窗口控制相关 =====

  // 显示干预对话框
  ipcMain.handle('dialog:showIntervention', (_, data: {
    activity: any;
    message: string;
  }) => {
    const mainWindow = getMainWindow();
    if (!mainWindow) {
      return { success: false, error: 'No main window' };
    }

    // 发送事件到渲染进程
    mainWindow.webContents.send('show-intervention-dialog', data);

    return { success: true };
  });

  // 关闭干预对话框
  ipcMain.handle('dialog:closeIntervention', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send('close-intervention-dialog');
    }
    return { success: true };
  });

  // 最小化窗口
  ipcMain.handle('window:minimize', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.minimize();
    }
    return true;
  });

  // 最大化/还原窗口
  ipcMain.handle('window:maximize', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
    return true;
  });

  // 关闭窗口
  ipcMain.handle('window:close', () => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.close();
    }
    return true;
  });

  // ===== 监控服务相关 =====

  // 启动监控
  ipcMain.handle('monitor:start', async (_, config) => {
    try {
      // 动态导入监控服务（避免循环依赖）
      const { monitorService } = await import('../monitors');
      monitorService.start(config);

      // 保存监控状态到配置
      configStorage.set('monitoring_enabled', '1');

      console.log('[IPC] 监控服务已启动');
      return { success: true };
    } catch (error) {
      console.error('[IPC] 启动监控失败:', error);
      return { success: false, error: String(error) };
    }
  });

  // 停止监控
  ipcMain.handle('monitor:stop', async () => {
    try {
      const { monitorService } = await import('../monitors');
      monitorService.stop();

      // 保存监控状态到配置
      configStorage.set('monitoring_enabled', '0');

      console.log('[IPC] 监控服务已停止');
      return { success: true };
    } catch (error) {
      console.error('[IPC] 停止监控失败:', error);
      return { success: false, error: String(error) };
    }
  });

  // 获取当前活动
  ipcMain.handle('monitor:getCurrentActivity', async () => {
    try {
      const { monitorService } = await import('../monitors');
      return monitorService.getCurrentActivity();
    } catch (error) {
      console.error('[IPC] 获取当前活动失败:', error);
      return null;
    }
  });

  // ===== AI判断相关 =====

  // 评估活动
  ipcMain.handle('ai:evaluate', async (_, activity: Activity) => {
    try {
      const { focusGuardService } = await import('../../services/focus-guard');
      return await focusGuardService.evaluateActivity(activity);
    } catch (error) {
      console.error('[IPC] AI评估失败:', error);
      return {
        isDistracted: false,
        confidence: 0,
        action: 'allow',
        reason: 'AI评估服务出错'
      };
    }
  });

  // 对话轮次（暂未实现，返回默认值）
  ipcMain.handle('ai:chat', async (_, message: string, context: any) => {
    console.log('[IPC] AI对话功能暂未实现');
    return {
      message: 'AI对话功能将在 Week 3 实现',
      isFinal: true,
      decision: 'allow'
    };
  });

  console.log('IPC处理器已注册');
}
