<template>
  <div class="similarity-page">
    <!-- Header -->
    <div class="page-header">
      <div class="flex items-center gap-3">
        <div class="w-1 h-8 bg-gradient-to-b from-purple-500 to-purple-600 rounded-full"></div>
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">K线形态研究</h1>
          <p class="text-sm text-[#787b86] mt-1">相似形态匹配与短线形态雷达统一工作台</p>
        </div>
      </div>
      <div class="module-switch" role="tablist" aria-label="形态研究模块">
        <button
          type="button"
          :class="{ active: activeModule === 'similarity' }"
          @click="setActiveModule('similarity')"
        >
          K线相似度
        </button>
        <button
          type="button"
          :class="{ active: activeModule === 'radar' }"
          @click="setActiveModule('radar')"
        >
          短线形态雷达
        </button>
      </div>
    </div>

    <div class="page-content" v-if="activeModule === 'similarity'">
      <a-row :gutter="24">
        <!-- 左侧搜索面板 -->
        <a-col :span="7">
          <div class="search-panel">
            <!-- 股票代码搜索 -->
            <div class="panel-section">
              <h3 class="section-title">选择股票</h3>
              <a-auto-complete
              v-model:value="searchForm.stock_code"
              :options="stockOptions"
              :filter-option="false"
              :dropdown-match-select-width="false"
              style="width: 100%"
              @search="onStockSearch"
              @select="onStockSelect"
              placeholder="输入股票代码，如 000001"
              popup-class-name="dark-select-dropdown"
            >
                <template #option="{ value, label }">
                  <div class="stock-option" style="min-width: 200px;">
                    <span class="stock-code">{{ value }}</span>
                    <span class="stock-name">{{ label }}</span>
                  </div>
                </template>
              </a-auto-complete>
            </div>

            <!-- K线预览图 -->
            <div class="panel-section" v-if="templateKlines.length > 0">
              <h3 class="section-title">模板K线</h3>
              <div class="template-kline-chart" ref="templateChartRef"></div>
              <div class="selection-info" v-if="selectionRange.start >= 0">
                <span>已选择: {{ selectionRange.end - selectionRange.start + 1 }} 日</span>
                <a-button type="primary" size="small" @click="onMatchWithSelection" :loading="loading">
                  匹配相似形态
                </a-button>
              </div>
            </div>

            <!-- 匹配参数 -->
            <div class="panel-section">
              <h3 class="section-title">匹配参数</h3>
              <a-form layout="vertical" :model="searchForm" class="search-form">
                <a-form-item label="返回数量">
                  <a-select v-model:value="searchForm.top_n" placeholder="选择返回数量">
                    <a-select-option :value="5">Top 5</a-select-option>
                    <a-select-option :value="10">Top 10</a-select-option>
                    <a-select-option :value="20">Top 20</a-select-option>
                  </a-select>
                </a-form-item>

                <a-form-item label="匹配算法">
                  <a-select v-model:value="searchForm.algorithm" placeholder="选择匹配算法">
                    <a-select-option value="dtw">DTW（经典）</a-select-option>
                    <a-select-option value="skeleton">骨架算法（推荐）</a-select-option>
                  </a-select>
                </a-form-item>

                <a-form-item label="场景配置" v-if="searchForm.algorithm === 'skeleton'">
                  <a-select v-model:value="searchForm.scene" placeholder="选择场景" allow-clear>
                    <a-select-option value="default">默认平衡</a-select-option>
                    <a-select-option value="breakout_volume">连板爆量</a-select-option>
                    <a-select-option value="limit_break">断板推新高</a-select-option>
                    <a-select-option value="n_shape">N字走势</a-select-option>
                    <a-select-option value="trend">趋势跟踪</a-select-option>
                  </a-select>
                </a-form-item>
              </a-form>
            </div>
          </div>
        </a-col>

        <!-- 右侧结果 -->
                <a-col :span="17">
          <!-- 主K线图 -->
          <div class="main-chart-panel" v-if="mainKlines.length > 0">
            <div class="chart-header">
              <span class="chart-title">{{ selectedStock }} - 近30日走势</span>
              <span class="chart-hint">在图表上拖动框选匹配区域</span>
            </div>
            <div class="main-kline-chart" ref="mainChartRef"></div>
          </div>

          <!-- 匹配结果 -->
          <div class="result-panel">
            <div class="result-header">
              <span class="result-title">匹配结果</span>
              <span class="result-count" v-if="resultData.length > 0">
                共 {{ resultData.length }} 条记录
              </span>
            </div>

            <a-table
              :columns="columns"
              :data-source="resultData"
              :loading="loading"
              :pagination="false"
              :locale="{ emptyText: '暂无匹配结果' }"
              :scroll="{ x: 880 }"
              :row-key="(record: any) => `${record.stock_code}-${record.start_date}-${record.end_date}`"
              :expanded-row-keys="expandedRowKeys"
              @expand="onExpand"
              class="result-table"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'stock_code'">
                  <div class="stock-code-cell">
                    <span class="code-main">{{ record.stock_name || record.stock_code }}</span>
                    <span class="code-sub">{{ record.start_date }} ~ {{ record.end_date }}</span>
                  </div>
                </template>
                <template v-else-if="column.key === 'similarity_score'">
                  <div class="score-cell">
                    <span class="score-value">{{ record.similarity_score?.toFixed(4) ?? '-' }}</span>
                    <div
                      class="score-bar"
                      :style="{ width: ((record.similarity_score || 0) * 100) + '%' }"
                    ></div>
                  </div>
                </template>
                <template v-else-if="column.key === 'date_range'">
                  {{ record.start_date }} ~ {{ record.end_date }}
                </template>
                <template v-else-if="column.key === 'structure_score'">
                  {{ record.structure_score != null ? record.structure_score.toFixed(4) : '-' }}
                </template>
                <template v-else-if="column.key === 'rhythm_score'">
                  {{ record.rhythm_score != null ? record.rhythm_score.toFixed(4) : '-' }}
                </template>
                <template v-else-if="column.key === 'ma_fit_score'">
                  {{ record.ma_fit_score != null ? record.ma_fit_score.toFixed(4) : '-' }}
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" size="small" @click="onViewKline(record)">
                    查看后续K线
                  </a-button>
                </template>
              </template>

              <template #expandedRowRender="{ record }">
                <div class="kline-preview-inline">
                  <!-- 前序+匹配+后续K线完整预览 -->
                  <div class="inline-kline-wrapper" v-if="record.matched_kline && record.matched_kline.length > 0">
                    <span class="inline-kline-label">
                      <template v-if="record.preceding_kline && record.preceding_kline.length > 0">
                        {{ record.preceding_kline.length }}日+
                      </template>
                      {{ record.matched_kline.length }}日
                      <template v-if="record.subsequent_kline && record.subsequent_kline.length > 0">
                        +{{ record.subsequent_kline.length }}日
                      </template>
                    </span>
                    <div class="inline-kline-chart" :id="`full-chart-${record.stock_code}-${record.end_date}`"></div>
                  </div>
                  <div v-else class="inline-kline-empty">暂无K线数据</div>
                </div>
              </template>
            </a-table>

            <div v-if="!loading && resultData.length === 0" class="empty-result">
              <InboxOutlined class="empty-icon" />
              <p>暂无匹配结果</p>
              <p class="empty-hint">请选择股票并框选K线形态后开始匹配</p>
            </div>
          </div>
        </a-col>
      </a-row>
    </div>

    <div class="page-content radar-content" v-else>
      <div class="search-panel radar-panel">
        <div class="radar-toolbar">
          <div>
            <h3 class="section-title">形态模板</h3>
            <p class="radar-subtitle">按事件标签扫描历史样本和近端候选，仅展示结构、原因、风险标签与统计结果。</p>
          </div>
          <a-button type="primary" :loading="radarLoading" @click="runRadarScan">
            {{ radarLoading ? '扫描中...' : '开始扫描' }}
          </a-button>
        </div>

        <div class="radar-template-grid">
          <button
            v-for="template in patternTemplates"
            :key="template.pattern_id"
            type="button"
            class="radar-template-card"
            :class="{ active: template.pattern_id === radarState.patternId }"
            @click="radarState.patternId = template.pattern_id"
          >
            <span class="template-name">{{ template.pattern_name }}</span>
            <span class="template-desc">{{ template.description }}</span>
          </button>
          <div v-if="!patternTemplates.length" class="radar-empty-card">暂无模板</div>
        </div>

        <a-form layout="vertical" :model="radarState" class="radar-form">
          <a-row :gutter="16">
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="开始日期">
                <a-input v-model:value="radarState.startDate" type="date" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="结束日期">
                <a-input v-model:value="radarState.endDate" type="date" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="股票池">
                <a-input v-model:value="radarState.symbolsText" placeholder="000001.SZ,000002.SZ" allow-clear />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="返回数量">
                <a-select v-model:value="radarState.limit">
                  <a-select-option :value="20">20 条</a-select-option>
                  <a-select-option :value="50">50 条</a-select-option>
                  <a-select-option :value="100">100 条</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item>
                <template #label>成交额门槛 <span class="amount-hint">{{ formatAmount(radarState.minAmount) }}</span></template>
                <a-input-number v-model:value="radarState.minAmount" :min="0" :step="1000000" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item>
                <template #label>最小市值 <span class="amount-hint">{{ formatAmount(radarState.minMarketCap) }}</span></template>
                <a-input-number v-model:value="radarState.minMarketCap" :min="0" :step="100000000" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item>
                <template #label>最大市值 <span class="amount-hint">{{ formatAmount(radarState.maxMarketCap) }}</span></template>
                <a-input-number v-model:value="radarState.maxMarketCap" :min="0" :step="100000000" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="最小累计涨幅">
                <a-input-number v-model:value="radarState.minCumulativeGainPct" :min="0" :step="1" addon-after="%" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="最少强势日">
                <a-input-number v-model:value="radarState.minStrongAttackDays" :min="1" :max="5" :step="1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12" :lg="6">
              <a-form-item label="过滤项">
                <a-space>
                  <a-checkbox v-model:checked="radarState.excludeSt">排除 ST</a-checkbox>
                  <a-checkbox v-model:checked="radarState.excludeOneLineLimit">排除一字板</a-checkbox>
                </a-space>
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>
        <p class="research-boundary">结果仅用于形态研究和样本统计，不构成交易指令。</p>
      </div>

      <div class="radar-summary-grid">
        <div class="metric-card">
          <span>命中数</span>
          <strong>{{ radarReport?.summary.total_matches ?? 0 }}</strong>
        </div>
        <div class="metric-card">
          <span>成功样本</span>
          <strong>{{ radarReport?.summary.success_cases ?? 0 }}</strong>
        </div>
        <div class="metric-card">
          <span>失败样本</span>
          <strong>{{ radarReport?.summary.failure_cases ?? 0 }}</strong>
        </div>
        <div class="metric-card">
          <span>成功率</span>
          <strong>{{ formatPercent(radarSuccessRatePct) }}</strong>
        </div>
      </div>

      <ErrorState v-if="radarError" :message="radarError" :retryable="false" />

      <div class="radar-result-grid">
        <div class="result-panel radar-result-panel">
          <div class="result-header">
            <span class="result-title">雷达结果</span>
            <span class="result-count" v-if="radarResults.length > 0">
              共 {{ radarResults.length }} 条记录
            </span>
          </div>

          <a-table
            :columns="radarColumns"
            :data-source="radarResults"
            :loading="radarLoading"
            :pagination="{ pageSize: 12, showSizeChanger: false }"
            :locale="{ emptyText: '暂无雷达结果' }"
            :scroll="{ x: 1120 }"
            :row-key="radarRowKey"
            :custom-row="radarCustomRow"
            :row-class-name="radarRowClassName"
            class="result-table radar-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'symbol'">
                <div class="stock-code-cell">
                  <span class="code-main">{{ record.stock_name || record.symbol }}</span>
                  <span class="code-sub">{{ record.symbol }} / {{ record.match_date }}</span>
                </div>
              </template>
              <template v-else-if="column.key === 'match_score'">
                <div class="score-cell">
                  <span class="score-value">{{ formatScore(record.match_score) }}</span>
                  <div class="score-bar" :style="{ width: `${Math.min((record.match_score || 0) * 100, 100)}%` }"></div>
                </div>
              </template>
              <template v-else-if="column.key === 'hit_reasons'">
                <div class="tag-list">
                  <a-tag v-for="reason in safeList(record.hit_reasons).slice(0, 3)" :key="reason" color="purple">
                    {{ reason }}
                  </a-tag>
                  <span v-if="safeList(record.hit_reasons).length === 0" class="muted-text">暂无</span>
                </div>
              </template>
              <template v-else-if="column.key === 'risk_flags'">
                <div class="tag-list">
                  <a-tag v-for="risk in safeList(record.risk_flags)" :key="risk" color="gold">
                    {{ risk }}
                  </a-tag>
                  <span v-if="safeList(record.risk_flags).length === 0" class="muted-text">无</span>
                </div>
              </template>
              <template v-else-if="column.key === 'future_return_1d'">
                <span :class="returnClass(record.future_return_1d)">{{ formatPercent(record.future_return_1d) }}</span>
              </template>
              <template v-else-if="column.key === 'future_return_3d'">
                <span :class="returnClass(record.future_return_3d)">{{ formatPercent(record.future_return_3d) }}</span>
              </template>
              <template v-else-if="column.key === 'future_return_5d'">
                <span :class="returnClass(record.future_return_5d)">{{ formatPercent(record.future_return_5d) }}</span>
              </template>
              <template v-else-if="column.key === 'future_return_10d'">
                <span :class="returnClass(record.future_return_10d)">{{ formatPercent(record.future_return_10d) }}</span>
              </template>
            </template>
          </a-table>

          <div v-if="!radarLoading && radarResults.length === 0" class="empty-result">
            <InboxOutlined class="empty-icon" />
            <p>暂无雷达结果</p>
            <p class="empty-hint">选择模板和参数后开始扫描</p>
          </div>
        </div>

        <PatternCaseReplay :match="selectedRadarMatch" class="radar-case-panel" />
      </div>
    </div>

    <!-- K线详情弹窗 -->
    <StockKlineModal
      v-model:visible="klineModalVisible"
      :stock-code="selectedStockCode"
      :stock-name="selectedStockName"
      :current-price="selectedCurrentPrice"
      :change-percent="selectedChangePercent"
      @close="onKlineModalClose"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue'
