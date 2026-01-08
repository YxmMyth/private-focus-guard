/**
 * 仪表板页面
 */

import { useState, useEffect } from 'react';

interface DashboardProps {}

export default function Dashboard({}: DashboardProps) {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [currentActivity, setCurrentActivity] = useState<any>(null);
  const [stats, setStats] = useState({
    totalActivities: 0,
    todayFocusTime: 0,
    distractionCount: 0
  });

  useEffect(() => {
    // 加载统计数据
    loadStats();

    // 定期刷新当前活动
    const interval = setInterval(() => {
      if (isMonitoring) {
        loadCurrentActivity();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [isMonitoring]);

  const loadStats = async () => {
    try {
      const stats = await window.electronAPI.db.getStats();
      setStats({
        totalActivities: stats.totalActivities || 0,
        todayFocusTime: 0,  // 需要后续实现计算逻辑
        distractionCount: 0  // 需要后续实现
      });
    } catch (error) {
      console.error('加载统计数据失败:', error);
    }
  };

  const loadCurrentActivity = async () => {
    try {
      const activity = await window.electronAPI.monitor.getCurrentActivity();
      setCurrentActivity(activity);
    } catch (error) {
      console.error('获取当前活动失败:', error);
    }
  };

  const toggleMonitoring = async () => {
    try {
      if (isMonitoring) {
        await window.electronAPI.monitor.stop();
        setIsMonitoring(false);
      } else {
        await window.electronAPI.monitor.start({
          interval: 5000,
          enableWindows: true,
          enableChrome: true
        });
        setIsMonitoring(true);
      }
    } catch (error) {
      console.error('切换监控状态失败:', error);
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>仪表板</h2>
        <button
          className={`btn ${isMonitoring ? 'btn-danger' : 'btn-success'}`}
          onClick={toggleMonitoring}
        >
          {isMonitoring ? '停止监控' : '开始监控'}
        </button>
      </div>

      <div className="dashboard-grid">
        {/* 统计卡片 */}
        <div className="card stat-card">
          <h3 className="card-title">今日专注时长</h3>
          <div className="stat-value">{formatTime(stats.todayFocusTime)}</div>
          <div className="stat-label">小时</div>
        </div>

        <div className="card stat-card">
          <h3 className="card-title">活动记录</h3>
          <div className="stat-value">{stats.totalActivities}</div>
          <div className="stat-label">条</div>
        </div>

        <div className="card stat-card">
          <h3 className="card-title">分心次数</h3>
          <div className="stat-value">{stats.distractionCount}</div>
          <div className="stat-label">次</div>
        </div>

        {/* 当前活动 */}
        <div className="card activity-card">
          <h3 className="card-title">当前活动</h3>
          {currentActivity ? (
            <div className="activity-info">
              <div className="activity-type">{getActivityTypeText(currentActivity.type)}</div>
              <div className="activity-details">
                {currentActivity.type === 'browser' ? (
                  <>
                    <div className="activity-name">{currentActivity.data.url}</div>
                    <div className="activity-meta">{currentActivity.data.title}</div>
                  </>
                ) : (
                  <>
                    <div className="activity-name">{currentActivity.data.appName}</div>
                    <div className="activity-meta">{currentActivity.data.windowTitle}</div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-text">暂无活动记录</div>
              <div className="empty-state-subtext">
                {isMonitoring ? '正在监控中...' : '请先开始监控'}
              </div>
            </div>
          )}
        </div>

        {/* 最近活动列表 */}
        <div className="card recent-activities-card">
          <h3 className="card-title">最近活动</h3>
          <div className="empty-state">
            <div className="empty-state-text">暂无活动记录</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 辅助函数
function formatTime(milliseconds: number): string {
  const hours = Math.floor(milliseconds / (1000 * 60 * 60));
  const minutes = Math.floor((milliseconds % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${minutes}m`;
}

function getActivityTypeText(type: string): string {
  const types: Record<string, string> = {
    browser: '🌐 浏览器',
    application: '🖥️ 应用程序',
    system: '⚙️ 系统活动'
  };
  return types[type] || type;
}
