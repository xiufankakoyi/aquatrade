<template>
  <div class="metrics-panel">
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-chart-bar"></i>
        策略收益指标
      </h3>
    </div>

    <div class="metrics-grid">
      <!-- 策略收益 -->
      <div class="metric-group">
        <h4 class="group-title">收益指标</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">策略收益</span>
            <span class="metric-value" :class="getValueClass(metrics.strategyReturn)">
              {{ formatPercent(metrics.strategyReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">策略年化收益</span>
            <span class="metric-value" :class="getValueClass(metrics.annualReturn)">
              {{ formatPercent(metrics.annualReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">超额收益</span>
            <span class="metric-value" :class="getValueClass(metrics.excessReturn)">
              {{ formatPercent(metrics.excessReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">基准收益</span>
            <span class="metric-value" :class="getValueClass(metrics.benchmarkReturn)">
              {{ formatPercent(metrics.benchmarkReturn) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 风险指标 -->
      <div class="metric-group">
        <h4 class="group-title">风险指标</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">最大回撤</span>
            <span class="metric-value text-down">
              {{ formatPercent(metrics.maxDrawdown) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">策略波动率</span>
            <span class="metric-value">{{ formatPercent(metrics.strategyVolatility) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">基准波动率</span>
            <span class="metric-value">{{ formatPercent(metrics.benchmarkVolatility) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">最大回撤区间</span>
            <span class="metric-value">{{ metrics.maxDrawdownPeriod }}</span>
          </div>
        </div>
      </div>

      <!-- 风险调整收益 -->
      <div class="metric-group">
        <h4 class="group-title">风险调整收益</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">夏普比率</span>
            <span class="metric-value highlight">{{ metrics.sharpeRatio.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">索提诺比率</span>
            <span class="metric-value">{{ metrics.sortinoRatio.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">卡玛比率</span>
            <span class="metric-value">{{ metrics.calmarRatio.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">信息比率</span>
            <span class="metric-value">{{ metrics.informationRatio.toFixed(2) }}</span>
          </div>
        </div>
      </div>

      <!-- Alpha/Beta -->
      <div class="metric-group">
        <h4 class="group-title">Alpha / Beta</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">阿尔法 (α)</span>
            <span class="metric-value" :class="getValueClass(metrics.alpha)">
              {{ metrics.alpha.toFixed(4) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">贝塔 (β)</span>
            <span class="metric-value">{{ metrics.beta.toFixed(4) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">日均超额收益</span>
            <span class="metric-value" :class="getValueClass(metrics.dailyExcessReturn)">
              {{ formatPercent(metrics.dailyExcessReturn) }}
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">超额收益最大回撤</span>
            <span class="metric-value text-down">
              {{ formatPercent(metrics.excessMaxDrawdown) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 交易统计 -->
      <div class="metric-group">
        <h4 class="group-title">交易统计</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">胜率</span>
            <span class="metric-value text-up">{{ formatPercent(metrics.winRate) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">盈亏比</span>
            <span class="metric-value">{{ metrics.profitLossRatio.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">盈利次数</span>
            <span class="metric-value text-up">{{ metrics.winCount }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">亏损次数</span>
            <span class="metric-value text-down">{{ metrics.lossCount }}</span>
          </div>
        </div>
      </div>

      <!-- 其他指标 -->
      <div class="metric-group">
        <h4 class="group-title">其他指标</h4>
        <div class="group-content">
          <div class="metric-item">
            <span class="metric-label">日胜率</span>
            <span class="metric-value">{{ formatPercent(metrics.dailyWinRate) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">超额收益夏普比率</span>
            <span class="metric-value">{{ metrics.excessSharpeRatio.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">总交易次数</span>
            <span class="metric-value">{{ metrics.totalTrades }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">平均持仓天数</span>
            <span class="metric-value">{{ metrics.avgHoldingDays.toFixed(1) }}天</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Metrics {
  // 收益指标
  strategyReturn: number;
  annualReturn: number;
  excessReturn: number;
  benchmarkReturn: number;
  
  // 风险指标
  maxDrawdown: number;
  strategyVolatility: number;
  benchmarkVolatility: number;
  maxDrawdownPeriod: string;
  
  // 风险调整收益
  sharpeRatio: number;
  sortinoRatio: number;
  calmarRatio: number;
  informationRatio: number;
  
  // Alpha/Beta
  alpha: number;
  beta: number;
  dailyExcessReturn: number;
  excessMaxDrawdown: number;
  excessSharpeRatio: number;
  
  // 交易统计
  winRate: number;
  profitLossRatio: number;
  winCount: number;
  lossCount: number;
  dailyWinRate: number;
  totalTrades: number;
  avgHoldingDays: number;
}

interface Props {
  metrics: Metrics;
}

const props = withDefaults(defineProps<Props>(), {
  metrics: () => ({
    strategyReturn: 0,
    annualReturn: 0,
    excessReturn: 0,
    benchmarkReturn: 0,
    maxDrawdown: 0,
    strategyVolatility: 0,
    benchmarkVolatility: 0,
    maxDrawdownPeriod: '--',
    sharpeRatio: 0,
    sortinoRatio: 0,
    calmarRatio: 0,
    informationRatio: 0,
    alpha: 0,
    beta: 0,
    dailyExcessReturn: 0,
    excessMaxDrawdown: 0,
    excessSharpeRatio: 0,
    winRate: 0,
    profitLossRatio: 0,
    winCount: 0,
    lossCount: 0,
    dailyWinRate: 0,
    totalTrades: 0,
    avgHoldingDays: 0,
  }),
});

function formatPercent(value: number): string {
  if (value === undefined || value === null) return '0.00%';
  const sign = value >= 0 ? '+' : '';
  return sign + (value * 100).toFixed(2) + '%';
}

function getValueClass(value: number): string {
  if (value > 0) return 'text-up';
  if (value < 0) return 'text-down';
  return '';
}
</script>

<style scoped>
.metrics-panel {
  background-color: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--border-color);
}

.panel-header {
  margin-bottom: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.panel-title i {
  color: var(--accent-primary);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.metric-group {
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.group-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.metric-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

.metric-value.highlight {
  color: var(--accent-primary);
  font-size: 14px;
}

.metric-value.text-up {
  color: var(--color-up);
}

.metric-value.text-down {
  color: var(--color-down);
}

/* 响应式 */
@media (max-width: 1199px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
