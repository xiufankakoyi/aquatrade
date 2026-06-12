<template>
  <div class="dragon-eye-page bg-[#0a0a0a] min-h-screen">
    <!-- Header -->
    <header class="h-14 px-4 flex items-center justify-between bg-[#111] border-b border-[#1a1a1a]">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-bold text-white flex items-center gap-2">
          <i class="fas fa-dragon text-orange-500"></i>
          DragonEye
        </h1>
        <span class="text-xs text-slate-500 pl-3 border-l border-[#2a2a2a]">龙虎榜监控</span>
      </div>
      
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-500">日期</span>
          <input 
            type="date" 
            v-model="targetDate" 
            class="h-7 px-2 text-xs text-white bg-[#1a1a1a] rounded border-none outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
        
        <div class="w-px h-5 bg-[#2a2a2a]"></div>
        
        <div class="flex gap-2">
          <button
            @click="startCrawl"
            :disabled="!!(isCrawling || activeJobId)"
            class="h-7 px-3 bg-[#1a1a1a] hover:bg-[#252525] text-slate-300 rounded text-xs font-medium transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            <i class="fas" :class="isCrawling ? 'fa-spinner fa-spin' : 'fa-spider'"></i>
            <span>启动抓取</span>
          </button>
          
          <button
            @click="startPipeline"
            :disabled="!!(isProcessing || activeJobId)"
            class="h-7 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50 flex items-center gap-1.5"
          >
            <i class="fas" :class="isProcessing ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
            <span>一键全流程</span>
          </button>
        </div>
      </div>
      
      <div class="flex items-center gap-2">
        <div v-if="activeJobId" class="flex items-center gap-2 px-2 py-1 bg-[#1a1a1a] rounded">
          <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
          <span class="text-xs text-slate-400">{{ jobProgress }}%</span>
        </div>
        <button @click="showLogs = !showLogs" class="w-7 h-7 flex items-center justify-center text-slate-400 hover:text-white transition-colors">
          <i class="fas fa-terminal text-xs"></i>
        </button>
        <button class="w-7 h-7 flex items-center justify-center text-slate-400 hover:text-white transition-colors">
          <i class="fas fa-cog text-xs"></i>
        </button>
      </div>
    </header>

    <!-- Progress Bar -->
    <div v-if="activeJobId" class="h-0.5 bg-[#1a1a1a]">
      <div 
        class="h-full transition-all duration-300 rounded-full"
        :class="{
          'bg-gradient-to-r from-orange-500 to-red-500': jobType === 'crawl',
          'bg-gradient-to-r from-blue-500 to-indigo-500': jobType === 'full_pipeline'
        }"
        :style="{ width: `${jobProgress}%` }"
      ></div>
    </div>
    <ErrorState v-if="pageError" class="m-3" :message="pageError" :retryable="false" />
    <section class="evidence-panel">
      <div class="evidence-heading">
        <div>
          <h2>本地证据完整度</h2>
          <p>缺失组件不会按 0 或完整结果展示。</p>
        </div>
        <span class="evidence-mode">{{ evidenceMode }}</span>
      </div>
      <LoadingState v-if="evidenceLoading" title="正在读取 DragonEye 证据" />
      <ErrorState v-else-if="evidenceError" :message="evidenceError" @retry="fetchEvidenceStatus" />
      <EmptyState v-else-if="!evidenceStatus" title="暂无证据完整度" description="暂无本地证据" />
      <dl v-else class="evidence-grid">
        <div><dt>has_ladder</dt><dd>{{ formatAvailability(evidenceStatus.has_ladder) }}</dd></div>
        <div><dt>has_limit_up</dt><dd>{{ formatAvailability(evidenceStatus.has_limit_up) }}</dd></div>
        <div><dt>has_sentiment</dt><dd>{{ formatAvailability(evidenceStatus.has_sentiment) }}</dd></div>
        <div><dt>has_theme_flow</dt><dd>{{ formatAvailability(evidenceStatus.has_theme_flow) }}</dd></div>
        <div><dt>证据日期</dt><dd>{{ evidenceStatus.evidence_date || 'unavailable' }}</dd></div>
        <div><dt>完整度分数</dt><dd>{{ formatScore(evidenceStatus.completeness_score) }}</dd></div>
        <div class="wide"><dt>缺失组件</dt><dd>{{ formatMissingParts(evidenceStatus.missing_parts) }}</dd></div>
        <div class="wide"><dt>状态</dt><dd>{{ evidenceMode }}</dd></div>
      </dl>
    </section>

    <!-- Main Content - Two Column Layout -->
    <div class="main-grid p-3">
      <!-- Left Column -->
      <div class="left-column">
        <!-- Metrics Row -->
        <div class="grid grid-cols-4 gap-2">
          <div class="bg-[#111] rounded-lg p-3 flex items-center">
            <div class="flex flex-col gap-0.5">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider">涨停家数</span>
              <span class="text-lg font-semibold font-mono" :class="(metrics.limitUp ?? 0) >= 50 ? 'text-[#00d084]' : 'text-slate-300'">{{ metrics.limitUp ?? 'unavailable' }}</span>
            </div>
          </div>
          <div class="bg-[#111] rounded-lg p-3 flex items-center">
            <div class="flex flex-col gap-0.5">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider">跌停家数</span>
              <span class="text-lg font-semibold font-mono" :class="(metrics.limitDown ?? 0) > 10 ? 'text-[#ff4757]' : 'text-slate-300'">{{ metrics.limitDown ?? 'unavailable' }}</span>
            </div>
          </div>
          <div class="bg-[#111] rounded-lg p-3 flex items-center">
            <div class="flex flex-col gap-0.5">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider">最高连板</span>
              <span class="text-lg font-semibold font-mono text-[#ffa502]">{{ metrics.maxHeight }}</span>
            </div>
          </div>
          <div class="bg-[#111] rounded-lg p-3 flex items-center">
            <div class="flex flex-col gap-0.5">
              <span class="text-[10px] text-slate-500 uppercase tracking-wider">炸板率</span>
              <span class="text-lg font-semibold font-mono" :class="parseFloat(metrics.brokenRatio) > 20 ? 'text-[#ff4757]' : 'text-[#ffa502]'">{{ metrics.brokenRatio }}</span>
            </div>
          </div>
        </div>

        <!-- Stock Table - 填满剩余高度 -->
        <div class="bg-[#111] rounded-lg flex-1 min-h-0 flex flex-col">
          <div class="px-3 py-2 flex items-center justify-between border-b border-[#1a1a1a]">
            <span class="text-xs font-medium text-white">龙头股实时因子</span>
            <div class="flex gap-1">
              <button class="w-6 h-6 flex items-center justify-center text-slate-500 hover:text-white transition-colors">
                <i class="fas fa-filter text-xs"></i>
              </button>
              <button class="w-6 h-6 flex items-center justify-center text-slate-500 hover:text-white transition-colors">
                <i class="fas fa-download text-xs"></i>
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-auto">
            <table class="w-full text-left text-xs">
              <thead class="sticky top-0 bg-[#111] z-10">
                <tr class="text-[10px] text-slate-500 uppercase tracking-wider">
                  <th class="px-3 py-2 font-medium">个股</th>
                  <th class="px-3 py-2 font-medium">连板</th>
                  <th class="px-3 py-2 font-medium text-right">封单额</th>
                  <th class="px-3 py-2 font-medium text-right">换手</th>
                  <th class="px-3 py-2 font-medium text-center">监管</th>
                  <th class="px-3 py-2 font-medium text-center">机构</th>
                  <th class="px-3 py-2 font-medium">题材</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="stock in dragonStocks" :key="stock.stock_code" class="hover:bg-[#1a1a1a] transition-colors">
                  <td class="px-3 py-2">
                    <div class="flex flex-col">
                      <span class="text-blue-400 font-medium">{{ stock.stock_name }}</span>
                      <span class="text-[10px] text-slate-600 font-mono">{{ stock.stock_code }}</span>
                    </div>
                  </td>
                  <td class="px-3 py-2">
                    <span class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium"
                      :class="stock.continue_num >= 5 ? 'bg-[#ff4757]/20 text-[#ff4757]' : stock.continue_num >= 3 ? 'bg-[#ffa502]/20 text-[#ffa502]' : 'bg-[#787b86]/20 text-[#787b86]'">
                      {{ stock.continue_num }}板
                    </span>
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-slate-300">{{ formatYi(stock.order_amount) }}</td>
                  <td class="px-3 py-2 text-right font-mono text-slate-300">{{ formatPercentValue(stock.turnover_rate) }}</td>
                  <td class="px-3 py-2 text-center">
                    <i v-if="stock.is_regulation" class="fas fa-exclamation-triangle text-[#ff4757] text-xs" title="处于监管监控"></i>
                    <span v-else class="text-slate-600">-</span>
                  </td>
                  <td class="px-3 py-2 text-center">
                    <i v-if="stock.is_institution_buy" class="fas fa-university text-[#00d084] text-xs" title="机构专用买入"></i>
                    <span v-else class="text-slate-600">-</span>
                  </td>
                  <td class="px-3 py-2">
                    <span class="text-[10px] text-slate-400 truncate max-w-[100px] block" :title="stock.leader_tag">{{ stock.leader_tag }}</span>
                  </td>
                </tr>
                <tr v-if="dragonStocks.length === 0">
                  <td colspan="7" class="px-3 py-8 text-center text-slate-500 text-xs">
                    暂无当日龙头个股数据
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Sentiment Chart -->
        <div class="bg-[#111] rounded-lg h-[200px] flex flex-col">
          <div class="px-3 py-2 flex items-center justify-between border-b border-[#1a1a1a]">
            <span class="text-xs font-medium text-white">市场情绪走势</span>
            <button class="w-6 h-6 flex items-center justify-center text-slate-500 hover:text-white transition-colors">
              <i class="fas fa-expand text-xs"></i>
            </button>
          </div>
          <div ref="sentimentChartRef" class="flex-1"></div>
        </div>
      </div>

      <!-- Right Column -->
      <div class="right-column">
        <!-- AI Daily Brief Panel -->
        <div class="bg-[#111] rounded-lg overflow-hidden" :class="{ 'collapsed': aiBriefCollapsed }">
          <div class="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-[#1a1a1a] transition-colors" @click="aiBriefCollapsed = !aiBriefCollapsed">
            <div class="flex items-center gap-2">
              <i class="fas fa-robot text-blue-400 text-xs"></i>
              <span class="text-xs font-medium text-white">AI 每日复盘简报</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-[10px] text-slate-500">{{ targetDate }}</span>
              <i class="fas fa-chevron-down text-[10px] text-slate-500 transition-transform" :class="{ 'rotate-180': !aiBriefCollapsed }"></i>
            </div>
          </div>
          
          <div v-show="!aiBriefCollapsed" class="px-3 pb-3 space-y-3">
            <!-- Key Metrics -->
            <div class="grid grid-cols-3 gap-2">
              <div class="bg-[#0a0a0a] rounded p-2 text-center">
                <div class="text-[10px] text-slate-500 mb-0.5">市场情绪</div>
                <div class="text-xs font-medium" :class="sentimentColor">{{ sentimentText }}</div>
              </div>
              <div class="bg-[#0a0a0a] rounded p-2 text-center">
                <div class="text-[10px] text-slate-500 mb-0.5">涨停家数</div>
                <div class="text-xs font-medium text-[#00d084]">{{ metrics.limitUp ?? 'unavailable' }}</div>
              </div>
              <div class="bg-[#0a0a0a] rounded p-2 text-center">
                <div class="text-[10px] text-slate-500 mb-0.5">最高连板</div>
                <div class="text-xs font-medium text-[#ffa502]">{{ metrics.maxHeight }}</div>
              </div>
            </div>
            
            <!-- Market Overview - Keywords -->
            <div>
              <div class="flex items-center gap-1.5 mb-1.5">
                <i class="fas fa-chart-line text-[10px] text-slate-400"></i>
                <span class="text-[10px] text-slate-400 uppercase tracking-wider">市场概况</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#00d084]/10 text-[#00d084]">
                  <i class="fas fa-arrow-up text-[8px]"></i>
                  涨停{{ metrics.limitUp ?? 'unavailable' }}家
                </span>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#ff4757]/10 text-[#ff4757]">
                  <i class="fas fa-arrow-down text-[8px]"></i>
                  跌停{{ metrics.limitDown ?? 'unavailable' }}家
                </span>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#ffa502]/10 text-[#ffa502]">
                  <i class="fas fa-layer-group text-[8px]"></i>
                  最高{{ metrics.maxHeight }}
                </span>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#6366f1]/10 text-[#6366f1]">
                  <i class="fas fa-percentage text-[8px]"></i>
                  炸板{{ metrics.brokenRatio }}
                </span>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px]" :class="sentimentTagClass">
                  <i class="fas fa-thermometer-half text-[8px]"></i>
                  {{ sentimentText }}
                </span>
              </div>
            </div>
            
            <!-- Theme Tags -->
            <div>
              <div class="flex items-center gap-1.5 mb-1.5">
                <i class="fas fa-fire text-[10px] text-slate-400"></i>
                <span class="text-[10px] text-slate-400 uppercase tracking-wider">题材热点</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <span 
                  v-for="theme in hotThemes" 
                  :key="theme.name"
                  @click="filterByTheme(theme.name)"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] cursor-pointer transition-all"
                  :class="activeTheme === theme.name ? 'bg-blue-500/20 text-blue-400' : 'bg-[#1a1a1a] text-slate-400 hover:bg-[#252525]'"
                  :style="{ color: activeTheme === theme.name ? theme.color : '' }"
                >
                  <i class="fas" :class="theme.icon" :style="{ color: theme.color }"></i>
                  {{ theme.name }}
                </span>
              </div>
            </div>
            
            <!-- Actions -->
            <div class="flex gap-2 pt-1">
              <button @click="fetchBrief" class="flex-1 h-7 flex items-center justify-center gap-1.5 bg-[#1a1a1a] hover:bg-[#252525] text-slate-300 rounded-full text-[10px] transition-all">
                <i class="fas fa-sync-alt" :class="{ 'fa-spin': isLoadingBrief }"></i>
                <span>刷新简报</span>
              </button>
              <button 
                @click="confirmAndPush" 
                :disabled="isPushing"
                class="flex-1 h-7 flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-full text-[10px] transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
              >
                <i class="fas" :class="isPushing ? 'fa-spinner fa-spin' : 'fa-paper-plane'"></i>
                <span>推送飞书</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Theme Flow Chart - 放大显示 -->
        <div class="bg-[#111] rounded-lg flex-1 min-h-0 flex flex-col">
          <div class="px-3 py-2 flex items-center justify-between border-b border-[#1a1a1a]">
            <div class="flex items-center gap-2">
              <span class="text-xs font-medium text-white">题材流向路径图</span>
              <span class="text-[10px] text-slate-500">{{ chartStartDate?.slice(5) }} → {{ chartEndDate?.slice(5) }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="flex items-center gap-1 text-[10px] text-slate-400">
                <i class="fas fa-circle text-[6px]" style="color: #00FF88"></i>
                主流
              </span>
              <span class="flex items-center gap-1 text-[10px] text-slate-400">
                <i class="fas fa-circle text-[6px]" style="color: #787B86"></i>
                普通
              </span>
            </div>
          </div>
          <div class="flex-1 min-h-0">
            <ThemeFlowChart
              ref="themeFlowChartRef"
              :data="themeFlowData"
              :loading="flowLoading"
            />
          </div>
          <!-- 流向解读 - 只保留这一个 -->
          <div class="px-3 py-2 border-t border-[#1a1a1a]">
            <div class="grid grid-cols-3 gap-2 text-[10px]">
              <div class="flex items-center gap-1.5 text-slate-400">
                <i class="fas fa-arrow-right text-[#00d084]"></i>
                <span>龙头引领</span>
              </div>
              <div class="flex items-center gap-1.5 text-slate-400">
                <i class="fas fa-arrows-alt text-[#ffa502]"></i>
                <span>跟风跟进</span>
              </div>
              <div class="flex items-center gap-1.5 text-slate-400">
                <i class="fas fa-expand text-[#ff6b81]"></i>
                <span>扩散补涨</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Trend Chart -->
        <div class="bg-[#111] rounded-lg h-[140px] flex flex-col">
          <div class="px-3 py-2 flex items-center justify-between border-b border-[#1a1a1a]">
            <span class="text-xs font-medium text-white">涨停趋势分析</span>
            <div class="flex items-center gap-3">
              <span class="flex items-center gap-1 text-[10px] text-slate-400">
                <span class="w-2 h-2 rounded-sm bg-[#ef4444]"></span>
                涨停数
              </span>
              <span class="flex items-center gap-1 text-[10px] text-slate-400">
                <span class="w-2 h-2 rounded-sm bg-[#f59e0b]"></span>
                最高连板
              </span>
            </div>
          </div>
          <div class="flex-1 min-h-0">
            <LimitUpTrendChart
              :data="limitUpTrendData"
              :loading="chartsLoading"
            />
          </div>
        </div>

        <!-- Bubble Matrix Chart -->
        <div class="bg-[#111] rounded-lg h-[140px] flex flex-col">
          <div class="px-3 py-2 flex items-center justify-between border-b border-[#1a1a1a]">
            <span class="text-xs font-medium text-white">涨停强度矩阵</span>
            <span class="text-[10px] text-slate-500">来源：本地结构化证据</span>
          </div>
          <div class="flex-1 min-h-0">
            <BubbleMatrixChart
              :data="bubbleMatrixData"
              :loading="bubbleLoading"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Logs Panel -->
    <div v-if="showLogs" class="fixed bottom-0 left-0 right-0 h-48 bg-[#111] border-t border-[#1a1a1a] z-50">
      <div class="h-8 px-3 flex items-center justify-between border-b border-[#1a1a1a]">
        <span class="text-xs font-medium text-white flex items-center gap-2">
          <i class="fas fa-terminal text-slate-400"></i>
          实时日志
        </span>
        <div class="flex gap-2">
          <button @click="clearLogs" class="text-[10px] text-slate-500 hover:text-white transition-colors">清空</button>
          <button @click="showLogs = false" class="text-[10px] text-slate-500 hover:text-white transition-colors">收起</button>
        </div>
      </div>
      <div ref="logContainer" class="h-40 overflow-y-auto p-3 space-y-1 font-mono text-[10px]">
        <div v-for="(log, index) in logs" :key="index" class="flex gap-2">
          <span class="text-slate-600 shrink-0">{{ formatTime(log.timestamp) }}</span>
          <span class="shrink-0 w-14 text-right" :class="{
            'text-blue-400': log.level === 'info',
            'text-green-400': log.level === 'success',
            'text-yellow-400': log.level === 'warning',
            'text-red-400': log.level === 'error'
          }">[{{ log.level.toUpperCase() }}]</span>
          <span class="text-slate-300 break-all">{{ log.message }}</span>
        </div>
        <div v-if="logs.length === 0" class="text-slate-600 text-center py-4">等待任务启动...</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import axios from '../api/index';
