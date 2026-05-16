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
      <div class="status-item" :class="localEvidenceLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-database"></i>
        <span>本地证据：{{ localEvidenceLoaded ? '已加载' : '暂无' }}</span>
      </div>
      <div class="status-item" :class="externalCandidatesLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-layer-group"></i>
        <span>外部候选：{{ externalCandidatesLoaded ? '已加载' : '暂无' }}</span>
      </div>
      <div class="status-item" :class="marketLoaded ? 'ok' : 'neutral'">
        <i class="fas fa-chart-line"></i>
        <span>行情确认：{{ marketLoaded ? '已加载' : '暂无' }}</span>
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

const localEvidenceLoaded = computed(() => {
  const manual = props.status?.manual_provider;
  const parquet = props.status?.parquet_files || {};
  return Boolean(manual?.evidence_exists || parquet.company_evidence);
});

const externalCandidatesLoaded = computed(() => Boolean(props.status?.parquet_files?.concept_members));
const marketLoaded = computed(() => Boolean(props.status?.parquet_files?.stock_market_snapshot || props.status?.parquet_files?.node_market_metrics));
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
