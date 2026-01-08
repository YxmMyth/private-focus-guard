/**
 * 设置页面
 */

import { useState, useEffect } from 'react';

interface SettingsProps {}

interface AppConfig {
  llmProvider: string;
  llmModel: string;
  llmApiKey: string;
  monitoringEnabled: boolean;
  monitoringInterval: number;
  notificationEnabled: boolean;
  autoStart: boolean;
}

export default function Settings({}: SettingsProps) {
  const [config, setConfig] = useState<AppConfig>({
    llmProvider: 'hunyuan',
    llmModel: 'hunyuan-lite',
    llmApiKey: '',
    monitoringEnabled: false,
    monitoringInterval: 3000,
    notificationEnabled: true,
    autoStart: false
  });

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      // TODO: 从数据库加载配置
      // const loadedConfig = await window.api.config.loadAppConfig();
      // setConfig(loadedConfig);
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      // TODO: 保存配置到数据库
      // await window.api.config.saveAppConfig(config);
      setTimeout(() => {
        setSaving(false);
        // 显示保存成功提示
      }, 500);
    } catch (error) {
      console.error('保存配置失败:', error);
      setSaving(false);
    }
  };

  const handleInputChange = (field: keyof AppConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <div className="settings">
      <div className="settings-header">
        <h2>设置</h2>
        <button className="btn btn-primary" onClick={saveConfig} disabled={saving}>
          {saving ? '保存中...' : '保存设置'}
        </button>
      </div>

      <div className="settings-content">
        {/* LLM配置 */}
        <div className="card">
          <h3 className="card-title">AI模型配置</h3>

          <div className="form-group">
            <label>LLM提供商</label>
            <select
              value={config.llmProvider}
              onChange={e => handleInputChange('llmProvider', e.target.value)}
            >
              <option value="hunyuan">腾讯混元</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (本地)</option>
            </select>
            <div className="form-help">
              目前仅支持腾讯混元lite（免费）
            </div>
          </div>

          <div className="form-group">
            <label>模型名称</label>
            <select
              value={config.llmModel}
              onChange={e => handleInputChange('llmModel', e.target.value)}
            >
              <option value="hunyuan-lite">hunyuan-lite (免费)</option>
              <option value="hunyuan-standard">hunyuan-standard</option>
              <option value="hunyuan-pro">hunyuan-pro</option>
            </select>
          </div>

          <div className="form-group">
            <label>API密钥</label>
            <input
              type="password"
              value={config.llmApiKey}
              onChange={e => handleInputChange('llmApiKey', e.target.value)}
              placeholder="请输入腾讯云API密钥"
            />
            <div className="form-help">
              访问腾讯云控制台获取API密钥：
              <a
                href="https://console.cloud.tencent.com/cam/capi"
                target="_blank"
                rel="noopener noreferrer"
              >
                获取密钥
              </a>
            </div>
          </div>
        </div>

        {/* 监控配置 */}
        <div className="card">
          <h3 className="card-title">监控配置</h3>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={config.monitoringEnabled}
                onChange={e => handleInputChange('monitoringEnabled', e.target.checked)}
              />
              <span>启用监控</span>
            </label>
            <div className="form-help">
              启用后将自动监控您的活动
            </div>
          </div>

          <div className="form-group">
            <label>监控间隔（毫秒）</label>
            <input
              type="number"
              value={config.monitoringInterval}
              onChange={e => handleInputChange('monitoringInterval', parseInt(e.target.value))}
              min="1000"
              max="10000"
              step="500"
            />
            <div className="form-help">
              建议设置为3000ms（3秒），过短可能影响性能
            </div>
          </div>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={config.autoStart}
                onChange={e => handleInputChange('autoStart', e.target.checked)}
              />
              <span>开机自动启动</span>
            </label>
            <div className="form-help">
              系统启动时自动开始监控
            </div>
          </div>
        </div>

        {/* 通知配置 */}
        <div className="card">
          <h3 className="card-title">通知配置</h3>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={config.notificationEnabled}
                onChange={e => handleInputChange('notificationEnabled', e.target.checked)}
              />
              <span>启用通知</span>
            </label>
            <div className="form-help">
              检测到分心活动时显示通知
            </div>
          </div>
        </div>

        {/* 数据管理 */}
        <div className="card">
          <h3 className="card-title">数据管理</h3>

          <div className="form-group">
            <p className="text-secondary">
              所有数据存储在本地SQLite数据库中。
            </p>
          </div>

          <button
            className="btn btn-danger"
            onClick={() => {
              if (confirm('确定要清空所有数据吗？此操作不可撤销。')) {
                // TODO: 清空数据库
                console.log('清空数据库');
              }
            }}
          >
            清空所有数据
          </button>
        </div>
      </div>
    </div>
  );
}
