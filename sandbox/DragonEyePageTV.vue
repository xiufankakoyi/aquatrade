<template>
  <div class="tv-container">
    <!-- Header - 紧凑的工具栏 -->
    <header class="tv-header-bar">
      <div class="tv-header-left">
        <h1 class="tv-page-title">
          <i class="fas fa-dragon"></i>
          DragonEye
        </h1>
        <span class="tv-page-subtitle">龙虎榜监控</span>
      </div>
      
      <div class="tv-header-center">
        <div class="tv-date-control">
          <span class="tv-label">日期</span>
          <input 
            type="date" 
            v-model="targetDate" 
            class="tv-input tv-input-date"
          />
        </div>
        
        <div class="tv-divider-vertical"></div>
        
        <div class="tv-btn-group">
          <button
            @click="startCrawl"
            :disabled="!!(isCrawling || activeJobId)"
            class="tv-btn tv-btn-secondary"
            :class="{ 'tv-btn-active': isCrawling }"
          >
            <i class="fas" :class="isCrawling ? 'fa-spinner fa-spin' : 'fa-spider'"></i>
            <span>{{ isCrawling ? '抓取中' : '启动抓取' }}</span>
          </button>
          
          <button
            @click="startPipeline"
            :disabled="!!(isProcessing || activeJobId)"
            class="tv-btn tv-btn-primary"
          >
            <i class="fas" :class="isProcessing ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
            <span>{{ isProcessing ? '处理中' : '一键全流程' }}</span>
          </button>
        </div>
      </div>
      
      <div class="tv-header-right">
        <div v-if="activeJobId" class="tv-status">
          <span class="tv-status-dot tv-status-dot-running"></span>
          <span>{{ statusText }} {{ jobProgress }}%</span>
        </div>
        <button class="tv-icon-btn" @click="showLogs = !showLogs">
          <i class="fas fa-terminal"></i>
        </button>
        <button class="tv-icon-btn">
          <i class="fas fa-cog"></i>
        </button>
      </div>
    </header>

    <!-- Progress Bar -->
    <div v-if="activeJobId" class="tv-progress" style="margin-bottom: 8px;">
      <div 
        class="tv-progress-bar"
        :style="{ width: `${jobProgress}%` }"
      ></div>
    </div>

    <!-- Main Content Grid -->
    <div class="tv-grid tv-grid-2" style="height: calc(100vh - 140px);">
      <!-- Left Column - 核心数据 -->
      <div class="tv-flex tv-flex-col" style="gap: 8px;">
        <!-- Key Metrics Cards -->
        <div class="tv-grid tv-grid-4">
          <div class="tv-panel tv-metric-card">
            <div class="tv-metric">
              <span class="tv-metric-label">涨停家数</span>
              <span class="tv-metric-value tv-metric-value-up">{{ metrics.limitUpCount || '--' }}</span>
            </div>
          </div>
          <div class="tv-panel tv-metric-card">
            <div class="tv-metric">
              <span class="tv-metric-label">跌停家数</span>
              <span class="tv-metric-value tv-metric-value-down">{{ metrics.limitDownCount || '--' }}</span>
            </div>
          </div>
          <div class="tv-panel tv-metric-card">
            <div class="tv-metric">
              <span class="tv-metric-label">最高连板</span>
              <span class="tv-metric-value tv-metric-value-up">{{ metrics.maxHeight || '--' }}板</span>
            </div>
          </div>
          <div class="tv-panel tv-metric-card">
            <div class="tv-metric">
              <span class="tv-metric-label">炸板率</span>
              <span class="tv-metric-value">{{ metrics.brokenRatio ? (metrics.brokenRatio * 100).toFixed(1) + '%' : '--' }}</span>
            </div>
          </div>
        </div>

        <!-- Stock Table - 核心数据表格 -->
        <div class="tv-panel tv-flex-1" style="display: flex; flex-direction: column; min-height: 0;">
          <div class="tv-panel-header" style="position: relative; padding: 8px 12px; border-bottom: 1px solid var(--tv-border);">
            <span class="tv-panel-label">龙头股实时因子</span>
            <div class="tv-panel-tools">
              <button class="tv-tool-btn"><i class="fas fa-filter"></i></button>
              <button class="tv-tool-btn"><i class="fas fa-download"></i></button>
            </div>
          </div>
          <div class="tv-table-container tv-flex-1">
            <table class="tv-table">
              <thead>
                <tr>
                  <th>个股</th>
                  <th>连板</th>
                  <th>封单额</th>
                  <th>换手</th>
                  <th>监管</th>
                  <th>机构</th>
                  <th>题材</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="stock in dragonStocks" :key="stock.stock_code" class="tv-table-row-up">
                  <td>
                    <div class="tv-flex tv-flex-col">
                      <span class="tv-text-primary tv-text-mono">{{ stock.stock_name }}</span>
                      <span class="tv-text-muted" style="font-size: 10px;">{{ stock.stock_code }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="tv-badge" :class="stock.continue_num >= 4 ? 'tv-badge-up' : 'tv-badge-neutral'">
                      {{ stock.continue_num }}板
                    </span>
                  </td>
                  <td class="tv-text-mono">{{ (stock.order_amount / 100000000).toFixed(2) }}亿</td>
                  <td class="tv-text-mono">{{ stock.turnover_rate.toFixed(2) }}%</td>
                  <td>
                    <i v-if="stock.is_regulation" class="fas fa-exclamation-triangle tv-text-down"></i>
                    <span v-else class="tv-text-muted">-</span>
                  </td>
                  <td>
                    <i v-if="stock.is_institution_buy" class="fas fa-university tv-text-up"></i>
                    <span v-else class="tv-text-muted">-</span>
                  </td>
                  <td>
                    <span class="tv-truncate" style="max-width: 120px; display: block;">{{ stock.leader_tag }}</span>
                  </td>
                </tr>
                <tr v-if="dragonStocks.length === 0">
                  <td colspan="7" class="tv-empty-cell">
                    <div class="tv-empty-state">
                      <i class="fas fa-inbox"></i>
                      <span>暂无数据</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Sentiment Chart -->
        <div class="tv-panel" style="height: 240px;">
          <div class="tv-panel-header">
            <span class="tv-panel-label">市场情绪走势</span>
            <div class="tv-panel-tools">
              <button class="tv-tool-btn"><i class="fas fa-expand"></i></button>
            </div>
          </div>
          <div ref="sentimentChartRef" class="tv-chart-wrapper"></div>
        </div>
      </div>

      <!-- Right Column - 分析图表 -->
      <div class="tv-flex tv-flex-col" style="gap: 8px;">
        <!-- Limit Up Trend Chart -->
        <div class="tv-panel" style="height: 280px;">
          <div class="tv-panel-header">
            <span class="tv-panel-label">涨停趋势分析</span>
            <div class="tv-legend tv-panel-tools">
              <span class="tv-legend-item">
                <span class="tv-legend-dot" style="background: #ef4444;"></span>
                <span>涨停数</span>
              </span>
              <span class="tv-legend-item">
                <span class="tv-legend-dot" style="background: #f59e0b;"></span>
                <span>最高连板</span>
              </span>
            </div>
          </div>
          <div ref="trendChartRef" class="tv-chart-wrapper"></div>
        </div>

        <!-- Bubble Matrix Chart -->
        <div class="tv-panel tv-flex-1" style="min-height: 0;">
          <div class="tv-panel-header">
            <span class="tv-panel-label">涨停强度矩阵</span>
            <div class="tv-legend tv-panel-tools">
              <span class="tv-legend-item">
                <span class="tv-legend-dot" style="background: #10b981;"></span>
                <span>强势</span>
              </span>
              <span class="tv-legend-item">
                <span class="tv-legend-dot" style="background: #3b82f6;"></span>
                <span>权重</span>
              </span>
            </div>
          </div>
          <div ref="bubbleChartRef" class="tv-chart-wrapper"></div>
        </div>

        <!-- Theme Flow Chart -->
        <div class="tv-panel" style="height: 200px;">
          <div class="tv-panel-header">
            <span class="tv-panel-label">题材流向</span>
          </div>
          <div ref="flowChartRef" class="tv-chart-wrapper"></div>
        </div>
      </div>
    </div>

    <!-- AI Brief Panel - 可折叠 -->
    <div v-if="showAiBrief" class="tv-ai-panel">
      <div class="tv-panel-header" style="position: relative; padding: 8px 12px; border-bottom: 1px solid var(--tv-border);">
        <span class="tv-panel-label">AI 每日复盘</span>
        <div class="tv-panel-tools">
          <button class="tv-tool-btn" @click="fetchBrief"><i class="fas fa-sync"></i></button>
          <button class="tv-tool-btn" @click="showAiBrief = false"><i class="fas fa-times"></i></button>
        </div>
      </div>
      <div class="tv-ai-content">
        <pre v-if="aiBrief" class="tv-ai-text">{{ aiBrief }}</pre>
        <div v-else class="tv-empty-state">
          <i class="fas fa-robot"></i>
          <span>点击刷新获取AI分析</span>
        </div>
      </div>
    </div>

    <!-- Logs Panel - 可折叠 -->
    <div v-if="showLogs" class="tv-logs-panel">
      <div class="tv-panel-header" style="position: relative; padding: 8px 12px; border-bottom: 1px solid var(--tv-border);">
        <span class="tv-panel-label">实时日志</span>
        <div class="tv-panel-tools">
          <button class="tv-tool-btn" @click="clearLogs"><i class="fas fa-trash"></i></button>
          <button class="tv-tool-btn" @click="showLogs = false"><i class="fas fa-times"></i></button>
        </div>
      </div>
      <div ref="logContainer" class="tv-logs-content">
        <div 
          v-for="(log, index) in logs" 
          :key="index"
          class="tv-log-line"
        >
          <span class="tv-log-time">{{ formatTime(log.timestamp) }}</span>
          <span 
            class="tv-log-level"
            :class="`tv-log-level-${log.level}`"
          >
            {{ log.level.toUpperCase() }}
          </span>
          <span class="tv-log-message">{{ log.message }}</span>
        </div>
        <div v-if="logs.length === 0" class="tv-empty-state">
          <span>等待任务启动...</span>
        </div>
      </div>
    </div>

    <!-- Floating Action Button for AI Brief -->
    <button 
      v-if="!showAiBrief"
      @click="showAiBrief = true"
      class="tv-fab"
      title="AI复盘"
    >
      <i class="fas fa-brain"></i>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import * as echarts from 'echarts';

// ==========================================
// State
// ==========================================
const targetDate = ref(new Date().toISOString().split('T')[0]);
const isCrawling = ref(false);
const isProcessing = ref(false);
const dragonStocks = ref<any[]>([]);
const aiBrief = ref('');
const showAiBrief = ref(false);
const showLogs = ref(false);
const logs = ref<any[]>([]);

// Metrics
const metrics = ref({
  limitUpCount: 0,
  limitDownCount: 0,
  maxHeight: 0,
  brokenRatio: 0
});

// Chart refs
const sentimentChartRef = ref<HTMLElement | null>(null);
const trendChartRef = ref<HTMLElement | null>(null);
const bubbleChartRef = ref<HTMLElement | null>(null);
const flowChartRef = ref<HTMLElement | null>(null);

let sentimentChart: echarts.ECharts | null = null;
let trendChart: echarts.ECharts | null = null;
let bubbleChart: echarts.ECharts | null = null;
let flowChart: echarts.ECharts | null = null;

// Job State
const activeJobId = ref<string | null>(null);
const jobStatus = ref<string>('');
const jobProgress = ref(0);

// ==========================================
// Computed
// ==========================================
const statusText = computed(() => {
  const map: Record<string, string> = {
    'pending': '等待',
    'running': '运行',
    'completed': '完成',
    'failed': '失败'
  };
  return map[jobStatus.value] || '空闲';
});

// ==========================================
// Mock Data for Demo
// ==========================================
const mockStocks = [
  { stock_code: '000001', stock_name: '平安银行', continue_num: 5, order_amount: 2500000000, turnover_rate: 15.5, is_regulation: false, is_institution_buy: true, leader_tag: '金融科技+区块链' },
  { stock_code: '000002', stock_name: '万科A', continue_num: 3, order_amount: 1800000000, turnover_rate: 8.2, is_regulation: false, is_institution_buy: false, leader_tag: '房地产+物业管理' },
  { stock_code: '000063', stock_name: '中兴通讯', continue_num: 4, order_amount: 3200000000, turnover_rate: 12.8, is_regulation: true, is_institution_buy: true, leader_tag: '5G+芯片+华为' },
  { stock_code: '000100', stock_name: 'TCL科技', continue_num: 2, order_amount: 900000000, turnover_rate: 6.5, is_regulation: false, is_institution_buy: false, leader_tag: '面板+半导体' },
  { stock_code: '000333', stock_name: '美的集团', continue_num: 1, order_amount: 1500000000, turnover_rate: 4.2, is_regulation: false, is_institution_buy: true, leader_tag: '家电+智能制造' },
  { stock_code: '000538', stock_name: '云南白药', continue_num: 2, order_amount: 800000000, turnover_rate: 3.8, is_regulation: false, is_institution_buy: false, leader_tag: '中药+医美' },
  { stock_code: '000568', stock_name: '泸州老窖', continue_num: 3, order_amount: 2100000000, turnover_rate: 7.5, is_regulation: false, is_institution_buy: true, leader_tag: '白酒+消费' },
  { stock_code: '000651', stock_name: '格力电器', continue_num: 1, order_amount: 1200000000, turnover_rate: 5.2, is_regulation: false, is_institution_buy: false, leader_tag: '家电+新能源' }
];

// ==========================================
// Methods
// ==========================================
const initCharts = () => {
  if (sentimentChartRef.value) {
    sentimentChart = echarts.init(sentimentChartRef.value);
    updateSentimentChart();
  }
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value);
    updateTrendChart();
  }
  if (bubbleChartRef.value) {
    bubbleChart = echarts.init(bubbleChartRef.value);
    updateBubbleChart();
  }
  if (flowChartRef.value) {
    flowChart = echarts.init(flowChartRef.value);
    updateFlowChart();
  }
};