import ErrorState from '../components/common/ErrorState.vue';
import LoadingState from '../components/common/LoadingState.vue';
import EmptyState from '../components/common/EmptyState.vue';

import LimitUpTrendChart from '../components/charts/LimitUpTrendChart.vue';
import BubbleMatrixChart from '../components/charts/BubbleMatrixChart.vue';
import ThemeFlowChart from '../components/charts/ThemeFlowChart.vue';

// State
const targetDate = ref('');
const pageError = ref('');
const isCrawling = ref(false);
const isProcessing = ref(false);
const isPushing = ref(false);
const isLoadingBrief = ref(false);
const dragonStocks = ref<any[]>([]);
const aiBrief = ref('');
const aiBriefCollapsed = ref(false);
const activeTheme = ref<string | null>(null);
const evidenceLoading = ref(false);
const evidenceError = ref('');
const evidenceStatus = ref<any>(null);
const evidenceOnly = ref(false);

// Metrics
const metrics = ref({
  limitUp: null as number | null,
  limitDown: null as number | null,
  maxHeight: 'N/A',
  brokenRatio: 'N/A'
});

// Chart refs
const sentimentChartRef = ref<HTMLElement | null>(null);
let sentimentChart: echarts.ECharts | null = null;
const themeFlowChartRef = ref<InstanceType<typeof ThemeFlowChart> | null>(null);

