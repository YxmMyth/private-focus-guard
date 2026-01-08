/**
 * SQLite数据库管理
 */

import path from 'path';
import { app } from 'electron';
import fs from 'fs';
import Database from 'better-sqlite3';

/**
 * 数据库接口（简化版）
 */
export interface IDatabase {
  exec: (sql: string) => any[];
  prepare: (sql: string) => any;
  close: () => void;
}

// 简单的内存数据库实现
class SimpleDatabase implements IDatabase {
  private data: Map<string, any[]> = new Map();

  exec(sql: string): any[] {
    console.log('[SimpleDB] 执行:', sql);
    return [];
  }

  prepare(sql: string): any {
    return {
      run: (stmt: string) => {
        console.log('[SimpleDB] 运行:', stmt);
        return { lastInsertRowid: 1, changes: 0 };
      },
      sql: ''
    };
  }

  close(): void {
    console.log('[SimpleDB] 数据库关闭');
    this.data.clear();
  }
}

/**
 * 数据库单例类
 */
export class DatabaseManager {
  private static instance: Database.Database | null = null;
  private static dbPath: string;

  /**
   * 初始化数据库
   */
  static initialize(): Database.Database {
    if (this.instance) {
      return this.instance;
    }

    // 获取用户数据目录
    const userDataPath = app.getPath('userData');
    const dbDir = path.join(userDataPath, 'data');

    // 确保目录存在
    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }

    this.dbPath = path.join(dbDir, 'focusguard.db');
    this.instance = new Database(this.dbPath);

    // 启用外键约束
    this.instance.pragma('foreign_keys = ON');

    // 初始化表结构
    this.initializeTables();

    console.log(`数据库已初始化: ${this.dbPath}`);

    return this.instance;
  }

  /**
   * 获取数据库实例
   */
  static getInstance(): Database.Database {
    if (!this.instance) {
      throw new Error('数据库未初始化，请先调用 initialize()');
    }
    return this.instance;
  }

  /**
   * 关闭数据库连接
   */
  static close(): void {
    if (this.instance) {
      this.instance.close();
      this.instance = null;
    }
  }

  /**
   * 初始化所有表
   */
  private static initializeTables(): void {
    const db = this.instance!;

    // 活动记录表
    db.exec(`
      CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        duration INTEGER DEFAULT 0,
        data TEXT NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
      );
    `);

    // 创建索引
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_activities_timestamp
      ON activities(timestamp);

      CREATE INDEX IF NOT EXISTS idx_activities_type
      ON activities(type);
    `);

    // 专注目标表
    db.exec(`
      CREATE TABLE IF NOT EXISTS focus_goals (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1,
        schedule TEXT,
        blocked_sites TEXT,
        allowed_sites TEXT,
        blocked_apps TEXT,
        allowed_apps TEXT,
        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
        updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
      );
    `);

    // 规则表
    db.exec(`
      CREATE TABLE IF NOT EXISTS rules (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        conditions TEXT NOT NULL,
        action TEXT NOT NULL,
        is_enabled INTEGER DEFAULT 1,
        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
        updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
      );
    `);

    // 判断历史表
    db.exec(`
      CREATE TABLE IF NOT EXISTS judgments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER,
        is_distracted INTEGER,
        confidence REAL,
        action TEXT,
        reason TEXT,
        llm_provider TEXT,
        llm_model TEXT,
        rule_id TEXT,
        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
        FOREIGN KEY (activity_id) REFERENCES activities(id)
      );
    `);

    // 创建索引
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_judgments_activity
      ON judgments(activity_id);

      CREATE INDEX IF NOT EXISTS idx_judgments_timestamp
      ON judgments(created_at);
    `);

    // 对话历史表
    db.exec(`
      CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judgment_id INTEGER,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
        FOREIGN KEY (judgment_id) REFERENCES judgments(id)
      );
    `);

    // 系统配置表
    db.exec(`
      CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
      );
    `);

    // 插入默认配置
    const configCount = db.prepare('SELECT COUNT(*) as count FROM config').get() as { count: number };
    if (configCount.count === 0) {
      const stmt = db.prepare(`
        INSERT INTO config (key, value) VALUES
        ('llm_provider', 'hunyuan'),
        ('llm_model', 'hunyuan-lite'),
        ('monitoring_enabled', '0'),
        ('monitoring_interval', '3000'),
        ('auto_start', '0')
      `);
      stmt.run();
    }
  }

  /**
   * 清空所有数据（谨慎使用）
   */
  static clearAllData(): void {
    const db = this.instance!;
    db.exec(`
      DELETE FROM activities;
      DELETE FROM focus_goals;
      DELETE FROM rules;
      DELETE FROM judgments;
      DELETE FROM conversations;
      DELETE FROM config;
    `);

    // 重新插入默认配置
    const stmt = db.prepare(`
      INSERT INTO config (key, value) VALUES
      ('llm_provider', 'hunyuan'),
      ('llm_model', 'hunyuan-lite'),
      ('monitoring_enabled', '0'),
      ('monitoring_interval', '3000'),
      ('auto_start', '0')
    `);
    stmt.run();
  }

  /**
   * 获取数据库统计信息
   */
  static getStats(): {
    activities: number;
    focusGoals: number;
    rules: number;
    judgments: number;
    conversations: number;
    dbSize: number;
  } {
    const db = this.instance!;

    const activities = db.prepare('SELECT COUNT(*) as count FROM activities').get() as { count: number };
    const focusGoals = db.prepare('SELECT COUNT(*) as count FROM focus_goals').get() as { count: number };
    const rules = db.prepare('SELECT COUNT(*) as count FROM rules').get() as { count: number };
    const judgments = db.prepare('SELECT COUNT(*) as count FROM judgments').get() as { count: number };
    const conversations = db.prepare('SELECT COUNT(*) as count FROM conversations').get() as { count: number };

    const stats = fs.statSync(this.dbPath);

    return {
      activities: activities.count,
      focusGoals: focusGoals.count,
      rules: rules.count,
      judgments: judgments.count,
      conversations: conversations.count,
      dbSize: stats.size
    };
  }
}

/**
 * 数据库初始化函数（供主进程调用）
 */
export function initializeDatabase(): Database.Database {
  return DatabaseManager.initialize();
}

/**
 * 关闭数据库函数
 */
export function closeDatabase(): void {
  DatabaseManager.close();
}
