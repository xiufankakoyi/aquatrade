<!--
  Dashboard 页面
  显示收益曲线、雷达图、热力图和版本切换下拉菜单
-->
<template>
  <div class="dashboard-page p-4 md:p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen overflow-x-hidden">
    <!-- 页面标题和版本选择 -->
    <div class="mb-4 md:mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <h1 class="text-2xl md:text-3xl font-bold text-gray-800 dark:text-slate-100">回测 Dashboard</h1>
      
      <!-- 版本切换下拉菜单和 AI 分析按钮 -->
      <div class="flex flex-col sm:flex-row items-start sm:items-center space-y-4 sm:space-y-0 sm:space-x-4 w-full sm:w-auto">
        <div class="flex items-center space-x-2 w-full sm:w-auto">
          <label class="text-sm font-medium text-gray-700 dark:text-slate-300">选择版本：</label>
          <select
            v-model="selectedVersionId"
            @change="handleVersionChange"
            class="px-3 py-2 md:px-4 md:py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-auto"
          >
            <option value="">全部版本</option>
            <option
              v-for="version in availableVersions"
              :key="version.id"
              :value="version.id"
            >
              {{ version.name }} ({{ version.version }})
            </option>
          </select>
        </div>
        
        <!-- AI 深度复盘按钮 -->
        <button
          v-if="currentBacktestResult && currentStrategyId"
          @click="analyzeStrategy"
          :disabled="isAnalyzing"
          class="px-3 py-2 md:px-4 md:py-2 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-lg font-medium hover:from-purple-600 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2 w-full sm:w-auto justify-center"
        >
          <span v-if="isAnalyzing" class="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
          <span v-else>🤖</span>
          <span>{{ isAnalyzing ? '分析中...' : 'AI 深度复盘' }}</span>
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="text-center py-8 md:py-12">
      <div class="inline-block animate-spin rounded-full h-8 w-8 md:h-12 md:w-12 border-b-2 border-blue-500"></div>
      <p class="mt-3 md:mt-4 text-gray-600 dark:text-slate-400">加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 md:p-4 mb-4 md:mb-6">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- 主要内容 -->
    <div v-else class="space-y-4 md:space-y-6">
      <!-- 收益曲线 -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6 overflow-hidden">
        <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">收益曲线</h2>
        <div class="w-full min-h-[200px] md:min-h-[300px]">
          <EquityCurve
            :versions="equityCurveData"
            :benchmark="benchmarkData"
            @hover="handleEquityHover"
            class="w-full h-full"
          />
        </div>
      </div>

      <!-- 雷达图和热力图 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        <!-- 雷达图 -->
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6 overflow-hidden">
          <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">策略雷达图</h2>
          <div class="w-full min-h-[250px] md:min-h-[300px]">
            <RadarChart
              v-if="currentLiveBacktestResult?.radarScores || currentRadarScores"
              :scores="currentLiveBacktestResult?.radarScores || currentRadarScores"
              class="w-full h-full"
            />
            <div v-else class="flex items-center justify-center w-full h-full text-center text-gray-500 dark:text-slate-400">
              暂无雷达图数据
            </div>
          </div>
        </div>

        <!-- 热力图 -->
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6 overflow-hidden">
          <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100 mb-3 md:mb-4">月度收益热力图</h2>
          <div class="w-full min-h-[250px] md:min-h-[300px]">
            <HeatmapChart
              v-if="monthlyReturnsData.length > 0"
              :data="monthlyReturnsData"
              class="w-full h-full"
            />
            <div v-else class="flex items-center justify-center w-full h-full text-center text-gray-500 dark:text-slate-400">
              暂无热力图数据
            </div>
          </div>
        </div>
      </div>

      <!-- 防守仓模块（默认隐藏，可展开） -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 md:p-6">
        <div class="flex items-center justify-between mb-3 md:mb-4">
          <h2 class="text-lg md:text-xl font-semibold text-gray-800 dark:text-slate-100">防守仓仓位分析</h2>
          <button
            @click="showDefensePortfolio = !showDefensePortfolio"
            class="px-3 py-1 md:px-4 md:py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
          >
            {{ showDefensePortfolio ? '隐藏' : '显示' }}
          </button>
        </div>
        <!-- 使用实时回测数据或 strategyStore 中的数据 -->
        <div v-if="showDefensePortfolio && (currentLiveBacktestResult || currentBacktestResult)" class="overflow-x-auto">
          <PortfolioDefense
            :trades="(currentLiveBacktestResult || currentBacktestResult)?.trades || []"
            class="w-full"
          />
        </div>
      </div>
    </div>

    <!-- AI 分析报告弹窗 -->
    <div
      v-if="showAnalysisModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-3 md:p-4 overflow-y-auto"
      @click.self="closeAnalysisModal"
    >
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        <!-- 弹窗头部 -->
        <div class="flex items-center justify-between p-4 md:p-6 border-b border-gray-200 dark:border-slate-700">
          <h2 class="text-xl md:text-2xl font-bold text-gray-800 dark:text-slate-100">🤖 AI 深度复盘报告</h2>
          <button
            @click="closeAnalysisModal"
            class="text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200 text-xl md:text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <!-- 弹窗内容 -->
        <div class="flex-1 overflow-y-auto p-4 md:p-6">
          <div v-if="isAnalyzing" class="text-center py-8 md:py-12">
            <div class="inline-block animate-spin rounded-full h-8 w-8 md:h-12 md:w-12 border-b-2 border-purple-500 mb-3 md:mb-4"></div>
            <p class="text-gray-600 dark:text-slate-400">AI 正在分析策略表现，请稍候...</p>
            <p class="text-sm text-gray-500 dark:text-slate-500 mt-1 md:mt-2">这可能需要几秒钟到几十秒钟</p>
          </div>

          <div v-else-if="analysisError" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 md:p-4">
            <p class="text-red-800 dark:text-red-200">{{ analysisError }}</p>
          </div>

          <div
            v-else-if="aiReportMarkdown"
            class="prose dark:prose-invert max-w-none text-sm md:text-base"
            v-html="renderMarkdown(aiReportMarkdown)"
          ></div>

          <div v-else class="text-center py-8 md:py-12 text-gray-500 dark:text-slate-400">
            暂无分析报告
          </div>
        </div>

        <!-- 弹窗底部 -->
        <div class="p-4 md:p-6 border-t border-gray-200 dark:border-slate-700 flex justify-end">
          <button
            @click="closeAnalysisModal"
            class="px-4 py-2 md:px-6 md:py-2 bg-gray-200 dark:bg-slate-700 text-gray-800 dark:text-slate-200 rounded-lg hover:bg-gray-300 dark:hover:bg-slate-600 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useBacktestStore } from '../store/backtestStore';