// Chart data
const chartsLoading = ref(false);
const bubbleLoading = ref(false);
const flowLoading = ref(false);
const limitUpTrendData = ref<any>(null);
const bubbleMatrixData = ref<any>(null);
const themeFlowData = ref<any>(null);
const chartStartDate = ref('');
const chartEndDate = ref('');

// Job & Logs
const activeJobId = ref<string | null>(null);
const jobStatus = ref<string>('');
const jobType = ref<string>('');
const jobProgress = ref(0);
const logs = ref<any[]>([]);
const showLogs = ref(false);
const logContainer = ref<HTMLElement | null>(null);
let eventSource: EventSource | null = null;

// Hot themes
const hotThemes = ref<any[]>([]);

// Computed
const sentimentText = computed(() => {
  const limitUp = metrics.value.limitUp;
  const limitDown = metrics.value.limitDown;
  if (limitUp == null || limitDown == null || limitUp + limitDown <= 0) return 'unavailable';
  const ratio = limitUp / (limitUp + limitDown);
  if (ratio > 0.9) return '强势';
  if (ratio > 0.8) return '偏暖';
  if (ratio > 0.6) return '震荡';
  return '偏冷';
});
const evidenceMode = computed(() => {
  if (!evidenceStatus.value) return 'unavailable';
  const partial = evidenceStatus.value.partial_success || evidenceStatus.value.status === 'partial';
  if (evidenceOnly.value && partial) return 'evidence_only / partial_success';
  if (evidenceOnly.value) return 'evidence_only';
  if (partial) return 'partial_success';
  return 'complete';
});