import ErrorState from '@/components/common/ErrorState.vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { matchSimilarity, searchStocks, getStockKline, type MatchResultItem, type KlineItem } from '@/api/similarity'
import { getPatternTemplates, searchPatterns, type PatternMatch, type PatternReport, type PatternTemplate } from '@/api/pattern'
import PatternCaseReplay from '@/components/pattern/PatternCaseReplay.vue'
import StockKlineModal from '@/components/screener/StockKlineModal.vue'
import * as echarts from 'echarts'

// ============ 状态 ============
type ModuleKey = 'similarity' | 'radar'
const route = useRoute()
const router = useRouter()
const activeModule = ref<ModuleKey>(readModuleFromQuery())
const loading = ref(false)
const resultData = ref<MatchResultItem[]>([])
const stockOptions = ref<{ value: string; label: string }[]>([])
const selectedStock = ref('')
const mainKlines = ref<KlineItem[]>([])
const templateKlines = ref<KlineItem[]>([])
const expandedRowKeys = ref<string[]>([])

// 框选范围
const selectionRange = reactive({
  start: -1,
  end: -1
})

const searchForm = reactive({
  stock_code: '',
  window_size: 20,
  top_n: 10,
  pattern_type: null as string | null,
  corr_threshold: 0.5,
  subsequent_days: 5,
  algorithm: 'dtw' as 'dtw' | 'skeleton',
  scene: 'default'
})

