<template>
  <div class="p-6 space-y-6">
    <!-- Header Section -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-white mb-1">股票舆情分析 Dashboard</h1>
        <p class="text-sm text-slate-400">
          基于东方财富股吧爬虫数据，采用多维度分析方法和机器学习算法进行情感分析和主题建模
        </p>
      </div>
      <div class="flex items-center space-x-4">
        <div class="text-right">
          <div class="text-sm text-slate-400">当前分析数据量</div>
          <div class="text-xl font-semibold text-blue-400">{{ totalDataCount }} 条</div>
        </div>
        <div class="flex items-center space-x-3">
          <label class="flex items-center space-x-2 text-sm text-slate-300">
            <span>展示条数</span>
            <input
              type="number"
              min="10"
              max="200"
              step="10"
              v-model.number="limit"
              @change="handleLimitChange"
              class="w-20 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </label>
          <button
            class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm text-slate-100 border border-slate-700 flex items-center space-x-2"
            @click="reload"
          >
            <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
            <span>刷新</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Dashboard Layout -->
    <div class="grid grid-cols-12 gap-6">
      <!-- Top Row: Sentiment Trend and LDA Topics -->
      <div class="col-span-12 lg:col-span-6">
        <SentimentTrendChart :selected-symbol="selectedItem?.symbol" />
      </div>
      <div class="col-span-12 lg:col-span-6">
        <LdaTopicChart :selected-symbol="selectedItem?.symbol" />
      </div>
      
      <!-- Second Row: Scatter Plot and Stock List -->
      <div class="col-span-12 lg:col-span-8">
        <ScatterPlotChart :selected-symbol="selectedItem?.symbol" />
      </div>
      <div class="col-span-12 lg:col-span-4">
        <div class="bg-[#151925] rounded-lg p-4 border border-slate-800 flex flex-col">
          <h2 class="text-lg font-semibold text-white mb-3">股票舆情列表</h2>
          <div class="flex-1 overflow-auto max-h-80">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-slate-400 border-b border-slate-800">
                  <th class="px-2 py-2 text-left">代码</th>
                  <th class="px-2 py-2 text-left">名称</th>
                  <th class="px-2 py-2 text-right">帖子数</th>
                  <th class="px-2 py-2 text-right">情绪</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in items.slice(0, 15)"
                  :key="item.symbol"
                  class="border-b border-slate-800/60 hover:bg-slate-800/40 cursor-pointer"
                  :class="{ 'bg-slate-800/60': selectedItem && selectedItem.symbol === item.symbol }"
                  @click="handleRowClick(item)"
                >
                  <td class="px-2 py-2 text-slate-100 whitespace-nowrap">{{ item.stockCode }}</td>
                  <td class="px-2 py-2 text-slate-100 truncate max-w-[6rem]">{{ item.stockName || '-' }}</td>
                  <td class="px-2 py-2 text-right text-slate-100">{{ item.totalPosts }}</td>
                  <td class="px-2 py-2 text-right" :class="sentimentClass(item.sentimentScore)">
                    {{ item.sentimentScore.toFixed(2) }}
                  </td>
                </tr>
                <tr v-if="!loading && !items.length">
                  <td colspan="4" class="px-2 py-4 text-center text-slate-500">
                    暂无数据
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="loading" class="mt-3 text-xs text-slate-400 flex items-center space-x-2">
            <i class="fas fa-spinner fa-spin"></i>
            <span>正在加载数据...</span>
          </div>
        </div>
      </div>
      
      <!-- Third Row: Word Cloud -->
      <div class="col-span-12">
        <div class="bg-[#151925] rounded-lg p-4 border border-slate-800">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2">
              <h2 class="text-lg font-semibold text-white">关键词词云分析</h2>
              <div class="group relative">
                <i class="fas fa-info-circle text-slate-400 cursor-help"></i>
                <div class="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-slate-800 text-xs text-slate-200 px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-10">
                  基于 TF-IDF 算法提取的关键词，绿色表示正面词汇，红色表示负面词汇
                </div>
              </div>
            </div>
            <div class="text-sm text-slate-400">
              <span v-if="selectedItem">
                {{ selectedItem.stockCode }} {{ selectedItem.stockName || '-' }} | 帖子
                {{ selectedItem.totalPosts }} | 基于 TF-IDF 算法
              </span>
              <span v-else>
                点击左侧列表中的股票，查看对应的关键词词云
              </span>
            </div>
          </div>
          <div ref="wordCloudContainer" class="h-80"></div>
          <div v-if="wordCloudLoading" class="flex items-center justify-center h-80 text-slate-400">
            <i class="fas fa-spinner fa-spin mr-2"></i>
            正在加载词云数据...
          </div>
          <div v-if="wordCloudError" class="text-red-400 text-sm mt-2">
            {{ wordCloudError }}
          </div>
          <div
            v-if="!wordCloudLoading && !wordCloudError && selectedItem && (!wordCloudData || !wordCloudData.words.length)"
            class="text-slate-400 text-sm mt-2"
          >
            该股票暂无可用的帖子标题或关键词。
          </div>
        </div>
      </div>
    </div>

    <!-- Algorithm Explanations -->
    <div class="bg-[#151925] rounded-lg p-4 border border-slate-800">
      <h3 class="text-lg font-semibold text-white mb-3">算法说明</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        <div class="flex items-start space-x-3">
          <i class="fas fa-chart-line text-blue-400 mt-1"></i>
          <div>
            <div class="text-white font-medium">情感趋势分析</div>
            <div class="text-slate-400">基于 SnowNLP 情感分析算法，对股票相关帖文进行情感倾向分析</div>
          </div>
        </div>
        <div class="flex items-start space-x-3">
          <i class="fas fa-layer-group text-green-400 mt-1"></i>
          <div>
            <div class="text-white font-medium">LDA 主题建模</div>
            <div class="text-slate-400">使用 Latent Dirichlet Allocation 算法进行主题聚类分析</div>
          </div>
        </div>
        <div class="flex items-start space-x-3">
          <i class="fas fa-project-diagram text-purple-400 mt-1"></i>
          <div>
            <div class="text-white font-medium">K-Means 聚类</div>
            <div class="text-slate-400">采用 K-Means 聚类算法对股票进行多维度特征分析</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="p-3 rounded bg-red-900/40 border border-red-500/40 text-sm text-red-200">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({
  name: 'StockSentimentPage'
});