const sentimentColor = computed(() => {
  const text = sentimentText.value;
  if (text === '强势') return 'text-[#00d084]';
  if (text === '偏暖') return 'text-[#00d084]';
  if (text === '震荡') return 'text-[#ffa502]';
  return 'text-[#ff4757]';
});

const sentimentTagClass = computed(() => {
  const text = sentimentText.value;
  if (text === '强势') return 'bg-[#00d084]/10 text-[#00d084]';
  if (text === '偏暖') return 'bg-[#00d084]/10 text-[#00d084]';
  if (text === '震荡') return 'bg-[#ffa502]/10 text-[#ffa502]';
  return 'bg-[#ff4757]/10 text-[#ff4757]';
});

// 获取数据库最新日期
const fetchLatestDate = async () => {
  try {
    const res = await axios.get('/api/dragon/latest-date');
    if (res.data && res.data.latest_date) {
      targetDate.value = res.data.latest_date;
    } else {
      targetDate.value = '';
    }
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '最新日期加载失败';
    console.error('Fetch latest date failed:', e);
    targetDate.value = '';
  }
};

const fetchEvidenceStatus = async () => {
  evidenceLoading.value = true;
  evidenceError.value = '';
  try {
    const res = await axios.get('/api/quant-flow/latest');
    const report = res.data?.data || res.data;
    const stage = report?.stages?.find((item: any) => item.stage === 'dragon_eye_summary');
    const stageData = stage?.data;
    if (!stageData) {
      evidenceStatus.value = null;
      evidenceOnly.value = false;
      return;
    }
    const partial = stageData.latest_partial_status;
    evidenceStatus.value = partial?.evidence_date === report.global_latest_trade_date
      ? { ...partial, partial_success: true }
      : stageData;
    evidenceOnly.value = report?.final_brief?.data?.research_output_level === 'evidence_only';
    const selectedCurrentEvidence = evidenceStatus.value === stageData
      && stageData.evidence_date === report.global_latest_trade_date;
    const themes = selectedCurrentEvidence
      ? stageData.evidence?.sector_heat_stats?.data
      : [];
    hotThemes.value = Array.isArray(themes)
      ? themes.slice(0, 8).map((item: any) => ({
          name: item.name,
          icon: 'fa-circle',
          color: '#787B86',
        }))
      : [];
  } catch (error) {
    evidenceStatus.value = null;
    evidenceError.value = error instanceof Error ? error.message : '证据完整度加载失败';
  } finally {
    evidenceLoading.value = false;
  }
};