interface RadarState {
  patternId: string
  startDate: string
  endDate: string
  symbolsText: string
  minAmount: number
  minMarketCap: number
  maxMarketCap: number
  minCumulativeGainPct: number
  minStrongAttackDays: number
  excludeSt: boolean
  excludeOneLineLimit: boolean
  limit: number
}

const RADAR_STORAGE_KEY = 'aquatrade_pattern_radar_state'
const patternTemplates = ref<PatternTemplate[]>([])
const radarReport = ref<PatternReport | null>(null)
const selectedRadarMatch = ref<PatternMatch | null>(null)
const radarLoading = ref(false)
const radarError = ref('')

const radarState = reactive<RadarState>({
  patternId: 'strong_break_reversal',
  startDate: '2024-01-01',
  endDate: '2024-03-31',
  symbolsText: '',
  minAmount: 0,
  minMarketCap: 0,
  maxMarketCap: 0,
  minCumulativeGainPct: 20,
  minStrongAttackDays: 2,
  excludeSt: true,
  excludeOneLineLimit: false,
  limit: 100
})

const radarResults = computed(() => radarReport.value?.results || [])
const radarSelectedKey = computed(() => (selectedRadarMatch.value ? radarRowKey(selectedRadarMatch.value) : ''))
const radarSuccessRatePct = computed(() => {
  const rate = radarReport.value?.summary.success_rate
  return rate === null || rate === undefined ? null : rate * 100
})

// K线弹窗状态
const klineModalVisible = ref(false)
const selectedStockCode = ref('')
const selectedStockName = ref('')
const selectedCurrentPrice = ref(0)
const selectedChangePercent = ref(0)

// 图表实例
const mainChartRef = ref<HTMLElement | null>(null)
const templateChartRef = ref<HTMLElement | null>(null)
let mainChart: echarts.ECharts | null = null
let templateChart: echarts.ECharts | null = null

// 展开行图表实例管理
const expandedCharts = new Map<string, echarts.ECharts>()

function renderExpandedCharts() {
  resultData.value.forEach(record => {
    // 渲染完整K线（前序+匹配+后续）
    if (record.matched_kline && record.matched_kline.length > 0) {
      const chartId = `full-chart-${record.stock_code}-${record.end_date}`
      const chartDom = document.getElementById(chartId)
      if (chartDom) {
        renderFullKlineChart(chartDom, record)
      }
    }
  })
}