const updateSentimentChart = () => {
  if (!sentimentChart) return;
  
  const dates = ['01-15', '01-16', '01-17', '01-18', '01-19', '01-20', '01-21'];
  const maxHeights = [3, 4, 5, 4, 6, 5, 7];
  const brokenRatios = [0.15, 0.12, 0.18, 0.10, 0.22, 0.14, 0.20];
  
  sentimentChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(19, 23, 34, 0.95)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10 }
    },
    yAxis: [
      {
        type: 'value',
        axisLine: { show: false },
        axisLabel: { color: '#787b86', fontSize: 10 },
        splitLine: { lineStyle: { color: '#2a2e39' } }
      },
      {
        type: 'value',
        max: 1,
        axisLine: { show: false },
        axisLabel: { color: '#787b86', fontSize: 10, formatter: (v: number) => (v * 100).toFixed(0) + '%' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '最高板',
        type: 'line',
        data: maxHeights,
        smooth: true,
        lineStyle: { color: '#089981', width: 2 },
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(8, 153, 129, 0.2)' },
            { offset: 1, color: 'transparent' }
          ])
        }
      },
      {
        name: '炸板率',
        type: 'bar',
        yAxisIndex: 1,
        data: brokenRatios,
        itemStyle: { color: '#f23645', borderRadius: [2, 2, 0, 0] },
        barWidth: '30%'
      }
    ]
  });
};

