<template>
  <div>
    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <h2 class="text-xl font-semibold text-white mb-4">历史记录</h2>
      <EmptyState
        v-if="historySessions.length === 0"
        title="暂无历史记录"
        description="尚未完成可保存的回测"
      />
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-800/50">
            <tr>
              <th class="px-4 py-3 text-left text-slate-400 font-semibold">时间</th>
              <th class="px-4 py-3 text-left text-slate-400 font-semibold">策略名</th>
              <th class="px-4 py-3 text-left text-slate-400 font-semibold">参数版本</th>
              <th class="px-4 py-3 text-right text-slate-400 font-semibold">收益率</th>
              <th class="px-4 py-3 text-right text-slate-400 font-semibold">最大回撤</th>
              <th class="px-4 py-3 text-right text-slate-400 font-semibold">夏普比率</th>
              <th class="px-4 py-3 text-center text-slate-400 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="session in historySessions"
              :key="session.id"
              class="border-b border-slate-800 hover:bg-slate-800/30 transition-colors"
            >
              <td class="px-4 py-3 text-slate-300">{{ formatDate(session.createdAt) }}</td>
              <td class="px-4 py-3 text-white font-medium">{{ session.name }}</td>
              <td class="px-4 py-3 text-slate-400">{{ session.version || 'v1.2.4' }}</td>
              <td
                class="px-4 py-3 text-right font-medium"
                :class="(session.summary?.totalReturn ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'"
              >
                {{ (session.summary?.totalReturn ?? 0) >= 0 ? '+' : '' }}{{ (session.summary?.totalReturn ?? 0).toFixed(2) }}%
              </td>
              <td class="px-4 py-3 text-right text-red-400">
                -{{ Math.abs(session.summary?.maxDrawdown ?? 0).toFixed(2) }}%
              </td>
              <td class="px-4 py-3 text-right text-slate-300">
                {{ (session.summary?.metrics?.sharpeRatio ?? 0).toFixed(2) }}
              </td>
              <td class="px-4 py-3 text-center">
                <button
                  @click="viewSession(session)"
                  class="px-3 py-1 bg-indigo-500 hover:bg-indigo-600 text-white rounded text-xs font-medium transition-colors"
                >
                  查看
                </button>
              </td>
            </tr>
            <tr v-if="historySessions.length === 0">
              <td colspan="7" class="px-4 py-8 text-center text-slate-500">暂无历史记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useHistoryStore } from '../store/historyStore';
import { useStrategyStore } from '../store/strategyStore';
import type { StrategySession } from '../types/backtest';
import EmptyState from '../components/common/EmptyState.vue';

const router = useRouter();
const historyStore = useHistoryStore();
const strategyStore = useStrategyStore();

const historySessions = computed(() => {
  if (historyStore.records.length > 0) {
    return historyStore.paginatedRecords.map(record => ({
      id: record.id,
      strategyId: record.id,
      name: record.strategyName,
      createdAt: record.createdAt,
      updatedAt: record.createdAt,
      version: 'v1.2.4',
      summary: {
        id: record.id,
        strategyName: record.strategyName,
        date: record.dateRange,
        createdAt: record.createdAt,
        status: record.status,
        metrics: record.metrics,
        totalReturn: record.metrics?.totalReturn,
        annualizedReturn: record.metrics?.annualizedReturn,
        maxDrawdown: record.metrics?.maxDrawdown,
      }
    } as StrategySession));
  }
  
  const sessions: StrategySession[] = [];
  const sessionsMap = strategyStore.strategySessions || {};
  Object.values(sessionsMap).forEach((strategySessions: StrategySession[]) => {
    sessions.push(...strategySessions);
  });
  return sessions.sort((a, b) => {
    const dateA = new Date(a.createdAt).getTime();
    const dateB = new Date(b.createdAt).getTime();
    return dateB - dateA;
  });
});

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function viewSession(session: StrategySession) {
  historyStore.selectRecord({
    id: session.id,
    strategyName: session.name,
    dateRange: session.summary.date || '',
    createdAt: session.createdAt,
    status: session.summary.status || 'completed',
    metrics: session.summary.metrics,
  });
  router.push(`/strategy/${session.strategyId}`);
}
</script>

