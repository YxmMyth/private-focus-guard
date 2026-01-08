/**
 * 配置数据访问层
 */

import Database from 'better-sqlite3';

export class ConfigRepository {
  constructor(private db: Database.Database) {}

  /**
   * 获取配置值
   */
  get(key: string): string | null {
    const stmt = this.db.prepare('SELECT value FROM config WHERE key = ?');
    const row = stmt.get(key) as any;
    return row ? row.value : null;
  }

  /**
   * 获取配置值（带默认值）
   */
  getOrDefault(key: string, defaultValue: string): string {
    const value = this.get(key);
    return value !== null ? value : defaultValue;
  }

  /**
   * 获取JSON配置
   */
  getJSON<T = any>(key: string): T | null {
    const value = this.get(key);
    if (!value) {
      return null;
    }

    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }

  /**
   * 设置配置值
   */
  set(key: string, value: string): void {
    const stmt = this.db.prepare(`
      INSERT INTO config (key, value, updated_at)
      VALUES (?, ?, strftime('%s', 'now') * 1000)
      ON CONFLICT(key) DO UPDATE SET
        value = excluded.value,
        updated_at = excluded.updated_at
    `);
    stmt.run(key, value);
  }

  /**
   * 设置JSON配置
   */
  setJSON(key: string, value: any): void {
    this.set(key, JSON.stringify(value));
  }

  /**
   * 删除配置
   */
  delete(key: string): void {
    const stmt = this.db.prepare('DELETE FROM config WHERE key = ?');
    stmt.run(key);
  }

  /**
   * 获取所有配置
   */
  getAll(): Record<string, string> {
    const stmt = this.db.prepare('SELECT key, value FROM config');
    const rows = stmt.all() as any[];
    const result: Record<string, string> = {};

    for (const row of rows) {
      result[row.key] = row.value;
    }

    return result;
  }

  /**
   * 批量设置配置
   */
  setMultiple(configs: Record<string, string>): void {
    const stmt = this.db.prepare(`
      INSERT INTO config (key, value, updated_at)
      VALUES (?, ?, strftime('%s', 'now') * 1000)
      ON CONFLICT(key) DO UPDATE SET
        value = excluded.value,
        updated_at = excluded.updated_at
    `);

    const transaction = this.db.transaction((items: Record<string, string>) => {
      for (const [key, value] of Object.entries(items)) {
        stmt.run(key, value);
      }
    });

    transaction(configs);
  }
}

/**
 * 配置键常量
 */
export const ConfigKeys = {
  // LLM配置
  LLM_PROVIDER: 'llm_provider',
  LLM_MODEL: 'llm_model',
  LLM_API_KEY: 'llm_api_key',
  LLM_API_ENDPOINT: 'llm_api_endpoint',

  // 监控配置
  MONITORING_ENABLED: 'monitoring_enabled',
  MONITORING_INTERVAL: 'monitoring_interval',
  AUTO_START: 'auto_start',

  // 通知配置
  NOTIFICATION_ENABLED: 'notification_enabled',
  NOTIFICATION_SOUND: 'notification_sound',

  // 隐私配置
  DATA_RETENTION_DAYS: 'data_retention_days',
  ANONYMIZE_DATA: 'anonymize_data',

  // 界面配置
  THEME: 'theme',
  LANGUAGE: 'language'
} as const;

/**
 * 配置类型定义
 */
export interface AppConfig {
  // LLM配置
  llmProvider: string;
  llmModel: string;
  llmApiKey: string;
  llmApiEndpoint?: string;

  // 监控配置
  monitoringEnabled: boolean;
  monitoringInterval: number;
  autoStart: boolean;

  // 通知配置
  notificationEnabled: boolean;
  notificationSound: boolean;

  // 隐私配置
  dataRetentionDays: number;
  anonymizeData: boolean;

  // 界面配置
  theme: 'light' | 'dark' | 'system';
  language: string;
}

/**
 * 从数据库加载完整配置
 */
export function loadAppConfig(repo: ConfigRepository): AppConfig {
  return {
    llmProvider: repo.getOrDefault(ConfigKeys.LLM_PROVIDER, 'hunyuan'),
    llmModel: repo.getOrDefault(ConfigKeys.LLM_MODEL, 'hunyuan-lite'),
    llmApiKey: repo.getOrDefault(ConfigKeys.LLM_API_KEY, ''),
    llmApiEndpoint: repo.get(ConfigKeys.LLM_API_ENDPOINT) || undefined,

    monitoringEnabled: repo.getOrDefault(ConfigKeys.MONITORING_ENABLED, '0') === '1',
    monitoringInterval: parseInt(repo.getOrDefault(ConfigKeys.MONITORING_INTERVAL, '3000')),
    autoStart: repo.getOrDefault(ConfigKeys.AUTO_START, '0') === '1',

    notificationEnabled: repo.getOrDefault(ConfigKeys.NOTIFICATION_ENABLED, '1') === '1',
    notificationSound: repo.getOrDefault(ConfigKeys.NOTIFICATION_SOUND, '1') === '1',

    dataRetentionDays: parseInt(repo.getOrDefault(ConfigKeys.DATA_RETENTION_DAYS, '30')),
    anonymizeData: repo.getOrDefault(ConfigKeys.ANONYMIZE_DATA, '0') === '1',

    theme: (repo.getOrDefault(ConfigKeys.THEME, 'system') as 'light' | 'dark' | 'system'),
    language: repo.getOrDefault(ConfigKeys.LANGUAGE, 'zh-CN')
  };
}

/**
 * 保存完整配置到数据库
 */
export function saveAppConfig(repo: ConfigRepository, config: AppConfig): void {
  repo.setMultiple({
    [ConfigKeys.LLM_PROVIDER]: config.llmProvider,
    [ConfigKeys.LLM_MODEL]: config.llmModel,
    [ConfigKeys.LLM_API_KEY]: config.llmApiKey,
    [ConfigKeys.LLM_API_ENDPOINT]: config.llmApiEndpoint || '',

    [ConfigKeys.MONITORING_ENABLED]: config.monitoringEnabled ? '1' : '0',
    [ConfigKeys.MONITORING_INTERVAL]: config.monitoringInterval.toString(),
    [ConfigKeys.AUTO_START]: config.autoStart ? '1' : '0',

    [ConfigKeys.NOTIFICATION_ENABLED]: config.notificationEnabled ? '1' : '0',
    [ConfigKeys.NOTIFICATION_SOUND]: config.notificationSound ? '1' : '0',

    [ConfigKeys.DATA_RETENTION_DAYS]: config.dataRetentionDays.toString(),
    [ConfigKeys.ANONYMIZE_DATA]: config.anonymizeData ? '1' : '0',

    [ConfigKeys.THEME]: config.theme,
    [ConfigKeys.LANGUAGE]: config.language
  });
}