const updateTrendChart = () => {
  if (!trendChart) return;
  
  const dates = ['01-15', '01-16', '01-17', '01-18', '01-19', '01-20', '01-21'];
  const limitUpCounts = [45, 52, 38, 65, 48, 72, 55];
  const maxHeights = [3, 4, 5, 4, 6, 5, 7];
  
  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(19, 23, 34, 0.95)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#787b86', fontSize: 10 },
      splitLine: { lineStyle: { color: '#2a2e39' } }
    },
    series: [
      {
        name: '涨停数',
        type: 'bar',
        data: limitUpCounts,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#ef4444' },
            { offset: 1, color: '#dc2626' }
          ]),
          borderRadius: [2, 2, 0, 0]
        },
        barWidth: '40%'
      },
      {
        name: '最高连板',
        type: 'line',
        data: maxHeights,
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 2 },
        symbol: 'circle',
        symbolSize: 5,
        itemStyle: { color: '#f59e0b' }
      }
    ]
  });
};

const updateBubbleChart = () => {
  if (!bubbleChart) return;
  
  const data = [
    { value: [30, 500, 25, 5], name: '强势股', itemStyle: { color: '#10b981' } },
    { value: [60, 800, 18, 3], name: '权重股', itemStyle: { color: '#3b82f6' } },
    { value: [90, 200, 12, 2], name: '跟风股', itemStyle: { color: '#f59e0b' } },
    { value: [45, 300, 20, 4], name: '题材股', itemStyle: { color: '#ec4899' } },
    { value: [25, 150, 30, 6], name: '强势股', itemStyle: { color: '#10b981' } },
    { value: [75, 600, 15, 3], name: '权重股', itemStyle: { color: '#3b82f6' } },
    { value: [120, 250, 10, 2], name: '跟风股', itemStyle: { color: '#f59e0b' } },
    { value: [50, 400, 22, 4], name: '题材股', itemStyle: { color: '#ec4899' } }
  ];
  
  bubbleChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(19, 23, 34, 0.95)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11 }
    },
    grid: { left: '8%', right: '8%', bottom: '12%', top: '8%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '封板时间',
      nameTextStyle: { color: '#787b86', fontSize: 10 },
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10 },
      splitLine: { lineStyle: { color: '#2a2e39' } }
    },
    yAxis: {
      type: 'value',
      name: '市值(亿)',
      nameTextStyle: { color: '#787b86', fontSize: 10 },
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10 },
      splitLine: { lineStyle: { color: '#2a2e39' } }
    },
    series: [{
      type: 'scatter',
      data: data,
      symbolSize: (d: number[]) => Math.max(10, Math.min(50, d[2])),
      itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.3)' }
    }]
  });
};