// API Functions
const fetchStocks = async () => {
  if (!targetDate.value) {
    dragonStocks.value = [];
    return;
  }
  try {
    const res = await axios.get('/api/dragon/stocks', {
      params: { start_date: targetDate.value, end_date: targetDate.value }
    });
    dragonStocks.value = res.data;
    // Update metrics from first stock if available
    if (res.data.length > 0) {
      // Calculate metrics from data
      const maxBoard = Math.max(...res.data.map((s: any) => s.continue_num));
      metrics.value.maxHeight = maxBoard + '板';
    }
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '龙头数据加载失败';
    console.error('Fetch stocks failed:', e);
  }
};

const fetchBrief = async () => {
  if (!targetDate.value) {
    aiBrief.value = '';
    return;
  }
  isLoadingBrief.value = true;
  try {
    const res = await axios.get('/api/dragon/brief', { params: { date: targetDate.value } });
    aiBrief.value = res.data.content;
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '市场简报加载失败';
    console.error('Fetch brief failed:', e);
  } finally {
    isLoadingBrief.value = false;
  }
};

const fetchSentimentHistory = async () => {
  try {
    const end = targetDate.value;
    if (!end) return;
    const start = new Date(new Date(end).getTime() - 15 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const res = await axios.get('/api/dragon/sentiment', { params: { start_date: start, end_date: end } });
    updateSentimentChart(res.data);
  } catch (e) {
    console.error('Fetch sentiment history failed:', e);
  }
};

const fetchLimitUpTrend = async () => {
  if (!chartStartDate.value || !chartEndDate.value) return;
  chartsLoading.value = true;
  try {
    const res = await axios.get('/api/dragon/limit-up-trend', {
      params: { start_date: chartStartDate.value, end_date: chartEndDate.value }
    });
    limitUpTrendData.value = res.data;
  } catch (e) {
    console.error('Fetch limit up trend failed:', e);
  } finally {
    chartsLoading.value = false;
  }
};

const fetchBubbleMatrix = async () => {
  if (!targetDate.value) return;
  bubbleLoading.value = true;
  try {
    const res = await axios.get('/api/dragon/bubble-matrix', { params: { date: targetDate.value } });
    bubbleMatrixData.value = res.data;
  } catch (e) {
    console.error('Fetch bubble matrix failed:', e);
  } finally {
    bubbleLoading.value = false;
  }
};

const fetchThemeFlow = async () => {
  if (!chartStartDate.value || !chartEndDate.value) return;
  flowLoading.value = true;
  try {
    const res = await axios.get('/api/dragon/theme-flow', {
      params: { start_date: chartStartDate.value, end_date: chartEndDate.value }
    });
    themeFlowData.value = res.data;
  } catch (e) {
    console.error('Fetch theme flow failed:', e);
  } finally {
    flowLoading.value = false;
  }
};

// Chart
const updateSentimentChart = (data: any[]) => {
  if (!sentimentChart) return;
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(d => d.trade_date.slice(5)),
      axisLine: { lineStyle: { color: '#1a1a1a' } },
      axisLabel: { color: '#64748b', fontSize: 9 }
    },
    yAxis: [
      {
        type: 'value',
        min: 0,
        axisLabel: { color: '#64748b', fontSize: 9 },
        splitLine: { lineStyle: { color: '#1a1a1a' } }
      },
      {
        type: 'value',
        max: 1,
        axisLabel: { color: '#64748b', fontSize: 9, formatter: (v: number) => (v * 100).toFixed(0) + '%' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '最高板',
        type: 'line',
        data: data.map(d => d.max_height),
        smooth: true,
        lineStyle: { color: '#00d084', width: 2 },
        symbol: 'none',
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(0, 208, 132, 0.2)' }, { offset: 1, color: 'transparent' }]) }
      },
      {
        name: '炸板率',
        type: 'bar',
        yAxisIndex: 1,
        data: data.map(d => d.broken_ratio),
        itemStyle: { color: '#6366f1', borderRadius: [1, 1, 0, 0] },
        barWidth: '30%'
      }
    ]
  };
  sentimentChart.setOption(option);
};

