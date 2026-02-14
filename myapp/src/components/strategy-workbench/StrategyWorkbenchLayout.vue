<template>
  <div class="strategy-workbench">
    <!-- 顶部工具栏 -->
    <WorkbenchToolbar
      :strategy-name="strategyName"
      :is-running="isRunning"
      :has-backtest-data="hasBacktestData"
      @run="handleRunBacktest"
      @stop="handleStopBacktest"
      @save="handleSaveStrategy"
      @reset="handleReset"
    />

    <!-- 三栏主布局 -->
    <div class="workbench-body">
      <!-- 左侧面板：代码与配置 -->
      <div
        class="left-panel"
        :style="{ width: leftPanelWidth + '%' }"
      >
        <CodeEditorPanel
          v-model="strategyCode"
          :strategy-name="strategyName"
          :is-running="isRunning"
          :backtest-config="backtestConfig"
          @update:config="updateBacktestConfig"
          @format="formatCode"
          @insert-code="insertCodeSnippet"
        />
      </div>

      <!-- 拖拽调整条 -->
      <div
        class="resize-bar vertical"
        @mousedown="startResizeLeft"
      >
        <div class="resize-handle"></div>
      </div>

      <!-- 中间面板：图表区域 -->
      <div
        class="center-panel"
        :style="{ width: centerPanelWidth + '%' }"
      >
        <ChartPanel
          :equity-series="equitySeries"
          :benchmark-series="benchmarkSeries"
          :position-series="positionSeries"
          :drawdown-series="drawdownSeries"
          :trade-frequency-data="tradeFrequencyData"
          :trades="trades"
          :is-loading="isRunning"
          :sync-date="syncDate"
          @hover="handleChartHover"
          @date-select="handleDateSelect"
        />
      </div>

      <!-- 拖拽调整条 -->
      <div
        class="resize-bar vertical"
        @mousedown="startResizeRight"
      >
        <div class="resize-handle"></div>
      </div>

      <!-- 右侧面板：数据透视 -->
      <div
        class="right-panel"
        :style="{ width: rightPanelWidth + '%' }"
      >
        <DataPanel
          :trades="trades"
          :positions="positions"
          :logs="logs"
          :errors="errors"
          :metrics="metrics"
          :selected-date="selectedDate"
          @trade-click="handleTradeClick"
          @date-change="handleDateChange"
        />
      </div>
    </div>

    <!-- 底部状态栏 -->
    <WorkbenchStatusBar
      :api-status="apiStatus"
      :last-update="lastUpdate"
      :current-date="currentBacktestDate"
      :progress="backtestProgress"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import WorkbenchToolbar from './WorkbenchToolbar.vue';
import CodeEditorPanel from './CodeEditorPanel.vue';
import ChartPanel from './ChartPanel.vue';
import DataPanel from './DataPanel.vue';
import WorkbenchStatusBar from './WorkbenchStatusBar.vue';
import { useSocketIO } from '../../composables/useSocketIO';
import type { BacktestConfig, Trade, Position, LogEntry, BacktestMetrics } from '../../types/backtest';

// ============================================
// 状态定义
// ============================================

// 面板宽度配置
const leftPanelWidth = ref(25);
const centerPanelWidth = ref(50);
const rightPanelWidth = computed(() => 100 - leftPanelWidth.value - centerPanelWidth.value);

// 拖拽状态
const isResizing = ref(false);
const resizeDirection = ref<'left' | 'right' | null>(null);

// 策略代码
const strategyCode = ref('');
const strategyName = ref('');

// 回测配置
const backtestConfig = ref<BacktestConfig>({
  initialCapital: 1000000,
  startDate: '',
  endDate: '',
  stockPool: 'all',
  benchmark: '000300.SH',
  commission: 0.0003,
  slippage: 0.001,
});

// 回测状态
const isRunning = ref(false);
const backtestProgress = ref(0);
const currentBacktestDate = ref('');

// 回测数据
const equitySeries = ref<Array<{ date: string; equity: number }>>([]);
const benchmarkSeries = ref<Array<{ date: string; equity: number }>>([]);
const positionSeries = ref<Array<{ date: string; position: number }>>([]);
const drawdownSeries = ref<Array<{ date: string; drawdown: number }>>([]);
const tradeFrequencyData = ref<Array<{ date: string; count: number }>>([]);
const trades = ref<Trade[]>([]);
const positions = ref<Position[]>([]);
const logs = ref<LogEntry[]>([]);
const errors = ref<LogEntry[]>([]);
const metrics = ref<BacktestMetrics | null>(null);

// 同步与选择状态
const syncDate = ref('');
const selectedDate = ref('');

// API 状态
const apiStatus = ref<'connected' | 'disconnected'>('disconnected');
const lastUpdate = ref('');

// Socket.IO
const { onEvent, emit } = useSocketIO();

// ============================================
// 计算属性
// ============================================

const hasBacktestData = computed(() => {
  return equitySeries.value.length > 0 && metrics.value !== null;
});

// ============================================
// 方法定义
// ============================================

// 拖拽调整面板宽度
function startResizeLeft(e: MouseEvent) {
  startResize(e, 'left');
}

function startResizeRight(e: MouseEvent) {
  startResize(e, 'right');
}

function startResize(e: MouseEvent, direction: 'left' | 'right') {
  isResizing.value = true;
  resizeDirection.value = direction;
  const startX = e.clientX;
  const startLeftWidth = leftPanelWidth.value;
  const startCenterWidth = centerPanelWidth.value;

  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing.value) return;
    
    const delta = ((e.clientX - startX) / window.innerWidth) * 100;
    
    if (direction === 'left') {
      // 调整左侧面板
      const newLeftWidth = Math.max(20, Math.min(40, startLeftWidth + delta));
      leftPanelWidth.value = newLeftWidth;
    } else {
      // 调整中间面板（影响中间和右侧）
      const newCenterWidth = Math.max(35, Math.min(60, startCenterWidth + delta));
      centerPanelWidth.value = newCenterWidth;
    }
  };

  const handleMouseUp = () => {
    isResizing.value = false;
    resizeDirection.value = null;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
}