import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import 'echarts-wordcloud';
import {
  fetchStockSentiment,
  fetchStockWordCloud,
  type StockSentimentItem,
  type StockWordCloudResponse
} from '../api/backtestApi';

// 导入新的图表组件
import SentimentTrendChart from '../components/SentimentTrendChart.vue';
import LdaTopicChart from '../components/LdaTopicChart.vue';
import ScatterPlotChart from '../components/ScatterPlotChart.vue';

const items = ref<StockSentimentItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const limit = ref(50);

const chartContainer = ref<HTMLDivElement | null>(null);
const wordCloudContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const selectedItem = ref<StockSentimentItem | null>(null);
const wordCloudData = ref<StockWordCloudResponse | null>(null);
const wordCloudLoading = ref(false);
const wordCloudError = ref<string | null>(null);

// 计算总数据量
const totalDataCount = ref(0);

async function loadData() {
  // 第一步：清空当前数据
  items.value = [];
  totalDataCount.value = 0;
  
  // 第二步：显示加载状态
  loading.value = true;
  error.value = null;
  
  try {
    // 第三步：获取新数据
    const response = await fetchStockSentiment(limit.value || 50);
    items.value = Array.isArray(response) ? response : [];
    
    // 计算总数据量
    totalDataCount.value = items.value.reduce((sum, item) => {
      return sum + (item.totalPosts || 0);
    }, 0);
    
    // 重置选择状态
    selectedItem.value = null;
    wordCloudData.value = null;
    wordCloudError.value = null;
  } catch (e) {
    console.error(e);
    error.value = '获取股票风评数据失败，请检查后端 /api/stock_sentiment 是否可用。';
  } finally {
    loading.value = false;
  }
}

