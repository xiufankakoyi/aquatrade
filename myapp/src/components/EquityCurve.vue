<template>
  <div class="equity-curve-container relative w-full h-full">
    <div ref="chartContainer" class="w-full h-full"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, markRaw } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import { useBacktestStore } from '../store/backtestStore';

const backtestStore = useBacktestStore();

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
  shadowSeries?: Array<{ date: string; equity: number }>; // NEW: Logic Sandbox
  syncXAxis?: string; // NEW: 为十字线联动提供支持
}

const props = withDefaults(defineProps<Props>(), {
  versions: () => [],
  benchmark: () => [],
  klineData: () => [],
  highlightRanges: () => [],
  tradeMarkers: () => [],
  mode: 'equity',
  scale: 'linear',
  shadowSeries: () => [],
  xAxisMin: '',
  xAxisMax: '',
  syncXAxis: ''
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
  open: number;
  high: number;
  low: number;
  close: number;
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

// 默认颜色 - 使用更专业、去饱和度的颜色
const versionColors = [
  '#2962ff', // 蓝色
  '#9c27b0', // 紫色
  '#089981', // 绿色
  '#f23645', // 红色
  '#ff9800', // 橙色
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

  chartInstance = markRaw(echarts.init(chartContainer.value));
  
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
            open: klinePoint.open,
            high: klinePoint.high,
            low: klinePoint.low,
            close: klinePoint.close,
            ma5: ma5Value,
            ma10: ma10Value,
            volume: klinePoint.volume || null
          };
        }
      }
      emit('hover', tooltipData.value);
    } else {
      // 权益曲线模式：更新 tooltipData
      const data = params.data;
      if (params.componentType === 'series' && data) {
        const equity = typeof data[2] === 'number' ? data[2] : parseFloat(data[1] || data[2] || '0') || 0;
        tooltipData.value = {
          date: data[0] || '',
          version: data[1] || params.seriesName || '',
          equity: equity,
          monthlyReturn: typeof data[3] === 'number' ? data[3] : undefined
        };
        
        // 更新 tooltip 位置
        tooltipStyle.value = {
          left: `${params.offsetX + 10}px`,
          top: `${params.offsetY + 10}px`
        };
        
        emit('hover', tooltipData.value);
      }
    }
  });

  // Watch for syncXAxis from parent
  watch(() => props.syncXAxis, (newVal) => {
    if (chartInstance && newVal && props.mode === 'equity') {
      chartInstance.dispatchAction({
        type: 'showTip',
        seriesIndex: 0,
        dataIndex: props.versions[0]?.data.findIndex(d => d.date === newVal)
      });
    }
  });

  // Handle Chart Click for Playback Sync
  chartInstance.on('click', (params: any) => {
    let date = '';
    if (params.axisValue) {
      date = typeof params.axisValue === 'string' ? params.axisValue : 
             new Date(params.axisValue).toISOString().split('T')[0];
    } else if (params.data && Array.isArray(params.data)) {
      date = params.data[0];
    }
    
    if (date && date.match(/^\d{4}-\d{2}-\d{2}/)) {
      backtestStore.setPlaybackCursor(date);
      backtestStore.togglePlaybackMode(true);
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
  // 【修复】如果图表未初始化，先初始化
  // 这解决了数据在图表初始化前到达导致的空白问题
  if (!chartInstance) {
    initChart();
    return; // initChart() will call updateChart() at the end
  }

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
        color: '#f23645',     // A股：红涨
        color0: '#089981',    // A股：绿跌
        borderColor: '#f23645',
        borderColor0: '#089981'
      },
      emphasis: {
        itemStyle: {
          borderWidth: 2
        }
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
            height: 10,
            bottom: '5',
            handleSize: '100%',
            borderColor: '#2A2E39', 
            backgroundColor: '#131722', 
            fillerColor: 'rgba(41, 98, 255, 0.1)', 
            handleStyle: {
              color: '#363A45',
              borderColor: '#2A2E39',
              borderWidth: 1
            },
            showDetail: false 
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
            height: 10,
            bottom: '5',
            borderColor: '#2A2E39', 
            backgroundColor: '#131722', 
            fillerColor: 'rgba(41, 98, 255, 0.1)', 
            handleStyle: {
              color: '#363A45',
              borderColor: '#2A2E39',
              borderWidth: 1
            },
            showDetail: false 
          }
        ];

    const option: EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1E222D',
        borderColor: '#2A2E39',
        textStyle: {
          color: '#D1D4DC'
        },
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#2A2E39',
            color: '#D1D4DC'
          },
          crossStyle: {
            color: '#787B86',
            type: 'dashed'
          }
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
          color: '#787B86'
        }
      },
      // CHANGED: 配置 grid，将图表分为两部分（K线在上，成交量在下）
      grid: hasVolume ? [
        {
          left: '3%',
          right: '4%',
          top: '10%',
          height: '60%',
          containLabel: true
        },
        {
          left: '3%',
          right: '4%',
          top: '75%',
          height: '18%',
          containLabel: true
        }
      ] : {
        left: '3%',
        right: '4%',
        top: '10%',
        bottom: '8%',
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
          axisLabel: { show: false },
          min: props.xAxisMin || undefined,
          max: props.xAxisMax || undefined
        },
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          gridIndex: 1,
          axisLine: { onZero: false },
          splitLine: { show: false },
          axisLabel: { 
            show: true,
            color: '#94a3b8',
            fontSize: 10
          },
          min: props.xAxisMin || undefined,
          max: props.xAxisMax || undefined
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
          scale: true,
          splitLine: {
            show: true,
            lineStyle: {
              color: '#2A2E39',
              type: 'dashed',
              width: 1
            }
          },
          axisLabel: { 
            color: '#787B86', 
            fontSize: 10,
            formatter: (value: number) => value.toFixed(2)
          },
          axisLine: {
            lineStyle: {
              color: '#2A2E39'
            }
          },
          gridIndex: 0
        },
        {
          type: 'value',
          name: '成交量',
          gridIndex: 1,
          scale: true,
          splitLine: {
            show: false
          },
          axisLabel: {
            color: '#787B86',
            formatter: (value: number) => formatVolume(value)
          },
          axisLine: {
            lineStyle: {
              color: '#2A2E39'
            }
          }
        }
      ] : {
        type: 'value',
        name: '股价',
        scale: true,
        axisLabel: {
          color: '#787B86',
          fontSize: 9,
          formatter: (value: number) => value.toFixed(2)
        },
        axisLine: { show: false },
        splitLine: { show: false }
      },
      dataZoom,
      series: series
    };
    chartInstance.setOption(option, { notMerge: true, lazyUpdate: false });
  } else {
    // 收益曲线模式
    const series: any[] = [];
    
    // 获取所有日期（合并版本和基准的日期）
    const allDates = new Set<string>();
    props.versions.forEach(v => v.data.forEach(d => allDates.add(d.date)));
    props.benchmark.forEach(d => allDates.add(d.date));
    const sortedDates = Array.from(allDates).sort();
    
    // Equity Curve versions
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
      
      const color = index === 0 ? '#2962ff' : versionColors[index % versionColors.length];
      
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
        yAxisIndex: 0, // CHANGED: Use the left (main) axis for benchmark alignment
        data: benchmarkData,
        smooth: true,
        lineStyle: {
          width: 1,
          type: 'dashed',
          color: '#34d399' // Green for benchmark
        },
        itemStyle: {
          color: '#34d399'
        },
        symbol: 'none'
      });
    }

    // Instruction B: Shadow Curve (Logic Sandbox)
    if (props.shadowSeries && props.shadowSeries.length > 0) {
      const shadowMap = new Map(props.shadowSeries.map(d => [d.date, d.equity]));
      const shadowData = sortedDates.map(date => {
        const equity = shadowMap.get(date);
        if (equity === undefined) return null;
        return {
          name: date,
          value: [date, equity]
        };
      }).filter(d => d !== null) as any[];

      series.push({
        name: '模拟净值 (剔除成交)',
        type: 'line',
        data: shadowData,
        smooth: true,
        lineStyle: {
          width: 1.5,
          type: 'dashed',
          color: '#cbd5e1', // Slate-300 / Grey-white
          opacity: 0.8
        },
        itemStyle: {
          color: '#cbd5e1'
        },
        symbol: 'none'
      });
    }

    const option: any = {
      axisPointer: {
        link: { xAxisIndex: 'all' },
        label: { backgroundColor: '#777' }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(19, 23, 34, 0.9)',
        borderColor: '#2a2e39',
        borderWidth: 1,
        borderRadius: 4,
        padding: [10, 15],
        textStyle: { color: '#d1d4dc', fontSize: 12 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          let dateStr = params[0].axisValue;
          if (typeof dateStr === 'number') dateStr = new Date(dateStr).toISOString().split('T')[0];
          
          let html = `<div style="font-weight:bold; margin-bottom:8px; color: #868993;">${dateStr}</div>`;
          params.forEach((item: any) => {
            const rawValue = Array.isArray(item.value) ? item.value[1] : item.value;
            const formattedValue = (typeof rawValue === 'number') ? rawValue.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 4
            }) : rawValue;

            html += `
              <div style="display:flex; justify-content:space-between; align-items:center; min-width:160px; margin: 4px 0;">
                <span style="display:flex; align-items:center; gap:6px;">${item.marker} <span style="color:#868993">${item.seriesName}</span></span>
                <span style="font-family:monospace; font-weight:bold; color: ${item.color};">${formattedValue}</span>
              </div>
            `;
          });
          return html;
        }
      },
      legend: {
        show: false
      },
      grid: {
        left: '3%',
        right: '4%',
        top: '10%',
        bottom: '10%',
        containLabel: true,
        backgroundColor: 'transparent'
      },
      xAxis: {
        type: 'time',
        boundaryGap: [0, 0],
        min: props.xAxisMin || undefined,
        max: props.xAxisMax || undefined,
        axisLine: {
          lineStyle: {
            color: 'var(--border-color)'
          }
        },
        axisLabel: {
          color: 'var(--text-secondary)',
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
      yAxis: [
        {
          type: props.scale === 'log' ? 'log' : 'value',
          scale: true,
          position: 'right', // Technical analysis often puts price on the right
          logBase: 10,
          axisLine: { show: false },
          axisLabel: { color: '#787B86', fontSize: 9 },
          splitLine: { show: false }
        },
        {
          type: 'value',
          show: false,
          scale: true,
          position: 'left'
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: 0,
          filterMode: 'filter',
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
          moveOnMouseWheel: true,
          preventDefaultMouseMove: true
        },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: 6,
          bottom: '2%',
          handleSize: '100%',
          borderColor: 'transparent',
          backgroundColor: 'rgba(30,41,59,0.1)',
          fillerColor: 'rgba(100,116,139,0.2)',
          handleStyle: {
            color: '#64748b',
            borderColor: '#475569',
            borderWidth: 1
          },
          showDetail: false
        }
      ],
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

watch(() => props.shadowSeries, () => {
  updateChart();
}, { deep: true }); // Instruction B: Ensure chart updates when shadow series changes

watch(() => props.scale, () => {
  updateChart();
});

// Sync Playback Mark
watch(() => backtestStore.playbackCursor, (newDate) => {
  if (!chartInstance || !newDate || props.mode !== 'equity') return;
  chartInstance.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: props.versions[0]?.data.findIndex(d => d.date === newDate) || 0
  });
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
  height: 100%;
}

.equity-curve-container .kline-chart {
  height: 100%;
  min-height: 25rem;
}
</style>

