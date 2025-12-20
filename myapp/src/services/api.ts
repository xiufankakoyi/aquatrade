import type {
  StrategyInfo,
  KlineData,
  KlineResponse,
  BacktestParams,
  ApiResponse
} from '../types/api';
import { useSocketIO } from '../composables/useSocketIO';

const API_BASE_URL = 'http://localhost:5000/api';

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

  async getKlineData(
    symbolCode: string,
    startDate: string,
    endDate: string
  ): Promise<KlineData[]> {
    const { emitEvent, onEvent } = useSocketIO();
    
    return new Promise((resolve, reject) => {
      const requestId = `kline_${Date.now()}_${Math.random()}`;
      let timeout: ReturnType<typeof setTimeout>;
      
      const unsubscribe = onEvent('kline_data', (response: KlineResponse) => {
        if (response.request_id === requestId) {
          clearTimeout(timeout);
          unsubscribe();
          
          if (response.error) {
            reject(new ApiError(response.error));
          } else {
            resolve(response.data || []);
          }
        }
      });

      timeout = setTimeout(() => {
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
};

export { ApiError };

