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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import WorkbenchToolbar from '../strategy-workbench/WorkbenchToolbar.vue';
import CodeEditorPanel from '../strategy-workbench/CodeEditorPanel.vue';
import ChartPanel from '../strategy-workbench/ChartPanel.vue';
import DataPanel from '../strategy-workbench/DataPanel.vue';
import WorkbenchStatusBar from '../strategy-workbench/WorkbenchStatusBar.vue';
import { useSocketIO } from '../../composables/useSocketIO';
import type { BacktestConfig, Trade, Position, LogEntry, BacktestMetrics } from '../../types/backtest';

defineOptions({
  name: 'StrategyWorkbench'
});

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

// 默认策略代码模板
const defaultStrategyCode = `from core.strategies.strategy_framework import StrategyBase

class MyStrategy(StrategyBase):
    """
    我的策略 - 简单均线突破策略
    """
    strategy_name = "MyStrategy"
    
    def __init__(self, name=None):
        super().__init__(name)
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        策略逻辑实现
        
        参数:
            current_date: 当前日期
            stock_pool_today: DataFrame，当日股票数据
            data_query: 数据查询对象
        
        返回:
            Dict[str, str]: {股票代码: 'buy'/'sell'/'hold'}
        """
        signals = {}
        
        for _, row in stock_pool_today.iterrows():
            code = row.get('stock_code') or row.get('symbol_code')
            if not code:
                continue
            
            close = row.get('close', 0)
            ma20 = row.get('ma20', 0)
            
            # 简单均线突破逻辑
            if close > ma20 * 1.02:
                signals[code] = 'buy'
            elif close < ma20 * 0.98:
                signals[code] = 'sell'
            else:
                signals[code] = 'hold'
        
        return signals`;

// 策略代码
const strategyCode = ref(defaultStrategyCode);
const strategyName = ref('MyStrategy');

// 回测配置
const backtestConfig = ref<BacktestConfig>({
  startDate: '2024-01-01',
  endDate: '2024-12-31',
  initialCapital: 100000,
  positionSize: 0.1,
  maxPositions: 10,
  commission: 0.0003,
  slippage: 0.001
});

// 回测状态
const isRunning = ref(false);
const backtestProgress = ref(0);
const currentBacktestDate = ref<string>('');

// 回测数据
const equitySeries = ref<{ date: string; value: number }[]>([]);
const benchmarkSeries = ref<{ date: string; value: number }[]>([]);
const positionSeries = ref<{ date: string; value: number }[]>([]);
const drawdownSeries = ref<{ date: string; value: number }[]>([]);
const tradeFrequencyData = ref<{ date: string; count: number }[]>([]);
const trades = ref<Trade[]>([]);
const positions = ref<Position[]>([]);
const logs = ref<LogEntry[]>([]);
const errors = ref<string[]>([]);
const metrics = ref<BacktestMetrics | null>(null);

// 同步状态
const syncDate = ref<string>('');
const selectedDate = ref<string>('');

// API 状态
const apiStatus = ref<'connected' | 'disconnected' | 'error'>('disconnected');
const lastUpdate = ref<Date | null>(null);

// Socket.io
const { isConnected, connect, disconnect, onEvent, emitEvent } = useSocketIO();

// 计算属性
const hasBacktestData = computed(() => {
  return equitySeries.value.length > 0 || trades.value.length > 0;
});

// ============================================
// 面板拖拽调整
// ============================================

const startResizeLeft = (e: MouseEvent) => {
  isResizing.value = true;
  resizeDirection.value = 'left';
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
};

const startResizeRight = (e: MouseEvent) => {
  isResizing.value = true;
  resizeDirection.value = 'right';
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
};

const handleResize = (e: MouseEvent) => {
  if (!isResizing.value) return;
  
  const containerWidth = window.innerWidth;
  const x = e.clientX;
  const percentage = (x / containerWidth) * 100;
  
  if (resizeDirection.value === 'left') {
    leftPanelWidth.value = Math.max(15, Math.min(40, percentage));
    centerPanelWidth.value = 100 - leftPanelWidth.value - rightPanelWidth.value;
  } else if (resizeDirection.value === 'right') {
    const rightPct = 100 - percentage;
    rightPanelWidth.value = Math.max(15, Math.min(40, rightPct));
    centerPanelWidth.value = 100 - leftPanelWidth.value - rightPanelWidth.value;
  }
};

const stopResize = () => {
  isResizing.value = false;
  resizeDirection.value = null;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
};

// ============================================
// 回测控制
// ============================================

const handleRunBacktest = async () => {
  if (isRunning.value) return;

  isRunning.value = true;
  backtestProgress.value = 0;
  errors.value = [];

  try {
    emitEvent('run_backtest', {
      code: strategyCode.value,
      config: backtestConfig.value
    });
  } catch (err) {
    console.error('启动回测失败:', err);
    errors.value.push('启动回测失败: ' + String(err));
    isRunning.value = false;
  }
};