// 回测配置更新
function updateBacktestConfig(config: Partial<BacktestConfig>) {
  backtestConfig.value = { ...backtestConfig.value, ...config };
}

// 运行回测
async function handleRunBacktest() {
  if (isRunning.value) return;
  
  isRunning.value = true;
  backtestProgress.value = 0;
  
  // 清空之前的数据
  equitySeries.value = [];
  benchmarkSeries.value = [];
  trades.value = [];
  logs.value = [];
  errors.value = [];
  
  try {
    emit('start_backtest', {
      strategy_code: strategyCode.value,
      config: backtestConfig.value,
    });
  } catch (error) {
    console.error('启动回测失败:', error);
    isRunning.value = false;
  }
}

// 停止回测
function handleStopBacktest() {
  emit('stop_backtest');
  isRunning.value = false;
}

// 保存策略
async function handleSaveStrategy() {
  try {
    emit('save_strategy', {
      name: strategyName.value,
      code: strategyCode.value,
    });
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      message: '策略已保存',
      type: 'info',
    });
  } catch (error) {
    errors.value.push({
      time: new Date().toLocaleTimeString(),
      message: `保存失败: ${error}`,
      type: 'error',
    });
  }
}

// 重置
function handleReset() {
  strategyCode.value = '';
  strategyName.value = '';
  equitySeries.value = [];
  trades.value = [];
  logs.value = [];
  errors.value = [];
}

// 代码格式化
function formatCode() {
  // 调用 Monaco Editor 的格式化功能
}

// 插入代码片段
function insertCodeSnippet(code: string) {
  strategyCode.value += code;
}

// 图表悬停事件
function handleChartHover(data: { date: string; equity?: number }) {
  syncDate.value = data.date;
}

// 日期选择
function handleDateSelect(date: string) {
  selectedDate.value = date;
  syncDate.value = date;
}

// 交易点击
function handleTradeClick(trade: Trade) {
  selectedDate.value = trade.date;
  syncDate.value = trade.date;
}

// 日期变化
function handleDateChange(date: string) {
  selectedDate.value = date;
  syncDate.value = date;
}

// ============================================
// 生命周期
// ============================================

let unsubscribeProgress: (() => void) | null = null;
let unsubscribeComplete: (() => void) | null = null;
let unsubscribeError: (() => void) | null = null;
let unsubscribeEquity: (() => void) | null = null;
let unsubscribeTrade: (() => void) | null = null;

onMounted(() => {
  // 监听回测进度
  unsubscribeProgress = onEvent('backtest_progress', (data: any) => {
    backtestProgress.value = data.progress || 0;
    currentBacktestDate.value = data.current_date || '';
  });

  // 监听净值数据流
  unsubscribeEquity = onEvent('equity_update', (data: any) => {
    if (data.equity_series) {
      equitySeries.value = data.equity_series;
    }
    if (data.benchmark_series) {
      benchmarkSeries.value = data.benchmark_series;
    }
    if (data.position_series) {
      positionSeries.value = data.position_series;
    }
    if (data.drawdown_series) {
      drawdownSeries.value = data.drawdown_series;
    }
  });

  // 监听交易信号
  unsubscribeTrade = onEvent('trade_signal', (data: any) => {
    if (data.trade) {
      trades.value.push(data.trade);
    }
  });

  // 监听回测完成
  unsubscribeComplete = onEvent('backtest_complete', (data: any) => {
    isRunning.value = false;
    metrics.value = data.metrics;
    
    // 完整数据更新
    if (data.equity_series) equitySeries.value = data.equity_series;
    if (data.benchmark_series) benchmarkSeries.value = data.benchmark_series;
    if (data.trades) trades.value = data.trades;
    
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      message: `回测完成 - 总收益: ${(data.metrics?.total_return * 100).toFixed(2)}%`,
      type: 'success',
    });
  });

  // 监听错误
  unsubscribeError = onEvent('backtest_error', (data: any) => {
    isRunning.value = false;
    errors.value.push({
      time: new Date().toLocaleTimeString(),
      message: data.message || '回测出错',
      type: 'error',
    });
  });
});

onBeforeUnmount(() => {
  unsubscribeProgress?.();
  unsubscribeComplete?.();
  unsubscribeError?.();
  unsubscribeEquity?.();
  unsubscribeTrade?.();
});
</script>

<style scoped>
.strategy-workbench {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
}

.workbench-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
}

.center-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.right-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
}

.resize-bar {
  width: 6px;
  background-color: var(--bg-primary);
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
  z-index: 10;
}

.resize-bar:hover {
  background-color: var(--accent-primary);
}

.resize-handle {
  width: 2px;
  height: 24px;
  background-color: var(--border-color);
  border-radius: 1px;
}

.resize-bar:hover .resize-handle {
  background-color: var(--text-primary);
}

/* 响应式适配 */
@media (max-width: 991px) {
  .left-panel {
    width: 30% !important;
  }
  
  .center-panel {
    width: 40% !important;
  }
  
  .right-panel {
    width: 30% !important;
  }
}

@media (max-width: 767px) {
  .workbench-body {
    flex-direction: column;
  }
  
  .left-panel,
  .center-panel,
  .right-panel {
    width: 100% !important;
    height: 33.33%;
    border: none;
    border-bottom: 1px solid var(--border-color);
  }
  
  .resize-bar.vertical {
    display: none;
  }
}
</style>
