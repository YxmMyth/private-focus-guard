/**
 * 简单的数据存储实现
 * 使用 JSON 文件存储，无需编译原生模块
 */

import fs from 'fs';
import path from 'path';
import { app } from 'electron';

const DATA_DIR = app.getPath('userData');
const STORAGE_FILE = path.join(DATA_DIR, 'focusguard-data.json');

interface StorageData {
  activities: any[];
  config: Record<string, any>;
  focusGoals: any[];
  lastId: number;
}

/**
 * 初始化存储
 */
export function initializeStorage(): void {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }

  if (!fs.existsSync(STORAGE_FILE)) {
    // 创建初始数据
    const initialData: StorageData = {
      activities: [],
      config: {},
      focusGoals: [],
      lastId: 0
    };

    fs.writeFileSync(STORAGE_FILE, JSON.stringify(initialData, null, 2));
    console.log('[SimpleStorage] 存储文件已创建:', STORAGE_FILE);
  }
}

/**
 * 获取所有数据
 */
export function getAllData(): StorageData {
  try {
    const data = fs.readFileSync(STORAGE_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('[SimpleStorage] 读取数据失败:', error);
    return { activities: [], config: {}, focusGoals: [], lastId: 0 };
  }
}

/**
 * 保存所有数据
 */
export function saveAllData(data: StorageData): void {
  try {
    fs.writeFileSync(STORAGE_FILE, JSON.stringify(data, null, 2));
    console.log('[SimpleStorage] 数据已保存');
  } catch (error) {
    console.error('[SimpleStorage] 保存数据失败:', error);
  }
}

/**
 * 活动数据操作
 */
export const activityStorage = {
  insert: (activity: any): number => {
    const data = getAllData();
    data.lastId += 1;
    data.activities.push(activity);
    saveAllData(data);
    return data.lastId;
  },

  findRecent: (limit: number): any[] => {
    const data = getAllData();
    return data.activities.slice(-limit).reverse();
  },

  query: (options: any): any[] => {
    const data = getAllData();
    const { type, startTime, endTime } = options;

    let filtered = data.activities;

    if (type) {
      filtered = filtered.filter((a: any) => a.type === type);
    }

    if (startTime && endTime) {
      filtered = filtered.filter((a: any) => {
        const time = a.timestamp;
        return time >= startTime && time <= endTime;
      });
    }

    return filtered.reverse();
  },

  getStats: (): any => {
    const data = getAllData();
    return {
      activities: data.activities.length,
      focusGoals: data.focusGoals.length,
      configKeys: Object.keys(data.config).length
    };
  },

  clear: (): void => {
    const initialData: StorageData = {
      activities: [],
      config: {},
      focusGoals: [],
      lastId: 0
    };
    saveAllData(initialData);
  }
};

/**
 * 配置数据操作
 */
export const configStorage = {
  get: (key: string): any => {
    const data = getAllData();
    return data.config[key];
  },

  set: (key: string, value: any): void => {
    const data = getAllData();
    data.config[key] = value;
    saveAllData(data);
  },

  getAll: (): Record<string, any> => {
    const data = getAllData();
    return data.config;
  }
};

/**
 * 专注目标数据操作
 */
export const focusGoalStorage = {
  getAll: (): any[] => {
    const data = getAllData();
    return data.focusGoals || [];
  },

  save: (goals: any[]): void => {
    const data = getAllData();
    data.focusGoals = goals;
    saveAllData(data);
  }
};
