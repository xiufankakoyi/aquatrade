<!--
  收益曲线组件
  支持多版本对比、基准线、hover 显示详细信息
-->
<template>
  <div class="equity-curve-container">
    <div ref="chartContainer" class="w-full kline-chart"></div>
    
    <!-- K线图动态图例 -->
    <div
      v-if="props.mode === 'kline' && legendData"
      class="absolute top-4 left-4 bg-black/70 backdrop-blur-sm border border-slate-700 rounded-lg px-3 py-2 z-50 pointer-events-none"
      style="min-width: 200px;"
    >
      <div class="text-xs space-y-1 text-slate-200">
        <div class="flex items-center space-x-2">
          <div class="w-3 h-0.5 bg-yellow-400"></div>
          <span class="text-slate-400">MA5:</span>
          <span class="font-mono font-semibold text-white">{{ legendData.ma5 !== null && legendData.ma5 !== undefined ? legendData.ma5.toFixed(2) : '--' }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <div class="w-3 h-0.5 bg-blue-400"></div>
          <span class="text-slate-400">MA10:</span>
          <span class="font-mono font-semibold text-white">{{ legendData.ma10 !== null && legendData.ma10 !== undefined ? legendData.ma10.toFixed(2) : '--' }}</span>
        </div>
        <div v-if="legendData.volume !== null && legendData.volume !== undefined" class="flex items-center space-x-2">
          <span class="text-slate-400">Vol:</span>
          <span class="font-mono font-semibold text-white">{{ formatVolume(legendData.volume) }}</span>
        </div>
      </div>
    </div>
    
    <!-- Tooltip 显示 -->
    <div
      v-if="tooltipData"
      :style="tooltipStyle"
      class="absolute bg-white dark:bg-slate-800 border border-gray-300 dark:border-slate-600 rounded-lg shadow-lg p-3 z-50 pointer-events-none"
    >
      <div class="text-sm space-y-1">
        <p class="font-semibold text-gray-800 dark:text-slate-100">{{ tooltipData.date }}</p>
        <p v-if="tooltipData.version" class="text-gray-600 dark:text-slate-300">
          版本：{{ tooltipData.version }}
        </p>
        <p class="text-gray-600 dark:text-slate-300">
          净值：{{ typeof tooltipData.equity === 'number' ? tooltipData.equity.toFixed(3) : (parseFloat(tooltipData.equity) || 0).toFixed(3) }}
        </p>
        <p v-if="tooltipData.monthlyReturn !== undefined && tooltipData.monthlyReturn !== null" class="text-gray-600 dark:text-slate-300">
          本月收益：{{ (typeof tooltipData.monthlyReturn === 'number' ? tooltipData.monthlyReturn : parseFloat(tooltipData.monthlyReturn) || 0) >= 0 ? '+' : '' }}{{ (typeof tooltipData.monthlyReturn === 'number' ? tooltipData.monthlyReturn : parseFloat(tooltipData.monthlyReturn) || 0).toFixed(2) }}%
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';

interface EquityCurveVersion {
  versionId: string;
  versionName: string;
  data: Array<{ date: string; equity: number }>;
}

interface TradeMarker {
  date: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  symbol?: string;
  profitLoss?: number;
  entryDate?: string;
  exitDate?: string;
  holdingDays?: number;
}

interface Props {
  versions?: EquityCurveVersion[];
  benchmark?: Array<{ date: string; equity: number }>;
  klineData?: any[];
  highlightRanges?: Array<{ start: string; end: string }>;
  tradeMarkers?: TradeMarker[];  // CHANGED: 添加交易标记
  mode?: 'equity' | 'kline';
  scale?: 'linear' | 'log';
}

const props = withDefaults(defineProps<Props>(), {
  versions: () => [],
  benchmark: () => [],
  klineData: () => [],
  highlightRanges: () => [],
  tradeMarkers: () => [],  // CHANGED: 添加交易标记默认值
  mode: 'equity',
  scale: 'linear'
});

const emit = defineEmits<{
  hover: [data: {
    date: string;
    version?: string;
    equity: number;
    monthlyReturn?: number;
  }];
}>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const tooltipData = ref<{
  date: string;
  version?: string;
  equity: number;
  monthlyReturn?: number;
} | null>(null);
const tooltipStyle = ref<{ left: string; top: string }>({ left: '0px', top: '0px' });

// K线图动态图例数据
const legendData = ref<{
  ma5: number | null;
  ma10: number | null;
  volume: number | null;
} | null>(null);

// 格式化成交量
function formatVolume(volume: number): string {
  if (volume >= 100000000) {
    return (volume / 100000000).toFixed(2) + '亿';
  } else if (volume >= 10000) {
    return (volume / 10000).toFixed(2) + '万';
  } else {
    return volume.toFixed(0);
  }
}

// 默认颜色 - 使用紫色渐变（第一个版本使用紫色）
const versionColors = [
  '#8b5cf6', // 紫色 - 主要颜色
  '#6366f1', // 靛蓝
  '#10b981', // 绿色
  '#f59e0b', // 橙色
  '#ef4444', // 红色
  '#06b6d4', // 青色
];

// 初始化图表
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
  
  // 监听鼠标移动和tooltip显示
  chartInstance.on('mousemove', (params: any) => {
    // K线模式下更新图例数据
    if (props.mode === 'kline' && props.klineData.length > 0) {
      let date = '';
      if (params.componentType === 'series' && params.data) {
        date = Array.isArray(params.data) ? params.data[0] : params.data;
      } else if (params.axisValue) {
        date = params.axisValue;
      } else if (params.componentType === 'xAxis' && params.value) {
        date = params.value;
      }
      
      if (date) {
        const klinePoint = props.klineData.find((d: any) => d.date === date);
        if (klinePoint) {
          // 计算或获取MA5和MA10
          const index = props.klineData.findIndex((d: any) => d.date === date);
          let ma5Value: number | null = null;
          let ma10Value: number | null = null;
          
          if (klinePoint.ma5 !== undefined && klinePoint.ma5 !== null && !isNaN(klinePoint.ma5)) {
            ma5Value = klinePoint.ma5;
          } else if (index >= 4) {
            const closes = props.klineData.slice(index - 4, index + 1).map((d: any) => d.close);
            ma5Value = closes.reduce((a, b) => a + b, 0) / 5;
          }
          
          if (klinePoint.ma10 !== undefined && klinePoint.ma10 !== null && !isNaN(klinePoint.ma10)) {
            ma10Value = klinePoint.ma10;
          } else if (index >= 9) {
            const closes = props.klineData.slice(index - 9, index + 1).map((d: any) => d.close);
            ma10Value = closes.reduce((a, b) => a + b, 0) / 10;
          }
          
          legendData.value = {
            ma5: ma5Value,
            ma10: ma10Value,
            volume: klinePoint.volume || null
          };
        }
      }
    }
    
    if (params.componentType === 'series') {
      const data = params.data;
      const seriesName = params.seriesName || '';
      
      // CHANGED: 区分不同的 series 类型
      // 如果是交易标记（买入/卖出），不显示 tooltip（使用 ECharts 内置 tooltip）
      if (seriesName === '买入' || seriesName === '卖出' || seriesName === '买入点' || seriesName === '卖出点') {
        tooltipData.value = null;
        return;
      }
      
      // 如果是 K 线图，从 K 线数据中提取信息
      if (props.mode === 'kline' && props.klineData.length > 0) {
        const date = data[0] || '';
        const klinePoint = props.klineData.find((d: any) => d.date === date);
        if (klinePoint) {
          tooltipData.value = {
            date: date,
            equity: typeof klinePoint.close === 'number' ? klinePoint.close : parseFloat(klinePoint.close) || 0,
            monthlyReturn: undefined
          };
        } else {
          // 如果找不到对应的 K 线点，尝试从 data 中提取
          const equity = typeof data[2] === 'number' ? data[2] : (typeof data[1] === 'number' ? data[1] : parseFloat(data[1] || data[2] || '0') || 0);
          tooltipData.value = {
            date: data[0] || '',
            equity: equity,
            monthlyReturn: undefined
          };
        }
      } else {
        // 权益曲线模式
        const equity = typeof data[2] === 'number' ? data[2] : parseFloat(data[2] || '0') || 0;
      tooltipData.value = {
        date: data[0] || '',
        version: data[1] || '',
          equity: equity,
          monthlyReturn: typeof data[3] === 'number' ? data[3] : (data[3] !== undefined ? parseFloat(data[3]) : undefined)
      };
      }
      
      // 更新 tooltip 位置
      tooltipStyle.value = {
        left: `${params.offsetX + 10}px`,
        top: `${params.offsetY + 10}px`
      };
      
      emit('hover', tooltipData.value);
    }
  });

  // 监听tooltip显示事件（用于更新图例）
  chartInstance.on('showTip', (params: any) => {
    if (props.mode === 'kline' && props.klineData.length > 0 && params && params.data) {
      const date = Array.isArray(params.data) ? params.data[0] : params.data;
      if (date) {
        const klinePoint = props.klineData.find((d: any) => d.date === date);
        if (klinePoint) {
          const index = props.klineData.findIndex((d: any) => d.date === date);
          let ma5Value: number | null = null;
          let ma10Value: number | null = null;
          
          if (klinePoint.ma5 !== undefined && klinePoint.ma5 !== null && !isNaN(klinePoint.ma5)) {
            ma5Value = klinePoint.ma5;
          } else if (index >= 4) {
            const closes = props.klineData.slice(index - 4, index + 1).map((d: any) => d.close);
            ma5Value = closes.reduce((a, b) => a + b, 0) / 5;
          }
          
          if (klinePoint.ma10 !== undefined && klinePoint.ma10 !== null && !isNaN(klinePoint.ma10)) {
            ma10Value = klinePoint.ma10;
          } else if (index >= 9) {
            const closes = props.klineData.slice(index - 9, index + 1).map((d: any) => d.close);
            ma10Value = closes.reduce((a, b) => a + b, 0) / 10;
          }
          
          legendData.value = {
            ma5: ma5Value,
            ma10: ma10Value,
            volume: klinePoint.volume || null
          };
        }
      }
    }
  });

  chartInstance.on('mouseout', () => {
    tooltipData.value = null;
    if (props.mode === 'kline') {
      legendData.value = null;
    }
  });

  updateChart();
}

