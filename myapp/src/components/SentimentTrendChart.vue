<template>
  <div class="bg-[#151925] rounded-lg p-4 border border-slate-800">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center space-x-2">
        <h2 class="text-lg font-semibold text-white">情感趋势分析</h2>
        <div class="group relative">
          <i class="fas fa-info-circle text-slate-400 cursor-help"></i>
          <div class="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-slate-800 text-xs text-slate-200 px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-10">
            时间序列情感分析：横轴为时间，纵轴为情感得分，柱状图为发帖数量
          </div>
        </div>
      </div>
      <div class="text-sm text-slate-400">
        基于 SnowNLP 情感分析
      </div>
    </div>
    <div ref="chartContainer" class="h-80"></div>
    <div v-if="loading" class="flex items-center justify-center h-80 text-slate-400">
      <i class="fas fa-spinner fa-spin mr-2"></i>
      正在加载情感趋势数据...
    </div>
    <div v-if="error" class="text-red-400 text-sm mt-2">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { fetchSentimentTrend, type SentimentTrendPoint } from '../api/backtestApi';

interface Props {
  selectedSymbol?: string;
}

const props = defineProps<Props>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const loading = ref(false);
const error = ref<string | null>(null);
const data = ref<SentimentTrendPoint[]>([]);

async function loadData() {
  // 第一步：清空当前数据
  data.value = [];
  error.value = null;
  
  // 第二步：显示加载状态
  loading.value = true;
  
  try {
    // 第三步：获取新数据
    const result = await fetchSentimentTrend(props.selectedSymbol, 30);
    data.value = result;
    await nextTick();
    updateChart();
  } catch (e) {
    console.error('获取情感趋势数据失败:', e);
    error.value = '获取数据失败，请检查后端 API';
  } finally {
    loading.value = false;
  }
}

function initChart() {
  if (!chartContainer.value) return;

  if (chartContainer.value.clientWidth === 0) {
    setTimeout(initChart, 100);
    return;
  }

  if (chartInstance) {
    chartInstance.dispose();
  }

  chartInstance = echarts.init(chartContainer.value);
  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  // 提取时间、情感得分和发帖数量数据
  const timeLabels = data.value.map(item => item.date);
  // 使用接口返回的平均情感值字段 avg_sentiment
  const sentimentScores = data.value.map(item => item.avg_sentiment);
  const postCounts = data.value.map(item => item.post_count);

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: function (params: any) {
        if (!Array.isArray(params) || params.length === 0) {
          return '';
        }

        let result = `${params[0].name}<br/>`;

        params.forEach((param: any) => {
          // ECharts 在部分图表中会把 value 作为数组，这里做一下兼容处理
          const rawValue = Array.isArray(param.value)
            ? (param.value[1] ?? param.value[0])
            : param.value;

          if (param.seriesName === '情感得分') {
            const num = Number(rawValue);
            const display = Number.isFinite(num) ? num.toFixed(3) : '-';
            result += `${param.seriesName}: ${display}<br/>`;
          } else {
            const display = rawValue ?? '-';
            result += `${param.seriesName}: ${display}<br/>`;
          }
        });

        return result;
      }
    },
    legend: {
      data: ['情感得分', '发帖数量'],
      textStyle: {
        color: '#94a3b8'
      }
    },
    grid: {
      top: '15%',
      left: '5%',
      right: '5%',
      bottom: '10%',
      containLabel: true
    },
    xAxis: [
      {
        type: 'category',
        boundaryGap: false,
        data: timeLabels,
        axisLine: {
          lineStyle: {
            color: '#475569'
          }
        },
        axisLabel: {
          color: '#94a3b8'
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: '情感得分',
        position: 'left',
        min: -1,
        max: 1,
        interval: 0.5,
        axisLine: {
          lineStyle: {
            color: '#475569'
          }
        },
        axisLabel: {
          color: '#94a3b8',
          formatter: function (value: number) {
            if (value === 1) return '极度看多';
            if (value === -1) return '极度看空';
            return value;
          }
        },
        splitLine: {
          lineStyle: {
            type: 'dashed',
            color: '#475569'
          }
        }
      },
      {
        type: 'value',
        name: '发帖数量',
        position: 'right',
        axisLine: {
          lineStyle: {
            color: '#475569'
          }
        },
        axisLabel: {
          color: '#94a3b8',
          formatter: '{value}'
        }
      }
    ],
    series: [
      {
        name: '情感得分',
        type: 'line',
        yAxisIndex: 0,
        smooth: 0.3,
        data: sentimentScores,
        lineStyle: {
          width: 3,
          color: '#3b82f6'
        },
        markLine: {
          data: [{ yAxis: 0 }],
          lineStyle: {
            color: '#94a3b8',
            opacity: 0.5,
            type: 'dashed'
          }
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: 'rgba(59, 130, 246, 0.3)'
              },
              {
                offset: 1,
                color: 'rgba(59, 130, 246, 0.05)'
              }
            ]
          }
        }
      },
      {
        name: '发帖数量',
        type: 'bar',
        yAxisIndex: 1,
        data: postCounts,
        itemStyle: {
          color: 'rgba(34, 197, 94, 0.6)'
        }
      }
    ]
  };

  chartInstance.setOption(option);
}

function handleResize() {
  chartInstance?.resize();
}

onMounted(() => {
  loadData();
  nextTick(() => {
    initChart();
    window.addEventListener('resize', handleResize);
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});

watch(
  () => data.value,
  () => {
    nextTick(() => updateChart());
  },
  { deep: true }
);

watch(
  () => props.selectedSymbol,
  () => {
    if (props.selectedSymbol) {
      loadData();
    }
  }
);
</script>