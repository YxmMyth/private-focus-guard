/**
 * 活动类型定义
 */

/**
 * 活动类型枚举
 */
export enum ActivityType {
  BROWSER = 'browser',
  APPLICATION = 'application',
  SYSTEM = 'system'
}

/**
 * 浏览器活动数据
 */
export interface BrowserActivity {
  /** URL地址 */
  url: string;
  /** 页面标题 */
  title: string;
  /** 标签页ID（可选） */
  tabId?: string;
  /** 浏览器名称 */
  browser: 'chrome' | 'firefox' | 'edge' | 'safari' | 'unknown';
}

/**
 * 应用程序活动数据
 */
export interface ApplicationActivity {
  /** 应用名称 */
  appName: string;
  /** 窗口标题 */
  windowTitle: string;
  /** 进程ID */
  processId: number;
  /** 可执行文件路径 */
  executablePath?: string;
}

/**
 * 系统活动数据
 */
export interface SystemActivity {
  /** 鼠标点击次数 */
  mouseClicks: number;
  /** 按键次数 */
  keystrokes: number;
  /** 鼠标移动距离（像素） */
  mouseDistance: number;
  /** 统计时间间隔（毫秒） */
  interval: number;
}

/**
 * 活动数据接口
 */
export interface Activity {
  /** 活动ID（数据库生成） */
  id?: number;
  /** 活动类型 */
  type: ActivityType;
  /** 时间戳（Unix毫秒） */
  timestamp: number;
  /** 活动持续时间（毫秒） */
  duration?: number;
  /** 具体数据 */
  data: BrowserActivity | ApplicationActivity | SystemActivity;
}

/**
 * 活动记录查询选项
 */
export interface ActivityQueryOptions {
  /** 开始时间 */
  startTime?: number;
  /** 结束时间 */
  endTime?: number;
  /** 活动类型 */
  type?: ActivityType;
  /** 限制数量 */
  limit?: number;
  /** 偏移量 */
  offset?: number;
}

/**
 * 活动统计信息
 */
export interface ActivityStatistics {
  /** 总活动时长（毫秒） */
  totalDuration: number;
  /** 各类型活动时长 */
  durationByType: Record<ActivityType, number>;
  /** 最频繁的应用/网站 */
  topActivities: Array<{
    name: string;
    duration: number;
    count: number;
  }>;
  /** 分心活动占比 */
  distractionRatio: number;
}

/**
 * 活动验证函数
 */
export function validateBrowserActivity(data: any): data is BrowserActivity {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof data.url === 'string' &&
    typeof data.title === 'string' &&
    (!data.tabId || typeof data.tabId === 'string')
  );
}

export function validateApplicationActivity(data: any): data is ApplicationActivity {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof data.appName === 'string' &&
    typeof data.windowTitle === 'string' &&
    typeof data.processId === 'number'
  );
}

export function validateSystemActivity(data: any): data is SystemActivity {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof data.mouseClicks === 'number' &&
    typeof data.keystrokes === 'number' &&
    typeof data.mouseDistance === 'number' &&
    typeof data.interval === 'number'
  );
}

export function validateActivity(activity: any): activity is Activity {
  if (!activity || typeof activity !== 'object') {
    return false;
  }

  const { type, timestamp, data } = activity;

  if (typeof timestamp !== 'number') {
    return false;
  }

  switch (type) {
    case ActivityType.BROWSER:
      return validateBrowserActivity(data);
    case ActivityType.APPLICATION:
      return validateApplicationActivity(data);
    case ActivityType.SYSTEM:
      return validateSystemActivity(data);
    default:
      return false;
  }
}
