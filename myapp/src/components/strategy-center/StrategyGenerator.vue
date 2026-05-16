<template>
  <div class="strategy-generator">
    <!-- 主内容区 -->
    <div class="generator-content">
      <!-- 输入区域 -->
      <div class="input-section">
        <div class="form-group">
          <label for="strategy-name">策略名称</label>
          <input
            id="strategy-name"
            v-model="strategyName"
            type="text"
            placeholder="例如：AI双均线策略"
            class="form-input"
          />
        </div>

        <div class="form-group">
          <label for="strategy-description">策略描述</label>
          <textarea
            id="strategy-description"
            v-model="strategyDescription"
            placeholder="例如：写一个策略，当5日均线上穿20日均线时买入，下穿时卖出。"
            class="form-textarea"
            rows="6"
          ></textarea>
          <div class="hint">
            <p>💡 提示：</p>
            <ul>
              <li>描述要清晰具体，包含买入和卖出条件</li>
              <li>可以指定使用的技术指标（如 MA、RSI、MACD 等）</li>
              <li>可以指定持仓天数、止损止盈等规则</li>
            </ul>
            <div class="examples">
              <p><strong>示例：</strong></p>
              <ul>
                <li>"股价突破20日均线买入，RSI大于70卖出，最多持仓5天"</li>
                <li>"当5日均线上穿20日均线时买入，下穿时卖出"</li>
                <li>"RSI小于30买入，大于70卖出，亏损超过10%止损"</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="form-actions">
          <button
            @click="generateStrategy"
            :disabled="isGenerating || !canGenerate"
            class="btn-primary"
          >
            <span v-if="isGenerating">生成中...</span>
            <span v-else>🤖 生成策略</span>
          </button>
          <button
            @click="clearForm"
            :disabled="isGenerating"
            class="btn-secondary"
          >
            清空
          </button>
        </div>
      </div>

      <!-- 结果区域 -->
      <div class="result-section" v-if="result || error">
        <div v-if="error" class="error-message">
          <h3>❌ 生成失败</h3>
          <p>{{ error }}</p>
        </div>

        <div v-if="result" class="success-message">
          <h3>✅ 策略生成成功</h3>
          <div class="result-info">
            <p><strong>文件名：</strong>{{ result.filename }}</p>
            <p><strong>消息：</strong>{{ result.message }}</p>
          </div>
          <div class="result-actions">
            <button @click="reloadStrategies" class="btn-reload" :disabled="isReloading">
              <span v-if="isReloading">加载中...</span>
              <span v-else>🔄 立即加载</span>
            </button>
            <button @click="viewStrategies" class="btn-primary">
              查看策略列表
            </button>
            <button @click="clearResult" class="btn-secondary">
              关闭
            </button>
          </div>
          <div v-if="reloadResult" class="reload-result">
            <p>{{ reloadResult.message }}</p>
            <p v-if="reloadResult.count">已发现 {{ reloadResult.count }} 个策略</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isGenerating" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>正在生成策略代码，请稍候...</p>
      <p class="loading-hint">这可能需要几秒钟到几十秒钟，取决于 LLM 服务的响应速度</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { apiService, ApiError } from '@/services/api';

const router = useRouter();

// 表单数据
const strategyName = ref('AI策略');
const strategyDescription = ref('');

// 状态
const isGenerating = ref(false);
const isReloading = ref(false);
const result = ref<{ filename: string; message: string } | null>(null);
const reloadResult = ref<{ message: string; count?: number } | null>(null);
const error = ref<string>('');

// 计算属性
const canGenerate = computed(() => {
  return strategyDescription.value.trim().length > 0;
});

// 生成策略
const generateStrategy = async () => {
  if (!canGenerate.value || isGenerating.value) {
    return;
  }

  isGenerating.value = true;
  error.value = '';
  result.value = null;

  try {
    const response = await apiService.generateStrategy(
      strategyDescription.value,
      strategyName.value || 'AI策略'
    );
    
    result.value = response;
  } catch (err) {
    if (err instanceof ApiError) {
      error.value = err.message;
    } else {
      error.value = '生成策略时发生未知错误';
    }
    console.error('生成策略失败:', err);
  } finally {
    isGenerating.value = false;
  }
};