// Theme filter
const filterByTheme = (theme: string) => {
  if (activeTheme.value === theme) {
    activeTheme.value = null;
    themeFlowChartRef.value?.highlightTheme(null);
  } else {
    activeTheme.value = theme;
    themeFlowChartRef.value?.highlightTheme(theme);
  }
};

// Job functions
const startCrawl = async () => {
  try {
    isCrawling.value = true;
    showLogs.value = true;
    clearLogs();
    
    const res = await axios.post('/api/dragon/crawl', { date: targetDate.value });
    const { job_id } = res.data;
    
    activeJobId.value = job_id;
    jobType.value = 'crawl';
    connectToStream(job_id);
  } catch (e: any) {
    console.error('Start crawl failed:', e);
    alert('启动抓取失败: ' + (e.response?.data?.error || e.message));
    isCrawling.value = false;
  }
};

const startPipeline = async () => {
  try {
    isProcessing.value = true;
    showLogs.value = true;
    clearLogs();
    
    const res = await axios.post('/api/dragon/pipeline', { 
      date: targetDate.value,
      push_feishu: true
    });
    const { job_id } = res.data;
    
    activeJobId.value = job_id;
    jobType.value = 'full_pipeline';
    connectToStream(job_id);
  } catch (e: any) {
    console.error('Start pipeline failed:', e);
    alert('启动工作流失败: ' + (e.response?.data?.error || e.message));
    isProcessing.value = false;
  }
};