function renderFullKlineChart(dom: HTMLElement, record: MatchResultItem) {
  const chartKey = dom.id
  // 销毁已存在的图表
  if (expandedCharts.has(chartKey)) {
    expandedCharts.get(chartKey)!.dispose()
  }

  const chart = echarts.init(dom)
  expandedCharts.set(chartKey, chart)

  // 合并前序+匹配+后续K线
  const preceding = record.preceding_kline || []
  const matched = record.matched_kline || []
  const subsequent = record.subsequent_kline || []
  const fullKlines = [...preceding, ...matched, ...subsequent]

  if (fullKlines.length === 0) return

  // 计算各段的分隔位置
  const precedingEnd = preceding.length
  const matchedEnd = precedingEnd + matched.length

  // 为不同段设置不同颜色
  const dataWithStyle = fullKlines.map((k, i) => {
    const isPreceding = i < precedingEnd
    const isMatched = i >= precedingEnd && i < matchedEnd

    // 前序和后续用淡色，匹配段用标准色
    if (isMatched) {
      return {
        value: [k.open, k.close, k.low, k.high],
        itemStyle: {
          color: k.close >= k.open ? '#ef5350' : '#26a69a',
          color0: k.close >= k.open ? '#ef5350' : '#26a69a',
          borderColor: k.close >= k.open ? '#ef5350' : '#26a69a',
          borderColor0: k.close >= k.open ? '#ef5350' : '#26a69a'
        }
      }
    } else if (isPreceding) {
      // 前序K线用灰色调
      return {
        value: [k.open, k.close, k.low, k.high],
        itemStyle: {
          color: k.close >= k.open ? '#6b7280' : '#4b5563',
          color0: k.close >= k.open ? '#6b7280' : '#4b5563',
          borderColor: k.close >= k.open ? '#6b7280' : '#4b5563',
          borderColor0: k.close >= k.open ? '#6b7280' : '#4b5563'
        }
      }
    } else {
      // 后续K线用半透明色
      return {
        value: [k.open, k.close, k.low, k.high],
        itemStyle: {
          color: k.close >= k.open ? 'rgba(239, 83, 80, 0.5)' : 'rgba(38, 166, 154, 0.5)',
          color0: k.close >= k.open ? 'rgba(239, 83, 80, 0.5)' : 'rgba(38, 166, 154, 0.5)',
          borderColor: k.close >= k.open ? 'rgba(239, 83, 80, 0.5)' : 'rgba(38, 166, 154, 0.5)',
          borderColor0: k.close >= k.open ? 'rgba(239, 83, 80, 0.5)' : 'rgba(38, 166, 154, 0.5)'
        }
      }
    }
  })

  // 添加分隔线标记
  const markLines = []
  if (precedingEnd > 0) {
    markLines.push({
      xAxis: precedingEnd - 0.5,
      lineStyle: { color: '#8b5cf6', type: 'dashed', width: 1 },
      label: { show: false }
    })
  }
  if (matchedEnd < fullKlines.length) {
    markLines.push({
      xAxis: matchedEnd - 0.5,
      lineStyle: { color: '#8b5cf6', type: 'dashed', width: 1 },
      label: { show: false }
    })
  }

  // 计算价格范围，确保K线有足够的高度展示
  const allPrices = fullKlines.flatMap(k => [k.high, k.low])
  const minPrice = Math.min(...allPrices)
  const maxPrice = Math.max(...allPrices)
  const priceRange = maxPrice - minPrice
  // 添加10%的padding，确保K线不会贴边
  const yMin = minPrice - priceRange * 0.1
  const yMax = maxPrice + priceRange * 0.1

  const option = {
    backgroundColor: 'transparent',
    grid: {
      left: '2%',
      right: '2%',
      top: '8%',
      bottom: '8%'
    },
    xAxis: {
      type: 'category',
      data: fullKlines.map((_, i) => i + 1),
      axisLine: { show: false },
      axisLabel: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
      axisLine: { show: false },
      axisLabel: { show: false },
      axisTick: { show: false },
      splitLine: { show: false }
    },
    series: [
      {
        type: 'candlestick',
        data: dataWithStyle,
        markLine: markLines.length > 0 ? {
          data: markLines,
          symbol: ['none', 'none']
        } : undefined
      }
    ]
  }

  chart.setOption(option)
}

// ============ 表格列定义 ============
const columns = [
  {
    title: '股票名称',
    dataIndex: 'stock_code',
    key: 'stock_code',
    width: 180,
    fixed: 'left'
  },
  {
    title: '相似度得分',
    dataIndex: 'similarity_score',
    key: 'similarity_score',
    width: 140
  },
  {
    title: '结构分',
    dataIndex: 'structure_score',
    key: 'structure_score',
    width: 90
  },
  {
    title: '节奏分',
    dataIndex: 'rhythm_score',
    key: 'rhythm_score',
    width: 90
  },
  {
    title: '均线拟合',
    dataIndex: 'ma_fit_score',
    key: 'ma_fit_score',
    width: 100
  },
  {
    title: '操作',
    key: 'action',
    width: 110,
    fixed: 'right'
  }
]

const radarColumns = [
  {
    title: '股票',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 180,
    fixed: 'left'
  },
  {
    title: '分数',
    dataIndex: 'match_score',
    key: 'match_score',
    width: 120
  },
  {
    title: '形态',
    dataIndex: 'pattern_name',
    key: 'pattern_name',
    width: 150
  },
  {
    title: '命中原因',
    dataIndex: 'hit_reasons',
    key: 'hit_reasons',
    width: 260
  },
  {
    title: '风险标签',
    dataIndex: 'risk_flags',
    key: 'risk_flags',
    width: 180
  },
  {
    title: '1日',
    dataIndex: 'future_return_1d',
    key: 'future_return_1d',
    width: 90
  },
  {
    title: '3日',
    dataIndex: 'future_return_3d',
    key: 'future_return_3d',
    width: 90
  },
  {
    title: '5日',
    dataIndex: 'future_return_5d',
    key: 'future_return_5d',
    width: 90
  },
  {
    title: '10日',
    dataIndex: 'future_return_10d',
    key: 'future_return_10d',
    width: 90
  }
]

function readModuleFromQuery(): ModuleKey {
  const module = route.query.module || route.query.tab
  return module === 'radar' ? 'radar' : 'similarity'
}

function setActiveModule(module: ModuleKey) {
  activeModule.value = module
  const query = { ...route.query }
  if (module === 'radar') {
    query.module = 'radar'
    void ensurePatternTemplates()
  } else {
    delete query.module
    delete query.tab
  }
  void router.replace({ path: '/similarity', query })
}

async function ensurePatternTemplates(): Promise<void> {
  if (patternTemplates.value.length > 0) return
  try {
    patternTemplates.value = await getPatternTemplates()
    if (!patternTemplates.value.some(template => template.pattern_id === radarState.patternId)) {
      radarState.patternId = patternTemplates.value[0]?.pattern_id || radarState.patternId
    }
  } catch (error) {
    radarError.value = error instanceof Error ? error.message : '形态模板加载失败'
  }
}

function restoreRadarState(): void {
  try {
    const saved = localStorage.getItem(RADAR_STORAGE_KEY)
    if (!saved) return
    Object.assign(radarState, JSON.parse(saved) as Partial<RadarState>)
  } catch {
    localStorage.removeItem(RADAR_STORAGE_KEY)
  }
}

