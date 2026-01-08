/**
 * 规则引擎相关定义
 */

/**
 * 规则类型
 */
export enum RuleType {
  /** URL黑名单 */
  URL_BLOCKLIST = 'url_blocklist',
  /** URL白名单 */
  URL_ALLOWLIST = 'url_allowlist',
  /** 应用黑名单 */
  APP_BLOCKLIST = 'app_blocklist',
  /** 应用白名单 */
  APP_ALLOWLIST = 'app_allowlist',
  /** 时间规则 */
  TIME_RULE = 'time_rule',
  /** 自定义规则 */
  CUSTOM = 'custom'
}

/**
 * 规则条件
 */
export interface RuleCondition {
  /** 字段名 */
  field: string;
  /** 操作符 */
  operator: 'equals' | 'contains' | 'matches' | 'startsWith' | 'endsWith';
  /** 值 */
  value: string | number | boolean;
}

/**
 * 规则定义
 */
export interface Rule {
  /** 规则ID */
  id: string;
  /** 规则名称 */
  name: string;
  /** 规则类型 */
  type: RuleType;
  /** 优先级（数字越大优先级越高） */
  priority: number;
  /** 规则条件 */
  conditions: RuleCondition[];
  /** 规则动作 */
  action: RuleAction;
  /** 是否启用 */
  isEnabled: boolean;
  /** 创建时间 */
  createdAt: number;
  /** 更新时间 */
  updatedAt: number;
}

/**
 * 规则动作
 */
export enum RuleAction {
  /** 允许 */
  ALLOW = 'allow',
  /** 阻止 */
  BLOCK = 'block',
  /** 警告 */
  WARN = 'warn',
  /** 需要AI判断 */
  REQUIRE_AI = 'require_ai'
}

/**
 * 规则执行结果
 */
export interface RuleExecutionResult {
  /** 是否匹配 */
  matched: boolean;
  /** 规则ID */
  ruleId?: string;
  /** 规则名称 */
  ruleName?: string;
  /** 动作 */
  action?: RuleAction;
  /** 置信度 (0-1) */
  confidence: number;
  /** 原因 */
  reason?: string;
}

/**
 * 规则集
 */
export interface RuleSet {
  /** 规则列表 */
  rules: Rule[];
  /** 默认动作（当没有规则匹配时） */
  defaultAction: RuleAction;
}

/**
 * 创建规则ID
 */
export function generateRuleId(): string {
  return `rule_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 评估规则条件
 */
export function evaluateCondition(
  condition: RuleCondition,
  target: any
): boolean {
  const fieldValue = getFieldValue(target, condition.field);

  switch (condition.operator) {
    case 'equals':
      return fieldValue === condition.value;
    case 'contains':
      return typeof fieldValue === 'string' &&
        String(condition.value).toLowerCase().includes(fieldValue.toLowerCase());
    case 'matches':
      try {
        const regex = new RegExp(String(condition.value), 'i');
        return regex.test(String(fieldValue));
      } catch {
        return false;
      }
    case 'startsWith':
      return typeof fieldValue === 'string' &&
        String(fieldValue).toLowerCase().startsWith(String(condition.value).toLowerCase());
    case 'endsWith':
      return typeof fieldValue === 'string' &&
        String(fieldValue).toLowerCase().endsWith(String(condition.value).toLowerCase());
    default:
      return false;
  }
}

/**
 * 获取字段值（支持嵌套路径，如 'data.url'）
 */
function getFieldValue(obj: any, path: string): any {
  const keys = path.split('.');
  let value = obj;

  for (const key of keys) {
    if (value == null) {
      return undefined;
    }
    value = value[key];
  }

  return value;
}

/**
 * 执行规则集
 */
export function executeRuleSet(
  ruleSet: RuleSet,
  activity: any
): RuleExecutionResult {
  // 按优先级排序规则
  const sortedRules = [...ruleSet.rules]
    .filter(rule => rule.isEnabled)
    .sort((a, b) => b.priority - a.priority);

  // 遍历规则
  for (const rule of sortedRules) {
    // 检查所有条件是否都满足
    const allConditionsMatch = rule.conditions.every(condition =>
      evaluateCondition(condition, activity)
    );

    if (allConditionsMatch) {
      return {
        matched: true,
        ruleId: rule.id,
        ruleName: rule.name,
        action: rule.action,
        confidence: 0.9, // 规则引擎给出高置信度
        reason: `匹配规则: ${rule.name}`
      };
    }
  }

  // 没有规则匹配，返回默认动作
  return {
    matched: false,
    action: ruleSet.defaultAction,
    confidence: 0.0,
    reason: '没有匹配的规则'
  };
}
