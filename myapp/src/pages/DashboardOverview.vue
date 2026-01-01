<template>
  <div class="p-6 space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <MetricCard
        label="回测收益率"
        :value="metrics?.totalReturn ?? null"
        format="percent"
        :subtitle="hasBacktestData && benchmarkReturn !== null ? `基准: ${benchmarkReturn >= 0 ? '+' : ''}${benchmarkReturn.toFixed(2)}%` : undefined"
      />
      <MetricCard
        label="夏普比率 (Sharpe)"
        :value="metrics?.sharpeRatio ?? null"
        format="number"
        :subtitle="hasBacktestData && metrics?.volatility ? `波动率 ${volatilityDisplay.toFixed(2)}%` : undefined"
      />
      <MetricCard
        label="最大回撤(MaxDD)"
        :value="metrics?.maxDrawdown !== undefined && metrics?.maxDrawdown !== null ? Math.abs(metrics.maxDrawdown) : null"
        format="percent"
        positive-color="text-red-400"
        negative-color="text-green-400"
        zero-color="text-gray-400"
        :use-original-value="true"
        :original-value="metrics?.maxDrawdown ?? null"
      />
      <MetricCard
        label="盈亏比(P/L Ratio)"
        :value="hasBacktestData && metrics?.profitFactor !== undefined ? (metrics.profitFactor ?? null) : null"
        format="number"
        :subtitle="hasBacktestData && winRatePercent !== null ? `胜率: ${winRatePercent.toFixed(0)}%` : undefined"
      />
    </div>

    <div class="grid grid-cols-2 gap-6">
      <div class="bg-[#151925] rounded-lg p-6 border border-slate-800 relative">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-white">资金收益曲线 (Equity Curve)</h3>
          <div class="flex space-x-2">
            <button
              @click="chartScale = 'linear'"
              :class="chartScale === 'linear' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'"
              class="px-3 py-1 rounded text-xs font-medium transition-colors"
            >
              Linear
            </button>
            <button
              @click="chartScale = 'log'"
              :class="chartScale === 'log' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'"
              class="px-3 py-1 rounded text-xs font-medium transition-colors"
            >
              Log
            </button>
          </div>
        </div>
        <div class="relative" style="min-height: 300px;">
          <EquityCurve
            v-if="equityCurveData.length > 0 || benchmarkData.length > 0"
            :versions="equityCurveData"
            :benchmark="benchmarkData"
            :kline-data="[]"
            :highlight-ranges="[]"
            mode="equity"
            :scale="chartScale"
            @hover="handleEquityHover"
          />
          <!-- 蒙层：如果没有数据，就盖在上面 -->
          <div
            v-if="!hasBacktestData"
            class="absolute inset-0 bg-gray-900/80 flex flex-col items-center justify-center z-10 backdrop-blur-sm rounded-lg"
          >
            <p class="text-gray-400 mb-4 text-lg">暂无回测数据</p>
            <button
              class="px-6 py-2 bg-indigo-600 rounded hover:bg-indigo-500 transition text-white font-medium"
              @click="router.push('/strategy')"
            >
              运行策略
            </button>
          </div>
        </div>
      </div>

      <div class="bg-[#151925] rounded-lg p-6 border border-slate-800 relative">
        <div class="relative" style="min-height: 300px;">
          <RadarAbility
            v-if="radarScores"
            :scores="radarScores"
            :benchmark="benchmarkRadarScores"
            :feasibility-score="overallFeasibilityScore"
          />
          <!-- 蒙层：如果没有数据，就盖在上面 -->
          <div
            v-if="!hasBacktestData"
            class="absolute inset-0 bg-gray-900/80 flex flex-col items-center justify-center z-10 backdrop-blur-sm rounded-lg"
          >
            <p class="text-gray-400 mb-4 text-lg">暂无回测数据</p>
            <button
              class="px-6 py-2 bg-indigo-600 rounded hover:bg-indigo-500 transition text-white font-medium"
              @click="router.push('/strategy')"
            >
              运行策略
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-white">月度收益热力图</h3>
        <div class="flex space-x-2">
          <button
            @click="heatmapView = 'calendar'"
            :class="heatmapView === 'calendar' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'"
            class="px-3 py-1 rounded text-xs font-medium transition-colors"
          >
            Calendar
          </button>
          <button
            @click="heatmapView = 'heatmap'"
            :class="heatmapView === 'heatmap' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-400'"
            class="px-3 py-1 rounded text-xs font-medium transition-colors"
          >
            Heatmap
          </button>
        </div>
      </div>
      <PnLCalendar v-if="heatmapView === 'calendar' && monthlyReturnsData.length > 0" :data="monthlyReturnsData" />
      <HeatmapChart v-else-if="heatmapView === 'heatmap' && monthlyReturnsData.length > 0" :data="monthlyReturnsData" />
      <div v-else class="flex items-center justify-center h-48 text-slate-500">
        <div class="text-center">
          <i class="fas a-calendar-alt text-4xl mb-2"></i>
          <p>暂无月度收益数据</p>
          <p class="text-sm mt-1">请运行回测以查看数据</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({
  name: 'DashboardOverview'
});

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { useSocketIO } from '../composables/useSocketIO';
import { subscribe, getAvailableVersions } from '../api/backtestApi';
import MetricCard from '../components/metrics/MetricCard.vue';
import EquityCurve from '../components/EquityCurve.vue';
import RadarAbility from '../components/charts/RadarAbility.vue';
import PnLCalendar from '../components/charts/PnLCalendar.vue';
import HeatmapChart from '../components/HeatmapChart.vue';
import type { Trade, Metrics } from '../types/backtest';

