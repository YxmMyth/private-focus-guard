/**
 * 配置初始化脚本
 *
 * 在数据库中预配置腾讯云 API 密钥
 * 运行: node scripts/init-config.js
 */

const Database = require('better-sqlite3');
const path = require('path');
const app = require('electron').app;

// 数据库路径
const DB_PATH = path.join(__dirname, '../focus-guard.db');

// 配置数据
const CONFIGS = [
  {
    key: 'tencent_secret_id',
    value: 'AKID41m9PSIvOjtqaBcrumU0KURUUKzSilbE'
  },
  {
    key: 'tencent_secret_key',
    value: 'UlpijdKtFPYlxypWDtwr5DH8mCPQEzd4'
  },
  {
    key: 'monitoring_interval',
    value: '5000'
  },
  {
    key: 'llm_model',
    value: 'hunyuan-lite'
  }
];

console.log('🔧 开始配置数据库...\n');

try {
  // 打开数据库
  const db = new Database(DB_PATH);

  // 创建配置表（如果不存在）
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    )
  `);

  // 插入或更新配置
  const insert = db.prepare(`
    INSERT INTO config (key, value, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET
      value = excluded.value,
      updated_at = excluded.updated_at
  `);

  const now = Date.now();

  CONFIGS.forEach(config => {
    const result = insert.run(config.key, config.value, now);
    console.log(`✅ ${config.key}: ${config.value.substring(0, 20)}...`);
  });

  // 验证配置
  console.log('\n📊 验证配置:\n');

  const rows = db.prepare('SELECT key, value FROM config').all();
  rows.forEach(row => {
    const value = row.key.includes('secret')
      ? `${row.value.substring(0, 10)}...`
      : row.value;
    console.log(`  ${row.key}: ${value}`);
  });

  db.close();

  console.log('\n✅ 配置完成！');
  console.log('\n⚠️  安全提示：');
  console.log('  - API 密钥已存储在本地数据库中');
  console.log('  - 不要将 focus-guard.db 提交到 Git 仓库');
  console.log('  - 建议将 focus-guard.db 添加到 .gitignore');

} catch (error) {
  console.error('❌ 配置失败:', error.message);
  process.exit(1);
}
