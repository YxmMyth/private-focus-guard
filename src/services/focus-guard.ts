/**
 * 专注守卫服务
 *
 * 作用：
 * 1. 评估用户活动是否分心
 * 2. 协调规则引擎和 AI 判断
 * 3. 实现缓存机制优化性能
 * 4. 提供降级策略确保可用性
 *
 * 判断流程：
 * 1. 检查服务是否启用
 * 2. 检查专注目标（黑白名单）
 * 3. 规则引擎快速判断
 * 4. 缓存检查
 * 5. LLM 智能评估
 *
 * 降级策略：
 * - 规则引擎失败 → 使用默认规则
 * - LLM 失败 → 降级到规则引擎
 * - 规则引擎和 LLM 都失败 → 默认 ALLOW（保守策略）
 */

import { Activity, ActivityType, BrowserActivity, ApplicationActivity, SystemActivity } from '../domain/activity';
import { FocusGoal, isInSchedule, matchesUrlPattern, matchesAppPattern } from '../domain/focus-goal';
import { RuleSet, RuleAction, executeRuleSet } from '../domain/rule';
import { HunyuanAdapter } from './llm/hunyuan';
import { JudgmentResult } from './llm/adapter';

/**
 * 缓存条目
 */
interface CacheEntry {
  /** 判断结果 */
  result: JudgmentResult;
  /** 缓存时间戳 */
  timestamp: number;
  /** 命中次数 */
  hitCount: number;
}

/**
 * 专注守卫服务类
 */
export class FocusGuardService {
  /** 是否启用 */
  private enabled: boolean = true;

  /** 专注目标列表 */
  private focusGoals: FocusGoal[] = [];

  /** 规则集 */
  private ruleSet: RuleSet = {
    rules: [],
    defaultAction: RuleAction.REQUIRE_AI
  };

  /** LLM 适配器 */
  private llmAdapter: HunyuanAdapter | null = null;

  /** 判断结果缓存 */
  private cache: Map<string, CacheEntry> = new Map();

  /** 缓存 TTL（毫秒），默认 5 分钟 */
  private readonly CACHE_TTL = 5 * 60 * 1000;

  /** 缓存最大大小 */
  private readonly CACHE_MAX_SIZE = 1000;

  /** 统计信息 */
  private stats = {
    totalEvaluations: 0,
    cacheHits: 0,
    llmCalls: 0,
    ruleMatches: 0,
    failures: 0
  };

  /**
   * 设置 LLM 适配器
   *
   * @param adapter LLM 适配器实例
   */
  setLLMAdapter(adapter: HunyuanAdapter | null): void {
    this.llmAdapter = adapter;
    console.log('[FocusGuard] LLM 适配器已', adapter ? '设置' : '移除');
  }

  /**
   * 设置专注目标
   *
   * @param goals 专注目标列表
   */
  setFocusGoals(goals: FocusGoal[]): void {
    this.focusGoals = goals;
    console.log(`[FocusGuard] 已设置 ${goals.length} 个专注目标`);
  }

  /**
   * 设置规则集
   *
   * @param ruleSet 规则集
   */
  setRuleSet(ruleSet: RuleSet): void {
    this.ruleSet = ruleSet;
    console.log(`[FocusGuard] 已设置规则集，包含 ${ruleSet.rules.length} 条规则`);
  }

