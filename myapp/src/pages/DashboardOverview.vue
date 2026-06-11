<template>
  <main class="dashboard">
    <header class="hero card">
      <div>
        <p class="eyebrow">AQUATRADE RESEARCH</p>
        <h1>策略回测仪表盘</h1>
        <div class="meta">
          <span>{{ strategyStore.currentVersion?.name || '未选择策略' }}</span>
          <span>{{ startDate }} 至 {{ endDate }}</span>
          <span>基准 {{ benchmark }}</span>
          <DataStatusBadge :status="dataHealth?.status" />
        </div>
      </div>
      <div class="actions">
        <button class="secondary" @click="activeTab = 'brief'">AI 复盘</button>
        <button class="primary" :disabled="isBacktestRunning" @click="runBacktest">
          {{ isBacktestRunning ? `运行中 ${progress}%` : '运行回测' }}
        </button>
      </div>
    </header>

    <section v-if="mockVisible" class="mock-banner">
      当前展示的是 Mock 回测数据，不代表真实策略结果。
    </section>

    <section class="filters card">
      <label>开始日期<input v-model="startDate" type="date"></label>
      <label>结束日期<input v-model="endDate" type="date"></label>
      <label>基准<select v-model="benchmark"><option value="000300.SH">沪深300</option><option value="000905.SH">中证500</option></select></label>
      <button class="link-button" @click="refreshWorkbench">刷新数据状态</button>
    </section>

    <ErrorState v-if="pageError" :message="pageError" @retry="refreshWorkbench" />
    <LoadingState v-else-if="pageLoading" title="正在加载研究工作台" />

    <template v-else>
      <section class="kpis">
        <article class="card kpi"><span>累计收益</span><strong>{{ formatPercent(metrics?.totalReturn) }}</strong><small>回测区间累计</small></article>
        <article class="card kpi"><span>最大回撤</span><strong class="risk">{{ formatPercent(metrics?.maxDrawdown) }}</strong><small>峰值至谷值</small></article>
        <article class="card kpi"><span>夏普比率</span><strong>{{ formatScore(metrics?.sharpeRatio) }}</strong><small>风险调整后指标</small></article>
        <article class="card kpi"><span>{{ tradeCount ? '胜率' : '风险状态' }}</span><strong>{{ tradeCount ? formatPercent(metrics?.winRate) : 'N/A' }}</strong><small>{{ tradeCount ? `盈亏比 ${profitRatioText}` : '无交易记录，无法计算' }}</small></article>
      </section>

      <section class="main-grid">
        <article class="card chart-card">
          <div class="section-title"><div><h2>净值曲线 vs 基准</h2><p>主图展示真实回测结果；无结果时不自动回退到 Mock。</p></div><DataStatusBadge :status="hasBacktestData ? 'ok' : 'unknown'" :label="hasBacktestData ? '已有回测结果' : '尚未运行'" /></div>
          <div class="chart-body">
            <EquityCurve v-if="hasBacktestData" :versions="equityVersions" :benchmark="backtestStore.benchmarkEquitySeries" />
            <EmptyState v-else title="尚未运行回测" description="请检查策略与日期后点击“运行回测”" />
          </div>
        </article>

        <aside class="card quant-card">
          <div class="section-title"><div><h2>QuantFlow</h2><p>最近一次五分钟投研流水线</p></div><button class="link-button" :disabled="quantRunning" @click="runQuantFlow">{{ quantRunning ? '运行中' : '立即运行' }}</button></div>
          <LoadingState v-if="quantLoading" title="正在读取流水线" />
          <ErrorState v-else-if="quantError" :message="quantError" @retry="loadQuantFlow" />
          <EmptyState v-else-if="!quantFlow?.run_at" title="尚未运行 QuantFlow" description="点击“立即运行”生成本地研究简报" />
          <template v-else>
            <p class="run-time">最近运行：{{ formatDateTime(quantFlow.run_at) }}</p>
            <ul class="stage-list">
              <li v-for="stage in quantFlow.stages" :key="stage.stage">
                <DataStatusBadge :status="stage.status === 'skipped' ? 'unknown' : stage.status" :label="stageLabel(stage.stage)" />
                <span>{{ stage.summary }}</span>
              </li>
            </ul>
            <p class="brief">{{ quantFlow.final_brief?.summary }}</p>
          </template>
        </aside>
      </section>

      <section class="support-grid">
        <article class="card support-card"><h2>月度收益</h2><div class="month-grid" v-if="backtestStore.monthlyReturns.length"><template v-for="row in backtestStore.monthlyReturns" :key="row.year"><span v-for="(value, index) in row.months" :key="`${row.year}-${index}`">{{ value == null ? 'N/A' : formatPercent(value) }}</span></template></div><EmptyState v-else description="暂无月度收益数据" /></article>
        <article class="card support-card"><h2>回撤曲线</h2><div class="support-chart"><DrawdownChart v-if="hasBacktestData" :equity-series="backtestStore.equitySeries" /><EmptyState v-else description="尚未运行回测" /></div></article>
        <article class="card support-card"><h2>风险指标</h2><dl class="risk-list"><div><dt>波动率</dt><dd>{{ formatPercent(metrics?.volatility) }}</dd></div><div><dt>交易次数</dt><dd>{{ tradeCount }}</dd></div><div><dt>盈亏比</dt><dd>{{ profitRatioText }}</dd></div><div><dt>数据状态</dt><dd>{{ dataHealth?.status || 'unknown' }}</dd></div></dl></article>
      </section>

      <section class="card details">
        <nav class="tabs">
          <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button>
        </nav>
        <div class="tab-body">
          <div v-if="activeTab === 'trades'">
            <table v-if="backtestStore.trades.length"><thead><tr><th>日期</th><th>代码</th><th>动作</th><th>价格</th><th>数量</th><th>损益</th></tr></thead><tbody><tr v-for="trade in backtestStore.trades" :key="trade.id"><td>{{ trade.date }}</td><td>{{ trade.symbolCode || trade.symbol }}</td><td>{{ trade.action }}</td><td>{{ formatAmount(trade.price) }}</td><td>{{ trade.quantity || 0 }}</td><td>{{ formatAmount(trade.profitLoss || 0) }}</td></tr></tbody></table>
            <EmptyState v-else title="暂无交易明细" description="无交易记录，胜率和盈亏比无法计算" />
          </div>
          <EmptyState v-else-if="activeTab === 'positions'" title="暂无当前持仓" description="当前回测结果未返回持仓快照" />
          <EmptyState v-else-if="activeTab === 'signals'" title="暂无信号日志" description="策略信号接口未返回本地证据" />
          <dl v-else-if="activeTab === 'metrics'" class="metric-explain"><div><dt>累计收益</dt><dd>回测结束净值相对初始净值的变化。</dd></div><div><dt>最大回撤</dt><dd>回测期间从峰值到后续谷值的最大跌幅。</dd></div><div><dt>胜率与盈亏比</dt><dd>仅在存在交易记录时计算。</dd></div></dl>
          <div v-else-if="activeTab === 'data'"><DataStatusBadge :status="dataHealth?.status" /><ul class="data-list"><li v-for="item in dataHealth?.datasets || []" :key="item.name"><strong>{{ item.name }}</strong><span>最新 {{ item.latest_date || 'N/A' }} · 行数 {{ formatInteger(item.row_count) }} · {{ item.message }}</span></li></ul></div>
          <div v-else><p class="brief">{{ quantFlow?.final_brief?.summary || '暂无本地证据' }}</p></div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useBacktestStore } from '../store/backtestStore'
