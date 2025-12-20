import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Metrics, MonthlyReturn, Trade } from '../types/backtest';

interface HoldingPeriod {
  positionId: string;
  symbolCode: string;
  symbolName: string;
  entryDate: string;
  exitDate: string;
  entryPrice?: number;
  exitPrice?: number;
  quantity?: number;
  profit?: number;
  holdingDays?: number;
}

interface LastRunParams {
  strategyName: string;
  startDate: string;
  endDate: string;
  benchmarkCode?: string;
}

const STORAGE_KEY = 'quantflow.backtest.v1';
const HISTORY_KEY = 'backtest_history';
// 避免 localStorage 爆满后持续疯狂写入：一旦检测到配额超限，就关闭历史写入
let historyDisabled = false;

export const useBacktestStore = defineStore('backtest', () => {
  const equitySeries = ref<Array<{ date: string; equity: number }>>([]);
  const benchmarkEquitySeries = ref<Array<{ date: string; equity: number }>>([]);
  const metrics = ref<Metrics | null>(null);
  const monthlyReturns = ref<MonthlyReturn[]>([]);
  const holdingPeriods = ref<HoldingPeriod[]>([]);
  const trades = ref<Trade[]>([]);
  const lastRunParams = ref<LastRunParams | null>(null);
  const lastUpdated = ref<string>('');
  const running = ref<boolean>(false);
  const progress = ref<number>(0);
  const isInitializing = ref<boolean>(false);  // CHANGED: 添加初始化状态

  // CHANGED: 使用 localStorage 替代 sessionStorage，实现冷存储
  function hydrateFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return;
      const data = JSON.parse(stored);
      if (data.equitySeries) equitySeries.value = data.equitySeries;
      if (data.benchmarkEquitySeries) benchmarkEquitySeries.value = data.benchmarkEquitySeries;
      if (data.metrics) metrics.value = data.metrics;
      if (data.monthlyReturns) monthlyReturns.value = data.monthlyReturns;
      if (data.holdingPeriods) holdingPeriods.value = data.holdingPeriods;
      if (data.trades) trades.value = data.trades;
      if (data.lastRunParams) lastRunParams.value = data.lastRunParams;
      if (data.lastUpdated) lastUpdated.value = data.lastUpdated;
      // CHANGED: 不恢复 running 和 progress 状态，因为这些是临时状态，不应该被持久化
      // 初始状态应该始终是 false/0
      running.value = false;
      progress.value = 0;
      isInitializing.value = false;
    } catch (e) {
    }
  }

  function persistToStorage() {
    try {
      const data = {
        equitySeries: equitySeries.value,
        benchmarkEquitySeries: benchmarkEquitySeries.value,
        metrics: metrics.value,
        monthlyReturns: monthlyReturns.value,
        holdingPeriods: holdingPeriods.value,
        trades: trades.value,
        lastRunParams: lastRunParams.value,
        lastUpdated: lastUpdated.value
        // CHANGED: 不保存 running 和 progress 状态，因为这些是临时状态
        // running: running.value,
        // progress: progress.value
      };
      // CHANGED: 使用 localStorage 实现冷存储
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
    }
  }
  
  // CHANGED: 保存回测结果到历史记录
  function saveToHistory() {
    if (historyDisabled) {
      return;
    }
    try {
      const history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
      
      // 这里只保存【精简版】历史记录，避免把整条权益曲线和所有成交明细塞进 localStorage
      const historyRecord = {
        id: `backtest_${Date.now()}`,
        strategyName: lastRunParams.value?.strategyName || 'Unknown',
        dateRange: `${lastRunParams.value?.startDate || ''} ~ ${lastRunParams.value?.endDate || ''}`,
        createdAt: new Date().toISOString(),
        status: 'completed' as const,
        metrics: metrics.value ? {
          totalReturn: metrics.value.totalReturn,
          annualizedReturn: metrics.value.annualizedReturn,
          maxDrawdown: metrics.value.maxDrawdown,
          sharpeRatio: metrics.value.sharpeRatio
        } : undefined
      };
      
      // 添加到历史记录开头
      history.unshift(historyRecord);
      
      // 限制历史记录数量（保留最近100条）
      if (history.length > 100) {
        history.splice(100);
      }
      
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) {
      // 如果是配额超限错误，则关闭后续历史写入，避免前端被日志刷爆 / 一直卡顿
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('QuotaExceededError')) {
        historyDisabled = true;
        console.warn('保存历史记录失败：localStorage 已满，本次会话内将不再写入 backtest_history。');
      } else {
        console.error('保存历史记录失败:', e);
      }
    }
  }

  function clearBacktestData() {
    equitySeries.value = [];
    benchmarkEquitySeries.value = [];
    metrics.value = null;
    monthlyReturns.value = [];
    holdingPeriods.value = [];
    trades.value = [];
  }

  function addTrade(trade: Trade) {
    const existingIndex = trades.value.findIndex(t => t.id === trade.id);
    if (existingIndex >= 0) {
      trades.value[existingIndex] = trade;
    } else {
      trades.value.push(trade);
    }
    persistToStorage();
  }

  function setTrades(newTrades: Trade[]) {
    trades.value = newTrades;
    persistToStorage();
  }

  function setRunning(value: boolean) {
    running.value = value;
    persistToStorage();
  }

  function setProgress(value: number) {
    progress.value = value;
  }

  // CHANGED: 设置初始化状态
  function setInitializing(value: boolean) {
    isInitializing.value = value;
  }

  function setLastUpdated(value: string) {
    lastUpdated.value = value;
    persistToStorage();
  }

  function setMetrics(value: Metrics, skipHistory: boolean = false) {
    metrics.value = value;
    persistToStorage();
    // CHANGED: 当指标更新时，保存到历史记录（流式回测时跳过，只在最终完成时保存）
    if (value && lastRunParams.value && !skipHistory && !running.value) {
      saveToHistory();
    }
  }

  function setMonthlyReturns(value: MonthlyReturn[]) {
    monthlyReturns.value = value;
    persistToStorage();
  }

  function setHoldingPeriods(value: HoldingPeriod[]) {
    holdingPeriods.value = value;
    persistToStorage();
  }

  function setLastRunParams(value: LastRunParams) {
    lastRunParams.value = value;
    persistToStorage();
  }

  function addEquityPoint(date: string, equity: number) {
    const existingIndex = equitySeries.value.findIndex(item => item.date === date);
    if (existingIndex >= 0) {
      equitySeries.value[existingIndex] = { date, equity };
    } else {
      equitySeries.value.push({ date, equity });
    }
    equitySeries.value.sort((a, b) => a.date.localeCompare(b.date));
    persistToStorage();
  }

  function addBenchmarkPoint(date: string, equity: number) {
    const existingIndex = benchmarkEquitySeries.value.findIndex(item => item.date === date);
    if (existingIndex >= 0) {
      benchmarkEquitySeries.value[existingIndex] = { date, equity };
    } else {
      benchmarkEquitySeries.value.push({ date, equity });
    }
    benchmarkEquitySeries.value.sort((a, b) => a.date.localeCompare(b.date));
    persistToStorage();
  }

  const hasData = computed(() => {
    return equitySeries.value.length > 0 || metrics.value !== null;
  });

  return {
    equitySeries,
    benchmarkEquitySeries,
    metrics,
    monthlyReturns,
    holdingPeriods,
    trades,
    lastRunParams,
    lastUpdated,
    running,
    progress,
    hasData,
    hydrateFromStorage,
    persistToStorage,
    clearBacktestData,
    setRunning,
    setProgress,
    setLastUpdated,
    setMetrics,
    setMonthlyReturns,
    setHoldingPeriods,
    setTrades,
    setLastRunParams,
    addEquityPoint,
    addBenchmarkPoint,
    addTrade,
    isInitializing,  // CHANGED: 导出初始化状态
    setInitializing  // CHANGED: 导出设置初始化状态的函数
  };
});