const connectToStream = (jobId: string) => {
  if (eventSource) eventSource.close();
  
  eventSource = new EventSource(`/api/dragon/stream/${jobId}`);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleStreamData(data);
  };
  
  eventSource.onerror = () => {
    eventSource?.close();
  };
};

const handleStreamData = (data: any) => {
  switch (data.type) {
    case 'connected':
      jobStatus.value = 'running';
      break;
    case 'log':
      logs.value.push(data.data);
      scrollToBottom();
      if (data.data.message.includes('%')) {
        const match = data.data.message.match(/(\d+)%/);
        if (match) jobProgress.value = parseInt(match[1]);
      }
      break;
    case 'complete':
      jobStatus.value = data.status;
      jobProgress.value = 100;
      activeJobId.value = null;
      isCrawling.value = false;
      isProcessing.value = false;
      fetchStocks();
      fetchBrief();
      fetchSentimentHistory();
      eventSource?.close();
      break;
    case 'error':
      jobStatus.value = 'failed';
      activeJobId.value = null;
      isCrawling.value = false;
      isProcessing.value = false;
      eventSource?.close();
      break;
  }
};

const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
};

const clearLogs = () => {
  logs.value = [];
};

const formatTime = (timestamp: string) => {
  if (!timestamp) return '';
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false });
};
const formatAvailability = (value: unknown) => typeof value === 'boolean' ? (value ? '是' : '否') : 'unavailable';
const formatScore = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(4) : 'unavailable';
const formatMissingParts = (value: unknown) => Array.isArray(value) ? (value.length ? value.join('、') : '无') : 'unavailable';
const formatYi = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${(value / 1e8).toFixed(2)}亿` : 'unavailable';
const formatPercentValue = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}%` : 'unavailable';