async function runRadarScan(): Promise<void> {
  if (!radarState.startDate || !radarState.endDate) {
    message.warning('请先选择扫描日期范围')
    return
  }
  if (!radarState.patternId) {
    message.warning('请先选择形态模板')
    return
  }

  radarLoading.value = true
  radarError.value = ''
  selectedRadarMatch.value = null
  try {
    await ensurePatternTemplates()
    const symbols = radarState.symbolsText
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)

    radarReport.value = await searchPatterns({
      pattern_id: radarState.patternId,
      start_date: radarState.startDate,
      end_date: radarState.endDate,
      symbols: symbols.length > 0 ? symbols : undefined,
      limit: radarState.limit,
      params: {
        min_amount: radarState.minAmount,
        min_market_cap: radarState.minMarketCap,
        max_market_cap: radarState.maxMarketCap,
        min_cumulative_gain_pct: radarState.minCumulativeGainPct,
        min_strong_attack_days: radarState.minStrongAttackDays,
        exclude_st: radarState.excludeSt,
        exclude_one_line_limit: radarState.excludeOneLineLimit
      }
    })
    selectedRadarMatch.value = radarReport.value.results[0] || null
    message.success(`扫描完成，命中 ${radarReport.value.results.length} 条记录`)
  } catch (error) {
    radarError.value = error instanceof Error ? error.message : '形态扫描失败'
    message.error(radarError.value)
  } finally {
    radarLoading.value = false
  }
}

function radarRowKey(item: PatternMatch): string {
  return `${item.pattern_id}:${item.symbol}:${item.match_date}`
}

function radarCustomRow(record: PatternMatch) {
  return {
    onClick: () => {
      selectedRadarMatch.value = record
    }
  }
}

function radarRowClassName(record: PatternMatch): string {
  return radarRowKey(record) === radarSelectedKey.value ? 'radar-row-selected' : ''
}

function safeList(value?: string[] | null): string[] {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function formatScore(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toFixed(4)
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function returnClass(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return ''
  return value >= 0 ? 'return-up' : 'return-down'
}

function formatAmount(value?: number | null): string {
  if (!value || Number.isNaN(value)) return '0'
  const absValue = Math.abs(value)
  if (absValue >= 100000000) return `${(value / 100000000).toFixed(2)}亿`
  if (absValue >= 10000) return `${(value / 10000).toFixed(2)}万`
  return value.toFixed(2)
}

// ============ 股票搜索 ============
let searchTimeout: NodeJS.Timeout | null = null

async function onStockSearch(keyword: string) {
  if (!keyword) {
    stockOptions.value = []
    return
  }

  // 防抖
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }

  searchTimeout = setTimeout(async () => {
    try {
      const res = await searchStocks(keyword, 10)
      if (res.data.success) {
        const rawOptions = res.data.data.map((item: any) => ({
          value: item.code,
          label: item.name || item.code
        }))
        
        // 去重：如果存在 000001 和 000001.SZ，只保留带后缀的完整格式
        const seen = new Map<string, { value: string; label: string }>()
        rawOptions.forEach((opt: { value: string; label: string }) => {
          const code = opt.value.toUpperCase()
          // 提取纯数字代码（去掉后缀）
          const pureCode = code.replace(/\.(SZ|SH|BJ)$/, '')
          
          if (seen.has(pureCode)) {
            const existing = seen.get(pureCode)!
            const existingCode = existing.value.toUpperCase()
            // 如果已有的是短格式（无后缀），替换为长格式（有后缀）
            if (!existingCode.match(/\.(SZ|SH|BJ)$/)) {
              seen.set(pureCode, opt)
            }
            // 否则保留已有的长格式
          } else {
            seen.set(pureCode, opt)
          }
        })
        
        stockOptions.value = Array.from(seen.values())
      } else {
        console.error('搜索失败:', res.data.error)
      }
    } catch (error) {
      console.error('搜索股票失败:', error)
    }
  }, 300)
}

async function onStockSelect(stockCode: string) {
  selectedStock.value = stockCode
  searchForm.stock_code = stockCode

  // 加载K线数据
  try {
    const res = await getStockKline(stockCode, 30)
    if (res.data.success) {
      mainKlines.value = res.data.data.klines
      // 使用 nextTick 确保 DOM 更新后再初始化图表
      nextTick(() => {
        setTimeout(() => {
          initMainChart()
        }, 100)
      })
    }
  } catch (error) {
    message.error('加载K线数据失败')
  }
}

// ============ K线图 ============
function initMainChart() {
  if (!mainChartRef.value || mainKlines.value.length === 0) return

  if (mainChart) {
    mainChart.dispose()
  }

  mainChart = echarts.init(mainChartRef.value)

  const data = mainKlines.value.map(k => [
    k.trade_date,
    k.open,
    k.close,
    k.low,
    k.high
  ])

  const option = {
    backgroundColor: 'transparent',
    grid: {
      left: '10%',
      right: '10%',
      top: '10%',
      bottom: '15%'
    },
    xAxis: {
      type: 'category',
      data: mainKlines.value.map(k => k.trade_date),
      axisLine: { lineStyle: { color: '#333' } },
      axisLabel: { color: '#787b86' }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { lineStyle: { color: '#333' } },
      axisLabel: { color: '#787b86' },
      splitLine: { lineStyle: { color: '#1a1a1a' } }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      }
    ],
    series: [
      {
        type: 'candlestick',
        data: data.map(d => [d[1], d[2], d[3], d[4]]),
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a'
        }
      }
    ],
    brush: {
      toolbox: ['rect', 'clear'],
      brushMode: 'single',
      brushStyle: {
        borderWidth: 1,
        color: 'rgba(139, 92, 246, 0.2)',
        borderColor: '#8b5cf6'
      }
    }
  }

  mainChart.setOption(option)

  // 监听框选事件
  mainChart.on('brushSelected', (params: any) => {
    const brushComponent = params.batch[0]
    if (brushComponent.selected && brushComponent.selected.length > 0) {
      const selected = brushComponent.selected[0]
      if (selected.dataIndex.length > 0) {
        const indices = selected.dataIndex.sort((a: number, b: number) => a - b)
        selectionRange.start = indices[0]
        selectionRange.end = indices[indices.length - 1]

        // 更新模板K线
        templateKlines.value = mainKlines.value.slice(selectionRange.start, selectionRange.end + 1)
        initTemplateChart()
      }
    }
  })
}

