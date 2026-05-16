<template>
  <aside class="node-panel">
    <div v-if="!node" class="empty-panel">
      <i class="fas fa-mouse-pointer"></i>
      <p>默认节点加载中...</p>
    </div>

    <div v-else-if="loading" class="loading-panel">
      <i class="fas fa-spinner fa-spin"></i>
      <p>加载节点详情...</p>
    </div>

    <div v-else class="panel-content">
      <div class="panel-header">
        <div>
          <h3>{{ node.name }}</h3>
          <p>{{ layerName }}</p>
        </div>
        <span class="node-type">{{ nodeType }}</span>
      </div>

      <div v-if="hotScoreSource" class="demo-note">
        {{ hotScoreSource }}仅用于缺数据时的展示高亮，不代表真实行情。
      </div>

      <section class="panel-section">
        <div class="section-title">简介</div>
        <div class="section-value description">{{ description }}</div>
      </section>

      <section class="panel-section">
        <div class="section-title">关键词</div>
        <div v-if="keywords.length" class="keywords">
          <span v-for="kw in keywords" :key="kw" class="keyword-tag">{{ kw }}</span>
        </div>
        <div v-else class="empty-line">暂无关键词</div>
      </section>

      <section class="panel-section">
        <div class="section-title">上游节点</div>
        <div v-if="upstream.length" class="node-links">
          <span v-for="item in upstream" :key="item.id" class="node-link">{{ item.name }}</span>
        </div>
        <div v-else class="empty-line">暂无上游节点</div>
      </section>

      <section class="panel-section">
        <div class="section-title">下游节点</div>
        <div v-if="downstream.length" class="node-links">
          <span v-for="item in downstream" :key="item.id" class="node-link">{{ item.name }}</span>
        </div>
        <div v-else class="empty-line">暂无下游节点</div>
      </section>

      <section class="panel-section">
        <div class="section-title">数据状态</div>
        <div class="metrics-grid">
          <div class="metric">
            <span class="metric-label">相关股票数量</span>
            <span class="metric-value">{{ stockCount }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">本地映射</span>
            <span class="metric-value">{{ stockCount > 0 ? '已加载' : '暂无' }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">行情确认</span>
            <span class="metric-value">{{ hasMarketData ? '已加载' : '暂无' }}</span>
          </div>
        </div>
        <div v-if="stockCount === 0" class="empty-line strong">暂无已验证公司映射</div>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ChainNode, NodeDetail } from '@/api/industryChain';

interface Props {
  node: ChainNode | null;
  nodeDetail: NodeDetail | null;
  loading: boolean;
}

const props = defineProps<Props>();

const detailNode = computed(() => props.nodeDetail?.node);
const nodeType = computed(() => detailNode.value?.type || props.node?.type || '节点');
const layerName = computed(() => detailNode.value?.layer_name || props.node?.layer_name || props.node?.layer || '暂无层级');
const description = computed(() => detailNode.value?.description || props.node?.description || '暂无描述');
const keywords = computed(() => detailNode.value?.keywords?.length ? detailNode.value.keywords : props.node?.keywords || []);
const upstream = computed(() => props.nodeDetail?.upstream || []);
const downstream = computed(() => props.nodeDetail?.downstream || []);
const stockCount = computed(() => props.nodeDetail?.stock_count ?? props.node?.stock_count ?? 0);
const hotScoreSource = computed(() => props.nodeDetail?.metrics?.hot_score_source || props.node?.hot_score_source || '');
const hasMarketData = computed(() => {
  const metrics = props.nodeDetail?.metrics || {};
  return Boolean(metrics.trade_date || metrics.avg_return_1d || metrics.total_amount || metrics.limit_up_count);
});
</script>

<style scoped>
.node-panel {
  min-height: 640px;
  max-height: 760px;
  overflow-y: auto;
  padding: 18px;
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 8px;
  background: #0f172a;
}

.empty-panel,
.loading-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  gap: 10px;
  color: #64748b;
  font-size: 14px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #1e293b;
}

.panel-header h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 20px;
  line-height: 1.25;
}

.panel-header p {
  margin: 5px 0 0;
  color: #94a3b8;
  font-size: 12px;
}

.node-type {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 6px;
  background: #1e293b;
  color: #cbd5e1;
  font-size: 11px;
}

.demo-note {
  margin-bottom: 14px;
  padding: 9px 10px;
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 6px;
  background: rgba(69, 26, 3, 0.25);
  color: #fbbf24;
  font-size: 12px;
  line-height: 1.5;
}

.panel-section {
  margin-bottom: 18px;
}

.section-title {
  margin-bottom: 7px;
  color: #64748b;
  font-size: 12px;
}

.section-value {
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.55;
}

.description {
  color: #cbd5e1;
}

.keywords,
.node-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-tag,
.node-link {
  padding: 4px 8px;
  border-radius: 6px;
  background: #1e293b;
  color: #cbd5e1;
  font-size: 12px;
}

.node-link {
  color: #67e8f9;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 9px;
  border-radius: 6px;
  background: #111827;
}

.metric-label {
  color: #64748b;
  font-size: 11px;
}

.metric-value {
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 650;
}

.empty-line {
  color: #94a3b8;
  font-size: 12px;
}

.empty-line.strong {
  margin-top: 10px;
  color: #fbbf24;
}
</style>
