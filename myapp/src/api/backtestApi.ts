import type { Metrics, MonthlyReturn, Trade } from '../types/backtest';
import type { BacktestResult, ParameterSearchResult, StrategyVersion } from '../store/strategyStore';
import { useSocketIO } from '../composables/useSocketIO';

const API_BASE_URL = 'http://localhost:5000/api';

type BacktestEventType = 'initializing' | 'initialized' | 'backtest_start' | 'daily_equity' | 'new_trade' | 'metrics_update' | 'final_metrics' | 'risk_data' | 'stream_complete' | 'progress' | 'error' | 'cancelled';

interface BacktestEvent {
  type: BacktestEventType;
  data: any;
}

const eventSubscribers: Set<(event: BacktestEvent) => void> = new Set();
let isSubscribed = false;
let socketIOInstance: ReturnType<typeof useSocketIO> | null = null;
let unsubscribers: Array<() => void> = [];

function normalizeEvent(eventName: string, data: any): BacktestEvent | null {
  const typeMap: Record<string, BacktestEventType> = {
    'initializing': 'initializing',
    'initialized': 'initialized',
    'backtest_start': 'backtest_start',
    'daily_update': 'daily_equity',
    'new_trade': 'new_trade',
    'metrics_update': 'metrics_update',
    'final_metrics': 'final_metrics',
    'risk_update': 'risk_data',
    'stream_complete': 'stream_complete',
    'progress': 'progress',
    'backtest_error': 'error',
    'backtest_cancelled': 'cancelled'
  };
  
  const type = typeMap[eventName];
  if (!type) return null;
  
  return { type, data };
}

function subscribe(callback: (event: BacktestEvent) => void): () => void {
  eventSubscribers.add(callback);
  
  if (!isSubscribed) {
    isSubscribed = true;
    socketIOInstance = useSocketIO();
    
    const events = ['initializing', 'initialized', 'backtest_start', 'daily_update', 'new_trade', 'metrics_update', 'final_metrics', 'risk_update', 'stream_complete', 'progress', 'backtest_error', 'backtest_cancelled'];
    
    events.forEach(eventName => {
      const unsub = socketIOInstance!.onEvent(eventName, (data: any) => {
        const normalized = normalizeEvent(eventName, data);
        if (normalized) {
          eventSubscribers.forEach(fn => fn(normalized));
        }
      });
      unsubscribers.push(unsub);
    });
  }
  
  return () => {
    eventSubscribers.delete(callback);
    if (eventSubscribers.size === 0 && isSubscribed) {
      unsubscribers.forEach(unsub => unsub());
      unsubscribers = [];
      isSubscribed = false;
    }
  };
}

/**
 * 获取 Dashboard 回测结果
 * 注意：后端没有此端点，数据通过 Socket.IO 实时接收
 * 此函数保留用于兼容，但会返回空数据
 */
export async function getDashboardResult(): Promise<{
  versions: Array<{
    versionId: string;
    versionName: string;
    equityCurve: Array<{ date: string; equity: number }>;
    metrics: Metrics;
  }>;
  benchmark: Array<{ date: string; equity: number }>;
}> {
  return {
    versions: [],
    benchmark: []
  };
}

export { subscribe };

/**
 * 获取策略详情
 * @param versionId 策略版本 ID
 */
export async function getStrategyDetail(versionId: string): Promise<BacktestResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategy/${versionId}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`获取策略详情失败 (${versionId}):`, error);
    throw error;
  }
}

/**
 * 获取参数搜索结果
 * @param versionId 策略版本 ID
 */
export async function getParameterSearchResults(versionId: string): Promise<ParameterSearchResult[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategy/${versionId}/parameters`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error(`获取参数搜索结果失败 (${versionId}):`, error);
    throw error;
  }
}

/**
 * 获取可用的策略版本列表
 */
export async function getAvailableVersions(): Promise<StrategyVersion[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/strategies`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    // 假设后端返回格式为 { success: true, data: [...] }
    const versions = data.data || data;
    return Array.isArray(versions) ? versions : [];
  } catch (error) {
    console.error('获取策略版本列表失败:', error);
    throw error;
  }
}

/**
 * 获取 K 线数据
 * @param symbolCode 股票代码
 * @param startDate 开始日期
 * @param endDate 结束日期
 */