const updateFlowChart = () => {
  if (!flowChart) return;
  
  flowChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(19, 23, 34, 0.95)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11 }
    },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeAlign: 'left',
      nodeGap: 8,
      nodeWidth: 16,
      lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.5 },
      label: { color: '#787b86', fontSize: 10 },
      data: [
        { name: '01-15_人工智能', itemStyle: { color: '#10b981' } },
        { name: '01-16_人工智能', itemStyle: { color: '#10b981' } },
        { name: '01-15_新能源', itemStyle: { color: '#3b82f6' } },
        { name: '01-16_新能源', itemStyle: { color: '#3b82f6' } },
        { name: '01-15_半导体', itemStyle: { color: '#f59e0b' } },
        { name: '01-16_半导体', itemStyle: { color: '#f59e0b' } }
      ],
      links: [
        { source: '01-15_人工智能', target: '01-16_人工智能', value: 10 },
        { source: '01-15_新能源', target: '01-16_新能源', value: 8 },
        { source: '01-15_半导体', target: '01-16_半导体', value: 6 }
      ]
    }]
  });
};

const startCrawl = () => {
  isCrawling.value = true;
  activeJobId.value = 'crawl-' + Date.now();
  jobStatus.value = 'running';
  jobProgress.value = 0;
  showLogs.value = true;
  
  // Simulate progress
  const interval = setInterval(() => {
    jobProgress.value += 10;
    logs.value.push({
      timestamp: new Date(),
      level: 'info',
      message: `正在抓取数据... ${jobProgress.value}%`
    });
    
    if (jobProgress.value >= 100) {
      clearInterval(interval);
      isCrawling.value = false;
      jobStatus.value = 'completed';
      dragonStocks.value = mockStocks;
      metrics.value = { limitUpCount: 55, limitDownCount: 12, maxHeight: 7, brokenRatio: 0.18 };
      logs.value.push({ timestamp: new Date(), level: 'success', message: '数据抓取完成' });
    }
  }, 300);
};