import { getAvailableVersions } from '../api/backtestApi';
import { apiService } from '../services/api';
import EquityCurve from '../components/EquityCurve.vue';
import RadarChart from '../components/RadarChart.vue';
import HeatmapChart from '../components/HeatmapChart.vue';
import PortfolioDefense from '../components/PortfolioDefense.vue';
import type { StrategyVersion } from '../store/strategyStore';

const router = useRouter();
const strategyStore = useStrategyStore();
const backtestStore = useBacktestStore();

// 状态
const selectedVersionId = ref<string>('');
const showDefensePortfolio = ref(false);

// AI 分析相关状态
const isAnalyzing = ref(false);
const showAnalysisModal = ref(false);
const aiReportMarkdown = ref<string>('');
const analysisError = ref<string>('');

// 当前策略ID（从版本ID或回测结果中获取）
const currentStrategyId = computed(() => {
  // 优先使用选中的版本ID
  if (selectedVersionId.value) {
    return selectedVersionId.value;
  }
  // 否则从回测结果中获取
  if (currentBacktestResult.value?.versionId) {
    return currentBacktestResult.value.versionId;
  }
  // 或者从当前版本中获取
  if (currentVersion.value?.id) {
    return currentVersion.value.id;
  }
  return '';
});

// 从 store 获取数据
const isLoading = computed(() => strategyStore.isLoading);
const error = computed(() => strategyStore.error);
const availableVersions = computed(() => strategyStore.availableVersions);
const dashboardData = computed(() => strategyStore.dashboardData);
const currentBacktestResult = computed(() => strategyStore.currentBacktestResult);
const currentRadarScores = computed(() => strategyStore.currentRadarScores);
const currentVersion = computed(() => strategyStore.currentVersion);

