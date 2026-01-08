/**
 * 专注目标数据访问层
 */

import Database from 'better-sqlite3';
import { FocusGoal, generateGoalId, FocusGoalCreateOptions, FocusGoalUpdateOptions } from '../../domain/focus-goal';

export class FocusGoalRepository {
  constructor(private db: Database.Database) {}

  /**
   * 创建专注目标
   */
  create(options: FocusGoalCreateOptions): FocusGoal {
    const now = Date.now();
    const goal: FocusGoal = {
      id: generateGoalId(),
      name: options.name,
      description: options.description,
      isActive: true,
      schedule: options.schedule,
      blockedSites: options.blockedSites,
      allowedSites: options.allowedSites,
      blockedApps: options.blockedApps,
      allowedApps: options.allowedApps,
      createdAt: now,
      updatedAt: now
    };

    const stmt = this.db.prepare(`
      INSERT INTO focus_goals (
        id, name, description, is_active, schedule,
        blocked_sites, allowed_sites, blocked_apps, allowed_apps,
        created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      goal.id,
      goal.name,
      goal.description,
      goal.isActive ? 1 : 0,
      goal.schedule ? JSON.stringify(goal.schedule) : null,
      goal.blockedSites ? JSON.stringify(goal.blockedSites) : null,
      goal.allowedSites ? JSON.stringify(goal.allowedSites) : null,
      goal.blockedApps ? JSON.stringify(goal.blockedApps) : null,
      goal.allowedApps ? JSON.stringify(goal.allowedApps) : null,
      goal.createdAt,
      goal.updatedAt
    );

    return goal;
  }

  /**
   * 根据ID查询专注目标
   */
  findById(id: string): FocusGoal | null {
    const stmt = this.db.prepare('SELECT * FROM focus_goals WHERE id = ?');
    const row = stmt.get(id) as any;

    if (!row) {
      return null;
    }

    return this.mapRowToFocusGoal(row);
  }

  /**
   * 查询所有专注目标
   */
  findAll(): FocusGoal[] {
    const stmt = this.db.prepare('SELECT * FROM focus_goals ORDER BY created_at DESC');
    const rows = stmt.all() as any[];
    return rows.map(row => this.mapRowToFocusGoal(row));
  }

  /**
   * 查询启用的专注目标
   */
  findActive(): FocusGoal[] {
    const stmt = this.db.prepare(
      'SELECT * FROM focus_goals WHERE is_active = 1 ORDER BY created_at DESC'
    );
    const rows = stmt.all() as any[];
    return rows.map(row => this.mapRowToFocusGoal(row));
  }

  /**
   * 更新专注目标
   */
  update(id: string, options: FocusGoalUpdateOptions): FocusGoal | null {
    const existing = this.findById(id);
    if (!existing) {
      return null;
    }

    const updated: FocusGoal = {
      ...existing,
      ...options,
      id, // 确保ID不被更改
      updatedAt: Date.now()
    };

    const stmt = this.db.prepare(`
      UPDATE focus_goals SET
        name = ?,
        description = ?,
        is_active = ?,
        schedule = ?,
        blocked_sites = ?,
        allowed_sites = ?,
        blocked_apps = ?,
        allowed_apps = ?,
        updated_at = ?
      WHERE id = ?
    `);

    stmt.run(
      updated.name,
      updated.description,
      updated.isActive ? 1 : 0,
      updated.schedule ? JSON.stringify(updated.schedule) : null,
      updated.blockedSites ? JSON.stringify(updated.blockedSites) : null,
      updated.allowedSites ? JSON.stringify(updated.allowedSites) : null,
      updated.blockedApps ? JSON.stringify(updated.blockedApps) : null,
      updated.allowedApps ? JSON.stringify(updated.allowedApps) : null,
      updated.updatedAt,
      id
    );

    return updated;
  }

  /**
   * 删除专注目标
   */
  delete(id: string): boolean {
    const stmt = this.db.prepare('DELETE FROM focus_goals WHERE id = ?');
    const result = stmt.run(id);
    return result.changes > 0;
  }

  /**
   * 启用/禁用专注目标
   */
  setActive(id: string, isActive: boolean): boolean {
    const stmt = this.db.prepare(`
      UPDATE focus_goals SET
        is_active = ?,
        updated_at = ?
      WHERE id = ?
    `);
    const result = stmt.run(isActive ? 1 : 0, Date.now(), id);
    return result.changes > 0;
  }

  /**
   * 获取当前活跃的专注目标
   */
  findCurrentActive(): FocusGoal[] {
    const all = this.findActive();
    return all.filter(goal => {
      // 如果没有时间表，则始终活跃
      if (!goal.schedule) {
        return true;
      }

      // 检查当前时间是否在时间表内
      const now = new Date();
      const currentTime = now.getHours() * 60 + now.getMinutes();
      const currentDay = now.getDay();

      if (!goal.schedule.repeat.weekdays.includes(currentDay)) {
        return false;
      }

      const [startHour, startMin] = goal.schedule.startTime.split(':').map(Number);
      const [endHour, endMin] = goal.schedule.endTime.split(':').map(Number);

      const startTime = startHour * 60 + startMin;
      const endTime = endHour * 60 + endMin;

      return currentTime >= startTime && currentTime <= endTime;
    });
  }

  /**
   * 将数据库行映射为FocusGoal对象
   */
  private mapRowToFocusGoal(row: any): FocusGoal {
    return {
      id: row.id,
      name: row.name,
      description: row.description,
      isActive: row.is_active === 1,
      schedule: row.schedule ? JSON.parse(row.schedule) : undefined,
      blockedSites: row.blocked_sites ? JSON.parse(row.blocked_sites) : undefined,
      allowedSites: row.allowed_sites ? JSON.parse(row.allowed_sites) : undefined,
      blockedApps: row.blocked_apps ? JSON.parse(row.blocked_apps) : undefined,
      allowedApps: row.allowed_apps ? JSON.parse(row.allowed_apps) : undefined,
      createdAt: row.created_at,
      updatedAt: row.updated_at
    };
  }
}