const router = useRouter();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();
const { connect } = useSocketIO();

const chartScale = ref<'linear' | 'log'>('linear');
const heatmapView = ref<'calendar' | 'heatmap'>('calendar');
const trades = ref<Trade[]>([]);
let hasReceivedFirstDailyUpdate = false;
let hasCompleted = false;

// 判断是否有回测数据
const hasBacktestData = computed(() => {
  return backtestStore.metrics !== null && 
         backtestStore.equitySeries.length > 0;
});

const metrics = computed(() => {
  return backtestStore.metrics;
});

const profitLossRatio = computed(() => {
  return metrics.value?.profitFactor ?? null;
});

const winRatePercent = computed(() => {
  if (!metrics.value || metrics.value.winRate === undefined || metrics.value.winRate === null) return null;
  // 后端传入的胜率需除以 100 才是百分数
  const pct = metrics.value.winRate;
  return Math.min(Math.max(pct, 0), 100);
});

const volatilityDisplay = computed(() => {
  if (!metrics.value) return 0;
  const raw = metrics.value.volatility || 0;
  // 后端传入的波动率需除以 100 才是百分数
  return raw;
});

const benchmarkReturn = computed(() => {
  if (backtestStore.benchmarkEquitySeries.length === 0) return null;
  const first = backtestStore.benchmarkEquitySeries[0]?.equity || 1;
  const last = backtestStore.benchmarkEquitySeries[backtestStore.benchmarkEquitySeries.length - 1]?.equity || 1;
  return ((last / first) - 1) * 100;
});

const equityCurveData = computed(() => {
  if (backtestStore.equitySeries.length > 0) {
    return [{
      versionId: 'current',
      versionName: '当前回测',
      data: backtestStore.equitySeries
    }];
  }
  return [];
});

const benchmarkData = computed(() => {
  return backtestStore.benchmarkEquitySeries;
});

const monthlyReturnsData = computed(() => {
  return backtestStore.monthlyReturns;
});

const clamp = (val: number, min: number, max: number) => Math.min(Math.max(val, min), max);

