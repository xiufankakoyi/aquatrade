import type {
  StrategyInfo,
  KlineData,
  KlineResponse,
  BacktestParams,
  ApiResponse
} from '../types/api';
import { useSocketIO } from '../composables/useSocketIO';

// 使用相对路径，让 Vite 代理可以正确代理请求到后端
const API_BASE_URL = '/api';

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        errorData.error || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        errorData.code
      );
    }

    const data: ApiResponse<T> = await response.json();

    if (!data.success) {
      throw new ApiError(data.error || '请求失败', response.status);
    }

    return data.data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error instanceof Error ? error.message : '网络请求失败'
    );
  }
}

export const apiService = {
  async getStrategies(): Promise<StrategyInfo[]> {
    try {
      return await request<StrategyInfo[]>('/strategies');
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return [];
      }
      throw error;
    }
  },

  async runBacktest(params: BacktestParams): Promise<any> {
    return await request('/run_backtest', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  /**
   * 流式回测 - 支持实时更新收益曲线
   * @param params 回测参数
   * @param callbacks 回调函数对象
   * @returns Promise 在回测完成时 resolve
   */
  async runStreamingBacktest(
    params: BacktestParams & { initial_capital?: number; commission?: number; slippage?: number },
    callbacks: {
      onStart?: (data: any) => void;
      onProgress?: (data: any) => void;
      onDailyUpdate?: (data: any) => void;
      onNewTrade?: (data: any) => void;
      onMetricsUpdate?: (data: any) => void;
      onRiskUpdate?: (data: any) => void;
      onComplete?: (data: any) => void;
      onError?: (error: any) => void;
    }
  ): Promise<any> {
    const { emitEvent, onEvent } = useSocketIO();

    return new Promise((resolve, reject) => {
      let result: any = null;
      let hasError = false;

      // 监听回测开始
      const unsubscribeStart = onEvent('backtest_start', (data) => {
        console.log('[流式回测] 开始:', data);
        callbacks.onStart?.(data);
      });

      // 监听进度更新
      const unsubscribeProgress = onEvent('progress', (data) => {
        callbacks.onProgress?.(data);
      });

      // 监听每日权益曲线更新 - 这是流式更新的关键
      const unsubscribeDailyUpdate = onEvent('daily_update', (data) => {
        // 处理 MsgPack 编码的数据
        if (data._msgpack && data._data) {
          try {
            // 解码 base64 数据
            const binaryString = atob(data._data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            // 这里需要 msgpack 解码，暂时直接传递原始数据
            callbacks.onDailyUpdate?.({ date: data.date, equity: data.equity });
          } catch (e) {
            callbacks.onDailyUpdate?.(data);
          }
        } else {
          callbacks.onDailyUpdate?.(data);
        }
      });

      // 监听新交易
      const unsubscribeNewTrade = onEvent('new_trade', (data) => {
        callbacks.onNewTrade?.(data);
      });

      // 监听指标更新
      const unsubscribeMetrics = onEvent('metrics_update', (data) => {
        callbacks.onMetricsUpdate?.(data);
      });

      // 监听风险更新
      const unsubscribeRisk = onEvent('risk_update', (data) => {
        callbacks.onRiskUpdate?.(data);
      });

      // 监听完成
      const unsubscribeComplete = onEvent('stream_complete', (data) => {
        console.log('[流式回测] 完成:', data);
        // 清理所有监听器
        unsubscribeStart();
        unsubscribeProgress();
        unsubscribeDailyUpdate();
        unsubscribeNewTrade();
        unsubscribeMetrics();
        unsubscribeRisk();
        unsubscribeComplete();
        unsubscribeError();
        unsubscribeCancelled();

        if (!hasError) {
          resolve(result || data);
        }
      });

      // 监听错误
      const unsubscribeError = onEvent('backtest_error', (error) => {
        console.error('[流式回测] 错误:', error);
        hasError = true;
        callbacks.onError?.(error);
        reject(new ApiError(error.message || '回测失败'));
      });

      // 监听取消
      const unsubscribeCancelled = onEvent('backtest_cancelled', (data) => {
        console.log('[流式回测] 已取消:', data);
        reject(new ApiError('回测已取消'));
      });

      // 发送流式回测请求
      emitEvent('run_streaming_backtest', {
        strategy_name: params.strategy_name,
        start_date: params.start_date,
        end_date: params.end_date,
        initial_capital: params.initial_capital || 1000000,
        commission: params.commission || 0.0003,
        slippage: params.slippage || 0.001,
      });
    });
  },

  async getKlineData(
    symbolCode: string,
    startDate: string,
    endDate: string
  ): Promise<{ data: KlineData[]; perf?: { query_ms: number; total_ms: number } }> {
    const { emitEvent, onEvent } = useSocketIO();

    return new Promise((resolve, reject) => {
      const requestId = `kline_${Date.now()}_${Math.random()}`;
      let timeout: ReturnType<typeof setTimeout>;

      const unsubscribe = onEvent('kline_data', (response: KlineResponse & { perf?: { query_ms: number; total_ms: number } }) => {
        console.log('[API] 收到 kline_data 事件:', {
          response_request_id: response?.request_id,
          expected_request_id: requestId,
          matched: response?.request_id === requestId,
          has_data: !!response?.data,
          data_length: response?.data?.length,
          has_error: !!response?.error,
          perf: response?.perf
        });

        if (response.request_id === requestId) {
          clearTimeout(timeout);
          unsubscribe();

          if (response.error) {
            reject(new ApiError(response.error));
          } else {
            const data = response.data || [];
            console.log('[API] 解析 K 线数据成功, 长度:', data.length);
            resolve({
              data,
              perf: response.perf
            });
          }
        } else {
          console.warn('[API] request_id 不匹配，忽略此响应:', {
            expected: requestId,
            received: response.request_id
          });
        }
      });

      timeout = setTimeout(() => {
        console.error('[API] K线数据请求超时:', {
          request_id: requestId,
          symbol_code: symbolCode,
          start_date: startDate,
          end_date: endDate
        });
        unsubscribe();
        reject(new ApiError('K线数据请求超时', 408));
      }, 30000);

      emitEvent('request_kline', {
        request_id: requestId,
        symbol_code: symbolCode,
        start_date: startDate,
        end_date: endDate,
      });
    });
  },

  async restartBackend(): Promise<void> {
    await request('/restart-backend', {
      method: 'POST',
    });
  },

  async generateStrategy(description: string, name?: string): Promise<{ filename: string; message: string }> {
    return await request('/strategies/generate', {
      method: 'POST',
      body: JSON.stringify({
        description,
        name: name || 'AI策略',
      }),
    });
  },

  async reloadStrategies(options?: {
    strategy_id?: string;
    file_path?: string;
    refresh_all?: boolean;
  }): Promise<{ action: string; message: string; strategies?: string[]; count?: number }> {
    return await request('/strategies/reload', {
      method: 'POST',
      body: JSON.stringify(options || {}),
    });
  },

  async getDiscoveredStrategies(): Promise<{ strategies: Array<{ id: string; module_path: string }>; count: number }> {
    return await request('/strategies/discovered');
  },

  /**
   * 保存策略文件
   * @param params 策略参数
   * @returns 保存结果
   */
  async saveStrategy(params: {
    name: string;
    description?: string;
    code: string;
    temp?: boolean;
  }): Promise<{ success: boolean; filename?: string; message?: string }> {
    return await request('/strategies/save', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },
};

export { ApiError };