// 从 backtestStore 获取实时回测数据
const equitySeries = computed(() => backtestStore.equitySeries);
const benchmarkSeries = computed(() => backtestStore.benchmarkEquitySeries);
const backtestMetrics = computed(() => backtestStore.metrics);
const backtestTrades = computed(() => backtestStore.trades);
const backtestMonthlyReturns = computed(() => backtestStore.monthlyReturns);

// 收益曲线数据 - 优先使用实时回测数据，否则使用 strategyStore 中的数据
const equityCurveData = computed(() => {
  // 如果有实时回测数据，使用它
  if (equitySeries.value.length > 0) {
    return [{
      versionId: 'current',
      versionName: '当前回测',
      data: equitySeries.value
    }];
  }
  // 否则使用 strategyStore 中的数据
  if (!dashboardData.value) return [];
  return dashboardData.value.versions.map(v => ({
    versionId: v.versionId,
    versionName: v.versionName,
    data: v.equityCurve
  }));
});

// 基准数据 - 优先使用实时回测数据，否则使用 strategyStore 中的数据
const benchmarkData = computed(() => {
  // 如果有实时基准数据，使用它
  if (benchmarkSeries.value.length > 0) {
    return benchmarkSeries.value;
  }
  // 否则使用 strategyStore 中的数据
  return dashboardData.value?.benchmark || [];
});

// 月度收益数据 - 优先使用实时回测数据，否则使用 strategyStore 中的数据
const monthlyReturnsData = computed(() => {
  // 如果有实时月度收益数据，使用它
  if (backtestMonthlyReturns.value.length > 0) {
    return backtestMonthlyReturns.value;
  }
  // 否则使用 strategyStore 中的数据
  if (!currentBacktestResult.value?.monthlyReturns) return [];
  return currentBacktestResult.value.monthlyReturns;
});

// 计算当前回测结果 - 优先使用实时回测数据
const currentLiveBacktestResult = computed(() => {
  if (equitySeries.value.length > 0 && backtestMetrics.value) {
    return {
      versionId: 'current',
      metrics: backtestMetrics.value,
      equityCurve: equitySeries.value,
      monthlyReturns: backtestMonthlyReturns.value,
      trades: backtestTrades.value
    };
  }
  return null;
});

// 版本切换处理
function handleVersionChange() {
  if (selectedVersionId.value) {
    router.push(`/strategy/${selectedVersionId.value}`);
  }
}

// 收益曲线 hover 事件
function handleEquityHover(data: {
  date: string;
  version?: string;
  equity: number;
  monthlyReturn?: number;
}) {
  // 可以在这里显示 tooltip 或其他交互
  console.log('Hover data:', data);
}

// 加载数据
async function loadDashboardData() {
  try {
    strategyStore.setLoading(true);
    strategyStore.setError(null);

    // 加载可用版本列表
    const versions = await getAvailableVersions();
    strategyStore.setAvailableVersions(versions);

    // 如果有选中的版本，加载该版本的详情
    if (selectedVersionId.value) {
      const version = versions.find(v => v.id === selectedVersionId.value);
      if (version) {
        // 可以在这里加载该版本的详细数据
      }
    }
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : '加载数据失败';
    strategyStore.setError(errorMessage);
    console.error('加载 Dashboard 数据失败:', err);
  } finally {
    strategyStore.setLoading(false);
  }
}

// 监听版本变化
watch(selectedVersionId, (newVersionId) => {
  if (newVersionId && dashboardData.value) {
    // 更新当前版本的回测结果
    const versionData = dashboardData.value.versions.find(v => v.versionId === newVersionId);
    if (versionData) {
      strategyStore.setCurrentVersion(newVersionId);
    }
  }
});