const startPipeline = () => {
  isProcessing.value = true;
  activeJobId.value = 'pipeline-' + Date.now();
  jobStatus.value = 'running';
  jobProgress.value = 0;
  showLogs.value = true;
  
  const interval = setInterval(() => {
    jobProgress.value += 5;
    logs.value.push({
      timestamp: new Date(),
      level: 'info',
      message: `正在处理... ${jobProgress.value}%`
    });
    
    if (jobProgress.value >= 100) {
      clearInterval(interval);
      isProcessing.value = false;
      jobStatus.value = 'completed';
      dragonStocks.value = mockStocks;
      metrics.value = { limitUpCount: 72, limitDownCount: 8, maxHeight: 8, brokenRatio: 0.15 };
      logs.value.push({ timestamp: new Date(), level: 'success', message: '全流程处理完成' });
    }
  }, 200);
};

const fetchBrief = () => {
  aiBrief.value = `【AI每日复盘】

今日市场涨停家数72家，跌停8家，市场情绪偏暖。

最高连板达到8板，为近期新高，显示短线资金活跃。

主流题材方面：
1. 人工智能板块持续发酵，龙头个股连板高度领先
2. 新能源板块资金流入明显，机构参与度较高
3. 半导体板块出现分化，部分个股炸板

建议关注：
- 连板高度超过5板的个股监管风险
- 机构买入信号的个股后续表现
- 题材轮动的节奏把握`;
};