export async function getKlineData(
  symbolCode: string,
  startDate: string,
  endDate: string
): Promise<Array<{
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}>> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/kline?symbol=${symbolCode}&start=${startDate}&end=${endDate}`
    );
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error(`获取 K 线数据失败 (${symbolCode}):`, error);
    throw error;
  }
}

/**
 * 批量获取最新价格
 */
export async function getLatestPrices(
  symbols: string[],
  targetDate?: string
): Promise<Record<string, { price: number; date: string }>> {
  if (!symbols.length) {
    return {};
  }

  const params = new URLSearchParams();
  params.set('symbols', symbols.join(','));
  if (targetDate) {
    params.set('date', targetDate);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/latest_price?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data || {};
  } catch (error) {
    console.error('获取最新价格失败:', error);
    throw error;
  }
}

/**
 * 运行参数优化
 * 通过 Socket.IO 发送优化请求，并通过事件监听进度和结果
 */
export function runOptimization(
  strategyName: string,
  startDate: string,
  endDate: string,
  config: {
    method: 'genetic' | 'bayesian';
    target: string;
    iterations: number;
    population?: number;
    mutationRate?: number;
    crossoverRate?: number;
  },
  selectedParams: Record<string, [number, number]>
): void {
  import('../composables/useSocketIO').then(({ useSocketIO }) => {
    const socket = useSocketIO();
    socket.emitEvent('run_optimization', {
      strategy_name: strategyName,
      start_date: startDate,
      end_date: endDate,
      config: config,
      selected_params: selectedParams
    });
  });
}

/**
 * 为指定策略创建参数预设（Profile）
 */
export async function createStrategyProfile(
  strategyName: string,
  payload: {
    profile_name: string;
    description?: string;
    params: Record<string, any>;
    source?: string;
  }
): Promise<any> {
  const res = await fetch(`/api/strategies/${encodeURIComponent(strategyName)}/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`创建策略预设失败: HTTP ${res.status} ${res.statusText} - ${text}`);
  }

  const data = await res.json();
  if (!data?.success) {
    throw new Error(data?.error || '创建策略预设失败');
  }
  return data.data;
}

/**
 * 获取某个策略下的所有参数预设
 */
export async function fetchStrategyProfiles(strategyName: string): Promise<any[]> {
  const res = await fetch(`/api/strategies/${encodeURIComponent(strategyName)}/profiles`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`获取策略预设失败: HTTP ${res.status} ${res.statusText} - ${text}`);
  }
  const data = await res.json();
  if (!data?.success) {
    throw new Error(data?.error || '获取策略预设失败');
  }
  return data.data || [];
}

export interface StockSentimentItem {
  symbol: string;
  stockCode: string;
  stockName: string;
  totalPosts: number;
  totalClicks: number;
  totalComments: number;
  bullishCount: number;
  bearishCount: number;
  neutralCount: number;
  sentimentScore: number;
  lastPostTime: string | null;
  activeDays: number | null;
}

/**
 * 获取股票舆情/风评汇总数据
 */