function normalizeRadarScores(m: Metrics) {
  // 期间收益：-100%~100% 映射到 0~100
  const excessReturn = clamp(((m.annualizedReturn || 0) + 100) / 2, 0, 100);
  // 夏普：-1~3 映射到 0~100
  const sharpe = clamp(((m.sharpeRatio || 0) + 1) * 25, 0, 100);
  // 最大回撤：越小越好，0~100 映射为 100-回撤
  const maxDdScore = clamp(100 - Math.abs(m.maxDrawdown || 0), 0, 100);
  // 交易质量：胜率(0~1)→0~100 占60%，盈利因子(0~5)→0~100 占40%
  const winPct = clamp((m.winRate || 0) * 100, 0, 100);
  const pfScore = clamp((m.profitFactor || 0) / 5 * 100, 0, 100);
  const tradingQuality = clamp(winPct * 0.6 + pfScore * 0.4, 0, 100);
  // 抗过拟合：交易次数 0~200 映射到 0~100
  const antiOverfit = clamp((m.tradesCount || 0) / 2, 0, 100);

  return {
    excessReturn,
    riskConsistency: sharpe,
    maxDrawdown: maxDdScore,
    tradingQuality,
    antiOverfitting: antiOverfit
  };
}

const radarScores = computed(() => {
  if (strategyStore.currentRadarScores) {
    return strategyStore.currentRadarScores;
  }
  
  if (backtestStore.metrics) {
    return normalizeRadarScores(backtestStore.metrics);
  }
  
  return null;
});

const overallFeasibilityScore = computed(() => {
  if (!radarScores.value) return null;
  const scores = [
    radarScores.value.excessReturn,
    radarScores.value.riskConsistency,
    radarScores.value.maxDrawdown,
    radarScores.value.tradingQuality,
    radarScores.value.antiOverfitting
  ];
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
});

const benchmarkRadarScores = computed(() => {
  if (!backtestStore.benchmarkEquitySeries.length || !backtestStore.equitySeries.length) {
    return null;
  }
  
  const benchmarkFirst = backtestStore.benchmarkEquitySeries[0]?.equity || 1;
  const benchmarkLast = backtestStore.benchmarkEquitySeries[backtestStore.benchmarkEquitySeries.length - 1]?.equity || 1;
  const benchmarkReturnVal = (benchmarkLast / benchmarkFirst - 1) * 100;
  
  const days = backtestStore.benchmarkEquitySeries.length;
  const years = days / 252.0;
  const benchmarkAnnualizedReturn = years > 0 && benchmarkFirst > 0 ? ((benchmarkLast / benchmarkFirst) ** (1 / years) - 1) * 100 : benchmarkReturnVal;
  
  const benchmarkReturns = backtestStore.benchmarkEquitySeries.map((e, i) => {
    if (i === 0) return 0;
    const prev = backtestStore.benchmarkEquitySeries[i - 1]?.equity || 1;
    return (e.equity / prev - 1) * 100;
  });
  const benchmarkMean = benchmarkReturns.reduce((a, b) => a + b, 0) / benchmarkReturns.length;
  const benchmarkStd = Math.sqrt(benchmarkReturns.reduce((sum, r) => sum + Math.pow(r - benchmarkMean, 2), 0) / benchmarkReturns.length);
  const benchmarkSharpe = benchmarkStd > 0 ? (benchmarkMean / benchmarkStd) * Math.sqrt(252) : 0;
  
  let benchmarkMaxDD = 0;
  let benchmarkPeak = benchmarkFirst;
  for (const point of backtestStore.benchmarkEquitySeries) {
    if (point.equity > benchmarkPeak) {
      benchmarkPeak = point.equity;
    }
    const drawdown = (point.equity - benchmarkPeak) / benchmarkPeak;
    if (drawdown < benchmarkMaxDD) {
      benchmarkMaxDD = drawdown;
    }
  }
  
  return {
    excessReturn: Math.min(100, Math.max(0, benchmarkAnnualizedReturn * 10)),
    riskConsistency: Math.min(100, Math.max(0, benchmarkSharpe * 20)),
    maxDrawdown: Math.min(100, Math.max(0, 100 - Math.abs(benchmarkMaxDD) * 2)),
    tradingQuality: 50,
    antiOverfitting: 50
  };
});

const recentTrades = computed(() => {
  if (trades.value.length > 0) {
    return trades.value.slice().reverse().slice(0, 10);
  }
  return strategyStore.currentBacktestResult?.trades || [];
});

function handleEquityHover(data: any) {
  console.log('Hover data:', data);
}

function handleTradeSelect(trade: Trade) {
  router.push(`/strategy/${strategyStore.currentVersionId || 'default'}`);
}

let unsubscribe: (() => void) | null = null;

