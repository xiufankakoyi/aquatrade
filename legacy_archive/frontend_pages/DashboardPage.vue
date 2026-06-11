<!--
  Dashboard 页面
  显示收益曲线、雷达图、热力图和版本切换下拉菜单
-->
<template>
  <div class="dashboard-page">
    <!-- 页面标题和版本选择 -->
    <div class="page-header">
      <h1 class="page-title">回测 Dashboard</h1>

      <!-- 版本切换下拉菜单和 AI 分析按钮 -->
      <div class="header-actions">
        <div class="version-selector">
          <label class="selector-label">版本</label>
          <select
            v-model="selectedVersionId"
            @change="handleVersionChange"
            class="version-select"
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
          class="ai-btn"
        >
          <span v-if="isAnalyzing" class="spinner-icon"></span>
          <i v-else class="fas fa-robot"></i>
          <span>{{ isAnalyzing ? '分析中' : 'AI 复盘' }}</span>
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-state">
      <div class="loading-spinner"></div>
      <p class="loading-text">加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-state">
      <p class="error-text">{{ error }}</p>
    </div>

    <!-- 主要内容 -->
    <div v-else class="content-area">
      <!-- 收益曲线 -->
      <div class="chart-card">
        <h2 class="card-title">收益曲线</h2>
        <div class="chart-wrapper">
          <EquityCurve
            :versions="equityCurveData"
            :benchmark="benchmarkData"
            @hover="handleEquityHover"
            class="equity-chart"
          />
        </div>
      </div>

      <!-- 雷达图和热力图 -->
      <div class="charts-grid">
        <!-- 雷达图 -->
        <div class="chart-card">
          <h2 class="card-title">策略雷达图</h2>
          <div class="chart-wrapper">
            <RadarChart
              v-if="currentLiveBacktestResult?.radarScores || currentRadarScores"
              :scores="currentLiveBacktestResult?.radarScores || currentRadarScores"
              class="radar-chart"
            />
            <div v-else class="empty-state">
              暂无雷达图数据
            </div>
          </div>
        </div>

        <!-- 热力图 -->
        <div class="chart-card">
          <h2 class="card-title">月度收益热力图</h2>
          <div class="chart-wrapper">
            <HeatmapChart
              v-if="monthlyReturnsData.length > 0"
              :data="monthlyReturnsData"
              class="heatmap-chart"
            />
            <div v-else class="empty-state">
              暂无热力图数据
            </div>
          </div>
        </div>
      </div>

      <!-- 防守仓模块（默认隐藏，可展开） -->
      <div class="chart-card">
        <div class="card-header">
          <h2 class="card-title">防守仓仓位分析</h2>
          <button
            @click="showDefensePortfolio = !showDefensePortfolio"
            class="toggle-btn"
          >
            {{ showDefensePortfolio ? '隐藏' : '显示' }}
          </button>
        </div>
        <!-- 使用实时回测数据或 strategyStore 中的数据 -->
        <div v-if="showDefensePortfolio && (currentLiveBacktestResult || currentBacktestResult)" class="defense-content">
          <PortfolioDefense
            :trades="(currentLiveBacktestResult || currentBacktestResult)?.trades || []"
            class="defense-component"
          />
        </div>
      </div>
    </div>

    <!-- AI 分析报告弹窗 -->
    <div
      v-if="showAnalysisModal"
      class="modal-overlay"
      @click.self="closeAnalysisModal"
    >
      <div class="modal-container">
        <!-- 弹窗头部 -->
        <div class="modal-header">
          <h2 class="modal-title">
            <i class="fas fa-robot"></i>
            AI 深度复盘报告
          </h2>
          <button
            @click="closeAnalysisModal"
            class="modal-close"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- 弹窗内容 -->
        <div class="modal-body">
          <div v-if="isAnalyzing" class="analyzing-state">
            <div class="loading-spinner"></div>
            <p class="analyzing-text">AI 正在分析策略表现，请稍候...</p>
            <p class="analyzing-hint">这可能需要几秒钟到几十秒钟</p>
          </div>

          <div v-else-if="analysisError" class="error-state">
            <p class="error-text">{{ analysisError }}</p>
          </div>

          <div
            v-else-if="aiReportMarkdown"
            class="report-content"
            v-html="renderMarkdown(aiReportMarkdown)"
          ></div>

          <div v-else class="empty-state">
            暂无分析报告
          </div>
        </div>

        <!-- 弹窗底部 -->
        <div class="modal-footer">
          <button
            @click="closeAnalysisModal"
            class="close-btn"
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

    // 使用相对路径，让 Vite 代理可以正确代理请求到后端
    const url = '/api/analyze_report';
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
    codeBlocks.push(`<pre class="code-block"><code>${escapeHtml(code)}</code></pre>`);
    return id;
  });

  // 处理行内代码
  const inlineCodes: string[] = [];
  html = html.replace(/`([^`]+)`/gim, (match, code) => {
    const id = `__INLINE_CODE_${inlineCodes.length}__`;
    inlineCodes.push(`<code class="inline-code">${escapeHtml(code)}</code>`);
    return id;
  });

  // 处理标题
  html = html.replace(/^### (.*$)/gim, '<h3 class="report-h3">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 class="report-h2">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 class="report-h1">$1</h1>');

  // 处理粗体
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong class="report-strong">$1</strong>');

  // 处理列表（无序列表）
  html = html.replace(/^[\-\*] (.+)$/gim, '<li class="report-li">$1</li>');
  // 处理有序列表
  html = html.replace(/^\d+\. (.+)$/gim, '<li class="report-li report-ol">$1</li>');

  // 包装连续的列表项
  html = html.replace(/(<li class="report-li[^>]*>.*?<\/li>\n?)+/gim, (match) => {
    return '<ul class="report-ul">' + match + '</ul>';
  });

  // 处理段落（双换行）
  const paragraphs = html.split(/\n\n+/);
  html = paragraphs.map(p => {
    p = p.trim();
    if (!p) return '';
    // 如果已经是 HTML 标签，不包装
    if (p.startsWith('<')) return p;
    return `<p class="report-p">${p}</p>`;
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
  padding: clamp(0.75rem, 2vw, 1rem);
  background: var(--bg-primary, #0a0a0a);
  color: #f3f4f6;
  min-height: 100%;
  overflow-x: hidden;
  transition: background-color 0.3s ease;
}

/* 页面头部 */
.page-header {
  margin-bottom: clamp(0.75rem, 2vw, 1rem);
  display: flex;
  flex-direction: column;
  gap: clamp(0.5rem, 1.5vw, 0.75rem);
}

@media (min-width: 768px) {
  .page-header {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}

.page-title {
  font-size: clamp(1.125rem, 2vw, 1.5rem);
  font-weight: 600;
  color: #f3f4f6;
  margin: 0;
}

.header-actions {
  display: flex;
  flex-direction: column;
  gap: clamp(0.5rem, 1vw, 0.75rem);
  width: 100%;
}

@media (min-width: 640px) {
  .header-actions {
    flex-direction: row;
    align-items: center;
    width: auto;
  }
}

.version-selector {
  display: flex;
  align-items: center;
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
  width: 100%;
}

@media (min-width: 640px) {
  .version-selector {
    width: auto;
  }
}

.selector-label {
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #737373;
  flex-shrink: 0;
}

.version-select {
  height: clamp(1.75rem, 5vh, 2rem);
  padding: 0 clamp(0.5rem, 1vw, 0.75rem);
  background: var(--bg-tertiary, #141414);
  border: 1px solid var(--border-card, #2a2a2a);
  border-radius: 0.25rem;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #e5e7eb;
  outline: none;
  flex: 1;
  min-width: 0;
}

@media (min-width: 640px) {
  .version-select {
    width: clamp(10rem, 20vw, 15rem);
    flex: none;
  }
}

.version-select:focus {
  border-color: var(--border-hover, #404040);
}

.ai-btn {
  height: clamp(1.75rem, 5vh, 2rem);
  padding: 0 clamp(0.5rem, 1vw, 0.75rem);
  background: var(--accent-ai, #7c3aed);
  border: none;
  border-radius: 0.25rem;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  font-weight: 500;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: clamp(0.25rem, 0.5vw, 0.375rem);
  width: 100%;
  justify-content: center;
}

@media (min-width: 640px) {
  .ai-btn {
    width: auto;
  }
}

.ai-btn:hover:not(:disabled) {
  background: var(--accent-ai-hover, #6d28d9);
}

.ai-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ai-btn i,
.spinner-icon {
  font-size: clamp(0.625rem, 0.7vw, 0.6875rem);
}

.spinner-icon {
  display: inline-block;
  width: clamp(0.75rem, 1vw, 0.875rem);
  height: clamp(0.75rem, 1vw, 0.875rem);
  border: 2px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 加载状态 */
.loading-state {
  text-align: center;
  padding: clamp(1.5rem, 5vh, 2rem) clamp(1rem, 3vw, 1.5rem);
}

.loading-spinner {
  display: inline-block;
  width: clamp(1.5rem, 4vw, 2rem);
  height: clamp(1.5rem, 4vw, 2rem);
  border: 2px solid var(--border-card, #2a2a2a);
  border-top-color: var(--accent-primary, #2962FF);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  margin-top: clamp(0.5rem, 1.5vh, 0.75rem);
  color: #737373;
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
}

/* 错误状态 */
.error-state {
  background: var(--error-bg, #2a0a0a);
  border: 1px solid var(--error-border, #4a1a1a);
  border-radius: 0.25rem;
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  margin-bottom: clamp(0.75rem, 2vw, 1rem);
}

.error-text {
  color: var(--error-color, #ef4444);
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  margin: 0;
}

/* 内容区域 */
.content-area {
  display: flex;
  flex-direction: column;
  gap: clamp(0.75rem, 2vw, 1rem);
}

/* 卡片样式 */
.chart-card {
  background: var(--bg-card, #111111);
  border: 1px solid var(--border-card, #1a1a1a);
  border-radius: 0.375rem;
  padding: clamp(0.75rem, 2vw, 1rem);
  overflow: hidden;
}

.card-title {
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
  font-weight: 500;
  color: #a3a3a3;
  margin: 0 0 clamp(0.5rem, 1.5vh, 0.75rem) 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: clamp(0.5rem, 1.5vh, 0.75rem);
}

.toggle-btn {
  height: clamp(1.375rem, 4vh, 1.5rem);
  padding: 0 clamp(0.375rem, 0.75vw, 0.5rem);
  background: transparent;
  border: 1px solid var(--border-card, #2a2a2a);
  border-radius: 0.25rem;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #a3a3a3;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-btn:hover {
  color: #e5e7eb;
  border-color: var(--border-hover, #404040);
}

/* 图表容器 */
.chart-wrapper {
  width: 100%;
  min-height: clamp(150px, 25vh, 200px);
}

@media (min-width: 768px) {
  .chart-wrapper {
    min-height: clamp(200px, 30vh, 300px);
  }
}

.equity-chart,
.radar-chart,
.heatmap-chart {
  width: 100%;
  height: 100%;
}

/* 图表网格 */
.charts-grid {
  display: grid;
  gap: clamp(0.75rem, 2vw, 1rem);
  grid-template-columns: 1fr;
}

@media (min-width: 992px) {
  .charts-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 空状态 */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: clamp(150px, 25vh, 200px);
  text-align: center;
  color: #525252;
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
}

/* 防守仓内容 */
.defense-content {
  overflow-x: auto;
}

.defense-component {
  width: 100%;
  min-width: 600px;
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: clamp(0.5rem, 2vw, 1rem);
}

.modal-container {
  background: var(--bg-card, #111111);
  border: 1px solid var(--border-card, #2a2a2a);
  border-radius: 0.375rem;
  width: min(95%, 64rem);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: clamp(0.75rem, 2vw, 1rem);
  border-bottom: 1px solid var(--border-color, #1a1a1a);
  gap: clamp(0.5rem, 1vw, 0.75rem);
}

.modal-title {
  font-size: clamp(0.9375rem, 1.2vw, 1rem);
  font-weight: 500;
  color: #e5e7eb;
  margin: 0;
  display: flex;
  align-items: center;
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
}

.modal-title i {
  color: var(--accent-ai, #7c3aed);
}

.modal-close {
  width: clamp(1.5rem, 3vw, 1.75rem);
  height: clamp(1.5rem, 3vw, 1.75rem);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #737373;
  cursor: pointer;
  transition: color 0.15s ease;
  border-radius: 0.25rem;
  flex-shrink: 0;
}

.modal-close:hover {
  color: #d4d4d4;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: clamp(0.75rem, 2vw, 1rem);
}

.modal-footer {
  padding: clamp(0.75rem, 2vw, 1rem);
  border-top: 1px solid var(--border-color, #1a1a1a);
  display: flex;
  justify-content: flex-end;
}

.close-btn {
  height: clamp(1.75rem, 5vh, 2rem);
  padding: 0 clamp(0.75rem, 1.5vw, 1rem);
  background: var(--bg-secondary, #1f1f1f);
  border: 1px solid var(--border-card, #2a2a2a);
  border-radius: 0.25rem;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #d4d4d4;
  cursor: pointer;
  transition: all 0.15s ease;
}

.close-btn:hover {
  background: var(--border-card, #2a2a2a);
}

/* 分析中状态 */
.analyzing-state {
  text-align: center;
  padding: clamp(1.5rem, 5vh, 2rem);
}

.analyzing-text {
  color: #a3a3a3;
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
  margin: clamp(0.5rem, 1.5vh, 0.75rem) 0 0 0;
}

.analyzing-hint {
  color: #525252;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  margin: clamp(0.25rem, 0.75vh, 0.375rem) 0 0 0;
}

/* 报告内容 */
.report-content {
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
  line-height: 1.6;
}

.report-content :deep(.report-h1) {
  font-size: clamp(1.25rem, 1.8vw, 1.5rem);
  font-weight: 700;
  margin: clamp(1.5rem, 3vh, 2rem) 0 clamp(0.75rem, 1.5vh, 1rem);
  color: #f9fafb;
}

.report-content :deep(.report-h2) {
  font-size: clamp(1.125rem, 1.5vw, 1.25rem);
  font-weight: 600;
  margin: clamp(1.25rem, 2.5vh, 1.5rem) 0 clamp(0.625rem, 1.25vh, 0.75rem);
  color: #f3f4f6;
}

.report-content :deep(.report-h3) {
  font-size: clamp(1rem, 1.2vw, 1.125rem);
  font-weight: 600;
  margin: clamp(1rem, 2vh, 1.25rem) 0 clamp(0.5rem, 1vh, 0.625rem);
  color: #e5e7eb;
}

.report-content :deep(.report-p) {
  margin-bottom: clamp(0.75rem, 1.5vh, 1rem);
  color: #d1d5db;
}

.report-content :deep(.report-ul) {
  margin-bottom: clamp(0.75rem, 1.5vh, 1rem);
  padding-left: clamp(1.25rem, 2.5vw, 1.5rem);
}

.report-content :deep(.report-li) {
  margin-bottom: clamp(0.375rem, 0.75vh, 0.5rem);
  color: #d1d5db;
}

.report-content :deep(.report-strong) {
  color: #f9fafb;
  font-weight: 600;
}

.report-content :deep(.code-block) {
  background: rgba(0, 0, 0, 0.3);
  padding: clamp(0.75rem, 1.5vw, 1rem);
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: clamp(0.75rem, 1.5vh, 1rem) 0;
}

.report-content :deep(.code-block code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: clamp(0.75rem, 0.9vw, 0.8125rem);
  color: #e5e7eb;
}

.report-content :deep(.inline-code) {
  background: rgba(0, 0, 0, 0.3);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: clamp(0.75rem, 0.9vw, 0.8125rem);
  color: #e5e7eb;
}
</style>
