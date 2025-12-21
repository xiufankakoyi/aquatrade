<!--
  策略详情页面
  显示该版本的交易记录表格、K线图和防守仓模块
-->
<template>
  <div class="strategy-detail-page p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen">
    <!-- 页面标题和返回按钮 -->
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <button
          @click="$router.push('/dashboard')"
          class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:text-gray-900 dark:hover:text-slate-100 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
        >
          ← 返回 Dashboard
        </button>
        <h1 class="text-3xl font-bold text-gray-800 dark:text-slate-100">
          策略详情：{{ versionName }}
        </h1>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="text-center py-12">
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      <p class="mt-4 text-gray-600 dark:text-slate-400">加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- 主要内容 -->
    <div v-else-if="backtestResult" class="space-y-6">
      <!-- 关键指标卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4">
          <p class="text-sm text-gray-500 dark:text-slate-400 mb-1">总收益率</p>
          <p class="text-2xl font-bold" :class="backtestResult.metrics.totalReturn >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'">
            {{ formatPercent(backtestResult.metrics.totalReturn) }}
          </p>
        </div>
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4">
          <p class="text-sm text-gray-500 dark:text-slate-400 mb-1">期间收益</p>
          <p class="text-2xl font-bold" :class="backtestResult.metrics.annualizedReturn >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'">
            {{ formatPercent(backtestResult.metrics.annualizedReturn) }}
          </p>
        </div>
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4">
          <p class="text-sm text-gray-500 dark:text-slate-400 mb-1">最大回撤</p>
          <p class="text-2xl font-bold text-red-600 dark:text-red-400">
            {{ formatPercent(backtestResult.metrics.maxDrawdown) }}
          </p>
        </div>
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4">
          <p class="text-sm text-gray-500 dark:text-slate-400 mb-1">夏普比率</p>
          <p class="text-2xl font-bold text-gray-800 dark:text-slate-100">
            {{ backtestResult.metrics.sharpeRatio.toFixed(2) }}
          </p>
        </div>
      </div>

      <!-- 交易记录表格 -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">交易记录</h2>
        <ResultsTable
          :trades="backtestResult.trades || []"
          @trade-select="handleTradeSelect"
        />
      </div>

      <!-- K线图 -->
      <div v-if="selectedTrade" class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">
          K线图：{{ selectedTrade.symbol }}
        </h2>
        <div class="h-96">
          <EquityCurve
            :kline-data="klineData"
            :highlight-ranges="highlightRanges"
            mode="kline"
            :versions="[]"
            :benchmark="[]"
          />
        </div>
      </div>

      <!-- 防守仓模块 -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">防守仓仓位分析</h2>
        <PortfolioDefense
          :trades="backtestResult.trades || []"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { getStrategyDetail, getKlineData } from '../api/backtestApi';
import ResultsTable from '../components/ResultsTable.vue';
import PortfolioDefense from '../components/PortfolioDefense.vue';
import EquityCurve from '../components/EquityCurve.vue';
import type { Trade } from '../types/backtest';
import type { BacktestResult } from '../store/strategyStore';

interface Props {
  versionId: string;
}

const props = defineProps<Props>();
const route = useRoute();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();

// 状态
const selectedTrade = ref<Trade | null>(null);
const klineData = ref<any[]>([]);
const highlightRanges = ref<Array<{ start: string; end: string }>>([]);

// 从 store 获取数据
const isLoading = computed(() => strategyStore.isLoading);
const error = computed(() => strategyStore.error);

// CHANGED: 优先从 backtestStore 获取数据（流式回测的数据保存在这里）
// 如果 backtestStore 有数据，使用它；否则使用 strategyStore 的数据
const backtestResult = computed<BacktestResult | null>(() => {
  // 如果 backtestStore 有交易记录，说明有回测数据
  if (backtestStore.trades.length > 0 || backtestStore.equitySeries.length > 0) {
    return {
      versionId: props.versionId,
      metrics: backtestStore.metrics || {
        totalReturn: 0,
        annualizedReturn: 0,
        maxDrawdown: 0,
        sharpeRatio: 0,
        winRate: 0,
        tradesCount: 0,
        profitFactor: 0,
        volatility: 0,
        sortinoRatio: 0,
        avgTradeReturn: 0,
        maxWinningStreak: 0,
        maxLosingStreak: 0
      },
      equityCurve: backtestStore.equitySeries.map(item => ({
        date: item.date,
        equity: item.equity,
        benchmarkEquity: backtestStore.benchmarkEquitySeries.find(b => b.date === item.date)?.equity
      })),
      monthlyReturns: backtestStore.monthlyReturns,
      trades: backtestStore.trades
    };
  }
  // 否则使用 strategyStore 的数据
  return strategyStore.currentBacktestResult;
});

// 版本名称
const versionName = computed(() => {
  const version = strategyStore.availableVersions.find(v => v.id === props.versionId);
  return version?.name || props.versionId;
});

// 格式化百分比
function formatPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

// 处理交易选择
async function handleTradeSelect(trade: Trade) {
  selectedTrade.value = trade;
  
  // 加载 K 线数据
  if (trade.symbolCode || trade.symbol) {
    try {
      const symbolCode = trade.symbolCode || trade.symbol;
      const startDate = trade.entryDate || '2024-01-01';
      const endDate = trade.exitDate || '2025-01-01';
      
      const kline = await getKlineData(symbolCode, startDate, endDate);
      klineData.value = kline;
      
      // 设置高亮范围
      if (trade.entryDate && trade.exitDate) {
        highlightRanges.value = [{
          start: trade.entryDate,
          end: trade.exitDate
        }];
      }
    } catch (err) {
      console.error('加载 K 线数据失败:', err);
    }
  }
}

// 加载策略详情
async function loadStrategyDetail() {
  try {
    strategyStore.setLoading(true);
    strategyStore.setError(null);
    
    const result = await getStrategyDetail(props.versionId);
    strategyStore.setCurrentBacktestResult(result);
    strategyStore.setCurrentVersion(props.versionId);
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : '加载策略详情失败';
    strategyStore.setError(errorMessage);
    console.error('加载策略详情失败:', err);
  } finally {
    strategyStore.setLoading(false);
  }
}

// 监听版本 ID 变化
watch(() => props.versionId, (newVersionId) => {
  if (newVersionId) {
    loadStrategyDetail();
  }
}, { immediate: true });

onMounted(() => {
  // CHANGED: 从 localStorage 恢复回测数据，而不是清空
  // 这样用户在回测完成后返回页面时，数据仍然存在
  backtestStore.hydrateFromStorage();
  
  if (props.versionId) {
    loadStrategyDetail();
  }
});
</script>

<style scoped>
.strategy-detail-page {
  transition: background-color 0.3s ease;
}
</style>

