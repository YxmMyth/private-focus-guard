/**
 * 活动数据访问层
 */

import Database from 'better-sqlite3';
import { Activity, ActivityQueryOptions, ActivityStatistics, ActivityType } from '../../domain/activity';

export class ActivityRepository {
  constructor(private db: Database.Database) {}

  /**
   * 插入活动记录
   */
  insert(activity: Activity): number {
    const stmt = this.db.prepare(`
      INSERT INTO activities (type, timestamp, duration, data)
      VALUES (?, ?, ?, ?)
    `);

    const result = stmt.run(
      activity.type,
      activity.timestamp,
      activity.duration || 0,
      JSON.stringify(activity.data)
    );

    return result.lastInsertRowid as number;
  }

  /**
   * 批量插入活动记录
   */
  insertBatch(activities: Activity[]): number {
    const stmt = this.db.prepare(`
      INSERT INTO activities (type, timestamp, duration, data)
      VALUES (?, ?, ?, ?)
    `);

    const transaction = this.db.transaction((acts: Activity[]) => {
      for (const activity of acts) {
        stmt.run(
          activity.type,
          activity.timestamp,
          activity.duration || 0,
          JSON.stringify(activity.data)
        );
      }
    });

    transaction(activities);
    return activities.length;
  }

  /**
   * 根据ID查询活动
   */
  findById(id: number): Activity | null {
    const stmt = this.db.prepare('SELECT * FROM activities WHERE id = ?');
    const row = stmt.get(id) as any;

    if (!row) {
      return null;
    }

    return this.mapRowToActivity(row);
  }

  /**
   * 查询活动列表
   */
  query(options: ActivityQueryOptions = {}): Activity[] {
    let sql = 'SELECT * FROM activities WHERE 1=1';
    const params: any[] = [];

    if (options.startTime !== undefined) {
      sql += ' AND timestamp >= ?';
      params.push(options.startTime);
    }

    if (options.endTime !== undefined) {
      sql += ' AND timestamp <= ?';
      params.push(options.endTime);
    }

    if (options.type !== undefined) {
      sql += ' AND type = ?';
      params.push(options.type);
    }

    sql += ' ORDER BY timestamp DESC';

    if (options.limit !== undefined) {
      sql += ' LIMIT ?';
      params.push(options.limit);
    }

    if (options.offset !== undefined) {
      sql += ' OFFSET ?';
      params.push(options.offset);
    }

    const stmt = this.db.prepare(sql);
    const rows = stmt.all(...params) as any[];

    return rows.map(row => this.mapRowToActivity(row));
  }

  /**
   * 查询最近的活动
   */
  findRecent(limit = 10): Activity[] {
    return this.query({ limit });
  }

  /**
   * 查询指定时间范围内的活动
   */
  findByTimeRange(startTime: number, endTime: number): Activity[] {
    return this.query({ startTime, endTime });
  }

  /**
   * 删除指定时间之前的活动
   */
  deleteBefore(timestamp: number): number {
    const stmt = this.db.prepare('DELETE FROM activities WHERE timestamp < ?');
    const result = stmt.run(timestamp);
    return result.changes;
  }

  /**
   * 清空所有活动记录
   */
  deleteAll(): number {
    const stmt = this.db.prepare('DELETE FROM activities');
    const result = stmt.run();
    return result.changes;
  }

  /**
   * 获取活动统计信息
   */
  getStatistics(startTime?: number, endTime?: number): ActivityStatistics {
    let whereClause = 'WHERE 1=1';
    const params: any[] = [];

    if (startTime !== undefined) {
      whereClause += ' AND timestamp >= ?';
      params.push(startTime);
    }

    if (endTime !== undefined) {
      whereClause += ' AND timestamp <= ?';
      params.push(endTime);
    }

    // 总时长
    const totalDurationStmt = this.db.prepare(
      `SELECT SUM(duration) as total FROM activities ${whereClause}`
    );
    const { total } = totalDurationStmt.get(...params) as any;

    // 各类型时长
    const byTypeStmt = this.db.prepare(`
      SELECT type, SUM(duration) as duration
      FROM activities ${whereClause}
      GROUP BY type
    `);
    const byTypeRows = byTypeStmt.all(...params) as any[];
    const durationByType: Record<ActivityType, number> = {
      [ActivityType.BROWSER]: 0,
      [ActivityType.APPLICATION]: 0,
      [ActivityType.SYSTEM]: 0
    };

    for (const row of byTypeRows) {
      durationByType[row.type as ActivityType] = row.duration || 0;
    }

    // 最频繁的活动（前10）
    const topActivitiesStmt = this.db.prepare(`
      SELECT
        json_extract(data, '$.url') as name,
        SUM(duration) as duration,
        COUNT(*) as count
      FROM activities ${whereClause}
      WHERE type = 'browser'
      GROUP BY name
      ORDER BY duration DESC
      LIMIT 10
    `);
    const topActivities = topActivitiesStmt.all(...params) as any[];

    return {
      totalDuration: total || 0,
      durationByType,
      topActivities: topActivities.map(item => ({
        name: item.name || 'Unknown',
        duration: item.duration,
        count: item.count
      })),
      distractionRatio: 0 // 将在judgment repository中计算
    };
  }

  /**
   * 将数据库行映射为Activity对象
   */
  private mapRowToActivity(row: any): Activity {
    return {
      id: row.id,
      type: row.type,
      timestamp: row.timestamp,
      duration: row.duration,
      data: JSON.parse(row.data)
    };
  }
}