// 清空表单
const clearForm = () => {
  strategyName.value = 'AI策略';
  strategyDescription.value = '';
  error.value = '';
  result.value = null;
};

// 清空结果
const clearResult = () => {
  result.value = null;
  error.value = '';
};

// 查看策略列表
const viewStrategies = () => {
  router.push('/dashboard');
};

// 立即加载策略
const reloadStrategies = async () => {
  isReloading.value = true;
  reloadResult.value = null;
  
  try {
    const response = await apiService.reloadStrategies({ refresh_all: true });
    reloadResult.value = {
      message: response.message,
      count: response.count,
    };
  } catch (err) {
    if (err instanceof ApiError) {
      error.value = err.message;
    } else {
      error.value = '加载策略时发生未知错误';
    }
    console.error('加载策略失败:', err);
  } finally {
    isReloading.value = false;
  }
};
</script>

<style scoped>
.strategy-generator {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.input-section {
  background: #131722;
  border-radius: 8px;
  padding: 24px;
  border: 1px solid #2a2e39;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #d1d4dc;
  font-size: 13px;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 12px;
  background: #0A0A0A;
  border: 1px solid #2a2e39;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: #d1d4dc;
  transition: border-color 0.2s;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: #2962ff;
}

.form-input::placeholder,
.form-textarea::placeholder {
  color: #787b86;
}

.form-textarea {
  resize: vertical;
  min-height: 120px;
}

.hint {
  margin-top: 12px;
  padding: 12px;
  background: #1a1a1a;
  border-radius: 4px;
  font-size: 12px;
  color: #787b86;
}

.hint p {
  margin: 0 0 8px 0;
  font-weight: 500;
  color: #d1d4dc;
}

.hint ul {
  margin: 8px 0;
  padding-left: 20px;
}

.hint li {
  margin-bottom: 4px;
}

.examples {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #2a2e39;
}

.examples ul {
  margin-top: 8px;
}

.examples li {
  margin-bottom: 8px;
  padding: 8px;
  background: #0A0A0A;
  border-left: 3px solid #2962ff;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #d1d4dc;
}

.form-actions {
  display: flex;
  gap: 12px;
}

.btn-primary,
.btn-secondary,
.btn-reload {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #2962ff;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #1e4bd8;
}

.btn-reload {
  background: #28a745;
  color: #fff;
}

.btn-reload:hover:not(:disabled) {
  background: #218838;
}

.btn-reload:disabled,
.btn-primary:disabled {
  background: #4a4a4a;
  cursor: not-allowed;
}

.btn-secondary {
  background: #2a2e39;
  color: #d1d4dc;
  border: 1px solid #3a3e49;
}

.btn-secondary:hover:not(:disabled) {
  background: #3a3e49;
}

.result-section {
  margin-top: 24px;
}

.error-message {
  background: rgba(255, 82, 82, 0.1);
  border: 1px solid rgba(255, 82, 82, 0.3);
  color: #ff5252;
  padding: 16px;
  border-radius: 4px;
}

.error-message h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.success-message {
  background: rgba(40, 167, 69, 0.1);
  border: 1px solid rgba(40, 167, 69, 0.3);
  color: #d1d4dc;
  padding: 16px;
  border-radius: 4px;
}

.success-message h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #28a745;
}

.result-info {
  margin-bottom: 16px;
}

.result-info p {
  margin: 4px 0;
  font-size: 13px;
}

.result-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.reload-result {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(40, 167, 69, 0.3);
  font-size: 13px;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 10, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #2a2e39;
  border-top-color: #2962ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-overlay p {
  color: #d1d4dc;
  font-size: 14px;
  margin: 4px 0;
}

.loading-hint {
  color: #787b86;
  font-size: 12px;
}
</style>
