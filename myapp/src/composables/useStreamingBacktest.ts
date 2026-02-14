import { ref, onUnmounted } from 'vue';
import { useSocketIO } from './useSocketIO';
import { subscribe } from '../api/backtestApi';
import type { BacktestEvent } from '../types/api';
import type { Trade } from '../types/backtest';
import { useBacktestStore } from '../store/backtestStore';
import { useErrorStore } from '../store/errorStore';
import { useErrorService } from '../services/errorService';
import { ERROR_CODES } from '../types/error';

export interface StreamingBacktestOptions {
  onStart?: () => void;
  onProgress?: (progress: number) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
  onCancel?: () => void;
}

let chunkedDataBuffers: Map<string, { chunks: any[], totalChunks: number, otherData: any }> = new Map();

async function _decompressData(data: any): Promise<any> {
  if (data._compressed && data._data) {
    try {
      const compressed = Uint8Array.from(atob(data._data), c => c.charCodeAt(0));

      if ('DecompressionStream' in window) {
        const stream = new DecompressionStream('gzip');
        const writer = stream.writable.getWriter();
        writer.write(compressed);
        writer.close();

        const reader = stream.readable.getReader();
        const chunks: Uint8Array[] = [];
        let done = false;

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            chunks.push(value);
          }
        }

        const decompressed = new Uint8Array(chunks.reduce((acc, chunk) => acc + chunk.length, 0));
        let offset = 0;
        for (const chunk of chunks) {
          decompressed.set(chunk, offset);
          offset += chunk.length;
        }

        const text = new TextDecoder().decode(decompressed);
        return JSON.parse(text);
      }

      // @ts-ignore
      if (typeof window !== 'undefined' && window.pako) {
        // @ts-ignore
        const pako = window.pako;
        const text = pako.inflate(compressed, { to: 'string' });
        return JSON.parse(text);
      }

      console.warn('浏览器不支持gzip解压缩，使用原始数据');
      return data;
    } catch (e) {
      console.error('解压缩失败:', e);
      return data;
    }
  }
  return data;
}

function _decompressDataSync(data: any): any {
  if (data._compressed && data._data) {
    console.warn('同步解压缩不可用，使用原始数据');
    return data;
  }
  return data;
}

function _handleChunkedData(data: any, key: string): any {
  if (data._chunked) {
    const chunkKey = `${key}_${data._key || 'default'}`;

    if (!chunkedDataBuffers.has(chunkKey)) {
      chunkedDataBuffers.set(chunkKey, {
        chunks: [],
        totalChunks: data._total_chunks || 1,
        otherData: data._other_data || {}
      });
    }

    const buffer = chunkedDataBuffers.get(chunkKey)!;
    buffer.chunks[data._chunk_index] = data._data;

    if (buffer.chunks.length === buffer.totalChunks &&
      buffer.chunks.every(chunk => chunk !== undefined)) {
      const result = { ...buffer.otherData };
      result[data._key] = buffer.chunks.flat();

      chunkedDataBuffers.delete(chunkKey);

      return result;
    }

    return null;
  }

  return _decompressDataSync(data);
}