function handleLimitChange() {
  if (!limit.value || limit.value < 10) {
    limit.value = 10;
  }
  if (limit.value > 200) {
    limit.value = 200;
  }
  reload();
}

function reload() {
  loadData().then(() => {
    nextTick(() => {
      updateWordCloudChart();
    });
  });
}

async function handleRowClick(item: StockSentimentItem) {
  selectedItem.value = item;
  await loadWordCloud();
}

function sentimentClass(score: number): string {
  if (score > 0.3) return 'text-green-300';
  if (score > 0.05) return 'text-green-200';
  if (score < -0.3) return 'text-red-300';
  if (score < -0.05) return 'text-red-200';
  return 'text-slate-200';
}

function initWordCloudChart() {
  if (!wordCloudContainer.value) return;

  if (wordCloudContainer.value.clientWidth === 0) {
    setTimeout(initWordCloudChart, 100);
    return;
  }

  if (chartInstance) {
    chartInstance.dispose();
  }

  chartInstance = echarts.init(wordCloudContainer.value);
  updateWordCloudChart();
}

function updateWordCloudChart() {
  if (!chartInstance) return;

  const data = wordCloudData.value;
  if (!data || !data.words || !data.words.length) {
    chartInstance.clear();
    return;
  }

  const seriesData = data.words.map((w) => {
    const pos = w.positiveWeight ?? 0;
    const neg = w.negativeWeight ?? 0;
    let color = '#e5e7eb';
    if (pos > neg * 1.2) {
      color = '#22c55e';
    } else if (neg > pos * 1.2) {
      color = '#ef4444';
    }

    return {
      name: w.word,
      value: w.weight,
      textStyle: {
        color
      },
      positiveWeight: pos,
      negativeWeight: neg,
      count: w.count
    };
  });

  const option: any = {
    tooltip: {
      show: true,
      formatter: (params: any) => {
        const d = params.data as any;
        const lines = [
          `词语：${d.name}`,
          `出现次数：${d.count ?? '-'}`,
          `权重：${(d.value ?? 0).toFixed(2)}`,
          `正向权重：${(d.positiveWeight ?? 0).toFixed(2)}`,
          `负向权重：${(d.negativeWeight ?? 0).toFixed(2)}`
        ];
        return lines.join('<br/>');
      }
    },
    series: [
      {
        type: 'wordCloud',
        gridSize: 8,
        sizeRange: [12, 48],
        rotationRange: [-45, 45],
        shape: 'circle',
        width: '100%',
        height: '100%',
        textStyle: {
          fontFamily:
            'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        },
        data: seriesData
      }
    ],
    backgroundColor: 'transparent'
  };

  chartInstance.setOption(option);
}

async function loadWordCloud() {
  if (!selectedItem.value) return;
  
  // 第一步：清空当前数据
  wordCloudData.value = null;
  wordCloudError.value = null;
  
  // 第二步：显示加载状态
  wordCloudLoading.value = true;
  
  try {
    // 第三步：获取新数据
    const data = await fetchStockWordCloud(selectedItem.value.symbol);
    wordCloudData.value = data;
    await nextTick();
    updateWordCloudChart();
  } catch (e) {
    console.error(e);
    wordCloudError.value = '获取词云数据失败，请检查后端 /api/stock_sentiment_words 是否可用。';
  } finally {
    wordCloudLoading.value = false;
  }
}

function handleResize() {
  chartInstance?.resize();
}

onMounted(async () => {
  await loadData();
  nextTick(() => {
    initWordCloudChart();
    window.addEventListener('resize', handleResize);
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});

watch(
  () => wordCloudData.value,
  () => {
    nextTick(() => updateWordCloudChart());
  },
  { deep: true }
);
</script>
