<template>
  <div class="h-full flex flex-col bg-[#0A0A0A] text-[#e0e0e0] overflow-hidden">
    <!-- Top Metrics Ticker Tape -->
    <MetricsToolbar 
      :strategy-name="strategyStore.currentVersion?.name || '未命名策略'"
      :metrics="metrics"
      :hover-metrics="hoverMetrics"
      :has-backtest-data="hasBacktestData"
    >
      <template #actions>
        <div class="flex items-center space-x-3">
          <button 
            @click="analyzeStrategy" 
            :disabled="isAnalyzing"
            class="text-[10px] bg-[#2962ff] hover:bg-[#1e4bd8] text-white px-2 py-1 rounded-sm font-bold uppercase disabled:opacity-50 transition-colors"
          >
            <i class="fas fa-brain mr-1"></i> {{ isAnalyzing ? 'ANALYZING' : 'AI REVIEW' }}
          </button>
          <button @click="isSidebarOpen = !isSidebarOpen" class="text-[#787b86] hover:text-white">
            <i class="fas fa-columns text-xs"></i>
          </button>
        </div>
      </template>
    </MetricsToolbar>

    <!-- Main Content Area: Flattened Dot Grid -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Primary Multi-Pane area - 动态调整行数 -->
      <div
        class="flex-1 grid grid-cols-1 gap-[1px] bg-[#2a2a2a] tv-dot-grid overflow-hidden"
        :class="hasBacktestData ? 'grid-rows-[1fr_minmax(150px,25%)_minmax(150px,25%)]' : 'grid-rows-1'"
      >
        
        <!-- K线图区域 - 有回测数据时显示净值曲线 -->
        <template v-if="hasBacktestData">
          <div class="tv-pane h-full bg-[#0A0A0A]">
            <div class="tv-pane-header-flat">
              <span class="tv-pane-label truncate text-[#888888]">净值曲线</span>
              <span class="flex-1"></span>
              <div class="flex bg-[#0A0A0A] rounded p-0.5 border border-[#2a2a2a] pointer-events-auto shrink-0">
                <button
                  @click="chartScale = 'linear'"
                  :class="chartScale === 'linear' ? 'text-[#3b82f6]' : 'text-[#888888]'"
                  class="px-1.5 py-0.5 text-[8px] font-bold uppercase transition-colors whitespace-nowrap"
                  >线性</button>
                <button
                  @click="chartScale = 'log'"
                  :class="chartScale === 'log' ? 'text-[#3b82f6]' : 'text-[#888888]'"
                  class="px-1.5 py-0.5 text-[8px] font-bold uppercase transition-colors whitespace-nowrap"
                  >对数</button>
              </div>
            </div>
            <div class="flex-1 min-h-0">
              <EquityCurve
                :versions="equityCurveData"
                :benchmark="benchmarkData"
                :scale="chartScale"
                :sync-x-axis="syncDate"
                :x-axis-min="xAxisMin"
                :x-axis-max="xAxisMax"
                @hover="handleChartHover"
              />
            </div>
          </div>
        </template>
        <template v-else>
          <!-- 无回测数据时显示空状态 -->
          <div class="h-full w-full min-h-0 bg-[#0A0A0A] flex items-center justify-center">
            <div class="text-center">
              <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-[#111111] border border-[#2a2a2a] flex items-center justify-center">
                <i class="fas fa-chart-line text-2xl text-[#3b82f6]"></i>
              </div>
              <h3 class="text-lg font-bold text-white mb-2">开始策略回测</h3>
              <p class="text-sm text-[#888888] mb-4 max-w-xs mx-auto">
                在右侧配置面板中设置回测参数，或点击按钮快速开始
              </p>
              <button 
                @click="quickStartBacktest"
                class="px-6 py-2.5 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-sm font-bold rounded-lg transition-all hover:scale-105 active:scale-95 shadow-lg shadow-[#3b82f6]/25"
              >
                <i class="fas fa-play mr-2"></i>运行回测
              </button>
            </div>
          </div>
        </template>

        <!-- Drawdown Pane - 只在有回测数据时显示 -->
        <div v-if="hasBacktestData" class="tv-pane min-h-[150px] border-t border-[#2a2a2a] bg-[#0A0A0A]">
          <div class="tv-pane-header-flat"><span class="tv-pane-label text-[#888888]">回撤序列</span></div>
          <div class="flex-1 min-h-0">
            <DrawdownChart 
              :equity-series="backtestStore.equitySeries"
              :sync-x-axis="syncDate"
            />
          </div>
        </div>

        <!-- Trade Frequency Pane - 只在有回测数据时显示 -->
        <div v-if="hasBacktestData" class="tv-pane min-h-[150px] border-t border-[#2a2a2a] bg-[#0A0A0A]">
          <div class="tv-pane-header-flat"><span class="tv-pane-label text-[#888888]">交易频率</span></div>
          <div class="flex-1 min-h-0 px-2 pb-2">
            <TradeFrequencyChart 
              :trades="backtestStore.trades"
              :sync-x-axis="syncDate"
            />
          </div>
        </div>
      </div>

      <!-- Gallery Sidebar (Right) -->
      <div
        v-if="isSidebarOpen"
        class="w-[280px] lg:w-[300px] xl:w-[320px] flex flex-col border-l border-[#2a2a2a] bg-[#0A0A0A] transition-all duration-300 pointer-events-auto flex-shrink-0"
      >
        <!-- 配置面板：无回测数据时显示 -->
        <template v-if="!hasBacktestData">
          <StrategyConfigPanel
            :is-running="isBacktestRunning"
            @run="handleRunBacktest"
            @save="handleSaveConfig"
          />
        </template>

        <!-- 结果面板：有回测数据时显示 -->
        <template v-else>
          <div class="p-3 border-b border-[#2a2a2a] flex items-center justify-between relative">
            <div class="flex items-center gap-3">
              <span class="text-[10px] font-bold text-[#888888] uppercase tracking-widest">{{ showOverviewPanel ? '指标概览' : '回测配置' }}</span>
              <!-- 切换按钮 -->
              <div class="flex items-center bg-[#111111] rounded p-0.5 border border-[#2a2a2a]">
                <button
                  @click="showOverviewPanel = false"
                  :class="!showOverviewPanel ? 'bg-[#3b82f6] text-white' : 'text-[#888888] hover:text-white'"
                  class="px-2 py-1 text-[9px] font-bold uppercase transition-colors rounded"
                  title="回测配置"
                >
                  CONFIG
                </button>
                <button
                  @click="showOverviewPanel = true"
                  :class="showOverviewPanel ? 'bg-[#3b82f6] text-white' : 'text-[#888888] hover:text-white'"
                  class="px-2 py-1 text-[9px] font-bold uppercase transition-colors rounded"
                  title="指标概览"
                >
                  概览
                </button>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="showConfigPanel"
                class="text-[#888888] hover:text-white transition-colors"
                title="清除数据并返回配置"
              >
                <i class="fas fa-trash-alt text-[10px]"></i>
              </button>
              <div class="relative" v-if="showOverviewPanel" ref="exportMenuRef">
                <button @click="toggleExportMenu" class="text-[#888888] hover:text-white transition-colors">
                  <i class="fas fa-file-export text-[10px]"></i>
                </button>
                <!-- 导出菜单 -->
                <div v-if="showExportMenu" class="absolute right-0 mt-2 w-48 bg-[#111111] rounded shadow-xl border border-[#2a2a2a] z-[100]">
                  <div class="py-1">
                    <button @click="exportToPDF" class="w-full text-left px-4 py-2 text-xs text-[#e0e0e0] hover:bg-[#1a1a1a] transition-colors flex items-center space-x-2">
                      <i class="fas fa-file-pdf text-[#ef4444]"></i>
                      <span>导出 PDF 报告</span>
                    </button>
                    <button @click="exportToExcel" class="w-full text-left px-4 py-2 text-xs text-[#e0e0e0] hover:bg-[#1a1a1a] transition-colors flex items-center space-x-2">
                      <i class="fas fa-file-excel text-[#10b981]"></i>
                      <span>导出 Excel 数据</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto no-scrollbar">
            <!-- 概览面板 -->
            <template v-if="showOverviewPanel">
              <!-- 收益分布热力图 -->
              <div class="p-3 border-b border-[#2a2a2a]">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[11px] font-bold text-[#888888] uppercase tracking-widest">收益分布</span>
                  <div class="flex bg-[#111111] rounded p-0.5 border border-[#2a2a2a]">
                    <button 
                      @click="returnsViewMode = 'daily'" 
                      :class="returnsViewMode === 'daily' ? 'bg-[#3b82f6] text-white' : 'text-[#888888] hover:text-white'"
                      class="px-2 py-0.5 text-[9px] font-bold uppercase transition-colors rounded"
                    >日</button>
                    <button 
                      @click="returnsViewMode = 'monthly'" 
                      :class="returnsViewMode === 'monthly' ? 'bg-[#3b82f6] text-white' : 'text-[#888888] hover:text-white'"
                      class="px-2 py-0.5 text-[9px] font-bold uppercase transition-colors rounded"
                    >月</button>
                    <button 
                      @click="returnsViewMode = 'yearly'" 
                      :class="returnsViewMode === 'yearly' ? 'bg-[#3b82f6] text-white' : 'text-[#888888] hover:text-white'"
                      class="px-2 py-0.5 text-[9px] font-bold uppercase transition-colors rounded"
                    >年</button>
                  </div>
                </div>
                <VerticalHeatmap 
                  v-if="monthlyReturnsData.length > 0"
                  :data="monthlyReturnsData"
                  @month-select="handleMonthSelect"
                />
                <div v-else class="h-[120px] flex items-center justify-center text-[#888888] text-xs">
                  <div class="text-center">
                    <i class="fas fa-calendar text-xl mb-2 opacity-50"></i>
                    <p>暂无收益分布数据</p>
                  </div>
                </div>
              </div>

              <!-- Metrics Panel -->
              <div class="flex-1 p-3 overflow-y-auto">
                <MetricsPanel :metrics="strategyMetrics" />
              </div>
            </template>

            <!-- 配置面板 -->
            <template v-else>
              <div class="p-4">
                <StrategyConfigPanel
                  :is-running="isBacktestRunning"
                  @run="handleRunBacktest"
                  @save="handleSaveConfig"
                />
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <!-- AI 分析报告弹窗 (Keep styled but updated to match TV dark theme) -->
    <div
      v-if="showAnalysisModal"
      class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[100] p-8"
      @click.self="closeAnalysisModal"
    >
      <div class="bg-[#1e222d] border border-[#2a2e39] shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
        <div class="tv-pane-header !py-4">
          <h2 class="text-[18px] font-bold text-white flex items-center gap-3">
            <i class="fas fa-robot text-[#2962ff]"></i> AI 深度全域复盘
          </h2>
          <button @click="closeAnalysisModal" class="text-[#787b86] hover:text-white text-2xl leading-none px-2">&times;</button>
        </div>

        <div class="flex-1 overflow-y-auto p-10 custom-scrollbar">
          <div v-if="isAnalyzing" class="flex flex-col items-center justify-center h-full space-y-6">
             <div class="w-16 h-16 border-4 border-[#2962ff]/20 border-t-[#2962ff] rounded-full animate-spin"></div>
             <div class="text-center">
               <div class="text-[16px] font-bold text-white mb-2">{{ analysisStage }}</div>
               <div class="w-64 h-1.5 bg-[#2a2e39] rounded-full overflow-hidden mt-4">
                 <div class="h-full bg-[#2962ff] transition-all duration-300" :style="{ width: `${analysisProgress}%` }"></div>
               </div>
               <div class="text-[11px] text-[#787b86] mt-4 uppercase tracking-widest">Generating Real-time Intelligence</div>
             </div>
          </div>
          <div v-else-if="analysisError" class="p-6 bg-[#f23645]/10 border border-[#f23645]/30 rounded text-[#f23645] text-sm">
             {{ analysisError }}
          </div>
          <div 
            v-else-if="aiReportMarkdown" 
            class="prose prose-invert prose-sm max-w-none prose-headings:text-white prose-strong:text-[#2962ff]"
            v-html="renderMarkdown(aiReportMarkdown)"
          ></div>
        </div>

        <div class="p-4 border-t border-[#2a2e39] bg-[#0A0A0A] flex justify-end">
          <button @click="closeAnalysisModal" class="px-6 py-2 bg-[#2a2e39] hover:bg-[#363a45] text-white text-xs font-bold uppercase tracking-wider transition-colors">关闭窗口</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({
  name: 'DashboardOverview'
});

import { ref, computed, onMounted, onUnmounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { useSocketIO } from '../composables/useSocketIO';
import { useStreamingBacktest } from '../composables/useStreamingBacktest';
import { isFetchMockEnabled } from '../api/fetchMock';
import { generateMockBacktestData } from '../api/mockSocketIO';
import MetricsToolbar from '../components/metrics/MetricsToolbar.vue';
import EquityCurve from '../components/EquityCurve.vue';
import DrawdownChart from '../components/charts/DrawdownChart.vue';
import TradeFrequencyChart from '../components/charts/TradeFrequencyChart.vue';
import VerticalHeatmap from '../components/charts/VerticalHeatmap.vue';

import StrategyConfigPanel from '../components/StrategyConfigPanel.vue';
import MetricsPanel from '../components/dashboard/MetricsPanel.vue';
import type { Trade, Metrics } from '../types/backtest';

const router = useRouter();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();
const { start: startBacktest, isRunning: isBacktestRunning } = useStreamingBacktest();

const chartScale = ref<'linear' | 'log'>('linear');
const syncDate = ref('');
const isSidebarOpen = ref(true);
const hoverMetrics = ref<{ totalReturn?: number | null; equity?: number | null } | null>(null);
const xAxisMin = ref('');
const xAxisMax = ref('');
const showExportMenu = ref(false);
const showOverviewPanel = ref(true); // 切换概览/配置面板
const exportMenuRef = ref<HTMLElement | null>(null);
const returnsViewMode = ref<'daily' | 'monthly' | 'yearly'>('monthly'); // 收益分布视图模式

// AI 分析相关状态
const isAnalyzing = ref(false);
const showAnalysisModal = ref(false);
const aiReportMarkdown = ref<string>('');
const analysisError = ref<string>('');
const analysisProgress = ref(0);
const analysisStage = ref('准备中...');
// 使用相对路径，让 Vite 代理可以正确代理请求到后端
const API_BASE_URL = '/api';

const hasBacktestData = computed(() => {
  // 【修复】流式模式下只要有权益数据就显示图表，不需要等待 metrics
  // metrics 只在 stream_complete 时才设置，会导致流式更新时图表不显示
  return backtestStore.equitySeries.length > 0 || backtestStore.running;
});

const metrics = computed(() => backtestStore.metrics);

// 策略收益指标数据（用于 MetricsPanel）- 字段名与 BacktestMetrics 接口匹配
const strategyMetrics = computed(() => {
  const m = backtestStore.metrics;
  if (!m) {
    return {
      totalReturn: 0,
      annualReturn: 0,
      excessReturn: 0,
      benchmarkReturn: 0,
      maxDrawdown: 0,
      volatility: 0,
      benchmarkVolatility: 0,
      sharpeRatio: 0,
      sortinoRatio: 0,
      calmarRatio: 0,
      winRate: 0,
      profitLossRatio: 0,
      totalTrades: 0,
      avgHoldingDays: 0,
    };
  }
  return {
    totalReturn: m.totalReturn || 0,
    annualReturn: m.annualReturn || 0,
    excessReturn: (m.totalReturn || 0) - (m.benchmarkReturn || 0),
    benchmarkReturn: m.benchmarkReturn || 0,
    maxDrawdown: m.maxDrawdown || 0,
    volatility: m.volatility || 0,
    benchmarkVolatility: m.benchmarkVolatility || 0,
    sharpeRatio: m.sharpeRatio || 0,
    sortinoRatio: m.sortinoRatio || 0,
    calmarRatio: m.calmarRatio || 0,
    winRate: m.winRate || 0,
    profitLossRatio: m.profitLossRatio || 0,
    totalTrades: m.totalTrades || 0,
    avgHoldingDays: m.avgHoldingDays || 0,
  };
});

const benchmarkData = computed(() => {
  const data = backtestStore.benchmarkEquitySeries;
  console.log('[DashboardOverview] benchmarkData computed:', data.length, 'points');
  return data;
});

const equityCurveData = computed(() => {
  const data = backtestStore.equitySeries;
  console.log('[DashboardOverview] equityCurveData computed:', data.length, 'points');
  if (data.length > 0) {
    return [{
      versionId: 'current',
      versionName: '当前回测',
      data: data
    }];
  }
  return [];
});


const monthlyReturnsData = computed(() => backtestStore.monthlyReturns);

// Crosshair synchronization handler
function handleChartHover(data: any) {
  if (data?.date) {
    syncDate.value = data.date;
    
    // Calculate real-time return if possible
    if (data.equity !== undefined && backtestStore.equitySeries.length > 0) {
      const initialEquity = backtestStore.equitySeries[0].equity || 1;
      const currentReturn = ((data.equity / initialEquity) - 1) * 100;
      hoverMetrics.value = {
        totalReturn: currentReturn,
        equity: data.equity
      };
    }
  } else {
    hoverMetrics.value = null;
  }
}

// Heatmap focus interaction (Jump to month)
function handleMonthSelect(data: { year: number; month: number }) {
  // Construct date strings for current month jump
  const startDay = `${data.year}-${String(data.month + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(data.year, data.month + 1, 0).getDate();
  const endDay = `${data.year}-${String(data.month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  
  xAxisMin.value = startDay;
  xAxisMax.value = endDay;
  
  // Show a message or feedback (optional)
  console.log(`Jumping to period: ${startDay} - ${endDay}`);
}

function toggleExportMenu() {
  showExportMenu.value = !showExportMenu.value;
}

function closeExportMenu() {
  showExportMenu.value = false;
}

// 点击外部关闭导出菜单
function handleClickOutside(event: MouseEvent) {
  if (showExportMenu.value && exportMenuRef.value) {
    const target = event.target as HTMLElement;
    if (!exportMenuRef.value.contains(target)) {
      closeExportMenu();
    }
  }
}

// 导出功能
async function exportToPDF() {
  showExportMenu.value = false;
  if (!hasBacktestData.value) return;
  try {
    const backtestResult = {
      metrics: backtestStore.metrics,
      equityCurve: backtestStore.equitySeries,
      monthlyReturns: backtestStore.monthlyReturns,
      trades: backtestStore.trades,
      strategyInfo: { name: strategyStore.currentVersion?.name || '策略' }
    };
    const response = await fetch(`${API_BASE_URL}/export/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: strategyStore.currentVersion?.id || '', backtest_result: backtestResult })
    });
    if (!response.ok) throw new Error('Export failed');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `分析报告_${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e: any) {
    alert('导出 PDF 失败: ' + e.message);
  }
}

async function exportToExcel() {
  showExportMenu.value = false;
  if (!hasBacktestData.value) return;
  try {
    const backtestResult = {
      metrics: backtestStore.metrics,
      equityCurve: backtestStore.equitySeries,
      monthlyReturns: backtestStore.monthlyReturns,
      trades: backtestStore.trades,
      strategyInfo: { name: strategyStore.currentVersion?.name || '策略' }
    };
    const response = await fetch(`${API_BASE_URL}/export/excel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: strategyStore.currentVersion?.id || '', backtest_result: backtestResult })
    });
    if (!response.ok) throw new Error('Export failed');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `回测数据_${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e: any) {
    alert('导出 Excel 失败: ' + e.message);
  }
}

const clamp = (val: number, min: number, max: number) => Math.min(Math.max(val, min), max);

function normalizeRadarScores(m: Metrics) {
  const excessReturn = clamp(((m.annualizedReturn || 0) + 100) / 2, 0, 100);
  const sharpe = clamp(((m.sharpeRatio || 0) + 1) * 25, 0, 100);
  const maxDdScore = clamp(100 - Math.abs(m.maxDrawdown || 0), 0, 100);
  const winPct = clamp((m.winRate || 0) * 100, 0, 100);
  const pfScore = clamp((m.profitFactor || 0) / 5 * 100, 0, 100);
  const tradingQuality = clamp(winPct * 0.6 + pfScore * 0.4, 0, 100);
  const antiOverfit = clamp((m.tradesCount || 0) / 2, 0, 100);

  return {
    excessReturn,
    riskConsistency: sharpe,
    maxDrawdown: maxDdScore,
    tradingQuality,
    antiOverfitting: antiOverfit
  };
}

const radarScores = computed(() => {
  if (strategyStore.currentRadarScores) return strategyStore.currentRadarScores;
  if (backtestStore.metrics) return normalizeRadarScores(backtestStore.metrics);
  return null;
});

const overallFeasibilityScore = computed(() => {
  if (!radarScores.value) return null;
  const scores = Object.values(radarScores.value);
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
});

const benchmarkRadarScores = computed(() => {
  if (!backtestStore.benchmarkEquitySeries.length || !backtestStore.equitySeries.length) return null;
  return {
    excessReturn: 50,
    riskConsistency: 50,
    maxDrawdown: 50,
    tradingQuality: 50,
    antiOverfitting: 50
  };
});

// AI Analyze logic (Preserved from original)
let controller: AbortController | null = null;
async function analyzeStrategy() {
  if (!hasBacktestData.value) return;
  isAnalyzing.value = true;
  analysisProgress.value = 0;
  analysisStage.value = '量子数据预处理...';
  showAnalysisModal.value = true;
  aiReportMarkdown.value = '';

  try {
    const backtestResult = {
      metrics: backtestStore.metrics,
      equityCurve: backtestStore.equitySeries,
      monthlyReturns: backtestStore.monthlyReturns,
      trades: backtestStore.trades,
      strategyInfo: {
        name: strategyStore.currentVersion?.name || '未知策略',
      }
    };

    controller = new AbortController();
    const response = await fetch(`${API_BASE_URL}/analyze_report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy_id: strategyStore.currentVersion?.id || '',
        backtest_result: backtestResult
      }),
      signal: controller.signal
    });

    const reader = response.body?.getReader();
    if (!reader) throw new Error('ReadableStream not supported');
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        if (line.startsWith('progress:')) {
          const data = JSON.parse(line.slice(9));
          analysisProgress.value = data.progress;
          analysisStage.value = data.stage;
        } else if (line.startsWith('stream:')) {
          const data = JSON.parse(line.slice(7));
          aiReportMarkdown.value += data.content;
        }
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') analysisError.value = e.message;
  } finally {
    isAnalyzing.value = false;
    controller = null;
  }
}

function closeAnalysisModal() {
  if (controller) controller.abort();
  showAnalysisModal.value = false;
  aiReportMarkdown.value = '';
}

/**
 * 运行回测
 * 从配置面板接收配置并启动回测
 */
function handleRunBacktest(config: {
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
  benchmark: string;
}) {
  if (!strategyStore.currentVersion) {
    alert('请先选择策略');
    return;
  }

  console.log('[Dashboard] 启动回测，配置:', {
    strategy: strategyStore.currentVersion.name,
    startDate: config.startDate,
    endDate: config.endDate,
    initialCapital: config.initialCapital,
    commission: config.commission,
    slippage: config.slippage,
    benchmark: config.benchmark
  });

  startBacktest({
    strategy_name: strategyStore.currentVersion.name,
    start_date: config.startDate,
    end_date: config.endDate,
    benchmark_code: config.benchmark,
    initial_capital: config.initialCapital,
    commission: config.commission,
    slippage: config.slippage
  }, {
    onStart: () => {
      console.log('[Dashboard] 回测开始');
    },
    onProgress: (progress: number) => {
      console.log('[Dashboard] 回测进度:', progress);
    },
    onComplete: () => {
      console.log('[Dashboard] 回测完成');
    },
    onError: (error: Error) => {
      console.error('[Dashboard] 回测错误:', error);
    }
  });
}

/**
 * 保存配置
 */
function handleSaveConfig(config: {
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
  benchmark: string;
}) {
  console.log('[Dashboard] 保存配置:', config);
  // 可以添加保存到服务器或本地存储的逻辑
}

/**
 * 显示配置面板（清除回测数据）
 */
function showConfigPanel() {
  if (confirm('切换回配置面板将清除当前回测数据，是否继续？')) {
    backtestStore.clearBacktestData();
  }
}

/**
 * 快速开始回测 - 使用 mock 数据填充，无需后端
 */
function quickStartBacktest() {
  if (!strategyStore.currentVersion) {
    alert('请先选择策略');
    return;
  }

  console.log('[Dashboard] 加载 mock 回测数据');

  // 生成 mock 数据
  const mockData = generateMockBacktestData(strategyStore.currentVersion.name);
  const fullData = mockData.getFullData();
  const metrics = mockData.getFinalMetrics();
  const monthlyReturns = mockData.getMonthlyReturns();

  // 清空现有数据
  backtestStore.clearBacktestData();

  // 填充 mock 数据到 store（使用 $patch 批量更新）
  backtestStore.$patch({
    equitySeries: fullData.equityCurve,
    benchmarkEquitySeries: fullData.benchmark,
    trades: fullData.trades,
    metrics: {
      totalReturn: metrics.totalReturn,
      annualizedReturn: metrics.annualReturn,
      benchmarkReturn: metrics.benchmarkReturn,
      excessReturn: metrics.excessReturn,
      sharpeRatio: metrics.sharpeRatio,
      maxDrawdown: metrics.maxDrawdown,
      volatility: metrics.volatility,
      benchmarkVolatility: metrics.benchmarkVolatility,
      winRate: metrics.winRate,
      profitLossRatio: metrics.profitLossRatio,
      tradesCount: metrics.totalTrades,
      avgHoldingDays: metrics.avgHoldingDays,
      calmarRatio: metrics.calmarRatio,
      sortinoRatio: metrics.sortinoRatio,
      alpha: metrics.excessReturn,
      beta: 0.85,
      informationRatio: 1.2,
      treynorRatio: 0.15,
      var95: -0.02,
      cvar95: -0.025,
      omegaRatio: 1.5,
      upsidePotential: 0.18,
      downsideRisk: 0.12,
      skewness: -0.3,
      kurtosis: 3.2,
      profitFactor: metrics.profitLossRatio,
      recoveryFactor: Math.abs(metrics.totalReturn / metrics.maxDrawdown),
      expectancy: 0.02,
      sqn: 2.5,
      ulcerIndex: 5.0,
      upCaptureRatio: 1.1,
      downCaptureRatio: 0.8,
      battingAverage: metrics.winRate,
      gainToPainRatio: 1.5,
      kRatio: 0.8,
      rSquared: 0.75,
      trackingError: 0.08,
      upsideDeviation: 0.15,
      downsideDeviation: 0.10,
      monthlyReturns: {},
      weeklyReturns: {},
      dailyReturns: {},
      yearlyReturns: {},
      rollingReturns: {},
      percentileReturns: {},
      returnDistribution: {},
      drawdownDistribution: {},
      tradeDistribution: {},
      timeAnalysis: {},
      sectorAnalysis: {},
      correlationMatrix: {},
      riskDecomposition: {},
      attributionAnalysis: {},
      turnoverAnalysis: {},
      costAnalysis: {},
      slippageAnalysis: {},
      marketImpact: {},
      liquidityAnalysis: {},
      capacityAnalysis: {},
      robustnessScore: 75,
      overfittingRisk: 'low',
      regimeAnalysis: {},
      stressTestResults: {},
      scenarioAnalysis: {},
      monteCarloResults: {},
      walkForwardResults: {},
      crossValidationResults: {},
      parameterSensitivity: {},
      modelConfidence: 0.85,
      predictionAccuracy: 0.72,
      featureImportance: {},
      modelStability: 0.8,
    },
    monthlyReturns: monthlyReturns,
    lastRunParams: {
      strategyName: strategyStore.currentVersion.name,
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      benchmarkCode: '000300'
    },
    lastUpdated: new Date().toLocaleTimeString('zh-CN', { hour12: false })
  });

  console.log('[Dashboard] Mock 数据加载完成');
}

function renderMarkdown(md: string) {
  // Simple renderer (can use marked if installed)
  return md
    .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mb-4 mt-8">$1</h1>')
    .replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mb-3 mt-6">$1</h2>')
    .replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold mb-2 mt-4 text-[#2962ff]">$1</h3>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong class="text-white">$1</strong>')
    .replace(/^- (.*$)/gim, '<li class="ml-4">$1</li>')
    .replace(/\n/g, '<br>');
}

// 自动初始化策略并运行 mock 回测，开局显示回测数据而非 K 线图
onMounted(() => {
  // 设置默认策略版本
  if (!strategyStore.currentVersionId) {
    strategyStore.setAvailableVersions([
      {
        id: 'mock-strategy-001',
        name: '双均线策略',
        version: 'v1.0',
        createdAt: new Date().toISOString(),
        description: '基于5日和20日均线金叉死叉的交易策略'
      }
    ]);
    strategyStore.setCurrentVersion('mock-strategy-001');
    console.log('[Dashboard] 已自动设置默认策略');

    // 自动运行 mock 回测，开局显示回测数据
    setTimeout(() => {
      quickStartBacktest();
    }, 500);
  }

  // 添加点击外部事件监听
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  // 移除点击外部事件监听
  document.removeEventListener('click', handleClickOutside);
});
</script>

<style>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #2a2e39;
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #363a45;
}
</style>
