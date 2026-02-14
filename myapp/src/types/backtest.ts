/**
 * 回测相关类型定义
 */

// 回测配置
export interface BacktestConfig {
  initialCapital: number;
  startDate: string;
  endDate: string;
  stockPool: 'all' | 'hs300' | 'zz500' | 'zz1000';
  benchmark: string;
  commission: number;
  slippage: number;
}

// 交易记录
export interface Trade {
  id: string;
  date: string;
  stockCode: string;
  stockName?: string;
  action: 'buy' | 'sell';
  price: number;
  volume: number;
  amount?: number;
  commission?: number;
  pnl?: number; // 单笔盈亏
}

// 持仓记录
export interface Position {
  date: string;
  stockCode: string;
  stockName: string;
  volume: number;
  costPrice: number;
  marketPrice?: number;
  marketValue?: number;
  pnl?: number;
}

// 日志条目
export interface LogEntry {
  time: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'warning';
}

// 回测指标
export interface BacktestMetrics {
  totalReturn: number; // 总收益率
  annualReturn: number; // 年化收益率
  sharpeRatio: number; // 夏普比率
  maxDrawdown: number; // 最大回撤
  volatility: number; // 波动率
  winRate: number; // 胜率
  profitLossRatio: number; // 盈亏比
  totalTrades: number; // 总交易次数
  avgHoldingDays: number; // 平均持仓天数
  calmarRatio?: number; // 卡玛比率
  sortinoRatio?: number; // 索提诺比率
  monthlyReturns: Record<string, number>; // 月度回报
}

// 回测结果
export interface BacktestResult {
  equitySeries: Array<{ date: string; equity: number }>;
  benchmarkSeries: Array<{ date: string; equity: number }>;
  positionSeries: Array<{ date: string; position: number }>;
  drawdownSeries: Array<{ date: string; drawdown: number }>;
  tradeFrequencyData: Array<{ date: string; count: number }>;
  trades: Trade[];
  metrics: BacktestMetrics;
}

// 策略信息
export interface Strategy {
  id: string;
  name: string;
  code: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string;
  isRunning?: boolean;
}

// 策略列表项
export interface StrategyListItem {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'error';
  todayReturn: number;
  sharpeRatio: number;
  totalReturn: number;
  lastRunAt?: string;
}
