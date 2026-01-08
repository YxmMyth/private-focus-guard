/**
 * 专注目标相关定义
 */

/**
 * 时间表定义
 */
export interface Schedule {
  /** 开始时间（HH:mm格式） */
  startTime: string;
  /** 结束时间（HH:mm格式） */
  endTime: string;
  /** 重复规则 */
  repeat: {
    /** 星期几 (0-6, 0=周日) */
    weekdays: number[];
  };
}

/**
 * 专注目标接口
 */
export interface FocusGoal {
  /** 目标ID */
  id: string;
  /** 目标名称 */
  name: string;
  /** 目标描述 */
  description: string;
  /** 是否启用 */
  isActive: boolean;
  /** 时间表（可选） */
  schedule?: Schedule;
  /** 阻止的网站列表（URL模式） */
  blockedSites?: string[];
  /** 允许的网站列表（白名单） */
  allowedSites?: string[];
  /** 阻止的应用列表（应用名模式） */
  blockedApps?: string[];
  /** 允许的应用列表（白名单） */
  allowedApps?: string[];
  /** 创建时间 */
  createdAt: number;
  /** 更新时间 */
  updatedAt: number;
}

/**
 * 专注目标创建选项
 */
export interface FocusGoalCreateOptions {
  name: string;
  description: string;
  schedule?: Schedule;
  blockedSites?: string[];
  allowedSites?: string[];
  blockedApps?: string[];
  allowedApps?: string[];
}

/**
 * 专注目标更新选项
 */
export type FocusGoalUpdateOptions = Partial<FocusGoalCreateOptions> & {
  isActive?: boolean;
};

/**
 * 检查当前时间是否符合专注目标的时间表
 */
export function isInSchedule(goal: FocusGoal): boolean {
  if (!goal.schedule || !goal.isActive) {
    return false;
  }

  const now = new Date();
  const currentTime = now.getHours() * 60 + now.getMinutes();
  const currentDay = now.getDay();

  // 检查是否在重复的星期几中
  if (!goal.schedule.repeat.weekdays.includes(currentDay)) {
    return false;
  }

  // 解析开始和结束时间
  const [startHour, startMin] = goal.schedule.startTime.split(':').map(Number);
  const [endHour, endMin] = goal.schedule.endTime.split(':').map(Number);

  const startTime = startHour * 60 + startMin;
  const endTime = endHour * 60 + endMin;

  return currentTime >= startTime && currentTime <= endTime;
}

/**
 * 验证URL模式是否匹配
 */
export function matchesUrlPattern(url: string, pattern: string): boolean {
  // 支持通配符 * 和正则表达式
  if (pattern.includes('*')) {
    const regex = new RegExp(
      '^' + pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$'
    );
    return regex.test(url);
  }

  // 尝试作为正则表达式
  try {
    const regex = new RegExp(pattern);
    return regex.test(url);
  } catch {
    // 简单字符串匹配
    return url.includes(pattern);
  }
}

/**
 * 验证应用名是否匹配
 */
export function matchesAppPattern(appName: string, pattern: string): boolean {
  if (pattern.includes('*')) {
    const regex = new RegExp(
      '^' + pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$',
      'i'
    );
    return regex.test(appName);
  }

  try {
    const regex = new RegExp(pattern, 'i');
    return regex.test(appName);
  } catch {
    return appName.toLowerCase().includes(pattern.toLowerCase());
  }
}

/**
 * 检查活动是否被专注目标允许
 */
export function isActivityAllowed(
  goal: FocusGoal,
  activityType: 'browser' | 'application',
  identifier: string
): {
  allowed: boolean;
  reason?: string;
} {
  // 如果目标未启用，默认允许
  if (!goal.isActive) {
    return { allowed: true };
  }

  // 如果不在时间表内，默认允许
  if (goal.schedule && !isInSchedule(goal)) {
    return { allowed: true };
  }

  if (activityType === 'browser') {
    // 检查黑名单
    if (goal.blockedSites && goal.blockedSites.length > 0) {
      for (const pattern of goal.blockedSites) {
        if (matchesUrlPattern(identifier, pattern)) {
          return {
            allowed: false,
            reason: `网站匹配黑名单模式: ${pattern}`
          };
        }
      }
    }

    // 检查白名单
    if (goal.allowedSites && goal.allowedSites.length > 0) {
      for (const pattern of goal.allowedSites) {
        if (matchesUrlPattern(identifier, pattern)) {
          return { allowed: true };
        }
      }
      return {
        allowed: false,
        reason: '网站不在白名单中'
      };
    }
  } else if (activityType === 'application') {
    // 检查应用黑名单
    if (goal.blockedApps && goal.blockedApps.length > 0) {
      for (const pattern of goal.blockedApps) {
        if (matchesAppPattern(identifier, pattern)) {
          return {
            allowed: false,
            reason: `应用匹配黑名单模式: ${pattern}`
          };
        }
      }
    }

    // 检查应用白名单
    if (goal.allowedApps && goal.allowedApps.length > 0) {
      for (const pattern of goal.allowedApps) {
        if (matchesAppPattern(identifier, pattern)) {
          return { allowed: true };
        }
      }
      return {
        allowed: false,
        reason: '应用不在白名单中'
      };
    }
  }

  return { allowed: true };
}

/**
 * 创建专注目标ID
 */
export function generateGoalId(): string {
  return `goal_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
