/**
 * 主应用组件
 */

import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';

// 导入页面组件
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';

// 导入类型
interface AppState {
  currentPage: 'dashboard' | 'settings';
  isMonitoring: boolean;
}

function App() {
  const [currentPage, setCurrentPage] = useState<AppState['currentPage']>('dashboard');
  const [isMonitoring, setIsMonitoring] = useState(false);

  useEffect(() => {
    // 检查监控状态
    // TODO: 从配置中加载
  }, []);

  return (
    <div className="app">
      {/* 顶部导航栏 */}
      <header className="app-header">
        <div className="app-title">
          <h1>🎯 FocusGuard</h1>
          <span className="subtitle">AI专注力监督工具</span>
        </div>

        <nav className="app-nav">
          <button
            className={currentPage === 'dashboard' ? 'active' : ''}
            onClick={() => setCurrentPage('dashboard')}
          >
            仪表板
          </button>
          <button
            className={currentPage === 'settings' ? 'active' : ''}
            onClick={() => setCurrentPage('settings')}
          >
            设置
          </button>
        </nav>

        <div className="app-status">
          <span className={`status-indicator ${isMonitoring ? 'active' : 'inactive'}`}>
            {isMonitoring ? '● 监控中' : '○ 已暂停'}
          </span>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="app-main">
        {currentPage === 'dashboard' && <Dashboard />}
        {currentPage === 'settings' && <Settings />}
      </main>

      {/* 干预对话框（条件渲染） */}
      {/* <InterventionDialog /> */}
    </div>
  );
}

export default App;
