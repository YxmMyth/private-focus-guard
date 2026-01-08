/**
 * Electron主进程入口
 */

import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import * as activeWin from 'active-win';
import { registerIPCHandlers } from './ipc/handlers';
import { Activity, ActivityType, validateActivity } from '../../domain/activity';

let mainWindow: BrowserWindow | null = null;

/**
 * 获取主窗口实例（供其他模块使用）
 */
export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

/**
 * 创建主窗口
 */
function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    },
    frame: true,
    title: 'FocusGuard - AI专注力监督'
  });

  // 开发模式下加载Vite开发服务器
  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产环境下加载打包后的文件
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  console.log('[Main] 窗口已创建');
}

/**
 * 应用就绪后初始化
 */
app.whenReady().then(async () => {
  try {
    // 初始化数据库
    const { initializeDatabase } = await import('../storage/database');
    initializeDatabase();
    console.log('[Main] 数据库已初始化');
  } catch (error) {
    console.error('[Main] 数据库初始化失败:', error);
  }

  // 注册完整的IPC处理器
  try {
    registerIPCHandlers();
    console.log('[Main] IPC处理器已注册');
  } catch (error) {
    console.error('[Main] IPC处理器注册失败:', error);
  }

  // 创建窗口
  createWindow();
});

/**
 * 处理未捕获的异常
 */
process.on('uncaughtException' as any, (error: Error) => {
  console.error('未捕获的异常:', error);
});

/**
 * 处理未处理的Promise拒绝
 */
process.on('unhandledRejection' as any, (reason: any) => {
  console.error('未处理的Promise拒绝:', reason);
});
