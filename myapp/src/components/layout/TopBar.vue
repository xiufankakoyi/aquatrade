<template>
  <header class="h-14 bg-[#151925] border-b border-slate-800 flex items-center justify-between px-6">
    <div class="flex items-center space-x-4">
      <select
        v-model="selectedStrategyId"
        @change="handleStrategyChange"
        class="bg-slate-800 border border-slate-700 rounded-lg px-4 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        <option v-for="strategy in strategies" :key="strategy.id" :value="strategy.id">
          {{ strategy.name }}
        </option>
      </select>
      
      <select
        v-model="selectedVersion"
        @change="handleVersionChange"
        class="bg-slate-800 border border-slate-700 rounded-lg px-4 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        <option value="">选择版本</option>
        <option
          v-for="version in availableVersions"
          :key="version.id"
          :value="version.id"
        >
          {{ version.name }} - {{ version.dateRange }}
        </option>
      </select>
      
      <!-- CHANGED: 添加回测时间区间选择器 -->
      <div class="flex items-center space-x-2">
        <input
          v-model="backtestParams.startDate"
          type="date"
          class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          @change="handleDateRangeChange"
        />
        <span class="text-slate-400 text-sm">至</span>
        <input
          v-model="backtestParams.endDate"
          type="date"
          class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          @change="handleDateRangeChange"
        />
      </div>
      <div class="flex items-center space-x-2 text-xs text-slate-300">
        <button
          class="px-2 py-1 rounded bg-slate-800 border border-slate-700 hover:border-indigo-500 transition-colors"
          @click="setQuickRange('1y')"
        >
          1年
        </button>
        <button
          class="px-2 py-1 rounded bg-slate-800 border border-slate-700 hover:border-indigo-500 transition-colors"
          @click="setQuickRange('3y')"
        >
          3年
        </button>
        <button
          class="px-2 py-1 rounded bg-slate-800 border border-slate-700 hover:border-indigo-500 transition-colors"
          @click="setQuickRange('ytd')"
        >
          年初至今
        </button>
      </div>
      
      <div v-if="running" class="flex items-center space-x-2">
        <div class="flex items-center space-x-2 px-3 py-1 bg-green-500/20 border border-green-500/30 rounded-full">
          <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span class="text-xs text-green-400 font-medium">运行中</span>
        </div>
        <button
          @click="handleStopBacktest"
          class="px-3 py-1 bg-red-500/20 border border-red-500/30 rounded-full hover:bg-red-500/30 transition-colors flex items-center space-x-2"
        >
          <i class="fas fa-stop text-xs text-red-400"></i>
          <span class="text-xs text-red-400 font-medium">停止回测</span>
        </button>
      </div>
    </div>
    
    <div class="flex items-center space-x-6">
      <div class="flex items-center space-x-2 text-sm text-slate-400">
        <div :class="apiConnected ? 'bg-green-500' : 'bg-red-500'" class="w-2 h-2 rounded-full"></div>
        <span>{{ apiConnected ? 'API 连接正常' : 'API 连接异常' }}</span>
      </div>
      <div class="flex items-center space-x-3">
        <div v-if="lastUpdateTime" class="flex items-center space-x-2 text-sm text-slate-400">
          <i class="fas fa-database"></i>
          <span>数据更新: {{ lastUpdateTime }}</span>
        </div>
        <div v-if="profiles.length" class="flex items-center space-x-2 text-xs text-slate-300">
          <span class="text-slate-400">参数预设</span>
          <select
            v-model="selectedProfileId"
            class="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100 focus:border-indigo-500 focus:outline-none"
          >
            <option :value="null">不使用预设</option>
            <option
              v-for="p in profiles"
              :key="p.id"
              :value="String(p.id)"
            >
              {{ p.profile_name }}
            </option>
          </select>
        </div>
        <button
          type="button"
          @click.prevent="handleRunBacktest"
          :disabled="isLoading || !apiConnected || !selectedStrategyId"
          class="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2"
        >
          <i v-if="!isLoading" class="fas fa-play"></i>
          <i v-else class="fas fa-spinner fa-spin"></i>
          <span>{{ isLoading ? '运行中...' : '运行回测' }}</span>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useSocketIO } from '../../composables/useSocketIO';
import { useBacktestStore } from '../../store/backtestStore';
import { useDashboardStore } from '../../store/dashboardStore';
import { useHistoryStore } from '../../store/historyStore';
import { useStreamingBacktest } from '../../composables/useStreamingBacktest';
import { fetchStrategyProfiles } from '../../api/backtestApi';

const { connect } = useSocketIO();
const backtestStore = useBacktestStore();
const dashboardStore = useDashboardStore();
const historyStore = useHistoryStore();
const { start: startBacktest, isRunning, cancel: cancelBacktest } = useStreamingBacktest();

