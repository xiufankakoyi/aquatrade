<template>
  <div class="h-screen flex flex-col bg-[#131722] text-[#d1d4dc] overflow-hidden">
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
      <!-- Primary Multi-Pane area -->
      <div class="flex-1 grid grid-cols-1 grid-rows-[1fr_200px_200px] gap-[1px] bg-[#2a2e39] tv-dot-grid overflow-hidden">
        
        <!-- Equity Curve Pane -->
        <div class="tv-pane h-full">
          <div class="tv-pane-header-flat">
            <span class="tv-pane-label">净值曲线 (Equity Curve)</span>
            <div class="flex bg-[#131722]/60 rounded p-0.5 border border-[#2a2e39] pointer-events-auto">
              <button 
                @click="chartScale = 'linear'" 
                :class="chartScale === 'linear' ? 'text-[#2962ff]' : 'text-[#787b86]'"
                class="px-1.5 py-0.5 text-[8px] font-bold uppercase transition-colors"
                >线性</button>
              <button 
                @click="chartScale = 'log'" 
                :class="chartScale === 'log' ? 'text-[#2962ff]' : 'text-[#787b86]'"
                class="px-1.5 py-0.5 text-[8px] font-bold uppercase transition-colors"
                >对数</button>
            </div>
          </div>
          <div class="flex-1 min-h-0">
            <EquityCurve
              v-if="hasBacktestData"
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

        <!-- Drawdown Pane -->
        <div class="tv-pane h-full border-t border-[#2a2e39]">
          <div class="tv-pane-header-flat"><span class="tv-pane-label">回撤序列 (DDR)</span></div>
          <div class="flex-1 min-h-0">
            <DrawdownChart 
              v-if="hasBacktestData"
              :equity-series="backtestStore.equitySeries"
              :sync-x-axis="syncDate"
            />
          </div>
        </div>

        <!-- Trade Frequency Pane -->
        <div class="tv-pane h-full border-t border-[#2a2e39]">
          <div class="tv-pane-header-flat"><span class="tv-pane-label">交易频率 (FREQ)</span></div>
          <div class="flex-1 min-h-0 px-2 pb-2">
            <TradeFrequencyChart 
              v-if="hasBacktestData"
              :trades="backtestStore.trades"
              :sync-x-axis="syncDate"
            />
          </div>
        </div>
      </div>

      <!-- Gallery Sidebar (Right) -->
      <div 
        v-if="isSidebarOpen"
        class="w-[300px] flex flex-col border-l border-[#2a2e39] bg-[#131722] tv-dot-grid transition-all duration-300 pointer-events-auto"
      >
        <div class="p-3 border-b border-[#2a2e39] flex items-center justify-between relative">
          <span class="text-[10px] font-bold text-[#787b86] uppercase tracking-widest">多维概览及导出</span>
          <div class="relative">
            <button @click="toggleExportMenu" class="text-[#787b86] hover:text-white transition-colors">
              <i class="fas fa-file-export text-[10px]"></i>
            </button>
            <!-- 导出菜单 -->
            <div v-if="showExportMenu" class="absolute right-0 mt-2 w-48 bg-[#1e222d] rounded shadow-xl border border-[#2a2e39] z-[100]">
              <div class="py-1">
                <button @click="exportToPDF" class="w-full text-left px-4 py-2 text-xs text-[#d1d4dc] hover:bg-[#2a2e39] transition-colors flex items-center space-x-2">
                  <i class="fas fa-file-pdf text-[#f23645]"></i>
                  <span>导出 PDF 报告</span>
                </button>
                <button @click="exportToExcel" class="w-full text-left px-4 py-2 text-xs text-[#d1d4dc] hover:bg-[#2a2e39] transition-colors flex items-center space-x-2">
                  <i class="fas fa-file-excel text-[#089981]"></i>
                  <span>导出 Excel 数据</span>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div class="flex-1 overflow-y-auto no-scrollbar">
          <!-- Calendar / Heatmap Screener -->
          <div class="p-4 border-b border-[#2a2e39]">
             <VerticalHeatmap 
              v-if="monthlyReturnsData.length > 0"
              :data="monthlyReturnsData"
              @month-select="handleMonthSelect"
            />
          </div>

          <!-- Capability Radar -->
          <div class="h-[250px] p-4 flex flex-col">
            <span class="tv-pane-label mb-4">策略能力指标 (CAPABILITY)</span>
            <div class="flex-1 min-h-0">
               <RadarAbility
                  v-if="radarScores"
                  :scores="radarScores"
                  :benchmark="benchmarkRadarScores"
                  :feasibility-score="overallFeasibilityScore"
                />
            </div>
          </div>
        </div>
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

        <div class="p-4 border-t border-[#2a2e39] bg-[#131722] flex justify-end">
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

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { useSocketIO } from '../composables/useSocketIO';
import MetricsToolbar from '../components/metrics/MetricsToolbar.vue';
import EquityCurve from '../components/EquityCurve.vue';
import DrawdownChart from '../components/charts/DrawdownChart.vue';
import TradeFrequencyChart from '../components/charts/TradeFrequencyChart.vue';
import VerticalHeatmap from '../components/charts/VerticalHeatmap.vue';
import RadarAbility from '../components/charts/RadarAbility.vue';
import type { Trade, Metrics } from '../types/backtest';

const router = useRouter();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();

const chartScale = ref<'linear' | 'log'>('linear');
const syncDate = ref('');
const isSidebarOpen = ref(true);
const hoverMetrics = ref<{ totalReturn?: number | null; equity?: number | null } | null>(null);
const xAxisMin = ref('');
const xAxisMax = ref('');
const showExportMenu = ref(false);

// AI 分析相关状态
const isAnalyzing = ref(false);
const showAnalysisModal = ref(false);
const aiReportMarkdown = ref<string>('');
const analysisError = ref<string>('');
const analysisProgress = ref(0);
const analysisStage = ref('准备中...');
const API_BASE_URL = 'http://localhost:5000/api';

const hasBacktestData = computed(() => {
  return backtestStore.metrics !== null && backtestStore.equitySeries.length > 0;
});

const metrics = computed(() => backtestStore.metrics);

const equityCurveData = computed(() => {
  if (backtestStore.equitySeries.length > 0) {
    return [{
      versionId: 'current',
      versionName: '当前回测',
      data: backtestStore.equitySeries
    }];
  }
  return [];
});

const benchmarkData = computed(() => backtestStore.benchmarkEquitySeries);
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
