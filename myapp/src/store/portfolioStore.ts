import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from '../api/index';

export interface Position {
  id?: number;
  stock_code: string;
  stock_name: string;
  buy_price: number;
  shares: number;
  cost: number;
  buy_date: string;
  stop_loss?: number;
  take_profit?: number;
  notes?: string;
  is_active: boolean;
  current_price?: number;
  market_value?: number;
  profit_loss?: number;
  profit_loss_pct?: number;
  weight?: number;
}

/**
 * 持仓历史记录接口
 */
export interface PositionHistory {
  id?: number;
  position_id: number;
  stock_code: string;
  stock_name: string;
  action: 'buy' | 'sell' | 'add' | 'reduce';
  shares: number;
  price: number;
  amount: number;
  date: string;
  notes?: string;
  created_at?: string;
}

/**
 * 持仓历史统计接口
 */
export interface PositionHistoryStats {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  add_count: number;
  reduce_count: number;
  total_buy_amount: number;
  total_sell_amount: number;
}

export interface Signal {
  stock_code: string;
  stock_name: string;
  signal_date: string;
  signal_type: 'buy' | 'sell' | 'watch';
  signal_name: string;
  signal_strength: number;
  price_at_signal: number;
  details: string;
}

export interface PortfolioSummary {
  total_market_value: number;
  total_cost: number;
  total_profit_loss: number;
  total_profit_loss_pct: number;
  position_count: number;
  active_count: number;
}

export interface IndustryDistribution {
  [industry: string]: number;
}

/**
 * 条件项接口
 */
export interface Condition {
  id: string;
  indicator: string;
  operator: string;
  value: number | null;
  period: number;
}

/**
 * 条件组接口
 */
export interface ConditionGroup {
  id: string;
  logic: 'AND' | 'OR';
  conditions: Condition[];
}

/**
 * 信号配置接口
 */
export interface SignalConfig {
  signalType: string;
  conditionGroups: ConditionGroup[];
}

const API_BASE = '/api/portfolio';