async function loadData() {
  try {
    strategyStore.setLoading(true);
    const versions = await getAvailableVersions();
    strategyStore.setAvailableVersions(versions);
    if (versions.length > 0 && versions[0]) {
      strategyStore.setCurrentVersion(versions[0].id);
    }
  } catch (error) {
    strategyStore.setError(null);
  } finally {
    strategyStore.setLoading(false);
  }
}

onMounted(() => {
  // CHANGED: 从 localStorage 恢复回测数据，而不是清空
  // 这样用户在回测完成后返回页面时，数据仍然存在
  backtestStore.hydrateFromStorage();
  loadData();
  connect('http://localhost:5000');
  
  unsubscribe = subscribe((event: any) => {
    if (event.type === 'initializing') {
      backtestStore.setInitializing(true);
    } else if (event.type === 'initialized') {
      backtestStore.setInitializing(false);
    } else if (event.type === 'backtest_start') {
      // 【关键修复】确保加载动画已关闭（作为备用，主要应该在 initialized 事件中关闭）
      backtestStore.setInitializing(false);
      hasReceivedFirstDailyUpdate = false;
      hasCompleted = false;
      backtestStore.setRunning(true);
      backtestStore.setProgress(0);
      backtestStore.clearBacktestData();
      const now = new Date();
      backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));
    } else if (event.type === 'daily_equity') {
      if (!hasReceivedFirstDailyUpdate) {
        hasReceivedFirstDailyUpdate = true;
        if (!backtestStore.running) {
          backtestStore.setRunning(true);
        }
      }
      const data = event.data;
      const equity = data.strategyReturn ?? data.equity;
      const benchmarkEquity = data.benchmarkReturn ?? data.benchmark_equity;
      if (data.date && equity !== undefined && equity !== null) {
        backtestStore.addEquityPoint(data.date, equity);
      }
      if (data.date && benchmarkEquity !== undefined && benchmarkEquity !== null) {
        backtestStore.addBenchmarkPoint(data.date, benchmarkEquity);
      }
      
      if (backtestStore.equitySeries.length > 0) {
        const tempMetrics = calculateTemporaryMetrics();
        if (tempMetrics) {
          backtestStore.setMetrics(tempMetrics, true);
        }
      }
      
      const now = new Date();
      backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));
    } else if (event.type === 'metrics_update' || event.type === 'final_metrics') {
      const data = event.data;
      if (data && !hasCompleted) {
        const metricsVal: Metrics = {
          totalReturn: data.totalReturn ?? data.total_return ?? 0,
          annualizedReturn: data.annualizedReturn ?? data.annualized_return ?? 0,
          maxDrawdown: data.maxDrawdown ?? data.max_drawdown ?? 0,
          sharpeRatio: data.sharpeRatio ?? data.sharpe_ratio ?? 0,
          sortinoRatio: data.sortinoRatio ?? data.sortino_ratio ?? 0,
          volatility: data.volatility ?? 0,
          winRate: data.winRate ?? data.win_rate ?? 0,
          profitFactor: data.profitFactor ?? data.profit_factor ?? 0,
          tradesCount: data.tradesCount ?? data.trades_count ?? 0,
          avgTradeReturn: data.avgTradeReturn ?? data.avg_trade_return ?? 0,
          maxWinningStreak: data.maxWinningStreak ?? data.max_winning_streak ?? 0,
          maxLosingStreak: data.maxLosingStreak ?? data.max_losing_streak ?? 0
        };
        backtestStore.setMetrics(metricsVal);
      }
    } else if (event.type === 'new_trade') {
      const data = event.data;
      if (data && data.date) {
        const trade: Trade = {
          id: data.id || `${data.date}-${data.symbolCode || data.symbol_code || data.symbol}-${data.action}`,
          symbol: data.symbol || '',
          symbolCode: data.symbolCode || data.symbol_code || data.symbol || '',
          date: data.date,
          action: data.action === 'buy' ? 'buy' : 'sell',
          price: data.price || 0,
          quantity: data.quantity || 0,
          value: (data.price || 0) * (data.quantity || 0),
          profitLoss: data.profitLoss ?? data.profit_loss ?? 0,
          cumulativePnL: data.cumulativePnL ?? data.cumulative_pnl ?? 0,
          positionId: data.positionId || data.position_id,
          entryDate: data.entryDate || data.entry_date,
          exitDate: data.exitDate || data.exit_date
        };
        backtestStore.addTrade(trade);
      }
    } else if (event.type === 'risk_data') {
      const data = event.data;
      if (data) {
        if (data.monthlyReturns) {
          if (Array.isArray(data.monthlyReturns)) {
            backtestStore.setMonthlyReturns(data.monthlyReturns);
          }
        } else if (data.monthly_returns && Array.isArray(data.monthly_returns)) {
          backtestStore.setMonthlyReturns(data.monthly_returns);
        }
        if (data.holdingPeriods && Array.isArray(data.holdingPeriods)) {
          backtestStore.setHoldingPeriods(data.holdingPeriods);
        }
      }
    } else if (event.type === 'stream_complete') {
      if (!hasCompleted) {
        hasCompleted = true;
        backtestStore.setRunning(false);
        backtestStore.setProgress(100);
        const now = new Date();
        backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));
        backtestStore.persistToStorage();
      }
    } else if (event.type === 'error' || event.type === 'cancelled') {
      backtestStore.setRunning(false);
      backtestStore.setProgress(0);
    } else if (event.type === 'progress') {
      const data = event.data;
      if (data && typeof data.progress === 'number') {
        backtestStore.setProgress(data.progress);
      }
    }
  });
});