export async function fetchStockSentiment(limit = 50, retryCount = 3): Promise<StockSentimentItem[]> {
  const params = new URLSearchParams();
  if (limit && limit > 0) {
    params.set('limit', String(limit));
  }

  const url = params.toString()
    ? `${API_BASE_URL}/stock_sentiment?${params.toString()}`
    : `${API_BASE_URL}/stock_sentiment`;

  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < retryCount; attempt++) {
    try {
      console.log(`尝试获取股票风评数据 (第 ${attempt + 1} 次)...`);
      
      // 添加超时控制（放宽到 60 秒，避免后端重计算时被过早中断）
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 秒超时
      
      const res = await fetch(url, {
        signal: controller.signal,
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      
      const data = await res.json();
      
      if (data && data.success && Array.isArray(data.data)) {
        return data.data as StockSentimentItem[];
      }
      if (Array.isArray(data)) {
        return data as StockSentimentItem[];
      }
      
      throw new Error('服务器返回的数据格式不正确');
    } catch (error) {
      console.error(`获取股票风评数据失败 (第 ${attempt + 1} 次尝试):`, error);
      lastError = error as Error;
      
      // 最后一次尝试失败
      if (attempt === retryCount - 1) {
        break;
      }
      
      // 等待一段时间后重试，指数退避
      const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  // 所有重试都失败
  console.error('获取股票风评数据失败，已达到最大重试次数:', lastError);
  throw lastError || new Error('获取股票风评数据失败');
}

export interface StockWordCloudWord {
  word: string;
  weight: number;
  positiveWeight: number;
  negativeWeight: number;
  count: number;
}

export interface StockWordCloudResponse {
  symbol: string;
  stockCode: string;
  stockName: string;
  totalPosts: number;
  totalClicks: number;
  totalComments: number;
  overallSentiment: number | null;
  words: StockWordCloudWord[];
}

/**
 * 获取单只股票的词云数据
 */
export async function fetchStockWordCloud(symbol: string): Promise<StockWordCloudResponse | null> {
  if (!symbol) return null;

  const params = new URLSearchParams();
  params.set('symbol', symbol);

  const url = `${API_BASE_URL}/stock_sentiment_words?${params.toString()}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    if (data && data.success && data.data) {
      return data.data as StockWordCloudResponse;
    }
    return null;
  } catch (error) {
    console.error('获取股票词云数据失败:', error);
    throw error;
  }
}

// 新增 API 接口用于 Dashboard
export interface SentimentTrendPoint {
  date: string;
  post_count: number;
  avg_sentiment: number;
}

export interface LdaTopicData {
  topics: string[];
  scores: number[];
}

export interface ScatterDataPoint {
  x: number;
  y: number;
  symbol: string;
  name: string;
  size: number;
  color: string;
}

/**
 * 获取情感趋势数据
 */
export async function fetchSentimentTrend(symbol?: string, days?: number): Promise<SentimentTrendPoint[]> {
  try {
    const params = new URLSearchParams();
    if (symbol) params.append('symbol', symbol);
    if (days) params.append('days', days.toString());
    
    const url = `${API_BASE_URL}/sentiment_trends${params.toString() ? '?' + params.toString() : ''}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    // 从后端响应中提取数据
    if (result && result.success && result.data) {
      return result.data;
    }
    
    throw new Error('Invalid data format from API');
  } catch (error) {
    console.error('获取情感趋势数据失败:', error);
    throw error;
  }
}

/**
 * 获取 LDA 主题分布数据
 */
export async function fetchLdaTopics(symbol?: string): Promise<LdaTopicData> {
  try {
    const params = new URLSearchParams();
    if (symbol) params.append('symbol', symbol);
    
    const url = `${API_BASE_URL}/lda_topics${params.toString() ? '?' + params.toString() : ''}`;
    console.log('Fetching LDA topics from:', url);
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    console.log('LDA topics API response:', result);
    
    // 从后端响应中提取数据 - 新格式
    if (result && result.success && result.data && result.data.topics && result.data.scores) {
      return {
        topics: result.data.topics,
        scores: result.data.scores
      };
    }
    
    throw new Error('Invalid data format from API');
  } catch (error) {
    console.error('获取 LDA 主题分布数据失败:', error);
    throw error;
  }
}

/**
 * 获取散点图数据
 */
export async function fetchScatterData(symbol?: string, retryCount = 3): Promise<ScatterDataPoint[]> {
  const params = new URLSearchParams();
  if (symbol) params.append('symbol', symbol);
  
  const url = `${API_BASE_URL}/scatter_data${params.toString() ? '?' + params.toString() : ''}`;
  console.log('Fetching scatter data from:', url);
  
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < retryCount; attempt++) {
    try {
      console.log(`尝试获取散点图数据 (第 ${attempt + 1} 次)...`);
      
      // 添加超时控制（放宽到 60 秒，避免后端重计算时被过早中断）
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 秒超时
      
      const response = await fetch(url, {
        signal: controller.signal,
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Scatter data API response:', result);
      
      // 从后端响应中提取数据并转换为前端期望的格式
      if (result && result.success && result.data) {
        return result.data.map((stock: any) => {
          // 根据情感值分配颜色
          let color = '#94a3b8'; // 默认中性色
          if (stock.sentiment > 0.2) {
            color = '#10b981'; // 积极 - 绿色
          } else if (stock.sentiment < -0.2) {
            color = '#ef4444'; // 消极 - 红色
          }
          
          return {
            x: stock.comment_count,
            y: stock.sentiment,
            symbol: stock.symbol,
            name: stock.name,
            size: Math.log(stock.market_cap + 1) * 10, // 使用市值的对数作为大小
            color: color
          };
        });
      }
      
      throw new Error('服务器返回的数据格式不正确');
    } catch (error) {
      console.error(`获取散点图数据失败 (第 ${attempt + 1} 次尝试):`, error);
      lastError = error as Error;
      
      // 最后一次尝试失败
      if (attempt === retryCount - 1) {
        break;
      }
      
      // 等待一段时间后重试，指数退避
      const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  // 所有重试都失败
  console.error('获取散点图数据失败，已达到最大重试次数:', lastError);
  throw lastError || new Error('获取散点图数据失败');
}
