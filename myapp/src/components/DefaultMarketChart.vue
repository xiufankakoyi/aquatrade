<template>
  <div class="w-full h-full flex flex-col">
    <div class="tv-pane-header-flat">
      <span class="tv-pane-label">沪深300指数 (000300.SH)</span>
      <span v-if="isLoading" class="text-[10px] text-[#2962ff]">
        <i class="fas fa-spinner fa-spin mr-1"></i>加载中...
      </span>
      <span v-else-if="loadError" class="text-[10px] text-[#f23645]">加载失败</span>
      <span v-else class="text-[10px] text-[#787b86]">{{ dateRangeText }}</span>
    </div>
    <div ref="chartContainer" class="flex-1 min-h-0 relative">
      <!-- 加载中状态 -->
      <div v-if="isLoading && !chart" class="absolute inset-0 flex items-center justify-center">
        <div class="text-center text-[#787b86]">
          <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
          <p class="text-xs">正在加载市场数据...</p>
        </div>
      </div>
      
      <!-- 错误状态 -->
      <div v-if="loadError && !chart" class="absolute inset-0 flex items-center justify-center">
        <div class="text-center text-[#787b86]">
          <i class="fas fa-exclamation-circle text-2xl mb-2 text-[#f23645]"></i>
          <p class="text-xs mb-2">数据加载失败</p>
          <button 
            @click="retryFetch"
            class="px-3 py-1 bg-[#2a2e39] hover:bg-[#363a45] text-white text-xs rounded transition-colors"
          >
            <i class="fas fa-redo mr-1"></i>重试
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import * as echarts from 'echarts';

const chartContainer = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;
const klineData = ref<any[]>([]);
const isLoading = ref(false);
const loadError = ref(false);
const retryCount = ref(0);
const MAX_RETRIES = 5;
const RETRY_DELAY = 2000;

const API_BASE_URL = 'http://localhost:5000/api';

// 计算显示的日期范围（使用数据的最新日期）
const dateRangeText = computed(() => {
  if (klineData.value.length === 0) return '';
  const firstDate = klineData.value[0].date;
  const lastDate = klineData.value[klineData.value.length - 1].date;
  return `${firstDate} ~ ${lastDate}`;
});

async function fetchHS300Kline(): Promise<any[] | null> {
  isLoading.value = true;
  loadError.value = false;
  
  try {
    // 查询大范围数据，后端会返回实际有的数据
    const endDate = new Date('2025-12-31'); // 使用未来日期确保获取最新数据
    const startDate = new Date('2000-01-01'); // 使用较早日期确保获取历史数据
    
    const start = startDate.toISOString().split('T')[0];
    const end = endDate.toISOString().split('T')[0];
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    
    const response = await fetch(
      `${API_BASE_URL}/kline?symbol=000300&start=${start}&end=${end}`,
      { signal: controller.signal }
    );
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success && data.data && data.data.length > 0) {
      retryCount.value = 0;
      // 只取最近一年的数据用于显示
      const allData = data.data;
      const oneYearAgo = new Date();
      oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
      const filteredData = allData.filter((item: any) => new Date(item.date) >= oneYearAgo);
      return filteredData.length > 0 ? filteredData : allData.slice(-252); // 如果没有过滤结果，取最后252个交易日
    }
    
    return null;
  } catch (error) {
    console.warn('获取沪深300数据失败:', error);
    return null;
  } finally {
    isLoading.value = false;
  }
}

async function retryFetch() {
  if (retryCount.value >= MAX_RETRIES) {
    loadError.value = true;
    return;
  }
  
  retryCount.value++;
  console.log(`[DefaultMarketChart] 第 ${retryCount.value} 次重试...`);
  
  const data = await fetchHS300Kline();
  
  if (data && data.length > 0) {
    klineData.value = data;
    initChart(data);
    window.addEventListener('resize', handleResize);
  } else {
    setTimeout(retryFetch, RETRY_DELAY);
  }
}

function initChart(data: any[]) {
  if (!chartContainer.value) return;
  
  if (chart) {
    chart.dispose();
  }
  
  chart = echarts.init(chartContainer.value, 'dark');
  
  const dates = data.map(item => item.date);
  const values = data.map(item => [
    item.open,
    item.close,
    item.low,
    item.high
  ]);
  
  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    grid: {
      left: '3%',
      right: '3%',
      top: '10%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { 
        color: '#787b86',
        fontSize: 10,
        formatter: (value: string) => {
          const date = new Date(value);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        }
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisLabel: { 
        color: '#787b86',
        fontSize: 10
      },
      splitLine: { 
        lineStyle: { 
          color: '#2a2e39',
          type: 'dashed'
        } 
      }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 20,
        bottom: 10,
        borderColor: '#2a2e39',
        fillerColor: 'rgba(41, 98, 255, 0.2)',
        handleStyle: {
          color: '#2962ff'
        },
        textStyle: {
          color: '#787b86'
        }
      }
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e222d',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11 },
      formatter: (params: any) => {
        const data = params[0];
        const values = data.data;
        return `
          <div style="font-weight:bold;margin-bottom:4px;">${data.name}</div>
          <div>开: ${values[1]}</div>
          <div>收: ${values[2]}</div>
          <div>低: ${values[3]}</div>
          <div>高: ${values[4]}</div>
        `;
      }
    },
    series: [
      {
        type: 'candlestick',
        data: values,
        itemStyle: {
          color: '#f23645',
          color0: '#089981',
          borderColor: '#f23645',
          borderColor0: '#089981'
        }
      },
      {
        type: 'line',
        data: calculateMA(20, values),
        smooth: true,
        showSymbol: false,
        lineStyle: {
          color: '#2962ff',
          width: 1,
          opacity: 0.8
        }
      }
    ]
  };
  
  chart.setOption(option);
}

function calculateMA(dayCount: number, data: number[][]) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < dayCount - 1) {
      result.push('-');
      continue;
    }
    let sum = 0;
    for (let j = 0; j < dayCount; j++) {
      sum += data[i - j][1];
    }
    result.push((sum / dayCount).toFixed(2));
  }
  return result;
}

function handleResize() {
  chart?.resize();
}

onMounted(async () => {
  const data = await fetchHS300Kline();
  
  if (data && data.length > 0) {
    klineData.value = data;
    initChart(data);
    window.addEventListener('resize', handleResize);
  } else {
    setTimeout(retryFetch, RETRY_DELAY);
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chart?.dispose();
});
</script>
