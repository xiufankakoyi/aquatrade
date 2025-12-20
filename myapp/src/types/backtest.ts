// 策略接口
export interface Strategy {
  id: string;
  name: string;
  displayName?: string;
  description?: string;
}

// 月度收益接口 - 支持两种格式
export interface MonthlyReturn {
  date?: string;
  return?: number;
  benchmarkReturn?: number;
  year?: number;
  months?: (number | null)[];
}

// 交易接口
export interface Trade {
  id?: string;
  symbol: string;
  symbolCode?: string;
  date: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  value: number;
  commission?: number;  // CHANGED: 添加手续费字段
  profitLoss?: number;
  profit_loss?: number;  // 后端返回的 snake_case 格式
  cumulativePnL?: number;
  positionId?: string;
  entryDate?: string;
  exitDate?: string;
  holdingDays?: number;  // CHANGED: 添加持有周期字段（天数）
  holding_days?: number;  // 后端返回的 snake_case 格式
  entry_price?: number;  // 后端返回的 FIFO 匹配的开仓价
  exit_price?: number;  // 后端返回的 FIFO 匹配的平仓价
  roi?: number;  // 后端返回的收益率
}

// 回撤接口
export interface Drawdown {
  date?: string;
  drawdown?: number;
  peak?: number;
  valley?: number;
  startDate?: string;
  value?: number;
}

// 持仓周期接口
export interface HoldingPeriod {
  symbol?: string;
  buyDate?: string;
  sellDate?: string;
  days?: number;
  positionId?: string;
  symbolCode?: string;
  symbolName?: string;
  entryDate?: string;
  exitDate?: string | null;
  profit?: number;
  holdingDays?: number;
  quantity?: number;
  entryPrice?: number;
  availableQuantity?: number;
}

// 金融数据点接口
export interface FinancialDataPoint {
  date?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  x?: number;
  o?: number;
  h?: number;
  l?: number;
  c?: number;
  v?: number;
}

// 指标接口
export interface Metrics {
  totalReturn: number;
  annualizedReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  totalTrades?: number;
  tradesCount?: number;
  profitTrades?: number;
  lossTrades?: number;
  avgWin?: number;
  avgLoss?: number;
  profitFactor: number;
  volatility?: number;
  calmarRatio?: number;
  sortinoRatio?: number;
  avgTradeReturn?: number;
  maxWinningStreak?: number;
  maxLosingStreak?: number;
}

// 会话快照接口
export interface SessionSnapshot {
  id?: string;
  timestamp?: number;
  strategyName?: string;
  startDate?: string;
  endDate?: string;
  benchmarkCode?: string | null;
  metrics: Metrics;
  equityCurve?: Array<{ date: string; equity: number }>;
  trades?: Trade[];
  monthlyReturns?: MonthlyReturn[];
  dailyEquityMap?: Record<string, number>;
  dailyReturnsMap?: Record<string, number>;
  totalTrades?: number;
  holdingPeriodsByPosition?: Record<string, HoldingPeriod>;
  holdingPeriodsBySymbol?: Record<string, HoldingPeriod[]>;
  equitySeries?: {
    labels: string[];
    strategy: number[];
    benchmark: number[];
  };
  drawdownSeries?: {
    labels: string[];
    values: number[];
  };
}

// 会话摘要接口
export interface SessionSummary {
  id?: string;
  strategyName?: string;
  date?: string;
  dateRange?: string;
  createdAt?: string;
  status?: 'running' | 'completed' | 'error' | 'cancelled';
  metrics?: Metrics;
  totalReturn?: number;
  annualizedReturn?: number;
  maxDrawdown?: number;
}

// 策略会话接口
export interface StrategySession {
  id: string;
  strategyId: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  summary: SessionSummary;
}

// 标的统计接口
export interface SymbolTopStat {
  symbol?: string;
  symbolCode?: string;
  symbolName?: string;
  totalReturn?: number;
  totalProfit?: number;
  tradeCount?: number;
  winRate?: number;
  avgReturn?: number;
  maxHoldingDays?: number;
  firstEntryDate?: string;
  lastExitDate?: string | null;
}

// 高亮范围接口
export interface HighlightRange {
  start?: string;
  end?: string;
  entryDate?: string;
  exitDate?: string | null;
  color?: string;
  label?: string;
}