onUnmounted(() => {
  unsubscribe?.();
});

function calculateTemporaryMetrics(): Metrics | null {
  if (backtestStore.equitySeries.length === 0) return null;
  
  const initialCapital = 1000000;
  const firstEquity = backtestStore.equitySeries[0]?.equity || initialCapital;
  const lastEquity = backtestStore.equitySeries[backtestStore.equitySeries.length - 1]?.equity || initialCapital;
  
  const totalReturn = (lastEquity / firstEquity - 1) * 100;
  
  const days = backtestStore.equitySeries.length;
  const years = days / 252.0;
  const annualizedReturn = years > 0 && firstEquity > 0 ? ((lastEquity / firstEquity) ** (1 / years) - 1) * 100 : totalReturn;
  
  let maxDrawdown = 0;
  let peak = firstEquity;
  for (const point of backtestStore.equitySeries) {
    if (point.equity > peak) {
      peak = point.equity;
    }
    const drawdown = (point.equity - peak) / peak;
    if (drawdown < maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }
  
  const returns = backtestStore.equitySeries.map((e, i) => {
    if (i === 0) return 0;
    const prev = backtestStore.equitySeries[i - 1]?.equity || firstEquity;
    return (e.equity / prev - 1) * 100;
  });
  const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const stdReturn = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / returns.length);
  const sharpeRatio = stdReturn > 0 ? (meanReturn / stdReturn) * Math.sqrt(252) : 0;
  
  const sellTrades = backtestStore.trades.filter(t => t.action === 'sell');
  const winTrades = sellTrades.filter(t => (t.profitLoss || 0) > 0);
  const winRate = sellTrades.length > 0 ? (winTrades.length / sellTrades.length) * 100 : 0;
  
  const totalProfit = sellTrades.filter(t => (t.profitLoss || 0) > 0).reduce((sum, t) => sum + (t.profitLoss || 0), 0);
  const totalLoss = Math.abs(sellTrades.filter(t => (t.profitLoss || 0) < 0).reduce((sum, t) => sum + (t.profitLoss || 0), 0));
  const profitFactor = totalLoss > 0 ? totalProfit / totalLoss : 0;
  
  return {
    totalReturn,
    annualizedReturn,
    maxDrawdown: maxDrawdown * 100,
    sharpeRatio,
    sortinoRatio: sharpeRatio,
    volatility: stdReturn * Math.sqrt(252),
    winRate: winRate,
    profitFactor,
    tradesCount: backtestStore.trades.length,
    avgTradeReturn: 0,
    maxWinningStreak: 0,
    maxLosingStreak: 0
  };
}
</script>

<style scoped>
.p-6 {
  transition: background-color 0.3s ease;
}
</style>
