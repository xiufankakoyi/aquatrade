import { ref, onUnmounted } from 'vue';
import { useSocketIO } from './useSocketIO';
import { subscribe } from '../api/backtestApi';
import type { BacktestEvent } from '../types/api';
import type { Trade } from '../types/backtest';
import { useBacktestStore } from '../store/backtestStore';

export interface StreamingBacktestOptions {
  onStart?: () => void;
  onProgress?: (progress: number) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
  onCancel?: () => void;
}

export function useStreamingBacktest() {
  const { emitEvent, connect } = useSocketIO();
  const backtestStore = useBacktestStore();
  
  const isRunning = ref(false);
  const progress = ref(0);
  const error = ref<Error | null>(null);
  
  let unsubscribe: (() => void) | null = null;
  let hasCompleted = false;
  let hasReceivedFirstDailyUpdate = false;

  function start(params: {
    strategy_name: string;
    start_date: string;
    end_date: string;
    benchmark_code?: string | null;
  }, options: StreamingBacktestOptions = {}) {
    if (isRunning.value) {
      throw new Error('回测已在运行中');
    }

    connect('http://localhost:5000');
    
    hasCompleted = false;
    hasReceivedFirstDailyUpdate = false;
    error.value = null;
    isRunning.value = true;
    progress.value = 0;
    
    backtestStore.setRunning(true);
    backtestStore.setProgress(0);
    backtestStore.clearBacktestData();
    
    // CHANGED: 在开始回测时立即设置回测参数，这样价格获取就能使用正确的结束日期
    backtestStore.setLastRunParams({
      strategyName: params.strategy_name,
      startDate: params.start_date,
      endDate: params.end_date,
      benchmarkCode: params.benchmark_code || undefined
    });
    
    const now = new Date();
    backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));

    unsubscribe = subscribe((event: BacktestEvent) => {
      try {
        handleEvent(event, options);
      } catch (err) {
        const errorObj = err instanceof Error ? err : new Error(String(err));
        error.value = errorObj;
        options.onError?.(errorObj);
        stop();
      }
    });

    emitEvent('run_streaming_backtest', params);
    options.onStart?.();
  }

  function handleEvent(event: BacktestEvent, options: StreamingBacktestOptions) {
    switch (event.type) {
      // CHANGED: 处理初始化事件
      case 'initializing':
        backtestStore.setInitializing(true);
        break;
      
      case 'initialized':
        backtestStore.setInitializing(false);
        break;
      
      case 'backtest_start':
        hasReceivedFirstDailyUpdate = false;
        hasCompleted = false;
        backtestStore.setRunning(true);
        backtestStore.setProgress(0);
        backtestStore.clearBacktestData();
        const now = new Date();
        backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));
        break;

      case 'daily_equity':
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
        const updateTime = new Date();
        backtestStore.setLastUpdated(updateTime.toLocaleTimeString('zh-CN', { hour12: false }));
        break;

      case 'new_trade':
        const tradeData = event.data;
        if (tradeData && tradeData.date) {
          const trade: Trade = {
            id: tradeData.id || `${tradeData.date}-${tradeData.symbolCode || tradeData.symbol_code || tradeData.symbol}-${tradeData.action}`,
            symbol: tradeData.symbol || '',
            symbolCode: tradeData.symbolCode || tradeData.symbol_code || tradeData.symbol || '',
            date: tradeData.date,
            action: tradeData.action === 'buy' ? 'buy' : 'sell',
            price: tradeData.price || 0,
            quantity: tradeData.quantity || 0,
            value: (tradeData.price || 0) * (tradeData.quantity || 0),
            profitLoss: tradeData.profitLoss ?? tradeData.profit_loss ?? 0,
            profit_loss: tradeData.profit_loss ?? tradeData.profitLoss ?? undefined,
            cumulativePnL: tradeData.cumulativePnL ?? tradeData.cumulative_pnl ?? 0,
            positionId: tradeData.positionId || tradeData.position_id,
            entryDate: tradeData.entryDate || tradeData.entry_date,
            exitDate: tradeData.exitDate || tradeData.exit_date,
            holdingDays: tradeData.holdingDays ?? tradeData.holding_days ?? undefined,
            holding_days: tradeData.holding_days ?? tradeData.holdingDays ?? undefined,
            entry_price: tradeData.entry_price ?? undefined,
            exit_price: tradeData.exit_price ?? undefined,
            roi: tradeData.roi ?? undefined
          };
          backtestStore.addTrade(trade);
        }
        break;

      case 'metrics_update':
      case 'final_metrics':
        if (!hasCompleted && event.data) {
          const metrics = {
            totalReturn: event.data.totalReturn ?? event.data.total_return ?? 0,
            annualizedReturn: event.data.annualizedReturn ?? event.data.annualized_return ?? 0,
            maxDrawdown: event.data.maxDrawdown ?? event.data.max_drawdown ?? 0,
            sharpeRatio: event.data.sharpeRatio ?? event.data.sharpe_ratio ?? 0,
            sortinoRatio: event.data.sortinoRatio ?? event.data.sortino_ratio ?? 0,
            volatility: event.data.volatility ?? 0,
            winRate: event.data.winRate ?? event.data.win_rate ?? 0,
            profitFactor: event.data.profitFactor ?? event.data.profit_factor ?? 0,
            tradesCount: event.data.tradesCount ?? event.data.trades_count ?? 0,
            avgTradeReturn: event.data.avgTradeReturn ?? event.data.avg_trade_return ?? 0,
            maxWinningStreak: event.data.maxWinningStreak ?? event.data.max_winning_streak ?? 0,
            maxLosingStreak: event.data.maxLosingStreak ?? event.data.max_losing_streak ?? 0
          };
          backtestStore.setMetrics(metrics);
        }
        break;

      case 'risk_data':
        if (event.data) {
          if (event.data.monthlyReturns && Array.isArray(event.data.monthlyReturns)) {
            backtestStore.setMonthlyReturns(event.data.monthlyReturns);
          } else if (event.data.monthly_returns && Array.isArray(event.data.monthly_returns)) {
            backtestStore.setMonthlyReturns(event.data.monthly_returns);
          }
          if (event.data.holdingPeriods && Array.isArray(event.data.holdingPeriods)) {
            backtestStore.setHoldingPeriods(event.data.holdingPeriods);
          }
        }
        break;

      case 'stream_complete':
        if (!hasCompleted) {
          hasCompleted = true;
          backtestStore.setRunning(false);
          backtestStore.setProgress(100);
          const completeTime = new Date();
          backtestStore.setLastUpdated(completeTime.toLocaleTimeString('zh-CN', { hour12: false }));
          backtestStore.persistToStorage();
          isRunning.value = false;
          progress.value = 100;
          options.onComplete?.();
        }
        break;

      case 'progress':
        if (event.data && typeof event.data.progress === 'number') {
          progress.value = event.data.progress;
          backtestStore.setProgress(event.data.progress);
          options.onProgress?.(event.data.progress);
        }
        break;

      case 'error':
        const errorMsg = event.data?.message || '回测发生错误';
        const errorObj = new Error(errorMsg);
        error.value = errorObj;
        backtestStore.setRunning(false);
        backtestStore.setProgress(0);
        isRunning.value = false;
        options.onError?.(errorObj);
        break;

      case 'cancelled':
        backtestStore.setRunning(false);
        backtestStore.setProgress(0);
        isRunning.value = false;
        options.onCancel?.();
        break;
    }
  }

  function cancel() {
    if (!isRunning.value) {
      return;
    }

    const { emitEvent } = useSocketIO();
    emitEvent('cancel_streaming_backtest', {});
  }

  function stop() {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
    isRunning.value = false;
    progress.value = 0;
  }

  onUnmounted(() => {
    stop();
  });

  return {
    isRunning,
    progress,
    error,
    start,
    cancel,
    stop,
  };
}

