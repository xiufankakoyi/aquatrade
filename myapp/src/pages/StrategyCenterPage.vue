<template>
  <div class="strategy-center-page">
    <!-- 顶部工具栏 -->
    <div class="center-header">
      <div class="header-left">
        <i class="fas fa-code text-[#2962ff] text-sm"></i>
        <span class="header-title">策略中心</span>
      </div>
      
      <!-- Tab 切换 -->
      <div class="tab-switcher">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <i :class="tab.icon"></i>
          <span>{{ tab.label }}</span>
        </button>
      </div>
      
      <div class="header-right">
        <span class="header-desc">{{ activeTabDesc }}</span>
      </div>
    </div>

    <div v-if="matrixCacheMissing" class="cache-warning">
      <span>回测缓存缺失，可点击重建</span>
      <button :disabled="cacheRebuilding" @click="rebuildMatrixCache">
        {{ cacheRebuilding ? '重建中' : '重建缓存' }}
      </button>
      <span v-if="cacheError" class="cache-error">{{ cacheError }}</span>
    </div>

    <!-- 内容区域 -->
    <div class="center-content">
      <!-- AI 策略生成器 -->
      <div v-show="activeTab === 'generator'" class="tab-panel">
        <StrategyGenerator />
      </div>

      <!-- 策略开发工作台 -->
      <div v-show="activeTab === 'editor'" class="tab-panel editor-panel">
        <StrategyWorkbench />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import StrategyGenerator from '../components/strategy-center/StrategyGenerator.vue';
import StrategyWorkbench from '../components/strategy-center/StrategyWorkbench.vue';

defineOptions({
  name: 'StrategyCenterPage'
});

// Tab 配置
const tabs = [
  { key: 'generator', label: 'AI 生成策略', icon: 'fas fa-robot', desc: '使用自然语言描述，让 AI 为您生成量化策略' },
  { key: 'editor', label: '代码编辑器', icon: 'fas fa-code', desc: '编写和调试您的量化策略代码' }
];

const activeTab = ref('generator');
const dataHealth = ref<any>(null);
const cacheRebuilding = ref(false);
const cacheError = ref('');
const matrixCacheMissing = computed(() => {
  const cache = dataHealth.value?.datasets?.find((item: any) => item.name === 'matrix_cache');
  return cache?.status === 'backtest_cache_missing';
});

const activeTabDesc = computed(() => {
  return tabs.find(t => t.key === activeTab.value)?.desc || '';
});

async function fetchJson(url: string, init?: RequestInit) {
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
  }
  return payload.data;
}

async function loadDataHealth() {
  dataHealth.value = await fetchJson('/api/data/health');
}

async function rebuildMatrixCache() {
  cacheRebuilding.value = true;
  cacheError.value = '';
  try {
    await fetchJson('/api/data/matrix-cache/rebuild', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    await loadDataHealth();
  } catch (error) {
    cacheError.value = error instanceof Error ? error.message : '回测缓存重建失败';
  } finally {
    cacheRebuilding.value = false;
  }
}

onMounted(() => {
  loadDataHealth().catch((error) => {
    cacheError.value = error instanceof Error ? error.message : '数据状态加载失败';
  });
});
</script>

<style scoped>
.strategy-center-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0A0A0A;
  color: #d1d4dc;
  overflow: hidden;
}

/* 顶部工具栏 */
.center-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  padding: 0 16px;
  background: #0A0A0A;
  border-bottom: 1px solid #2a2e39;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: #d1d4dc;
}

.header-right {
  min-width: 200px;
  text-align: right;
}

.header-desc {
  font-size: 11px;
  color: #787b86;
}

/* Tab 切换器 */
.tab-switcher {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #1a1a1a;
  padding: 3px;
  border-radius: 6px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  color: #787b86;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: #d1d4dc;
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: #fff;
  background: #2962ff;
}

.tab-btn i {
  font-size: 11px;
}

/* 内容区域 */
.center-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.cache-warning {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 16px;
  color: #f6c453;
  background: #2b2515;
  border-bottom: 1px solid #5b4a1c;
  font-size: 12px;
}

.cache-warning button {
  padding: 5px 10px;
  color: #fff;
  background: #8a6a16;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
}

.cache-warning button:disabled {
  opacity: .55;
  cursor: default;
}

.cache-error {
  color: #ff8a80;
}

.tab-panel {
  height: 100%;
  overflow: auto;
}

.editor-panel {
  overflow: hidden;
}
</style>