// AI 分析策略
async function analyzeStrategy() {
  // 优先使用实时回测数据，否则使用 strategyStore 中的数据
  const backtestResult = currentLiveBacktestResult.value || currentBacktestResult.value;
  if (!backtestResult || !currentStrategyId.value) {
    analysisError.value = '请先运行回测或选择策略';
    showAnalysisModal.value = true;
    return;
  }

  isAnalyzing.value = true;
  analysisError.value = '';
  aiReportMarkdown.value = '';
  showAnalysisModal.value = true;

  try {
    const reportBacktestResult = {
      ...backtestResult,
      strategyInfo: backtestResult.strategyInfo || {
        name: currentVersion.value?.name || currentStrategyId.value,
        description: currentVersion.value?.description || '',
      },
    };

    const url = 'http://localhost:5000/api/analyze_report';
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy_id: currentStrategyId.value,
        backtest_result: reportBacktestResult,
      })
    });

    if (!response.ok) throw new Error('分析请求失败');
    
    const reader = response.body?.getReader();
    if (!reader) throw new Error('无法初始化流读取器');

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
        try {
          if (line.startsWith('stream:')) {
            const data = JSON.parse(line.slice(7));
            if (data.content) aiReportMarkdown.value += data.content;
          } else if (line.startsWith('progress:')) {
            // 可选：在这里处理进度显示，DashboardPage.vue 目前没显示详细进度
          }
        } catch (e) {
          console.error('解析流数据失败', e);
        }
      }
    }
  } catch (error: any) {
    console.error('AI 分析失败', error);
    analysisError.value = error.message || 'AI 分析失败，请稍后重试';
  } finally {
    isAnalyzing.value = false;
  }
}

// 关闭分析弹窗
function closeAnalysisModal() {
  showAnalysisModal.value = false;
  aiReportMarkdown.value = '';
  analysisError.value = '';
}

// 简单的 Markdown 渲染（将 Markdown 转换为 HTML）
function renderMarkdown(markdown: string): string {
  if (!markdown) return '';

  // 转义 HTML 特殊字符
  function escapeHtml(text: string): string {
    const map: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

  // 先处理代码块（避免被其他规则影响）
  const codeBlocks: string[] = [];
  let html = markdown.replace(/```[\s\S]*?```/gim, (match) => {
    const code = match.replace(/```/g, '').trim();
    const id = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push(`<pre class="bg-gray-100 dark:bg-slate-700 p-4 rounded-lg overflow-x-auto my-4 text-sm font-mono"><code>${escapeHtml(code)}</code></pre>`);
    return id;
  });

  // 处理行内代码
  const inlineCodes: string[] = [];
  html = html.replace(/`([^`]+)`/gim, (match, code) => {
    const id = `__INLINE_CODE_${inlineCodes.length}__`;
    inlineCodes.push(`<code class="bg-gray-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-sm font-mono">${escapeHtml(code)}</code>`);
    return id;
  });

  // 处理标题
  html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-6 mb-3 text-gray-800 dark:text-slate-100">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mt-8 mb-4 text-gray-800 dark:text-slate-100">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-10 mb-5 text-gray-900 dark:text-slate-50">$1</h1>');

  // 处理粗体
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong class="font-semibold text-gray-900 dark:text-slate-50">$1</strong>');

  // 处理列表（无序列表）
  html = html.replace(/^[\-\*] (.+)$/gim, '<li class="ml-6 mb-2">$1</li>');
  // 处理有序列表
  html = html.replace(/^\d+\. (.+)$/gim, '<li class="ml-6 mb-2 list-decimal">$1</li>');

  // 包装连续的列表项
  html = html.replace(/(<li class="ml-6 mb-2[^>]*>.*?<\/li>\n?)+/gim, (match) => {
    return '<ul class="list-disc ml-6 mb-4 space-y-1">' + match + '</ul>';
  });

  // 处理段落（双换行）
  const paragraphs = html.split(/\n\n+/);
  html = paragraphs.map(p => {
    p = p.trim();
    if (!p) return '';
    // 如果已经是 HTML 标签，不包装
    if (p.startsWith('<')) return p;
    return `<p class="mb-4 text-gray-700 dark:text-slate-300 leading-relaxed">${p}</p>`;
  }).join('');

  // 处理单换行
  html = html.replace(/\n(?!<)/g, '<br>');

  // 恢复代码块
  codeBlocks.forEach((code, index) => {
    html = html.replace(`__CODE_BLOCK_${index}__`, code);
  });

  // 恢复行内代码
  inlineCodes.forEach((code, index) => {
    html = html.replace(`__INLINE_CODE_${index}__`, code);
  });

  return html;
}

onMounted(() => {
  // 从 localStorage 加载回测数据
  backtestStore.hydrateFromStorage();
  // 加载可用版本列表
  loadDashboardData();
});
</script>

<style scoped>
.dashboard-page {
  transition: background-color 0.3s ease;
}
</style>