  /**
   * 设置服务启用状态
   *
   * @param enabled 是否启用
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    console.log('[FocusGuard] 服务', enabled ? '已启用' : '已禁用');
  }

  /**
   * 评估活动是否分心
   *
   * 这是核心方法，按照判断流程依次检查：
   * 1. 服务启用检查
   * 2. 专注目标检查
   * 3. 规则引擎检查
   * 4. 缓存检查
   * 5. LLM 评估
   *
   * @param activity 要评估的活动
   * @returns 判断结果
   */
  async evaluateActivity(activity: Activity): Promise<JudgmentResult> {
    this.stats.totalEvaluations++;

    try {
      // 1. 检查服务是否启用
      if (!this.enabled) {
        return {
          isDistracted: false,
          confidence: 1.0,
          action: 'allow',
          reason: '监控服务未启用'
        };
      }

      // 2. 检查专注目标
      const goalCheck = this.checkFocusGoals(activity);
      if (!goalCheck.allowed) {
        return {
          isDistracted: true,
          confidence: 1.0,
          action: 'block',
          reason: goalCheck.reason || '违反专注目标'
        };
      }

      // 3. 规则引擎判断
      const ruleResult = executeRuleSet(this.ruleSet, activity);
      if (ruleResult.matched) {
        this.stats.ruleMatches++;

        // 如果规则明确要求 ALLOW 或 BLOCK，直接返回
        if (ruleResult.action === RuleAction.ALLOW) {
          return {
            isDistracted: false,
            confidence: ruleResult.confidence,
            action: 'allow',
            reason: ruleResult.reason || '规则允许'
          };
        }

        if (ruleResult.action === RuleAction.BLOCK) {
          return {
            isDistracted: true,
            confidence: ruleResult.confidence,
            action: 'block',
            reason: ruleResult.reason || '规则阻止'
          };
        }

        // WARN 和 REQUIRE_AI 需要继续处理
      }

      // 4. 缓存检查
      const cacheKey = this.getCacheKey(activity);
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
        this.stats.cacheHits++;
        cached.hitCount++;

        console.log(`[FocusGuard] 缓存命中 (${cached.hitCount}次):`, cacheKey);
        return cached.result;
      }

      // 5. LLM 评估
      if (this.llmAdapter) {
        try {
          this.stats.llmCalls++;

          const result = await this.llmAdapter.evaluateActivity(activity, this.focusGoals);

          // 缓存结果
          this.setCache(cacheKey, result);

          console.log('[FocusGuard] LLM 评估结果:', result.action, '置信度:', result.confidence);
          return result;
        } catch (error) {
          this.stats.failures++;
          console.error('[FocusGuard] LLM 评估失败:', error);

          // LLM 失败，使用降级策略
          return {
            isDistracted: false,
            confidence: 0,
            action: 'allow',
            reason: 'AI评估失败，默认放行（降级策略）'
          };
        }
      }

      // 6. 没有配置 LLM，返回默认值
      return {
        isDistracted: false,
        confidence: 0,
        action: 'allow',
        reason: '未配置AI服务'
      };
    } catch (error) {
      this.stats.failures++;
      console.error('[FocusGuard] 评估活动失败:', error);

      // 保守策略：出错时默认允许
      return {
        isDistracted: false,
        confidence: 0,
        action: 'allow',
        reason: '评估服务出错，默认放行'
      };
    }
  }

  /**
   * 检查专注目标
   *
   * @param activity 活动对象
   * @returns { allowed: boolean, reason?: string }
   */
  private checkFocusGoals(activity: Activity): { allowed: boolean; reason?: string } {
    for (const goal of this.focusGoals) {
      // 检查目标是否启用
      if (!goal.isActive) {
        continue;
      }

      // 检查时间表
      if (goal.schedule && !isInSchedule(goal)) {
        // 不在时间表内，跳过此目标
        continue;
      }

      // 根据活动类型检查
      let identifier: string;
      let activityType: 'browser' | 'application';

      if (activity.type === ActivityType.BROWSER) {
        const browserActivity = activity.data as BrowserActivity;
        identifier = browserActivity.url;
        activityType = 'browser';
      } else if (activity.type === ActivityType.APPLICATION) {
        const appActivity = activity.data as ApplicationActivity;
        identifier = appActivity.appName;
        activityType = 'application';
      } else {
        // 系统活动不检查
        continue;
      }

      // 检查黑名单
      const blocklist = activityType === 'browser' ? goal.blockedSites : goal.blockedApps;
      if (blocklist && blocklist.length > 0) {
        for (const pattern of blocklist) {
          const matches = activityType === 'browser'
            ? matchesUrlPattern(identifier, pattern)
            : matchesAppPattern(identifier, pattern);

          if (matches) {
            return {
              allowed: false,
              reason: `在专注目标"${goal.name}"的黑名单中`
            };
          }
        }
      }

      // 检查白名单（如果配置了白名单，只允许白名单内的内容）
      const allowlist = activityType === 'browser' ? goal.allowedSites : goal.allowedApps;
      if (allowlist && allowlist.length > 0) {
        let allowed = false;
        for (const pattern of allowlist) {
          const matches = activityType === 'browser'
            ? matchesUrlPattern(identifier, pattern)
            : matchesAppPattern(identifier, pattern);

          if (matches) {
            allowed = true;
            break;
          }
        }

        if (!allowed) {
          return {
            allowed: false,
            reason: `不在专注目标"${goal.name}"的白名单中`
          };
        }
      }
    }

    return { allowed: true };
  }

  /**
   * 生成缓存键
   *
   * @param activity 活动对象
   * @returns 缓存键
   */
  private getCacheKey(activity: Activity): string {
    // 简单的缓存策略：使用类型和主要标识符
    if (activity.type === ActivityType.BROWSER) {
      // 浏览器活动使用 URL（去掉查询参数和 fragment）
      const browserData = activity.data as BrowserActivity;
      const url = new URL(browserData.url);
      return `browser:${url.hostname}${url.pathname}`;
    } else if (activity.type === ActivityType.APPLICATION) {
      // 应用程序活动使用应用名
      const appData = activity.data as ApplicationActivity;
      return `app:${appData.appName}`;
    } else {
      // 其他活动使用时间戳
      return `other:${activity.timestamp}`;
    }
  }

  /**
   * 设置缓存
   *
   * @param key 缓存键
   * @param result 判断结果
   */
  private setCache(key: string, result: JudgmentResult): void {
    // 如果缓存已满，删除最旧的条目
    if (this.cache.size >= this.CACHE_MAX_SIZE) {
      let oldestKey: string | null = null;
      let oldestTime = Infinity;

      for (const [k, v] of this.cache.entries()) {
        if (v.timestamp < oldestTime) {
          oldestTime = v.timestamp;
          oldestKey = k;
        }
      }

      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }

    // 添加新条目
    this.cache.set(key, {
      result,
      timestamp: Date.now(),
      hitCount: 0
    });
  }

  /**
   * 清空缓存
   */
  clearCache(): void {
    this.cache.clear();
    console.log('[FocusGuard] 缓存已清空');
  }

  /**
   * 获取统计信息
   *
   * @returns 统计信息对象
   */
  getStats() {
    return {
      ...this.stats,
      cacheSize: this.cache.size,
      cacheHitRate: this.stats.totalEvaluations > 0
        ? this.stats.cacheHits / this.stats.totalEvaluations
        : 0
    };
  }

  /**
   * 重置统计信息
   */
  resetStats(): void {
    this.stats = {
      totalEvaluations: 0,
      cacheHits: 0,
      llmCalls: 0,
      ruleMatches: 0,
      failures: 0
    };
    console.log('[FocusGuard] 统计信息已重置');
  }

  /**
   * 获取服务状态
   *
   * @returns 服务状态对象
   */
  getStatus() {
    return {
      enabled: this.enabled,
      llmConfigured: this.llmAdapter !== null,
      focusGoalsCount: this.focusGoals.filter(g => g.isActive).length,
      rulesCount: this.ruleSet.rules.filter(r => r.isEnabled).length,
      cacheSize: this.cache.size
    };
  }
}

/**
 * 导出单例
 */
export const focusGuardService = new FocusGuardService();
