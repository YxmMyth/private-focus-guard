/**
 * 服务初始化
 *
 * 作用：
 * 1. 初始化 LLM 适配器
 * 2. 配置专注守卫服务
 * 3. 从数据库加载配置
 */

import { DatabaseManager } from '../../storage/database';
import { ConfigRepository } from '../../storage/repositories';
import { createHunyuanAdapter } from '../../services/llm/hunyuan';
import { focusGuardService } from '../../services/focus-guard';

/**
 * 初始化所有服务
 */
export async function initializeServices(): Promise<void> {
  console.log('[Services] 开始初始化服务...');

  try {
    // 1. 获取数据库实例
    const db = DatabaseManager.getInstance();
    const configRepo = new ConfigRepository(db);

    // 2. 从数据库加载腾讯云 API 密钥
    const secretId = configRepo.get('tencent_secret_id');
    const secretKey = configRepo.get('tencent_secret_key');

    // 3. 如果配置了密钥，初始化 LLM 适配器
    if (secretId && secretKey) {
      console.log('[Services] 检测到腾讯云 API 密钥，正在初始化 LLM 适配器...');

      try {
        const llmAdapter = createHunyuanAdapter({
          secretId,
          secretKey,
          region: 'ap-guangzhou' // 默认区域
        });

        // 测试连接
        const isConnected = await llmAdapter.testConnection();

        if (isConnected) {
          console.log('[Services] ✅ 腾讯混元 LLM 适配器初始化成功');
          focusGuardService.setLLMAdapter(llmAdapter);
        } else {
          console.warn('[Services] ⚠️ 腾讯混元连接测试失败，请检查密钥');
        }
      } catch (error) {
        console.error('[Services] ❌ LLM 适配器初始化失败:', error);
      }
    } else {
      console.log('[Services] 未配置腾讯云 API 密钥，跳过 LLM 初始化');
      console.log('[Services] 提示：请在 Settings 页面配置密钥');
    }

    // 4. 加载专注目标（如果有）
    // TODO: 从数据库加载专注目标
    const goalsJson = configRepo.get('focus_goals');
    if (goalsJson) {
      try {
        const goals = JSON.parse(goalsJson);
        focusGuardService.setFocusGoals(goals);
        console.log(`[Services] 已加载 ${goals.length} 个专注目标`);
      } catch (error) {
        console.error('[Services] 加载专注目标失败:', error);
      }
    }

    console.log('[Services] ✅ 服务初始化完成');
  } catch (error) {
    console.error('[Services] ❌ 服务初始化失败:', error);
    // 不抛出异常，允许应用继续运行
  }
}

/**
 * 重新初始化 LLM 适配器
 *
 * 用于用户更新 API 密钥后重新初始化
 */
export async function reinitializeLLM(): Promise<boolean> {
  try {
    const db = DatabaseManager.getInstance();
    const configRepo = new ConfigRepository(db);

    const secretId = configRepo.get('tencent_secret_id');
    const secretKey = configRepo.get('tencent_secret_key');

    if (!secretId || !secretKey) {
      console.warn('[Services] 缺少 API 密钥');
      return false;
    }

    const llmAdapter = createHunyuanAdapter({
      secretId,
      secretKey,
      region: 'ap-guangzhou'
    });

    const isConnected = await llmAdapter.testConnection();

    if (isConnected) {
      focusGuardService.setLLMAdapter(llmAdapter);
      console.log('[Services] ✅ LLM 适配器重新初始化成功');
      return true;
    } else {
      console.warn('[Services] ⚠️ LLM 连接测试失败');
      return false;
    }
  } catch (error) {
    console.error('[Services] ❌ LLM 适配器重新初始化失败:', error);
    return false;
  }
}