export function useStreamingBacktest() {
  const { emitEvent, connect, status: socketStatus } = useSocketIO();
  const backtestStore = useBacktestStore();
  const errorStore = useErrorStore();
  const {
    createError,
    parseBackendError,
    createNetworkError,
    createSocketError,
    validateBacktestParams
  } = useErrorService();

  const isRunning = ref(false);
  const progress = ref(0);
  const error = ref<Error | null>(null);
  const currentParams = ref<{
    strategy_name: string;
    start_date: string;
    end_date: string;
    benchmark_code?: string | null;
    initial_capital?: number;
    commission?: number;
    slippage?: number;
  } | null>(null);

  let unsubscribe: (() => void) | null = null;
  let hasCompleted = false;
  let hasReceivedFirstDailyUpdate = false;

  const eventBuffer = ref<Map<string, any[]>>(new Map());
  let updateInterval: NodeJS.Timeout | null = null;

  function start(params: {
    strategy_name: string;
    start_date: string;
    end_date: string;
    benchmark_code?: string | null;
    initial_capital?: number;
    commission?: number;
    slippage?: number;
  }, options: StreamingBacktestOptions = {}) {
    if (isRunning.value) {
      const validationError = createError(
        ERROR_CODES.FRONTEND_INVALID_PARAMS,
        { strategyName: params.strategy_name },
        { message: '回测已在运行中' },
        '请等待当前回测完成后再启动新的回测'
      );
      errorStore.setError(validationError);
      throw new Error('回测已在运行中');
    }

    const paramError = validateBacktestParams(params);
    if (paramError) {
      errorStore.setError(paramError);
      options.onError?.(new Error(paramError.message));
      return;
    }

    if (!navigator.onLine) {
      const networkError = createNetworkError({
        strategyName: params.strategy_name,
        startDate: params.start_date,
        endDate: params.end_date
      });
      errorStore.setError(networkError);
      options.onError?.(new Error(networkError.message));
      return;
    }

    currentParams.value = params;

    const backendUrl = 'http://localhost:5000';
    connect(backendUrl);

    setTimeout(() => {
      if (socketStatus.value !== 'OPEN') {
        const socketError = createSocketError({
          strategyName: params.strategy_name,
          startDate: params.start_date,
          endDate: params.end_date
        });
        errorStore.setError(socketError);
        options.onError?.(new Error(socketError.message));
        return;
      }
    }, 5000);

    hasCompleted = false;
    hasReceivedFirstDailyUpdate = false;
    error.value = null;
    isRunning.value = true;
    progress.value = 0;

    backtestStore.setRunning(true);
    backtestStore.setProgress(0);
    backtestStore.clearBacktestData();

    backtestStore.setLastRunParams({
      strategyName: params.strategy_name,
      startDate: params.start_date,
      endDate: params.end_date,
      benchmarkCode: params.benchmark_code || undefined
    });

    const now = new Date();
    backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));

    updateInterval = setInterval(() => {
      processEventBuffer();
    }, 100);

    unsubscribe = subscribe((event: BacktestEvent) => {
      try {
        handleEvent(event, options);
      } catch (err) {
        const errorObj = err instanceof Error ? err : new Error(String(err));
        error.value = errorObj;
        
        const backtestError = parseBackendError(
          errorObj.message,
          {
            strategyName: params.strategy_name,
            startDate: params.start_date,
            endDate: params.end_date
          },
          err
        );
        errorStore.setError(backtestError);
        
        options.onError?.(errorObj);
        stop();
      }
    });

    emitEvent('run_streaming_backtest', params);
    options.onStart?.();
  }

  function processEventBuffer() {
    if (eventBuffer.value.size === 0) return;

    for (const [eventType, events] of eventBuffer.value) {
      if (events.length === 0) continue;

      switch (eventType) {
        case 'daily_equity':
          const equityPoints: Array<{ date: string; equity: number }> = [];
          const benchmarkPoints: Array<{ date: string; equity: number }> = [];

          for (const data of events) {
            if (!hasReceivedFirstDailyUpdate) {
              hasReceivedFirstDailyUpdate = true;
              if (!backtestStore.running) {
                backtestStore.setRunning(true);
              }
            }
            const equity = data.strategyReturn ?? data.equity;
            const benchmarkEquity = data.benchmarkReturn ?? data.benchmark_equity;
            if (data.date && equity !== undefined && equity !== null) {
              equityPoints.push({ date: data.date, equity });
            }
            if (data.date && benchmarkEquity !== undefined && benchmarkEquity !== null) {
              benchmarkPoints.push({ date: data.date, equity: benchmarkEquity });
            }
          }

          if (equityPoints.length > 0) {
            backtestStore.addEquityPoints(equityPoints);
          }
          if (benchmarkPoints.length > 0) {
            backtestStore.addBenchmarkPoints(benchmarkPoints);
          }

          if (events.length > 0) {
            const updateTime = new Date();
            backtestStore.setLastUpdated(updateTime.toLocaleTimeString('zh-CN', { hour12: false }));
          }
          break;

        case 'new_trade':
          const tradesToAdd: Trade[] = [];
          for (const tradeData of events) {
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
                roi: tradeData.roi ?? undefined,
                profitRatio: (tradeData.roi ?? 0) / 100
              };
              tradesToAdd.push(trade);
            }
          }
          if (tradesToAdd.length > 0) {
            backtestStore.addTrades(tradesToAdd);
          }
          break;

        case 'risk_data':
        case 'risk_update':
          for (const data of events) {
            const processedData = _handleChunkedData(data, 'risk_data');
            if (processedData) {
              if (processedData.monthlyReturns && Array.isArray(processedData.monthlyReturns)) {
                backtestStore.setMonthlyReturns(processedData.monthlyReturns);
              } else if (processedData.monthly_returns && Array.isArray(processedData.monthly_returns)) {
                backtestStore.setMonthlyReturns(processedData.monthly_returns);
              }
              if (processedData.holdingPeriods && Array.isArray(processedData.holdingPeriods)) {
                backtestStore.setHoldingPeriods(processedData.holdingPeriods);
              }
            }
          }
          break;
      }
    }

    eventBuffer.value.clear();
  }

  function handleEvent(event: BacktestEvent, options: StreamingBacktestOptions) {
    switch (event.type) {
      case 'initializing':
        backtestStore.setInitializing(true);
        break;

      case 'initialized':
        backtestStore.setInitializing(false);
        break;

      case 'backtest_start':
        backtestStore.setInitializing(false);
        hasReceivedFirstDailyUpdate = false;
        hasCompleted = false;
        backtestStore.setRunning(true);
        backtestStore.setProgress(0);
        backtestStore.clearBacktestData();
        const now = new Date();
        backtestStore.setLastUpdated(now.toLocaleTimeString('zh-CN', { hour12: false }));
        break;

      case 'daily_equity':
        // 【修复】直接实时更新权益曲线，不经过缓冲区
        if (event.data) {
          if (!hasReceivedFirstDailyUpdate) {
            hasReceivedFirstDailyUpdate = true;
            if (!backtestStore.running) {
              backtestStore.setRunning(true);
            }
          }
          const equity = event.data.strategyReturn ?? event.data.equity;
          const benchmarkEquity = event.data.benchmarkReturn ?? event.data.benchmark_equity;
          if (event.data.date && equity !== undefined && equity !== null) {
            backtestStore.addEquityPoints([{ date: event.data.date, equity }]);
          }
          if (event.data.date && benchmarkEquity !== undefined && benchmarkEquity !== null) {
            backtestStore.addBenchmarkPoints([{ date: event.data.date, equity: benchmarkEquity }]);
          }
          // 更新时间戳
          backtestStore.setLastUpdated(new Date().toLocaleTimeString('zh-CN', { hour12: false }));
        }
        break;

      case 'new_trade':
        if (!eventBuffer.value.has('new_trade')) {
          eventBuffer.value.set('new_trade', []);
        }
        eventBuffer.value.get('new_trade')?.push(event.data);
        break;

      case 'metrics_update':
      case 'final_metrics':
        if (!hasCompleted && event.data) {
          _decompressData(event.data).then((data) => {
            if (data) {
              const metrics = {
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
              backtestStore.setMetrics(metrics);
            }
          }).catch((err) => {
            console.error('解压缩metrics数据失败:', err);
            const data = _decompressDataSync(event.data);
            if (data && !data._compressed) {
              const metrics = {
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
              backtestStore.setMetrics(metrics);
            }
          });
        }
        break;

      case 'risk_data':
      case 'risk_update':
        if (event.data) {
          const type = event.type;
          if (!eventBuffer.value.has(type)) {
            eventBuffer.value.set(type, []);
          }
          eventBuffer.value.get(type)?.push(event.data);
        }
        break;

      case 'stream_complete':
        if (!hasCompleted) {
          processEventBuffer();

          if (event.data && Array.isArray(event.data.trades) && event.data.trades.length > 0) {
            console.log(`[useStreamingBacktest] 从 stream_complete 接收到 ${event.data.trades.length} 条最终交易记录`);
            backtestStore.setTrades(event.data.trades);
          }

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
        processEventBuffer();

        const errorMsg = event.data?.message || '回测发生错误';
        const errorObj = new Error(errorMsg);
        error.value = errorObj;
        
        const backtestError = parseBackendError(
          errorMsg,
          {
            strategyName: currentParams.value?.strategy_name,
            startDate: currentParams.value?.start_date,
            endDate: currentParams.value?.end_date,
            benchmarkCode: currentParams.value?.benchmark_code || undefined
          },
          event.data
        );
        errorStore.setError(backtestError);
        
        backtestStore.setRunning(false);
        backtestStore.setProgress(0);
        isRunning.value = false;
        options.onError?.(errorObj);
        break;

      case 'cancelled':
        processEventBuffer();

        backtestStore.setRunning(false);
        backtestStore.setProgress(0);
        isRunning.value = false;
        options.onCancel?.();
        break;

      case 'backtest_error':
        processEventBuffer();

        const backendErrorMsg = event.data?.message || event.data?.error || '后端回测错误';
        const backendError = parseBackendError(
          backendErrorMsg,
          {
            strategyName: currentParams.value?.strategy_name,
            startDate: currentParams.value?.start_date,
            endDate: currentParams.value?.end_date
          },
          event.data
        );
        errorStore.setError(backendError);
        error.value = new Error(backendErrorMsg);
        
        backtestStore.setRunning(false);
        backtestStore.setProgress(0);
        isRunning.value = false;
        options.onError?.(error.value);
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
    if (updateInterval) {
      clearInterval(updateInterval);
      updateInterval = null;
    }

    processEventBuffer();

    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }

    isRunning.value = false;
    progress.value = 0;
  }

  function retry() {
    if (currentParams.value) {
      errorStore.clearError();
      start(currentParams.value);
    }
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
    retry
  };
}