import { useStrategyStore } from '../store/strategyStore'
import { useStreamingBacktest } from '../composables/useStreamingBacktest'
import { isFetchMockEnabled } from '../api/fetchMock'
import { generateMockBacktestData } from '../api/mockSocketIO'
import EquityCurve from '../components/EquityCurve.vue'
import DrawdownChart from '../components/charts/DrawdownChart.vue'
import LoadingState from '../components/common/LoadingState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import DataStatusBadge from '../components/common/DataStatusBadge.vue'

const backtestStore = useBacktestStore()
const strategyStore = useStrategyStore()
const { start, isRunning: isBacktestRunning, progress } = useStreamingBacktest()
const today = new Date()
const endDate = ref(today.toISOString().slice(0, 10))
const startDate = ref(new Date(today.getFullYear() - 1, today.getMonth(), today.getDate()).toISOString().slice(0, 10))
const benchmark = ref('000300.SH')
const pageLoading = ref(true)
const pageError = ref('')
const quantLoading = ref(false)
const quantRunning = ref(false)
const quantError = ref('')
const dataHealth = ref<any>(null)
const quantFlow = ref<any>(null)
const mockVisible = ref(false)
const activeTab = ref('trades')
const tabs = [
  { key: 'trades', label: '交易明细' }, { key: 'positions', label: '当前持仓' },
  { key: 'signals', label: '信号日志' }, { key: 'metrics', label: '指标解释' },
  { key: 'data', label: '数据状态' }, { key: 'brief', label: '投研简报' },
]
const metrics = computed(() => backtestStore.metrics)
const tradeCount = computed(() => metrics.value?.tradesCount ?? metrics.value?.totalTrades ?? backtestStore.trades.length)
const hasBacktestData = computed(() => backtestStore.equitySeries.length > 0)
const profitRatioText = computed(() => tradeCount.value > 0 ? formatScore(metrics.value?.profitLossRatio ?? metrics.value?.profitFactor) : 'N/A')
const equityVersions = computed(() => hasBacktestData.value ? [{ versionId: 'current', versionName: strategyStore.currentVersion?.name || '当前策略', data: backtestStore.equitySeries }] : [])