const handleStopBacktest = () => {
  emitEvent('stop_backtest');
  isRunning.value = false;
};

const handleSaveStrategy = () => {
  // 保存策略代码到本地或服务器
  const blob = new Blob([strategyCode.value], { type: 'text/python' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${strategyName.value || 'strategy'}.py`;
  a.click();
  URL.revokeObjectURL(url);
};

const handleReset = () => {
  strategyCode.value = defaultStrategyCode;
  strategyName.value = 'MyStrategy';
  equitySeries.value = [];
  benchmarkSeries.value = [];
  positionSeries.value = [];
  drawdownSeries.value = [];
  tradeFrequencyData.value = [];
  trades.value = [];
  positions.value = [];
  logs.value = [];
  errors.value = [];
  metrics.value = null;
};

// ============================================
// 代码编辑
// ============================================

const formatCode = () => {
  // 简单的代码格式化（缩进处理）
  const lines = strategyCode.value.split('\n');
  let indent = 0;
  const formatted = lines.map(line => {
    const trimmed = line.trim();
    if (trimmed.endsWith(':')) {
      const result = '  '.repeat(indent) + trimmed;
      indent++;
      return result;
    } else if (trimmed.startsWith('return') || trimmed.startsWith('pass')) {
      indent = Math.max(0, indent - 1);
      return '  '.repeat(indent) + trimmed;
    }
    return '  '.repeat(indent) + trimmed;
  });
  strategyCode.value = formatted.join('\n');
};

const insertCodeSnippet = (snippet: string) => {
  const textarea = document.querySelector('.code-editor textarea') as HTMLTextAreaElement;
  if (textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const value = strategyCode.value;
    strategyCode.value = value.substring(0, start) + snippet + value.substring(end);
  }
};

const updateBacktestConfig = (config: Partial<BacktestConfig>) => {
  backtestConfig.value = { ...backtestConfig.value, ...config };
};

// ============================================
// 图表交互
// ============================================

const handleChartHover = (date: string) => {
  syncDate.value = date;
};

const handleDateSelect = (date: string) => {
  selectedDate.value = date;
};

const handleDateChange = (date: string) => {
  selectedDate.value = date;
  syncDate.value = date;
};

const handleTradeClick = (trade: Trade) => {
  selectedDate.value = trade.date;
  syncDate.value = trade.date;
};

// ============================================
// Socket.io 事件监听
// ============================================

onMounted(() => {
  connect(import.meta.env.VITE_API_URL || 'http://localhost:5000');

  onEvent('connect', () => {
    apiStatus.value = 'connected';
    lastUpdate.value = new Date();
  });

  onEvent('disconnect', () => {
    apiStatus.value = 'disconnected';
  });

  onEvent('backtest_progress', (data: { progress: number; currentDate: string }) => {
    backtestProgress.value = data.progress;
    currentBacktestDate.value = data.currentDate;
  });

  onEvent('backtest_result', (data: any) => {
    isRunning.value = false;

    if (data.equity) {
      equitySeries.value = data.equity;
    }
    if (data.benchmark) {
      benchmarkSeries.value = data.benchmark;
    }
    if (data.positions) {
      positionSeries.value = data.positions;
    }
    if (data.drawdown) {
      drawdownSeries.value = data.drawdown;
    }
    if (data.tradeFrequency) {
      tradeFrequencyData.value = data.tradeFrequency;
    }
    if (data.trades) {
      trades.value = data.trades;
    }
    if (data.metrics) {
      metrics.value = data.metrics;
    }

    lastUpdate.value = new Date();
  });

  onEvent('backtest_error', (data: { error: string }) => {
    errors.value.push(data.error);
    isRunning.value = false;
  });

  onEvent('backtest_log', (data: { level: string; message: string; timestamp: string }) => {
    logs.value.push({
      level: data.level,
      message: data.message,
      timestamp: data.timestamp
    });
  });
});

onBeforeUnmount(() => {
  disconnect();
  
  // 清理事件监听
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
});

// 监听连接状态
watch(() => isConnected(), (connected) => {
  apiStatus.value = connected ? 'connected' : 'disconnected';
});
</script>

<style scoped>
.strategy-workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0A0A0A;
  overflow: hidden;
}

.workbench-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel,
.center-panel,
.right-panel {
  height: 100%;
  overflow: hidden;
}

.left-panel {
  min-width: 200px;
}

.center-panel {
  min-width: 300px;
}

.right-panel {
  min-width: 200px;
}

/* 拖拽调整条 */
.resize-bar {
  width: 4px;
  background: #1a1a1a;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.resize-bar:hover {
  background: #2962ff;
}

.resize-handle {
  width: 2px;
  height: 30px;
  background: #3a3e49;
  border-radius: 1px;
}

.resize-bar:hover .resize-handle {
  background: #fff;
}
</style>