// 更新图表
function updateChart() {
  if (!chartInstance) return;

  if (props.mode === 'kline' && props.klineData.length > 0) {
    // K 线模式
    const dates = props.klineData.map((d: any) => d.date);
    
    // CHANGED: 检查是否有成交量数据
    const volumeData = props.klineData.map((d: any) => d.volume || 0);
    const hasVolume = volumeData.some(v => v > 0);
    
    // CHANGED: 使用数据库中的 MA5 和 MA10（如果可用），否则计算
    const ma5: number[] = [];
    const ma10: number[] = [];
    const closes: number[] = [];
    
    // 先收集所有收盘价
    for (let i = 0; i < props.klineData.length; i++) {
      closes.push(props.klineData[i].close);
    }
    
    // 计算或使用数据库中的 MA5 和 MA10
    for (let i = 0; i < props.klineData.length; i++) {
      const klinePoint = props.klineData[i];
      
      // 优先使用数据库中的 MA5
      if (klinePoint.ma5 !== undefined && klinePoint.ma5 !== null && !isNaN(klinePoint.ma5)) {
        ma5.push(klinePoint.ma5);
      } else {
        // 如果数据库中没有，计算 MA5（需要至少5个数据点）
        if (i >= 4) {
          const sum5 = closes.slice(i - 4, i + 1).reduce((a, b) => a + b, 0);
          ma5.push(sum5 / 5);
        } else {
          ma5.push(null as any);
        }
      }
      
      // 优先使用数据库中的 MA10
      if (klinePoint.ma10 !== undefined && klinePoint.ma10 !== null && !isNaN(klinePoint.ma10)) {
        ma10.push(klinePoint.ma10);
      } else {
        // 如果数据库中没有，计算 MA10（需要至少10个数据点）
        if (i >= 9) {
          const sum10 = closes.slice(i - 9, i + 1).reduce((a, b) => a + b, 0);
          ma10.push(sum10 / 10);
        } else {
          ma10.push(null as any);
        }
      }
    }
    
    const klineSeries = {
      name: 'K线',
      type: 'candlestick' as const,
      data: props.klineData.map((d: any) => [d.open, d.close, d.low, d.high]),
      itemStyle: {
        color: '#ef4444',
        color0: '#22c55e',
        borderColor: '#b91c1c',
        borderColor0: '#065f46'
      },
      xAxisIndex: hasVolume ? 0 : 0,
      yAxisIndex: hasVolume ? 0 : 0
    };

    // CHANGED: 添加买入/卖出标记和移动平均线
    const series: any[] = [klineSeries];
    
    // CHANGED: 添加五日线
    series.push({
      name: 'MA5',
      type: 'line',
      data: dates.map((date, index) => [date, ma5[index]]).filter(d => d[1] !== null),
      smooth: true,
      lineStyle: {
        width: 2,
        color: '#fbbf24'  // 黄色
      },
      itemStyle: {
        color: '#fbbf24'
      },
      symbol: 'none',
      xAxisIndex: hasVolume ? 0 : 0,
      yAxisIndex: hasVolume ? 0 : 0
    });
    
    // CHANGED: 添加十日线
    series.push({
      name: 'MA10',
      type: 'line',
      data: dates.map((date, index) => [date, ma10[index]]).filter(d => d[1] !== null),
      smooth: true,
      lineStyle: {
        width: 2,
        color: '#3b82f6'  // 蓝色
      },
      itemStyle: {
        color: '#3b82f6'
      },
      symbol: 'none',
      xAxisIndex: hasVolume ? 0 : 0,
      yAxisIndex: hasVolume ? 0 : 0
    });
    
    // 买入标记 - 放在最低价下方，不遮挡K线
    const buyMarkers = props.tradeMarkers.filter(m => m.action === 'buy');
    if (buyMarkers.length > 0) {
      const buyData = dates.map((date, index) => {
        const marker = buyMarkers.find(m => m.date === date);
        if (marker) {
          const klinePoint = props.klineData[index];
          if (klinePoint) {
            // 放在最低价下方，留出一定间距（约2%的价格范围）
            const priceRange = klinePoint.high - klinePoint.low;
            const offset = priceRange * 0.02 || (klinePoint.close * 0.01);
            const markerY = klinePoint.low - offset;
            return [date, markerY, marker, klinePoint.low];
          }
          return [date, marker.price * 0.98, marker, marker.price];
        }
        return null;
      }).filter(d => d !== null);

      series.push({
        name: '买入点',
        type: 'scatter',
        data: buyData,
        symbol: 'circle',
        symbolSize: 12, // 缩小图标，不遮挡K线
        itemStyle: {
          color: '#ef4444',  // 红色（A股：红买）
          borderColor: '#ffffff',
          borderWidth: 1.5
        },
        xAxisIndex: hasVolume ? 0 : 0,
        yAxisIndex: hasVolume ? 0 : 0,
        label: {
          show: true,
          position: 'inside',
          formatter: 'B',
          color: '#ffffff',
          fontSize: 10,
          fontWeight: 'bold',
          offset: [0, 0]
        },
        tooltip: {
          formatter: (params: any) => {
            const marker = params.data[2] as TradeMarker;
            const holdingDays = marker.holdingDays || (marker.exitDate && marker.entryDate 
              ? Math.floor((new Date(marker.exitDate).getTime() - new Date(marker.entryDate).getTime()) / (1000 * 60 * 60 * 24))
              : null);
            let html = `<div style="padding: 10px; background: rgba(0, 0, 0, 0.85); border-radius: 6px; border: 1px solid #ef4444;">
              <div style="font-weight: bold; font-size: 14px; color: #ef4444; margin-bottom: 8px;">🔴 买入</div>
              <div style="display: flex; flex-direction: column; gap: 4px; font-size: 12px;">
                <div><span style="color: #94a3b8;">日期:</span> <span style="color: #fff; font-weight: 500;">${marker.date}</span></div>
                <div><span style="color: #94a3b8;">价格:</span> <span style="color: #fff; font-weight: 500;">￥${marker.price.toFixed(2)}</span></div>
                <div><span style="color: #94a3b8;">数量:</span> <span style="color: #fff; font-weight: 500;">${marker.quantity.toLocaleString()} 股</span></div>
                <div><span style="color: #94a3b8;">金额:</span> <span style="color: #fff; font-weight: 500;">￥${(marker.price * marker.quantity).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>`;
            if (marker.symbol) {
              html += `<div><span style="color: #94a3b8;">标的:</span> <span style="color: #fff; font-weight: 500;">${marker.symbol}</span></div>`;
            }
            if (holdingDays !== null) {
              html += `<div><span style="color: #94a3b8;">持有周期:</span> <span style="color: #fff; font-weight: 500;">${holdingDays} 天</span></div>`;
            }
            if (marker.profitLoss !== undefined && marker.profitLoss !== null) {
              const returnRate = marker.profitLoss / (marker.price * marker.quantity) * 100;
              const profitColor = marker.profitLoss >= 0 ? '#22c55e' : '#ef4444';
              html += `<div><span style="color: #94a3b8;">收益率:</span> <span style="color: ${profitColor}; font-weight: 500;">${returnRate >= 0 ? '+' : ''}${returnRate.toFixed(2)}%</span></div>`;
              html += `<div><span style="color: #94a3b8;">盈亏:</span> <span style="color: ${profitColor}; font-weight: 500;">${marker.profitLoss >= 0 ? '+' : ''}￥${marker.profitLoss.toFixed(2)}</span></div>`;
            }
            html += `</div></div>`;
            return html;
          }
        }
      });
      
      // 添加买入点指向K线的细线
      buyData.forEach((d: any) => {
        const [date, markerY, , low] = d;
        series.push({
          name: '买入线',
          type: 'line',
          data: [
            [date, markerY],
            [date, low]
          ],
          lineStyle: {
            color: '#ef4444',
            width: 1,
            type: 'solid',
            opacity: 0.6
          },
          symbol: 'none',
          silent: true,
          xAxisIndex: hasVolume ? 0 : 0,
          yAxisIndex: hasVolume ? 0 : 0,
          tooltip: { show: false }
        });
      });
    }

    // 卖出标记 - 放在最高价上方，不遮挡K线
    // 过滤条件：只有当 exitDate 存在且 price > 0 时才生成卖出标记
    const sellMarkers = props.tradeMarkers.filter(m => 
      m.action === 'sell' && 
      m.exitDate && 
      m.price > 0
    );
    if (sellMarkers.length > 0) {
      const sellData = dates.map((date, index) => {
        const marker = sellMarkers.find(m => m.date === date);
        if (marker && marker.exitDate && marker.price > 0) {
          const klinePoint = props.klineData[index];
          if (klinePoint) {
            // 放在最高价上方，留出一定间距（约2%的价格范围）
            const priceRange = klinePoint.high - klinePoint.low;
            const offset = priceRange * 0.02 || (klinePoint.close * 0.01);
            const markerY = klinePoint.high + offset;
            return [date, markerY, marker, klinePoint.high];
          }
          return [date, marker.price * 1.02, marker, marker.price];
        }
        return null;
      }).filter(d => d !== null);

      series.push({
        name: '卖出点',
        type: 'scatter',
        data: sellData,
        symbol: 'circle',
        symbolSize: 12, // 缩小图标，不遮挡K线
        itemStyle: {
          color: '#22c55e',  // 绿色（A股：绿卖）
          borderColor: '#ffffff',
          borderWidth: 1.5
        },
        xAxisIndex: hasVolume ? 0 : 0,
        yAxisIndex: hasVolume ? 0 : 0,
        label: {
          show: true,
          position: 'inside',
          formatter: 'S',
          color: '#ffffff',
          fontSize: 10,
          fontWeight: 'bold',
          offset: [0, 0]
        },
        tooltip: {
          formatter: (params: any) => {
            const marker = params.data[2] as TradeMarker;
            const holdingDays = marker.holdingDays || (marker.exitDate && marker.entryDate 
              ? Math.floor((new Date(marker.exitDate).getTime() - new Date(marker.entryDate).getTime()) / (1000 * 60 * 60 * 24))
              : null);
            let html = `<div style="padding: 10px; background: rgba(0, 0, 0, 0.85); border-radius: 6px; border: 1px solid #22c55e;">
              <div style="font-weight: bold; font-size: 14px; color: #22c55e; margin-bottom: 8px;">🟢 卖出</div>
              <div style="display: flex; flex-direction: column; gap: 4px; font-size: 12px;">
                <div><span style="color: #94a3b8;">日期:</span> <span style="color: #fff; font-weight: 500;">${marker.date}</span></div>
                <div><span style="color: #94a3b8;">价格:</span> <span style="color: #fff; font-weight: 500;">￥${marker.price.toFixed(2)}</span></div>
                <div><span style="color: #94a3b8;">数量:</span> <span style="color: #fff; font-weight: 500;">${marker.quantity.toLocaleString()} 股</span></div>
                <div><span style="color: #94a3b8;">金额:</span> <span style="color: #fff; font-weight: 500;">￥${(marker.price * marker.quantity).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>`;
            if (marker.symbol) {
              html += `<div><span style="color: #94a3b8;">标的:</span> <span style="color: #fff; font-weight: 500;">${marker.symbol}</span></div>`;
            }
            if (holdingDays !== null) {
              html += `<div><span style="color: #94a3b8;">持有周期:</span> <span style="color: #fff; font-weight: 500;">${holdingDays} 天</span></div>`;
            }
            if (marker.profitLoss !== undefined && marker.profitLoss !== null) {
              const returnRate = marker.profitLoss / (marker.price * marker.quantity) * 100;
              const profitColor = marker.profitLoss >= 0 ? '#22c55e' : '#ef4444';
              html += `<div><span style="color: #94a3b8;">收益率:</span> <span style="color: ${profitColor}; font-weight: 500;">${returnRate >= 0 ? '+' : ''}${returnRate.toFixed(2)}%</span></div>`;
              html += `<div><span style="color: #94a3b8;">盈亏:</span> <span style="color: ${profitColor}; font-weight: 500;">${marker.profitLoss >= 0 ? '+' : ''}￥${marker.profitLoss.toFixed(2)}</span></div>`;
            }
            html += `</div></div>`;
            return html;
          }
        }
      });
      
      // 添加卖出点指向K线的细线
      sellData.forEach((d: any) => {
        const [date, markerY, , high] = d;
        series.push({
          name: '卖出线',
          type: 'line',
          data: [
            [date, markerY],
            [date, high]
          ],
          lineStyle: {
            color: '#22c55e',
            width: 1,
            type: 'solid',
            opacity: 0.6
          },
          symbol: 'none',
          silent: true,
          xAxisIndex: hasVolume ? 0 : 0,
          yAxisIndex: hasVolume ? 0 : 0,
          tooltip: { show: false }
        });
      });
    }

    // CHANGED: 添加成交量柱状图
    if (hasVolume) {
      series.push({
        name: '成交量',
        type: 'bar',
        data: volumeData,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (params: any) => {
            const index = params.dataIndex;
            const klinePoint = props.klineData[index];
            // 涨红跌绿
            return klinePoint && klinePoint.close >= klinePoint.open ? '#ef4444' : '#22c55e';
          }
        },
        barWidth: '60%'
      });
    }

    const dataZoom: EChartsOption['dataZoom'] = hasVolume
      ? [
          {
            type: 'inside',
            xAxisIndex: [0, 1],
            filterMode: 'filter' as const,
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
            preventDefaultMouseMove: true
          },
          {
            type: 'slider',
            xAxisIndex: [0, 1],
            height: 6, // 变细
            bottom: '2%',
            handleSize: '100%',
            borderColor: 'transparent', // 透明边框
            backgroundColor: 'rgba(30,41,59,0.1)', // 更透明
            fillerColor: 'rgba(100,116,139,0.2)', // 选中区域颜色
            handleStyle: {
              color: '#64748b', // 深灰色滑块
              borderColor: '#475569',
              borderWidth: 1
            },
            showDetail: false // 隐藏详情
          }
        ]
      : [
          {
            type: 'inside',
            xAxisIndex: 0,
            filterMode: 'none' as const,
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
            preventDefaultMouseMove: true
          },
          {
            type: 'slider',
            xAxisIndex: 0,
            height: 6, // 变细
            bottom: '2%',
            borderColor: 'transparent', // 透明边框
            backgroundColor: 'rgba(30,41,59,0.1)', // 更透明
            fillerColor: 'rgba(100,116,139,0.2)', // 选中区域颜色
            handleStyle: {
              color: '#64748b', // 深灰色滑块
              borderColor: '#475569',
              borderWidth: 1
            },
            showDetail: false // 隐藏详情
          }
        ];

    const option: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        }
      },
      legend: {
        data: ['K线', 'MA5', 'MA10', '买入点', '卖出点', ...(hasVolume ? ['成交量'] : [])].filter((_name, index) => {
          // 只显示存在的系列（不显示指向线）
          if (index === 0) return true;  // K线
          if (index === 1) return ma5.some(v => v !== null);  // MA5
          if (index === 2) return ma10.some(v => v !== null);  // MA10
          if (index === 3) return buyMarkers.length > 0;  // 买入点
          if (index === 4) return sellMarkers.length > 0;  // 卖出点
          if (index === 5) return hasVolume;  // 成交量
          return false;
        }),
        top: 10,
        textStyle: {
          color: '#94a3b8'
        }
      },
      // CHANGED: 配置 grid，将图表分为两部分（K线在上，成交量在下）
      grid: hasVolume ? [
        {
          left: '3%',
          right: '4%',
          top: '15%',
          height: '60%',
          containLabel: true
        },
        {
          left: '3%',
          right: '4%',
          top: '80%',
          height: '15%',
          containLabel: true
        }
      ] : {
        left: '3%',
        right: '4%',
        top: '15%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: hasVolume ? [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          gridIndex: 0,
          axisLine: { onZero: false },
          splitLine: { show: false },
          // CHANGED: 移除 min/max 限制，允许显示完整的时间范围
          // min: 'dataMin',
          // max: 'dataMax',
          // CHANGED: 隐藏K线图x轴标签，只显示成交量区域的
          axisLabel: { show: false }
        },
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          gridIndex: 1,
          axisLine: { onZero: false },
          splitLine: { show: false },
          // CHANGED: 移除 min/max 限制，允许显示完整的时间范围
          // min: 'dataMin',
          // max: 'dataMax',
          // CHANGED: 只在成交量区域显示x轴标签
          axisLabel: { 
            show: true,
            color: '#94a3b8',
            fontSize: 10
          }
        }
      ] : {
        type: 'category',
        data: dates,
        boundaryGap: false
        // CHANGED: 移除 min/max 限制，允许显示完整的时间范围
      },
      yAxis: hasVolume ? [
        {
          type: 'value',
          name: '股价',
          scale: true, // 防止被0值拉平
          splitLine: {
            show: true,
            lineStyle: {
              color: 'rgba(148, 163, 184, 0.1)', // 极淡灰色虚线
              type: 'dashed',
              width: 1
            }
          },
          axisLabel: {
            color: '#94a3b8',
            formatter: (value: number) => {
              // 股价Y轴：保留2位小数，不用'w'格式化
              return value.toFixed(2);
            }
          },
          axisLine: {
            lineStyle: {
              color: '#334155'
            }
          },
          gridIndex: 0
        },
        {
          type: 'value',
          name: '成交量',
          gridIndex: 1,
          scale: true, // 修复成交量缩放问题
          splitLine: {
            show: false
          },
          // CHANGED: 隐藏成交量y轴
          show: false
        }
      ] : {
        type: 'value',
        name: '股价',
        // CHANGED: 自适应缩放
        scale: true,
        axisLabel: {
          color: '#94a3b8',
          formatter: (value: number) => {
            // 股价Y轴：保留2位小数，不用'w'格式化
            return value.toFixed(2);
          }
        },
        axisLine: {
          lineStyle: {
            color: '#334155'
          }
        },
        // CHANGED: 添加极淡灰色虚线网格线
        splitLine: {
          show: true,
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.1)', // 极淡灰色虚线
            type: 'dashed',
            width: 1
          }
        }
      },
      dataZoom,
      series: series
    };
    chartInstance.setOption(option);
  } else {
    // 收益曲线模式
    const series: any[] = [];
    
    // 获取所有日期（合并版本和基准的日期）
    const allDates = new Set<string>();
    props.versions.forEach(v => v.data.forEach(d => allDates.add(d.date)));
    props.benchmark.forEach(d => allDates.add(d.date));
    const sortedDates = Array.from(allDates).sort();
    
    // 添加版本数据
    props.versions.forEach((version, index) => {
      const equityMap = new Map(version.data.map(d => [d.date, d.equity]));
      const data = sortedDates.map(date => {
        const equity = equityMap.get(date);
        if (equity === undefined) return null;
        return {
          name: date,
          value: [date, equity]
        };
      }).filter(d => d !== null) as any[];
      
      const color = index === 0 ? '#8b5cf6' : versionColors[index % versionColors.length];
      
      series.push({
        name: version.versionName,
        type: 'line',
        data: data,
        smooth: true,
        lineStyle: {
          width: 2,
          color: color
        },
        itemStyle: {
          color: color
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [{
              offset: 0,
              color: color + 'CC' // 更不透明的起始颜色（80%透明度）
            }, {
              offset: 0.5,
              color: color + '66' // 中间颜色（40%透明度）
            }, {
              offset: 1,
              color: color + '00' // 完全透明
            }]
          }
        },
        symbol: 'none',
        emphasis: {
          focus: 'series'
        }
      });
    });
    
    // 添加基准数据
    if (props.benchmark.length > 0) {
      const benchmarkMap = new Map(props.benchmark.map(d => [d.date, d.equity]));
      const benchmarkData = sortedDates.map(date => {
        const equity = benchmarkMap.get(date);
        if (equity === undefined) return null;
        return {
          name: date,
          value: [date, equity]
        };
      }).filter(d => d !== null) as any[];
      
      series.push({
        name: '基准',
        type: 'line',
        data: benchmarkData,
        smooth: true,
        lineStyle: {
          width: 1,
          type: 'dashed',
          color: '#94a3b8'
        },
        itemStyle: {
          color: '#94a3b8'
        },
        symbol: 'none'
      });
    }

    const option: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(20, 20, 20, 0.9)',
        borderColor: '#333',
        textStyle: { color: '#eee' },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          
          // 处理时间标题：将时间戳或日期字符串转换为 YYYY-MM-DD 格式
          let dateStr = '';
          const dateValue = params[0].axisValue;
          
          if (typeof dateValue === 'string') {
            // 如果已经是日期字符串，直接使用
            if (dateValue.match(/^\d{4}-\d{2}-\d{2}/)) {
              dateStr = dateValue;
            } else {
              // 尝试解析日期字符串
              const dateObj = new Date(dateValue);
              if (!isNaN(dateObj.getTime())) {
                dateStr = dateObj.toLocaleDateString('zh-CN', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit'
                }).replace(/\//g, '-');
              } else {
                dateStr = dateValue;
              }
            }
          } else if (typeof dateValue === 'number') {
            // 如果是时间戳
            const dateObj = new Date(dateValue);
            dateStr = dateObj.toLocaleDateString('zh-CN', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit'
            }).replace(/\//g, '-');
          } else {
            dateStr = String(dateValue);
          }

          let html = `<div style="font-weight:bold; margin-bottom:5px;">${dateStr}</div>`;

          // 遍历每条线（当前回测、基准）
          params.forEach((item: any) => {
            // 处理数值：保留2位小数，加千分位
            const rawValue = Array.isArray(item.value) ? item.value[1] : item.value;
            const numValue = parseFloat(rawValue) || 0;
            const formattedValue = numValue.toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2
            });

            html += `
              <div style="display:flex; justify-content:space-between; align-items:center; min-width:150px;">
                <span style="margin-right:10px;">${item.marker} ${item.seriesName}</span>
                <span style="font-family:monospace; font-weight:bold;">${formattedValue}</span>
              </div>
            `;
          });

          return html;
        }
      },
      legend: {
        data: [...props.versions.map(v => v.versionName), ...(props.benchmark.length > 0 ? ['基准'] : [])],
        top: 10,
        textStyle: {
          color: '#94a3b8'
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
        backgroundColor: 'transparent'
      },
      xAxis: {
        type: 'time',
        boundaryGap: [0, 0],
        axisLine: {
          lineStyle: {
            color: '#334155'
          }
        },
        axisLabel: {
          color: '#888',
          formatter: {
            year: '{yyyy}',
            month: '{MM}-{dd}',
            day: '{MM}-{dd}'
          },
          hideOverlap: true
        },
        splitLine: {
          show: false
        }
      },
      yAxis: {
        type: props.scale === 'log' ? 'log' : 'value',
        name: '净值',
        scale: true, // 自动缩放，脱离 0 值束缚
        logBase: 10,
        axisLine: {
          lineStyle: {
            color: '#334155'
          }
        },
        axisLabel: {
          color: '#94a3b8',
          formatter: (value: number) => {
            // 格式化Y轴数字：800000 -> 80w, 1000000 -> 100w
            return (value / 10000).toFixed(0) + 'w';
          }
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#333',
            type: 'dashed'
          }
        }
      },
      series: series
    };

    chartInstance.setOption(option, { notMerge: true, lazyUpdate: false });
  }
}

watch(() => props.versions, () => {
  updateChart();
}, { deep: true });

watch(() => props.benchmark, () => {
  updateChart();
}, { deep: true });

watch(() => props.klineData, () => {
  updateChart();
}, { deep: true });

watch(() => props.tradeMarkers, () => {
  updateChart();
}, { deep: true });

watch(() => props.scale, () => {
  updateChart();
});

// 窗口大小变化时调整图表
function handleResize() {
  chartInstance?.resize();
}

onMounted(() => {
  nextTick(() => {
    initChart();
    if (chartInstance) {
      chartInstance.resize();
    }
    window.addEventListener('resize', handleResize);
  });
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});
</script>

<style scoped>
.equity-curve-container {
  position: relative;
  width: 100%;
}

.equity-curve-container .kline-chart {
  height: 25rem; /* 30% taller than previous 16rem (h-64) */
}
</style>