function formatPercent(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return 'N/A'
  const normalized = Math.abs(value) <= 1 ? value * 100 : value
  return `${normalized.toFixed(2)}%`
}
function formatScore(value?: number | null) { return value == null || !Number.isFinite(value) ? 'N/A' : value.toFixed(4) }
function formatAmount(value: number) { const abs = Math.abs(value); if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`; if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`; return value.toFixed(2) }
function formatInteger(value: number | null) { return value == null ? 'N/A' : value.toLocaleString('zh-CN') }
function formatDateTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function stageLabel(stage: string) { return ({ data_health_check: '数据健康', market_regime_detect: '市场状态', dragon_eye_summary: '市场雷达', stock_screener_candidates: '研究候选', strategy_signal_scan: '策略信号', portfolio_risk_check: '持仓风险', final_research_brief: '最终简报' } as Record<string, string>)[stage] || stage }

async function fetchJson(url: string, init?: RequestInit) {
  const response = await fetch(url, init)
  const payload = await response.json()
  if (!response.ok || payload.success === false) throw new Error(payload.error || payload.message || `HTTP ${response.status}`)
  return payload.data
}
async function loadStrategies() {
  const data = await fetchJson('/api/strategies')
  const versions = (Array.isArray(data) ? data : []).map((item: any) => ({ id: item.id, name: item.name, version: item.version || 'local', createdAt: item.createdAt || new Date().toISOString(), description: item.description || '' }))
  strategyStore.setAvailableVersions(versions)
  if (!strategyStore.currentVersionId && versions.length) strategyStore.setCurrentVersion(versions[0].id)
}
async function loadDataHealth() { dataHealth.value = await fetchJson('/api/data/health') }
async function loadQuantFlow() {
  quantLoading.value = true; quantError.value = ''
  try { quantFlow.value = await fetchJson('/api/quant-flow/latest') } catch (error) { quantError.value = error instanceof Error ? error.message : 'QuantFlow 加载失败' } finally { quantLoading.value = false }
}
async function refreshWorkbench() {
  pageLoading.value = true; pageError.value = ''
  try { await Promise.all([loadStrategies(), loadDataHealth(), loadQuantFlow()]); backtestStore.hydrateFromStorage() } catch (error) { pageError.value = error instanceof Error ? error.message : '工作台加载失败' } finally { pageLoading.value = false }
}
function loadMockBacktest() {
  const mock = generateMockBacktestData(strategyStore.currentVersion?.name || 'MockStrategy')
  const full = mock.getFullData(); const result = mock.getFinalMetrics()
  backtestStore.clearBacktestData()
  backtestStore.addEquityPoints(full.equityCurve)
  backtestStore.addBenchmarkPoints(full.benchmark)
  backtestStore.setTrades(full.trades)
  backtestStore.setMetrics({ totalReturn: result.totalReturn, annualizedReturn: result.annualReturn, maxDrawdown: result.maxDrawdown, sharpeRatio: result.sharpeRatio, volatility: result.volatility, winRate: result.winRate, profitFactor: result.profitLossRatio, profitLossRatio: result.profitLossRatio, tradesCount: result.totalTrades })
  backtestStore.setMonthlyReturns(mock.getMonthlyReturns())
  mockVisible.value = true
}
function runBacktest() {
  pageError.value = ''; mockVisible.value = false
  if (!strategyStore.currentVersion) { pageError.value = '暂无可运行策略'; return }
  if (isFetchMockEnabled()) { loadMockBacktest(); return }
  start({ strategy_name: strategyStore.currentVersion.name, start_date: startDate.value, end_date: endDate.value, benchmark_code: benchmark.value, initial_capital: 1000000, commission: 0.0003, slippage: 0.001 }, {
    onError: (error) => { pageError.value = error.message },
  })
}
async function runQuantFlow() {
  quantRunning.value = true; quantError.value = ''
  try { quantFlow.value = await fetchJson('/api/quant-flow/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); await loadDataHealth() } catch (error) { quantError.value = error instanceof Error ? error.message : 'QuantFlow 运行失败' } finally { quantRunning.value = false }
}
onMounted(refreshWorkbench)
</script>

<style scoped>
.dashboard { min-height: 100%; padding: 22px; color: #172033; background: #f3f1eb; overflow: auto; }
.card { background: rgba(255,255,255,.92); border: 1px solid #e6e2d8; border-radius: 16px; box-shadow: 0 8px 24px rgba(51,65,85,.06); }
.hero { display: flex; justify-content: space-between; gap: 24px; padding: 24px 26px; }
.eyebrow { margin: 0 0 6px; color: #4774b8; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h1,h2,p { margin-top: 0; } h1 { margin-bottom: 10px; font-size: 28px; } h2 { margin-bottom: 5px; font-size: 16px; }
.meta,.actions,.filters { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }.meta { color: #64748b; font-size: 13px; }
button { border: 0; border-radius: 10px; padding: 10px 16px; font-weight: 700; cursor: pointer; } button:disabled { opacity: .55; cursor: default; }
.primary { color: white; background: #3569ad; }.secondary { color: #315f98; background: #e8f0fa; }.link-button { color: #315f98; background: #edf3fa; padding: 8px 12px; }
.filters { margin-top: 14px; padding: 14px 18px; }.filters label { display: grid; gap: 4px; color: #64748b; font-size: 12px; }.filters input,.filters select { min-width: 150px; padding: 8px 10px; border: 1px solid #d9dee7; border-radius: 8px; color: #334155; background: white; }
.mock-banner { margin-top: 14px; padding: 12px 16px; border: 1px solid #f4c86d; border-radius: 12px; color: #7c4b00; background: #fff7df; font-weight: 700; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }.kpi { padding: 18px; }.kpi span,.kpi small { display: block; color: #7b8799; }.kpi strong { display: block; margin: 8px 0 4px; font-size: 25px; color: #244e83; }.kpi strong.risk { color: #b45353; }
.main-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, .8fr); gap: 14px; margin-top: 14px; }.chart-card,.quant-card,.support-card,.details { padding: 18px; }.section-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.section-title p { color: #8a94a4; font-size: 12px; }.chart-body { height: 430px; }.run-time,.brief { color: #64748b; font-size: 13px; line-height: 1.7; }.stage-list { display: grid; gap: 9px; padding: 0; list-style: none; }.stage-list li { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 8px; color: #526174; font-size: 12px; }
.support-grid { display: grid; grid-template-columns: 1.05fr 1.4fr .8fr; gap: 14px; margin-top: 14px; }.support-chart { height: 210px; }.month-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }.month-grid span { padding: 8px; border-radius: 8px; text-align: center; color: #475569; background: #f1f5f9; font-size: 12px; }.risk-list,.metric-explain { display: grid; gap: 0; }.risk-list div,.metric-explain div { display: flex; justify-content: space-between; gap: 16px; padding: 11px 0; border-bottom: 1px solid #edf0f4; }.risk-list dt,.metric-explain dt { color: #64748b; }.risk-list dd,.metric-explain dd { margin: 0; font-weight: 700; }
.details { margin-top: 14px; }.tabs { display: flex; gap: 6px; border-bottom: 1px solid #e5e7eb; }.tabs button { border-radius: 8px 8px 0 0; color: #64748b; background: transparent; }.tabs button.active { color: #24578f; background: #eaf1f9; }.tab-body { min-height: 190px; padding-top: 16px; } table { width: 100%; border-collapse: collapse; } th,td { padding: 10px; border-bottom: 1px solid #edf0f4; text-align: left; font-size: 12px; }.data-list { display: grid; gap: 8px; padding: 0; list-style: none; }.data-list li { display: flex; justify-content: space-between; gap: 14px; padding: 10px 0; border-bottom: 1px solid #edf0f4; color: #64748b; }.data-list strong { color: #334155; }
@media (max-width: 1050px) { .kpis,.support-grid { grid-template-columns: repeat(2, 1fr); }.main-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .dashboard { padding: 12px; }.hero { flex-direction: column; }.kpis,.support-grid { grid-template-columns: 1fr; }.chart-body { height: 320px; } }
</style>
