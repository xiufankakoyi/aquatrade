<template>
  <div class="data-source-bar">
    <div v-if="loading" class="bar-loading">
      <i class="fas fa-spinner fa-spin"></i>
      <span>检查数据状态...</span>
    </div>

    <div v-else class="bar-content">
      <div class="status-item ok">
        <i class="fas fa-sitemap"></i>
        <span>产业链结构：{{ structureLoaded ? '已加载' : '暂无' }}</span>
      </div>
      <div class="status-item" :class="autoDataLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-database"></i>
        <span>自动更新：{{ autoDataLoaded ? '已生成' : '未运行' }}</span>
      </div>
      <div class="status-item" :class="marketLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-chart-line"></i>
        <span>行情快照：{{ marketLoaded ? '已加载' : '暂无' }}</span>
      </div>
      <div class="status-item" :class="candidateLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-layer-group"></i>
        <span>节点候选：{{ candidateLoaded ? '已生成' : '暂无' }}</span>
      </div>
      <div class="status-item neutral">
        <i class="fas fa-clock"></i>
        <span>更新时间：{{ status?.last_sync || '暂无' }}</span>
      </div>
      <div class="status-item neutral">
        <i class="fas fa-plug"></i>
        <span>数据源：{{ providerNames }}</span>
      </div>
      <div v-if="usingFallback" class="status-item warn">
        <i class="fas fa-exclamation-circle"></i>
        <span>当前使用内置结构示例</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { DataSourceStatus } from '@/api/industryChain';

interface Props {
  status: DataSourceStatus | null;
  loading: boolean;
  structureLoaded: boolean;
  usingFallback: boolean;
}

const props = defineProps<Props>();

const autoDataLoaded = computed(() => Boolean(props.status?.parquet_files?.industry_node_metrics));
const candidateLoaded = computed(() => Boolean(props.status?.parquet_files?.industry_node_candidates));
const marketLoaded = computed(() => Boolean(props.status?.parquet_files?.market_snapshot));
const providerNames = computed(() => {
  const providers = props.status?.providers || {};
  const names = Object.entries(providers)
    .filter(([, value]) => value?.available)
    .map(([name]) => name);
  return names.length ? names.join(' / ') : '暂无可用外部源';
});
</script>

<style scoped>
.data-source-bar {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 8px;
  background: #0f172a;
}

.bar-loading,
.bar-content {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.bar-loading {
  color: #64748b;
  font-size: 13px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.8);
  color: #94a3b8;
  font-size: 12px;
}

.status-item.ok {
  background: rgba(6, 78, 59, 0.32);
  color: #34d399;
}

.status-item.neutral {
  background: rgba(51, 65, 85, 0.36);
  color: #cbd5e1;
}

.status-item.warn {
  background: rgba(69, 26, 3, 0.42);
  color: #fbbf24;
}
</style>