const confirmAndPush = async () => {
  isPushing.value = true;
  try {
    await axios.post('/api/dragon/push', { date: targetDate.value });
    alert('已成功推送至飞书');
  } catch (e: any) {
    alert('推送失败: ' + (e.response?.data?.error || e.message));
  } finally {
    isPushing.value = false;
  }
};

// Lifecycle
onMounted(async () => {
  if (sentimentChartRef.value) {
    sentimentChart = echarts.init(sentimentChartRef.value);
    window.addEventListener('resize', () => sentimentChart?.resize());
  }
  
  // 先获取数据库最新日期
  await Promise.all([fetchLatestDate(), fetchEvidenceStatus()]);
  
  // Init date range
  if (targetDate.value) {
    const endDate = new Date(targetDate.value);
    const startDate = new Date(endDate.getTime() - 15 * 24 * 60 * 60 * 1000);
    chartStartDate.value = startDate.toISOString().split('T')[0];
    chartEndDate.value = targetDate.value;
  }
  
  // Fetch data
  fetchStocks();
  fetchBrief();
  fetchSentimentHistory();
  fetchLimitUpTrend();
  fetchBubbleMatrix();
  fetchThemeFlow();
});

watch(targetDate, () => {
  fetchStocks();
  fetchBrief();
  fetchSentimentHistory();
  fetchBubbleMatrix();
});

onUnmounted(() => {
  sentimentChart?.dispose();
  eventSource?.close();
});
</script>

<style scoped>
.dragon-eye-page {
  display: flex;
  flex-direction: column;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.evidence-panel {
  margin: 12px 12px 0;
  padding: 12px;
  border: 1px solid #242936;
  border-radius: 8px;
  color: #D1D4DC;
  background: #111;
}

.evidence-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.evidence-heading h2,
.evidence-heading p {
  margin: 0;
}

.evidence-heading h2 {
  font-size: 13px;
}

.evidence-heading p {
  margin-top: 3px;
  color: #64748b;
  font-size: 10px;
}

.evidence-mode {
  padding: 3px 7px;
  border-radius: 999px;
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.12);
  font-size: 10px;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.evidence-grid div {
  padding: 8px;
  border-radius: 6px;
  background: #0a0a0a;
}

.evidence-grid .wide {
  grid-column: span 2;
}

.evidence-grid dt {
  color: #64748b;
  font-size: 10px;
}

.evidence-grid dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
  font-size: 12px;
}

.left-column,
.right-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

::-webkit-scrollbar-thumb:hover {
  background: #444;
}

/* Collapsed state for AI brief */
.collapsed .tv-ai-brief-content {
  display: none;
}
</style>