// CHANGED: 从历史记录中获取可用版本
const availableVersions = computed(() => {
  return historyStore.records.map(record => ({
    id: record.id,
    name: record.strategyName,
    dateRange: record.dateRange,
    createdAt: record.createdAt
  }));
});

const selectedVersion = ref('');
const isLoading = computed(() => backtestStore.running || isRunning.value);
const running = computed(() => backtestStore.running || isRunning.value);
const lastUpdateTime = computed(() => backtestStore.lastUpdated);
const strategies = computed(() => dashboardStore.strategies);
const selectedStrategyId = computed({
  get: () => dashboardStore.selectedStrategyId,
  set: (value) => dashboardStore.setSelectedStrategy(value || '')
});
const apiConnected = computed(() => dashboardStore.apiConnected);

// 策略参数预设（Profile）相关状态
const profiles = ref<any[]>([]);
const selectedProfileId = ref<string | null>(null);

// 回测参数
const backtestParams = ref({
  startDate: '2024-05-20',
  endDate: '2025-01-15',
  benchmarkCode: '000300'
});

const formatDate = (d: Date) => d.toISOString().split('T')[0];

function setQuickRange(type: '1y' | '3y' | 'ytd') {
  const end = new Date();
  let start = new Date(end);
  if (type === '1y') {
    start.setFullYear(end.getFullYear() - 1);
  } else if (type === '3y') {
    start.setFullYear(end.getFullYear() - 3);
  } else if (type === 'ytd') {
    start = new Date(end.getFullYear(), 0, 1);
  }
  backtestParams.value.startDate = formatDate(start);
  backtestParams.value.endDate = formatDate(end);
  handleDateRangeChange();
}

function handleStrategyChange() {
  dashboardStore.setSelectedStrategy(selectedStrategyId.value || '');
  // 策略变化时刷新该策略下的预设列表
  const strategy = dashboardStore.selectedStrategy;
  profiles.value = [];
  selectedProfileId.value = null;
  if (strategy) {
    fetchStrategyProfiles(strategy.name)
      .then((list) => {
        profiles.value = Array.isArray(list) ? list : [];
      })
      .catch((err) => {
        console.error('获取策略预设失败', err);
      });
  }
}

// CHANGED: 处理日期区间变化
function handleDateRangeChange() {
  // 日期区间变化时，可以触发一些操作，比如更新回测参数
  // 这里暂时不做任何操作，只是保存到 backtestParams
}

// CHANGED: 处理版本切换，加载对应的回测结果
function handleVersionChange() {
  if (!selectedVersion.value) return;
  
  const record = historyStore.records.find(r => r.id === selectedVersion.value);
  if (record && 'equitySeries' in record) {
    // 加载历史回测结果
    backtestStore.equitySeries = (record as any).equitySeries || [];
    backtestStore.benchmarkEquitySeries = (record as any).benchmarkEquitySeries || [];
    backtestStore.trades = (record as any).trades || [];
    backtestStore.monthlyReturns = (record as any).monthlyReturns || [];
    backtestStore.holdingPeriods = (record as any).holdingPeriods || [];
    if (record.metrics) {
      backtestStore.metrics = {
        totalReturn: record.metrics.totalReturn,
        annualizedReturn: record.metrics.annualizedReturn,
        maxDrawdown: record.metrics.maxDrawdown,
        sharpeRatio: record.metrics.sharpeRatio,
        sortinoRatio: 0,
        volatility: 0,
        winRate: 0,
        profitFactor: 0,
        tradesCount: 0,
        avgTradeReturn: 0,
        maxWinningStreak: 0,
        maxLosingStreak: 0
      };
    }
  }
}

async function handleRunBacktest() {
  if (!selectedStrategyId.value || isLoading.value || !apiConnected.value) {
    return;
  }
  
  const strategy = dashboardStore.selectedStrategy;
  if (!strategy) return;
  
  try {
    startBacktest(
      {
        strategy_name: strategy.name,
        start_date: backtestParams.value.startDate,
        end_date: backtestParams.value.endDate,
        benchmark_code: backtestParams.value.benchmarkCode || null,
        profile_id: selectedProfileId.value ? Number(selectedProfileId.value) : undefined,
      },
      {
        onError: (error) => {
          dashboardStore.error = error.message;
        },
        onCancel: () => {
          console.log('回测已取消');
        },
      }
    );
  } catch (error) {
    dashboardStore.error = error instanceof Error ? error.message : '启动回测失败';
  }
}

function handleStopBacktest() {
  if (!running.value) return;
  cancelBacktest();
}

onMounted(async () => {
  connect('http://localhost:5000');
  await dashboardStore.loadStrategies();
  // CHANGED: 加载历史记录
  historyStore.loadFromStorage();
});
</script>