function initTemplateChart() {
  if (!templateChartRef.value || templateKlines.value.length === 0) return

  if (templateChart) {
    templateChart.dispose()
  }

  templateChart = echarts.init(templateChartRef.value)

  const data = templateKlines.value.map(k => [k.open, k.close, k.low, k.high])

  const option = {
    backgroundColor: 'transparent',
    grid: {
      left: '5%',
      right: '5%',
      top: '10%',
      bottom: '10%'
    },
    xAxis: {
      type: 'category',
      data: templateKlines.value.map((_, i) => i + 1),
      axisLine: { lineStyle: { color: '#333' } },
      axisLabel: { color: '#787b86' }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { lineStyle: { color: '#333' } },
      axisLabel: { color: '#787b86' },
      splitLine: { lineStyle: { color: '#1a1a1a' } }
    },
    series: [
      {
        type: 'candlestick',
        data: data,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a'
        }
      }
    ]
  }

  templateChart.setOption(option)
}

// ============ 匹配 ============
async function onMatchWithSelection() {
  if (selectionRange.start < 0 || selectionRange.end < 0) {
    message.warning('请先框选K线形态')
    return
  }

  if (!searchForm.stock_code) {
    message.warning('请先选择股票')
    return
  }

  const windowSize = selectionRange.end - selectionRange.start + 1

  loading.value = true
  resultData.value = []

  try {
    const res = await matchSimilarity({
      stock_code: searchForm.stock_code,
      window_size: windowSize,
      top_n: searchForm.top_n,
      pattern_type: searchForm.pattern_type,
      corr_threshold: searchForm.corr_threshold,
      subsequent_days: searchForm.subsequent_days,
      algorithm: searchForm.algorithm,
      scene: searchForm.scene !== 'default' ? searchForm.scene : undefined
    })

    if (res.data.success) {
      resultData.value = res.data.data
      // 自动展开所有行以显示K线预览
      expandedRowKeys.value = res.data.data.map((item: any) =>
        `${item.stock_code}-${item.start_date}-${item.end_date}`
      )
      message.success(`匹配完成，找到 ${res.data.data.length} 条结果`)
      // 延迟渲染K线图
      nextTick(() => {
        setTimeout(() => {
          renderExpandedCharts()
        }, 200)
      })
    } else {
      message.error(res.data.error || '匹配失败')
    }
  } catch (error: any) {
    message.error(error.message || '匹配请求失败')
  } finally {
    loading.value = false
  }
}

// ============ 查看K线 ============
function onViewKline(record: MatchResultItem) {
  selectedStockCode.value = record.stock_code
  selectedStockName.value = record.stock_code

  const subsequentKline = record.subsequent_kline || []
  if (subsequentKline.length > 0) {
    const first = subsequentKline[0]!
    const last = subsequentKline[subsequentKline.length - 1]!
    selectedCurrentPrice.value = last.close
    if (first.open !== 0) {
      selectedChangePercent.value = ((last.close - first.open) / first.open) * 100
    } else {
      selectedChangePercent.value = 0
    }
  } else {
    selectedCurrentPrice.value = 0
    selectedChangePercent.value = 0
  }

  klineModalVisible.value = true
}

function onKlineModalClose() {
  klineModalVisible.value = false
}

// ============ 展开行处理 ============
function onExpand(expanded: boolean, record: any) {
  const key = `${record.stock_code}-${record.start_date}-${record.end_date}`
  if (expanded) {
    expandedRowKeys.value.push(key)
    // 延迟渲染图表，确保DOM已更新
    nextTick(() => {
      setTimeout(() => {
        renderExpandedCharts()
      }, 100)
    })
  } else {
    expandedRowKeys.value = expandedRowKeys.value.filter(k => k !== key)
    // 清理图表实例
    const matchedKey = `matched-chart-${record.stock_code}-${record.end_date}`
    const subsequentKey = `subsequent-chart-${record.stock_code}-${record.end_date}`
    if (expandedCharts.has(matchedKey)) {
      expandedCharts.get(matchedKey)!.dispose()
      expandedCharts.delete(matchedKey)
    }
    if (expandedCharts.has(subsequentKey)) {
      expandedCharts.get(subsequentKey)!.dispose()
      expandedCharts.delete(subsequentKey)
    }
  }
}

// ============ 生命周期 ============
onMounted(() => {
  restoreRadarState()
  if (typeof route.query.symbols === 'string') {
    radarState.symbolsText = route.query.symbols
  }
  if (activeModule.value === 'radar') {
    void ensurePatternTemplates()
  }
  window.addEventListener('resize', () => {
    mainChart?.resize()
    templateChart?.resize()
    // 调整展开行图表大小
    expandedCharts.forEach(chart => chart.resize())
  })
})

watch(
  () => [route.query.module, route.query.tab] as const,
  () => {
    activeModule.value = readModuleFromQuery()
    if (activeModule.value === 'radar') {
      void ensurePatternTemplates()
    }
  }
)

watch(
  radarState,
  () => {
    localStorage.setItem(RADAR_STORAGE_KEY, JSON.stringify(radarState))
  },
  { deep: true }
)

onUnmounted(() => {
  mainChart?.dispose()
  templateChart?.dispose()
  // 清理展开行图表
  expandedCharts.forEach(chart => chart.dispose())
  expandedCharts.clear()
})
</script>

