<template>
  <div class="bg-[#151925] rounded-lg p-4 border border-slate-800">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center space-x-2">
        <h2 class="text-lg font-semibold text-white">热度 vs 情感分析</h2>
        <div class="group relative">
          <i class="fas fa-info-circle text-slate-400 cursor-help"></i>
          <div class="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-slate-800 text-xs text-slate-200 px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-10">
            多维数据关系分析：横轴为讨论热度，纵轴为情感倾向
          </div>
        </div>
      </div>
      <div class="text-sm text-slate-400">
        基于 K-Means 聚类分析
      </div>
    </div>
    <div ref="chartContainer" class="h-80"></div>
    <div v-if="loading" class="flex items-center justify-center h-80 text-slate-400">
      <i class="fas fa-spinner fa-spin mr-2"></i>
      正在加载散点图数据...
    </div>
    <div v-if="error" class="text-red-400 text-sm mt-2">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { fetchScatterData, type ScatterDataPoint } from '../api/backtestApi';

interface Props {
  selectedSymbol?: string;
}

const props = defineProps<Props>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const loading = ref(false);
const error = ref<string | null>(null);
const data = ref<ScatterDataPoint[]>([]);

async function loadData() {
  // 第一步：清空当前数据
  data.value = [];
  error.value = null;
  
  // 第二步：显示加载状态
  loading.value = true;
  
  try {
    // 第三步：获取新数据
    const result = await fetchScatterData(props.selectedSymbol);
    data.value = result;
    await nextTick();
    updateChart();
  } catch (e) {
    console.error('获取散点图数据失败:', e);
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

  // 确保 data.value 是数组类型
  const points = Array.isArray(data.value) ? data.value : [];
  
  // 按颜色分组数据
  const groupedData: Record<string, ScatterDataPoint[]> = {};
  points.forEach(point => {
    if (!groupedData[point.color]) {
      groupedData[point.color] = [];
    }
    groupedData[point.color].push(point);
  });

  const series = Object.entries(groupedData).map(([color, points]) => ({
    name: color,
    type: 'scatter',
    data: points.map(p => [p.x, p.y, p.size]),
    symbolSize: (data: number[]) => Math.sqrt(data[2]) * 2,
    itemStyle: {
      color: color
    },
    emphasis: {
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2
      }
    }
  }));

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const data = params.data;
        const point = data;
        return `${params.seriesName}<br/>
                股票代码: ${data.name || 'N/A'}<br/>
                讨论热度: ${point[0]}<br/>
                情感倾向: ${point[1].toFixed(3)}<br/>
                数据量: ${point[2]}`;
      }
    },
    legend: {
      data: Object.keys(groupedData),
      textStyle: {
        color: '#94a3b8'
      }
    },
    grid: {
      left: '3%',
      right: '7%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '讨论热度 (发帖数)',
      nameLocation: 'middle',
      nameGap: 30,
      scale: true, // 不从0开始，适合热度数据
      axisLine: {
        lineStyle: {
          color: '#475569'
        }
      },
      axisLabel: {
        color: '#94a3b8'
      },
      splitLine: {
        show: false // 隐藏网格线，减少视觉干扰
      }
    },
    yAxis: {
      type: 'value',
      name: '情感倾向',
      nameLocation: 'middle',
      nameGap: 50,
      min: -1,  // 【关键】锁死 Y 轴范围
      max: 1,
      axisLine: {
        lineStyle: {
          color: '#475569'
        },
        onZero: true // 轴线在 0 刻度上
      },
      axisLabel: {
        color: '#94a3b8',
        formatter: '{value}'
      },
      splitLine: {
        show: false
      }
    },
    series: series,
    // 【关键】加上十字辅助线
    markLine: {
      silent: true,
      symbol: 'none',
      label: { show: false },
      lineStyle: { type: 'solid', color: '#666' },
      data: [
        { yAxis: 0 }, // 情感分界线
        // 可选择添加平均热度线
        // { xAxis: averageHeat } 
      ]
    }
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

// 当选择的股票符号改变时，重新加载数据
watch(
  () => props.selectedSymbol,
  () => {
    if (props.selectedSymbol) {
      loadData();
    }
  }
);
</script>