const clearLogs = () => {
  logs.value = [];
};

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false });
};

// ==========================================
// Lifecycle
// ==========================================
onMounted(() => {
  initCharts();
  
  const resizeHandler = () => {
    sentimentChart?.resize();
    trendChart?.resize();
    bubbleChart?.resize();
    flowChart?.resize();
  };
  window.addEventListener('resize', resizeHandler);
  
  onUnmounted(() => {
    window.removeEventListener('resize', resizeHandler);
    sentimentChart?.dispose();
    trendChart?.dispose();
    bubbleChart?.dispose();
    flowChart?.dispose();
  });
});
</script>

<style scoped>
@import './tv-design-system.css';

/* Header Bar */
.tv-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--tv-bg-secondary);
  border: 1px solid var(--tv-border);
  border-radius: var(--tv-radius-md);
  margin-bottom: 8px;
}

.tv-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tv-page-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--tv-text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.tv-page-title i {
  color: var(--tv-warning);
}

.tv-page-subtitle {
  font-size: 11px;
  color: var(--tv-text-secondary);
  padding-left: 8px;
  border-left: 1px solid var(--tv-border);
}

.tv-header-center {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tv-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tv-date-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tv-label {
  font-size: 11px;
  color: var(--tv-text-secondary);
}

.tv-input-date {
  width: 120px;
}

.tv-btn-group {
  display: flex;
  gap: 4px;
}

.tv-btn-active {
  background: var(--tv-up);
  color: white;
}

/* Metric Card */
.tv-metric-card {
  padding: 12px;
  display: flex;
  align-items: center;
}

/* Legend */
.tv-legend {
  display: flex;
  gap: 12px;
}

.tv-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--tv-text-secondary);
}

.tv-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

/* Empty States */
.tv-empty-cell {
  padding: 40px;
}

.tv-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--tv-text-secondary);
  font-size: 12px;
}

.tv-empty-state i {
  font-size: 24px;
  opacity: 0.5;
}

/* AI Panel */
.tv-ai-panel {
  position: fixed;
  right: 12px;
  top: 60px;
  width: 320px;
  background: var(--tv-bg-secondary);
  border: 1px solid var(--tv-border);
  border-radius: var(--tv-radius-md);
  box-shadow: var(--tv-shadow-lg);
  z-index: 100;
}

.tv-ai-content {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.tv-ai-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--tv-text-primary);
  white-space: pre-wrap;
  font-family: inherit;
}

/* Logs Panel */
.tv-logs-panel {
  position: fixed;
  right: 12px;
  bottom: 60px;
  width: 480px;
  height: 240px;
  background: var(--tv-bg-secondary);
  border: 1px solid var(--tv-border);
  border-radius: var(--tv-radius-md);
  box-shadow: var(--tv-shadow-lg);
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.tv-logs-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.tv-log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}

.tv-log-time {
  color: var(--tv-text-muted);
  flex-shrink: 0;
}

.tv-log-level {
  flex-shrink: 0;
  width: 50px;
  text-align: center;
  border-radius: 2px;
  font-size: 10px;
  font-weight: 600;
}

.tv-log-level-info {
  color: var(--tv-accent);
}

.tv-log-level-success {
  color: var(--tv-up);
}

.tv-log-level-warning {
  color: var(--tv-warning);
}

.tv-log-level-error {
  color: var(--tv-down);
}

.tv-log-message {
  color: var(--tv-text-primary);
  word-break: break-all;
}

/* Floating Action Button */
.tv-fab {
  position: fixed;
  right: 12px;
  bottom: 12px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--tv-accent);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--tv-shadow-md);
  transition: all var(--tv-transition-fast);
  z-index: 50;
}

.tv-fab:hover {
  background: var(--tv-accent-hover);
  transform: scale(1.05);
}

/* Flex utilities */
.tv-flex-1 {
  flex: 1;
  min-height: 0;
}
</style>
