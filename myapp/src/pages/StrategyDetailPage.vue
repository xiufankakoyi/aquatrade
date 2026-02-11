<!--
  策略详情页面
  显示该版本的交易记录表格、K线图和防守仓模块
-->
<template>
  <div class="strategy-detail-page p-4 md:p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen">
  <ProgressBar :percentage="klineLoadingProgress" v-if="klineLoading" />
    <!-- 页面标题和返回按钮 -->
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <button
          @click="$router.push('/dashboard')"
          class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:text-gray-900 dark:hover:text-slate-100 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
        >
          ← 返回 Dashboard
        </button>
        <h1 class="text-2xl md:text-3xl font-bold text-gray-800 dark:text-slate-100">
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
            {{ formatPercent(backtestResult.metrics.maxDrawdown, true) }}
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
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6">
        <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">交易记录</h2>
        <ResultsTable
          :trades="backtestResult.trades || []"
          @trade-select="handleTradeSelect"
        />
      </div>

      <!-- K线图 -->
      <div v-if="selectedTrade" class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6">
        <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">
          K线图：{{ selectedTrade.symbol }}
        </h2>
        <div class="min-h-[300px] md:h-96">
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
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6">
        <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">防守仓仓位分析</h2>
        <PortfolioDefense
          :trades="backtestResult.trades || []"
        />
      </div>
    </div>

    <!-- Deep Dive Modal -->
    <TradeDeepDive
      v-if="selectedDeepDiveTrade"
      :is-open="isDeepDiveOpen"
      :symbol-code="selectedDeepDiveTrade.symbolCode"
      :symbol-name="selectedDeepDiveTrade.symbol"
      :start-date="deepDiveStartDate"
      :end-date="deepDiveEndDate"
      :trades="backtestStore.trades"
      :benchmark-code="backtestStore.lastRunParams?.benchmarkCode"
      @close="isDeepDiveOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import ProgressBar from '../components/ProgressBar.vue';
import { useBacktestStore } from '../store/backtestStore';
import { useRoute } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { getStrategyDetail, getKlineData } from '../api/backtestApi';
import ResultsTable from '../components/ResultsTable.vue';
import PortfolioDefense from '../components/PortfolioDefense.vue';
import EquityCurve from '../components/EquityCurve.vue';
import TradeDeepDive from '../components/modals/TradeDeepDive.vue';
import type { Trade } from '../types/backtest';
import type { BacktestResult } from '../store/strategyStore';

interface Props {
  versionId: string;
}

const props = defineProps<Props>();
const backtestStore = useBacktestStore();
const route = useRoute();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();

// 状态
const selectedTrade = ref<Trade | null>(null);
const klineLoading = ref(false);
const klineLoadingProgress = ref<number | null>(null);
const klineData = ref<any[]>([]);
const highlightRanges = ref<Array<{ start: string; end: string }>>([]);

// Deep Dive Modal 状态
const selectedDeepDiveTrade = ref<Trade | null>(null);
const isDeepDiveOpen = ref(false);
const deepDiveStartDate = ref('');
const deepDiveEndDate = ref('');

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
function formatPercent(value: number, isDrawdown = false): string {
  // 对于最大回撤，确保显示为负值且不加+号
  if (isDrawdown) {
    return `-${Math.abs(value).toFixed(2)}%`;
  }
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

// 处理交易选择
async function handleTradeSelect(trade: Trade) {
  selectedTrade.value = trade;
  
  // 用于弹窗分析
  selectedDeepDiveTrade.value = trade;
  isDeepDiveOpen.value = true;
  
  const symbolCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
  if (symbolCode) {
    // 计算分析窗口 (-20d / +10d)
    const entry = new Date(trade.entryDate || trade.date);
    const exit = trade.exitDate ? new Date(trade.exitDate) : new Date(entry);
    
    const start = new Date(entry);
    start.setDate(start.getDate() - 20);
    const end = new Date(exit);
    end.setDate(end.getDate() + 10);

    const formatDateStr = (date: Date) => date.toISOString().split('T')[0];
    deepDiveStartDate.value = formatDateStr(start);
    deepDiveEndDate.value = formatDateStr(end);
    
    try {
      let cached = backtestStore.klineCache[symbolCode];
if (cached) {
  klineData.value = cached;
  highlightRanges.value = trade.entryDate && trade.exitDate ? [{ start: trade.entryDate, end: trade.exitDate }] : [];
} else {
  klineLoading.value = true;
  klineLoadingProgress.value = 0;
  try {
    const kline = await getKlineData(symbolCode, deepDiveStartDate.value, deepDiveEndDate.value);
    klineData.value = kline;
    backtestStore.klineCache[symbolCode] = kline;
    highlightRanges.value = trade.entryDate && trade.exitDate ? [{ start: trade.entryDate, end: trade.exitDate }] : [];
  } catch (err) {
    console.error('加载 K 线数据失败:', err);
  } finally {
    klineLoading.value = false;
    klineLoadingProgress.value = null;
  }
}
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

function normalizeSymbolCode(value?: string | null): string {
  if (!value) return '';
  const trimmed = value.trim().toUpperCase();
  const match = trimmed.match(/(\d+)/);
  if (match) {
    const digits = match[1];
    return digits.length < 6 ? digits.padStart(6, '0') : digits;
  }
  return trimmed;
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

