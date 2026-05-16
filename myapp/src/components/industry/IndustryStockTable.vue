<template>
  <div class="stock-table-section">
    <div class="table-header">
      <h3 class="section-title">相关个股 / 外部候选</h3>
      <div class="table-filters">
        <label class="filter-item">
          <input v-model="localVerifiedOnly" type="checkbox" />
          <span>只看已验证</span>
        </label>
        <label class="filter-item">
          <input v-model="localIncludeCandidates" type="checkbox" />
          <span>显示外部候选</span>
        </label>
        <select v-model="localSortBy" class="sort-select">
          <option value="final_score">按正宗性排序</option>
          <option value="hot_score">按热度排序</option>
          <option value="pct_chg">按今日涨幅排序</option>
          <option value="amount">按成交额排序</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <i class="fas fa-spinner fa-spin"></i>
      <span>加载中...</span>
    </div>

    <div v-else-if="message" class="empty-message">
      <i class="fas fa-info-circle"></i>
      <span>{{ message }}</span>
    </div>

    <div v-else-if="stocks.length === 0" class="empty-message">
      <i class="fas fa-info-circle"></i>
      <span>暂无本地公司证据。请维护 knowledge/stock_concept_mapping.csv 或 knowledge/data_sources/company_evidence.csv 后查看映射。</span>
    </div>

    <div v-else class="table-wrapper">
      <table class="stock-table">
        <thead>
          <tr>
            <th>股票代码</th>
            <th>股票名称</th>
            <th>来源</th>
            <th>状态</th>
            <th>正宗性评分</th>
            <th>今日涨幅</th>
            <th>成交额</th>
            <th>证据类型</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="stock in stocks"
            :key="stock.symbol"
            :class="{ candidate: stock.is_candidate, verified: stock.is_verified }"
          >
            <td>{{ stock.symbol }}</td>
            <td>{{ stock.stock_name }}</td>
            <td>
              <span class="source-tag" :class="stock.is_verified ? 'verified' : 'candidate'">
                {{ stock.is_verified ? '本地' : stock.source }}
              </span>
            </td>
            <td>
              <span class="status-tag" :class="stock.is_verified ? 'verified' : 'candidate'">
                {{ stock.is_verified ? '已验证' : '外部候选' }}
              </span>
            </td>
            <td>
              <span class="score" :class="getScoreClass(stock.final_score)">
                {{ stock.final_score > 0 ? stock.final_score.toFixed(4) : '—' }}
              </span>
            </td>
            <td :class="getChangeClass(stock.pct_chg)">
              {{ stock.pct_chg !== null && stock.pct_chg !== undefined ? stock.pct_chg.toFixed(2) + '%' : '—' }}
            </td>
            <td>{{ formatAmount(stock.amount) }}</td>
            <td>{{ stock.evidence_type || '—' }}</td>
            <td>{{ stock.updated_at || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ChainStock } from '@/api/industryChain';

interface Props {
  stocks: ChainStock[];
  message: string;
  loading: boolean;
  includeCandidates: boolean;
  verifiedOnly: boolean;
  sortBy: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:includeCandidates', value: boolean): void;
  (e: 'update:verifiedOnly', value: boolean): void;
  (e: 'update:sortBy', value: string): void;
}>();

const localIncludeCandidates = computed({
  get: () => props.includeCandidates,
  set: (val) => emit('update:includeCandidates', val),
});

const localVerifiedOnly = computed({
  get: () => props.verifiedOnly,
  set: (val) => emit('update:verifiedOnly', val),
});

const localSortBy = computed({
  get: () => props.sortBy,
  set: (val) => emit('update:sortBy', val),
});

function getScoreClass(score: number): string {
  if (score >= 0.8) return 'high';
  if (score >= 0.6) return 'medium';
  if (score >= 0.4) return 'low';
  return 'none';
}

function getChangeClass(pct: number | null): string {
  if (pct === null || pct === undefined) return '';
  if (pct > 0) return 'up';
  if (pct < 0) return 'down';
  return '';
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return '—';
  if (amount >= 1e8) {
    return (amount / 1e8).toFixed(2) + '亿';
  }
  if (amount >= 1e4) {
    return (amount / 1e4).toFixed(2) + '万';
  }
  return amount.toFixed(2);
}
</script>

<style scoped>
.stock-table-section {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 8px;
  background: #0f172a;
}

.table-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  color: #f8fafc;
}

.table-filters {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
}

.filter-item input {
  cursor: pointer;
}

.sort-select {
  padding: 4px 8px;
  border: 1px solid #334155;
  border-radius: 4px;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 12px;
}

.loading,
.empty-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  border: 1px dashed #334155;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  color: #94a3b8;
  font-size: 14px;
  text-align: center;
}

.table-wrapper {
  overflow-x: auto;
}

.stock-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.stock-table th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 500;
  color: #64748b;
  border-bottom: 1px solid #1e293b;
  white-space: nowrap;
}

.stock-table td {
  padding: 10px 12px;
  color: #e2e8f0;
  border-bottom: 1px solid #0f172a;
  white-space: nowrap;
}

.stock-table tr:hover td {
  background: #0f172a;
}

.stock-table tr.candidate td {
  opacity: 0.85;
}

.source-tag,
.status-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.source-tag.verified,
.status-tag.verified {
  background: #064e3b;
  color: #34d399;
}

.source-tag.candidate,
.status-tag.candidate {
  background: #451a03;
  color: #fbbf24;
}

.score {
  font-weight: 500;
}

.score.high {
  color: #22c55e;
}

.score.medium {
  color: #f59e0b;
}

.score.low {
  color: #ef4444;
}

.score.none {
  color: #64748b;
}

.up {
  color: #ef4444;
}

.down {
  color: #22c55e;
}
</style>
