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

// 【修复】数据解压缩和分块处理工具函数
let chunkedDataBuffers: Map<string, { chunks: any[], totalChunks: number, otherData: any }> = new Map();

async function _decompressData(data: any): Promise<any> {
  // 处理压缩数据
  if (data._compressed && data._data) {
    try {
      // 浏览器端解压缩
      const compressed = Uint8Array.from(atob(data._data), c => c.charCodeAt(0));
      
      // 使用浏览器原生DecompressionStream（Chrome 80+, Firefox 113+）
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
      
      // 回退：尝试使用pako库（如果已安装）
      // @ts-ignore
      if (typeof window !== 'undefined' && window.pako) {
        // @ts-ignore
        const pako = window.pako;
        const text = pako.inflate(compressed, { to: 'string' });
        return JSON.parse(text);
      }
      
      // 如果都不支持，返回原始数据（后端应该检测到不支持压缩时不会压缩）
      console.warn('浏览器不支持gzip解压缩，使用原始数据');
      return data;
    } catch (e) {
      console.error('解压缩失败:', e);
      return data;
    }
  }
  return data;
}

// 同步版本（用于非异步场景）
function _decompressDataSync(data: any): any {
  if (data._compressed && data._data) {
    // 如果浏览器不支持，直接返回原始数据
    // 实际解压缩应该在异步函数中完成
    console.warn('同步解压缩不可用，使用原始数据');
    return data;
  }
  return data;
}

function _handleChunkedData(data: any, key: string): any {
  // 处理分块数据
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
    
    // 如果所有块都接收完成
    if (buffer.chunks.length === buffer.totalChunks && 
        buffer.chunks.every(chunk => chunk !== undefined)) {
      // 合并数据
      const result = { ...buffer.otherData };
      result[data._key] = buffer.chunks.flat();
      
      // 清理缓冲区
      chunkedDataBuffers.delete(chunkKey);
      
      return result;
    }
    
    // 还在接收中，返回null
    return null;
  }
  
  // 非分块数据，使用同步解压缩（实际解压缩在异步函数中完成）
  return _decompressDataSync(data);
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
          // 【修复】处理压缩和分块数据（异步解压缩）
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
            // 回退：尝试使用原始数据
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
          // 【修复】处理压缩和分块数据
          const data = _handleChunkedData(event.data, 'risk_data');
          if (data) {
            if (data.monthlyReturns && Array.isArray(data.monthlyReturns)) {
              backtestStore.setMonthlyReturns(data.monthlyReturns);
            } else if (data.monthly_returns && Array.isArray(data.monthly_returns)) {
              backtestStore.setMonthlyReturns(data.monthly_returns);
            }
            if (data.holdingPeriods && Array.isArray(data.holdingPeriods)) {
              backtestStore.setHoldingPeriods(data.holdingPeriods);
            }
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