export const usePortfolioStore = defineStore('portfolio', () => {
  const positions = ref<Position[]>([]);
  const signals = ref<{ buy: Signal[]; sell: Signal[]; watch: Signal[] }>({
    buy: [],
    sell: [],
    watch: []
  });
  const summary = ref<PortfolioSummary>({
    total_market_value: 0,
    total_cost: 0,
    total_profit_loss: 0,
    total_profit_loss_pct: 0,
    position_count: 0,
    active_count: 0
  });
  const industryDistribution = ref<IndustryDistribution>({});
  const rules = ref<Record<string, any>>({});
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  
  // Signal configuration state
  const signalConfig = ref<SignalConfig | null>(null);
  
  // Position history state
  const positionHistory = ref<PositionHistory[]>([]);
  const positionHistoryStats = ref<PositionHistoryStats | null>(null);

  const profitPositions = computed(() => 
    positions.value.filter(p => (p.profit_loss_pct || 0) > 0)
  );

  const lossPositions = computed(() => 
    positions.value.filter(p => (p.profit_loss_pct || 0) < 0)
  );

  const totalProfitPct = computed(() => summary.value.total_profit_loss_pct);

  async function fetchPositions(activeOnly: boolean = true) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/positions`, {
        params: { active_only: activeOnly }
      });
      if (response.data.success) {
        positions.value = response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取持仓失败';
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchAnalysis() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/analysis`);
      if (response.data.success) {
        const data = response.data.data;
        positions.value = data.positions;
        summary.value = data.summary;
        industryDistribution.value = data.industry_distribution || {};
      }
    } catch (e: any) {
      error.value = e.message || '获取分析失败';
    } finally {
      isLoading.value = false;
    }
  }

  async function addPosition(position: Position) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/positions`, position);
      if (response.data.success) {
        await fetchAnalysis();
        return response.data.data.id;
      }
    } catch (e: any) {
      error.value = e.message || '添加持仓失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  async function updatePosition(position: Position) {
    if (!position.id) return false;
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.put(`${API_BASE}/positions/${position.id}`, position);
      if (response.data.success) {
        await fetchAnalysis();
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '更新持仓失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function deletePosition(positionId: number) {
    isLoading.value = true;
    error.value = null;
    try {
      console.log(`[deletePosition] 正在删除持仓 ID=${positionId}`);
      const response = await axios.delete(`${API_BASE}/positions/${positionId}`);
      console.log(`[deletePosition] 响应:`, response.data);
      if (response.data.success) {
        await fetchAnalysis();
        console.log(`[deletePosition] 删除成功，已刷新数据`);
        return true;
      } else {
        error.value = response.data.error || '删除失败';
        console.error(`[deletePosition] 删除失败:`, response.data.error);
      }
    } catch (e: any) {
      error.value = e.message || '删除持仓失败';
      console.error(`[deletePosition] 请求错误:`, e);
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function fetchSignals(watchlist?: string) {
    isLoading.value = true;
    error.value = null;
    try {
      const params: Record<string, string> = {};
      if (watchlist) {
        params.watchlist = watchlist;
      }
      const response = await axios.get(`${API_BASE}/signals`, { params });
      if (response.data.success) {
        signals.value = response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取信号失败';
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchRules() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/rules`);
      if (response.data.success) {
        rules.value = response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取规则失败';
    } finally {
      isLoading.value = false;
    }
  }

  async function updateRules(newRules: Record<string, any>) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/rules`, newRules);
      if (response.data.success) {
        rules.value = response.data.data;
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '更新规则失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function generateReport() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/report`);
      if (response.data.success) {
        return response.data.data.report;
      }
    } catch (e: any) {
      error.value = e.message || '生成报告失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  async function pushToFeishu(webhookUrl?: string) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/push`, { webhook_url: webhookUrl });
      return response.data.success;
    } catch (e: any) {
      error.value = e.message || '推送失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function fetchSuggestions(watchlist?: string) {
    isLoading.value = true;
    error.value = null;
    try {
      const params: Record<string, string> = {};
      if (watchlist) {
        params.watchlist = watchlist;
      }
      const response = await axios.get(`${API_BASE}/suggestions`, { params });
      if (response.data.success) {
        return response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取建议失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  /**
   * 更新信号配置
   * @param config - 信号配置
   */
  async function updateSignalConfig(config: SignalConfig) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/signal-config`, config);
      if (response.data.success) {
        signalConfig.value = config;
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '更新信号配置失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  /**
   * 获取信号配置
   */
  async function fetchSignalConfig() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/signal-config`);
      if (response.data.success) {
        signalConfig.value = response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取信号配置失败';
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 获取持仓历史记录
   */
  async function fetchPositionHistory(positionId?: number) {
    isLoading.value = true;
    error.value = null;
    try {
      const params: Record<string, number> = {};
      if (positionId) {
        params.position_id = positionId;
      }
      const response = await axios.get(`${API_BASE}/position-history`, { params });
      if (response.data.success) {
        positionHistory.value = response.data.data.history || [];
        positionHistoryStats.value = response.data.data.stats || null;
      }
    } catch (e: any) {
      error.value = e.message || '获取持仓历史失败';
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 添加持仓历史记录
   */
  async function addPositionHistory(history: PositionHistory) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/position-history`, history);
      if (response.data.success) {
        await fetchPositionHistory();
        return response.data.data.id;
      }
    } catch (e: any) {
      error.value = e.message || '添加持仓历史失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  /**
   * 删除持仓历史记录
   */
  async function deletePositionHistory(historyId: number) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.delete(`${API_BASE}/position-history/${historyId}`);
      if (response.data.success) {
        await fetchPositionHistory();
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '删除持仓历史失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  return {
    positions,
    signals,
    summary,
    industryDistribution,
    rules,
    isLoading,
    error,
    signalConfig,
    positionHistory,
    positionHistoryStats,
    profitPositions,
    lossPositions,
    totalProfitPct,
    fetchPositions,
    fetchAnalysis,
    addPosition,
    updatePosition,
    deletePosition,
    fetchSignals,
    fetchRules,
    updateRules,
    generateReport,
    pushToFeishu,
    fetchSuggestions,
    updateSignalConfig,
    fetchSignalConfig,
    fetchPositionHistory,
    addPositionHistory,
    deletePositionHistory
  };
});

export interface WatchItem {
  id?: number;
  stock_code: string;
  stock_name: string;
  buy_target_price?: number;
  sell_target_price?: number;
  conditions?: Array<{
    key: string;
    enabled: boolean;
    params: Record<string, any>;
  }>;
  notes?: string;
  tags?: string[];
  is_active: boolean;
  feishu_notify: boolean;
  last_trigger_time?: string;
  last_trigger_condition?: string;
  last_notify_time?: string;
  created_at?: string;
  updated_at?: string;
  current_price?: number;
}

export interface FeishuWebhookConfig {
  webhook_url: string;
  masked_url: string;
  is_configured: boolean;
}

export interface SignalCheckResult {
  signals: Array<{
    stock_code: string;
    stock_name: string;
    current_price: number;
    condition_key: string;
    condition_name: string;
    message: string;
    severity: 'buy' | 'sell' | 'warning' | 'info';
  }>;
  notified: boolean;
  notification_count: number;
}

export const useWatchlistStore = defineStore('watchlist', () => {
  const watchlist = ref<WatchItem[]>([]);
  const feishuConfig = ref<FeishuWebhookConfig>({
    webhook_url: '',
    masked_url: '',
    is_configured: false
  });
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const lastCheckResult = ref<SignalCheckResult | null>(null);

  async function fetchWatchlist(activeOnly: boolean = true) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${API_BASE}/watchlist`, {
        params: { active_only: activeOnly }
      });
      if (response.data.success) {
        watchlist.value = response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '获取监控列表失败';
    } finally {
      isLoading.value = false;
    }
  }

  async function addWatchlistItem(item: WatchItem) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/watchlist`, item);
      if (response.data.success) {
        await fetchWatchlist();
        return response.data.data.id;
      }
    } catch (e: any) {
      error.value = e.message || '添加监控股票失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  async function updateWatchlistItem(item: WatchItem) {
    if (!item.id) return false;
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.put(`${API_BASE}/watchlist/${item.id}`, item);
      if (response.data.success) {
        await fetchWatchlist();
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '更新监控股票失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function deleteWatchlistItem(itemId: number) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.delete(`${API_BASE}/watchlist/${itemId}`);
      if (response.data.success) {
        await fetchWatchlist();
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '删除监控股票失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function batchAddWatchlist(items: WatchItem[]) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/watchlist/batch`, { items });
      if (response.data.success) {
        await fetchWatchlist();
        return response.data.data.added_count;
      }
    } catch (e: any) {
      error.value = e.message || '批量添加失败';
    } finally {
      isLoading.value = false;
    }
    return 0;
  }

  async function checkSignals(webhookUrl?: string, cooldownHours: number = 4) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/watchlist/check-signals`, {
        webhook_url: webhookUrl,
        cooldown_hours: cooldownHours
      });
      if (response.data.success) {
        lastCheckResult.value = response.data.data;
        return response.data.data;
      }
    } catch (e: any) {
      error.value = e.message || '检查信号失败';
    } finally {
      isLoading.value = false;
    }
    return null;
  }

  async function fetchFeishuConfig() {
    try {
      const response = await axios.get(`${API_BASE}/feishu-webhook`);
      if (response.data.success) {
        feishuConfig.value = response.data.data;
      }
    } catch (e: any) {
      console.error('获取飞书配置失败:', e);
    }
  }

  async function updateFeishuConfig(webhookUrl: string) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/feishu-webhook`, {
        webhook_url: webhookUrl
      });
      if (response.data.success) {
        await fetchFeishuConfig();
        return true;
      }
    } catch (e: any) {
      error.value = e.message || '保存飞书配置失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  async function testFeishuPush(webhookUrl?: string) {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${API_BASE}/feishu-webhook/test`, {
        webhook_url: webhookUrl
      });
      return response.data.success;
    } catch (e: any) {
      error.value = e.message || '测试推送失败';
    } finally {
      isLoading.value = false;
    }
    return false;
  }

  return {
    watchlist,
    feishuConfig,
    isLoading,
    error,
    lastCheckResult,
    fetchWatchlist,
    addWatchlistItem,
    updateWatchlistItem,
    deleteWatchlistItem,
    batchAddWatchlist,
    checkSignals,
    fetchFeishuConfig,
    updateFeishuConfig,
    testFeishuPush
  };
});