<style scoped lang="scss">
// 动画关键帧
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.similarity-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0a0a0a 0%, #111111 100%);
  padding: 24px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    animation: fadeInUp 0.5s ease-out;
  }

  .module-switch {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.03);

    button {
      min-width: 112px;
      height: 34px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: #8b8f9a;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        color: #d1d5db;
        background: rgba(139, 92, 246, 0.08);
      }

      &.active {
        color: #fff;
        background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
        box-shadow: 0 6px 16px rgba(139, 92, 246, 0.25);
      }
    }
  }

  .page-content {
    .search-panel {
      background: linear-gradient(145deg, #161616 0%, #131313 100%);
      border-radius: 16px;
      padding: 24px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      box-shadow:
        0 4px 24px rgba(0, 0, 0, 0.4),
        inset 0 1px 0 rgba(255, 255, 255, 0.02);
      animation: slideInLeft 0.5s ease-out 0.1s both;
      transition: transform 0.3s ease, box-shadow 0.3s ease;

      &:hover {
        box-shadow:
          0 8px 32px rgba(0, 0, 0, 0.5),
          inset 0 1px 0 rgba(255, 255, 255, 0.03);
      }

      .panel-section {
        margin-bottom: 28px;
        animation: fadeInUp 0.4s ease-out;

        &:last-child {
          margin-bottom: 0;
        }

        .section-title {
          font-size: 13px;
          font-weight: 600;
          color: #9ca3af;
          margin-bottom: 14px;
          padding-bottom: 10px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          display: flex;
          align-items: center;
          gap: 8px;

          &::before {
            content: '';
            width: 3px;
            height: 14px;
            background: linear-gradient(180deg, #8b5cf6 0%, #7c3aed 100%);
            border-radius: 2px;
          }
        }
      }

      // 股票选择器样式优化
      :deep(.ant-select) {
        .ant-select-selector {
          background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%);
          border: 1px solid rgba(139, 92, 246, 0.2);
          border-radius: 10px;
          color: #e5e7eb;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);

          &:hover {
            border-color: rgba(139, 92, 246, 0.4);
            box-shadow:
              inset 0 2px 4px rgba(0, 0, 0, 0.3),
              0 0 0 3px rgba(139, 92, 246, 0.1);
          }

          .ant-select-selection-placeholder {
            color: #6b7280;
          }

          .ant-select-selection-search-input {
            color: #e5e7eb;
          }
        }

        &.ant-select-focused .ant-select-selector {
          border-color: #8b5cf6;
          box-shadow:
            inset 0 2px 4px rgba(0, 0, 0, 0.3),
            0 0 0 3px rgba(139, 92, 246, 0.15);
        }
      }

      // 下拉菜单样式
      :deep(.ant-select-dropdown) {
        background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        animation: fadeIn 0.2s ease-out;

        .ant-select-item {
          color: #d1d5db;
          transition: all 0.2s ease;

          &:hover {
            background: rgba(139, 92, 246, 0.1);
          }

          &.ant-select-item-option-selected {
            background: rgba(139, 92, 246, 0.2);
            color: #8b5cf6;
          }
        }
      }

      // 表单控件样式
      :deep(.ant-form-item) {
        margin-bottom: 20px;

        .ant-form-item-label > label {
          color: #9ca3af;
          font-size: 12px;
          font-weight: 500;
        }
      }

      :deep(.ant-select:not(.ant-select-customize-input)) {
        .ant-select-selector {
          background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          color: #e5e7eb;

          &:hover {
            border-color: rgba(139, 92, 246, 0.4);
          }
        }
      }

      :deep(.ant-input),
      :deep(.ant-input-number),
      :deep(.ant-input-number-input),
      :deep(.ant-input-number-group-addon) {
        background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%);
        border-color: rgba(255, 255, 255, 0.08);
        color: #e5e7eb;
      }

      :deep(.ant-input-number),
      :deep(.ant-input) {
        border-radius: 8px;

        &:hover,
        &:focus {
          border-color: rgba(139, 92, 246, 0.4);
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
        }
      }

      :deep(.ant-checkbox-wrapper) {
        color: #9ca3af;
        font-size: 12px;
      }

      :deep(.ant-checkbox-checked .ant-checkbox-inner) {
        background-color: #8b5cf6;
        border-color: #8b5cf6;
      }

      .template-kline-chart {
        height: 200px;
        background: linear-gradient(145deg, #0f0f0f 0%, #0a0a0a 100%);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.4);
        animation: fadeIn 0.5s ease-out;
      }

      .selection-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 16px;
        padding: 12px 16px;
        background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        animation: fadeInUp 0.4s ease-out;

        span {
          color: #9ca3af;
          font-size: 13px;
          font-weight: 500;
        }

        :deep(.ant-btn) {
          background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
          border: none;
          border-radius: 8px;
          font-weight: 500;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);

          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.4);
          }

          &:active {
            transform: translateY(0);
          }
        }
      }
    }

    .main-chart-panel {
      background: linear-gradient(145deg, #161616 0%, #131313 100%);
      border-radius: 16px;
      padding: 20px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
      margin-bottom: 24px;
      animation: fadeInUp 0.5s ease-out 0.2s both;

      .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;

        .chart-title {
          font-size: 14px;
          font-weight: 600;
          color: #e5e7eb;
          display: flex;
          align-items: center;
          gap: 8px;

          &::before {
            content: '';
            width: 8px;
            height: 8px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
          }
        }

        .chart-hint {
          font-size: 12px;
          color: #6b7280;
          background: rgba(139, 92, 246, 0.1);
          padding: 4px 12px;
          border-radius: 20px;
          border: 1px solid rgba(139, 92, 246, 0.2);
        }
      }

      .main-kline-chart {
        height: 320px;
        background: linear-gradient(145deg, #0f0f0f 0%, #0a0a0a 100%);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
      }
    }

    .result-panel {
      background: linear-gradient(145deg, #161616 0%, #131313 100%);
      border-radius: 16px;
      padding: 24px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
      animation: fadeInUp 0.5s ease-out 0.3s both;

      .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;

        .result-title {
          font-size: 14px;
          font-weight: 600;
          color: #e5e7eb;
          display: flex;
          align-items: center;
          gap: 8px;

          &::before {
            content: '';
            width: 8px;
            height: 8px;
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(139, 92, 246, 0.5);
          }
        }

        .result-count {
          font-size: 12px;
          color: #6b7280;
          background: rgba(255, 255, 255, 0.05);
          padding: 4px 12px;
          border-radius: 20px;
        }
      }

      .result-table {
        :deep(.ant-table) {
          background: transparent;

          .ant-table-thead > tr > th {
            background: rgba(255, 255, 255, 0.03);
            color: #9ca3af;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            font-weight: 500;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }

          .ant-table-tbody > tr {
            transition: all 0.2s ease;

            > td {
              background: transparent;
              color: #d1d5db;
              border-bottom: 1px solid rgba(255, 255, 255, 0.04);
              transition: all 0.2s ease;
            }

            &:hover > td {
              background: rgba(139, 92, 246, 0.05);
            }
          }

          .ant-table-row-expand-icon {
            color: #6b7280;
            border-color: rgba(255, 255, 255, 0.1);
            transition: all 0.2s ease;

            &:hover {
              color: #8b5cf6;
              border-color: #8b5cf6;
            }
          }
        }
      }

      .empty-result {
        text-align: center;
        padding: 60px 20px;
        color: #6b7280;
        animation: fadeIn 0.5s ease-out;

        .empty-icon {
          font-size: 48px;
          margin-bottom: 16px;
          opacity: 0.3;
        }

        p {
          margin: 0;

          &.empty-hint {
            font-size: 12px;
            margin-top: 8px;
            opacity: 0.6;
          }
        }
      }
    }

    &.radar-content {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .radar-panel {
      animation: fadeInUp 0.5s ease-out 0.1s both;

      .section-title {
        margin-bottom: 6px;
      }
    }

    .radar-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 16px;

      :deep(.ant-btn) {
        min-width: 104px;
        border: 0;
        border-radius: 8px;
        background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.28);
        font-weight: 600;
      }
    }

    .radar-subtitle,
    .research-boundary {
      margin: 0;
      color: #787b86;
      font-size: 12px;
      line-height: 1.6;
    }

    .research-boundary {
      margin-top: 4px;
      color: #9ca3af;
    }

    .radar-template-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .radar-template-card,
    .radar-empty-card {
      min-height: 92px;
      padding: 14px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      background: linear-gradient(145deg, #1b1b1b 0%, #171717 100%);
      color: #d1d5db;
      text-align: left;
    }

    .radar-template-card {
      cursor: pointer;
      transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;

      &:hover {
        border-color: rgba(139, 92, 246, 0.35);
        transform: translateY(-1px);
      }

      &.active {
        border-color: #8b5cf6;
        background: linear-gradient(145deg, rgba(139, 92, 246, 0.16) 0%, rgba(124, 58, 237, 0.08) 100%);
      }

      .template-name {
        display: block;
        margin-bottom: 8px;
        color: #f3f4f6;
        font-size: 14px;
        font-weight: 700;
      }

      .template-desc {
        display: block;
        color: #8b8f9a;
        font-size: 12px;
        line-height: 1.5;
      }
    }

    .radar-empty-card {
      display: grid;
      place-items: center;
      color: #6b7280;
    }

    .radar-form {
      :deep(.ant-form-item) {
        margin-bottom: 16px;
      }

      :deep(.ant-form-item-label > label) {
        color: #9ca3af;
        font-size: 12px;
        font-weight: 600;
      }

      .amount-hint {
        margin-left: 6px;
        color: #6b7280;
        font-weight: 500;
      }
    }

    .radar-summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .metric-card {
      padding: 16px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 8px;
      background: linear-gradient(145deg, #161616 0%, #131313 100%);
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);

      span {
        display: block;
        color: #8b8f9a;
        font-size: 12px;
      }

      strong {
        display: block;
        margin-top: 6px;
        color: #f3f4f6;
        font-size: 24px;
        line-height: 1;
      }
    }

    .radar-error {
      margin: 0;
      padding: 10px 12px;
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-radius: 8px;
      background: rgba(239, 68, 68, 0.12);
      color: #fecaca;
      font-size: 13px;
    }

    .radar-result-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(380px, 0.85fr);
      gap: 16px;
      align-items: start;
    }

    .radar-result-panel {
      min-width: 0;
    }

    .radar-table {
      :deep(.ant-table-tbody > tr) {
        cursor: pointer;
      }

      :deep(.radar-row-selected > td) {
        background: rgba(139, 92, 246, 0.1) !important;
      }
    }

    .radar-case-panel {
      border-radius: 16px;
      background: linear-gradient(145deg, #161616 0%, #131313 100%);
      border-color: rgba(255, 255, 255, 0.06);
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    }

    .tag-list {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .muted-text {
      color: #6b7280;
      font-size: 12px;
    }
  }
}

.score-cell {
  position: relative;
  display: flex;
  align-items: center;
  height: 24px;

  .score-value {
    position: relative;
    z-index: 2;
    color: #8b5cf6;
    font-weight: 600;
    background: rgba(30, 32, 38, 0.9);
    padding: 0 4px;
    border-radius: 2px;
  }

  .score-bar {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: linear-gradient(90deg, #8b5cf6 0%, #7c3aed 100%);
    border-radius: 2px;
    max-width: 100%;
    transition: width 0.3s ease;
    z-index: 1;
  }
}

.return-up {
  color: #ef5350;
  font-weight: 600;
}

.return-down {
  color: #26a69a;
  font-weight: 600;
}

// 股票代码单元格样式
.stock-code-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .code-main {
    font-size: 14px;
    font-weight: 600;
    color: #e5e7eb;
  }

  .code-sub {
    font-size: 11px;
    color: #6b7280;
  }
}

// 内联K线预览
.kline-preview-inline {
  padding: 12px 16px;
  background: rgba(10, 10, 10, 0.6);
  border-radius: 8px;

  .inline-kline-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .inline-kline-label {
    font-size: 11px;
    color: #6b7280;
    white-space: nowrap;
    min-width: 90px;
    line-height: 1.4;

    small {
      font-size: 10px;
      color: #4b5563;
    }
  }

  .inline-kline-chart {
    flex: 1;
    height: 80px;
    min-width: 300px;
    background: rgba(19, 19, 19, 0.8);
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.04);
  }

  .inline-kline-empty {
    text-align: center;
    padding: 20px;
    color: #4b5563;
    font-size: 12px;
  }
}

.stock-option {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .stock-code {
    font-weight: 600;
    color: #d1d4dc;
  }

  .stock-name {
    color: #787b86;
    font-size: 12px;
  }
}

@media (max-width: 1180px) {
  .similarity-page {
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }

    .module-switch {
      width: 100%;

      button {
        flex: 1;
      }
    }

    .page-content {
      .radar-template-grid,
      .radar-summary-grid,
      .radar-result-grid {
        grid-template-columns: 1fr;
      }
    }
  }
}
</style>

<!-- 全局样式：修复下拉菜单深色主题 -->
<style lang="scss">
.dark-select-dropdown {
  background: linear-gradient(145deg, #1e1e1e 0%, #1a1a1a 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px !important;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5) !important;

  .ant-select-item {
    color: #d1d5db !important;
    transition: all 0.2s ease !important;

    &:hover {
      background: rgba(139, 92, 246, 0.1) !important;
    }

    &.ant-select-item-option-selected {
      background: rgba(139, 92, 246, 0.2) !important;
      color: #8b5cf6 !important;
    }

    &.ant-select-item-option-active {
      background: rgba(139, 92, 246, 0.15) !important;
    }
  }
}
</style>
