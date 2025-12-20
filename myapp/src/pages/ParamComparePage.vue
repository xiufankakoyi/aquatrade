<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import EquityCurve from '../components/EquityCurve.vue';

const API_BASE_URL = 'http://localhost:5000/api';

// 策略相关
const availableStrategies = ref<Array<{ id: string; name: string }>>([]);
const selectedStrategy = ref('');
const isLoadingStrategies = ref(false);
const isLoadingParams = ref(false);

// 参数相关
const strategyParams = ref<Array<{
  key: string;
  label: string;
  type: string;
  min: number;
  max: number;
  step: number;
  default: number;
  group?: string;
  group_label?: string;
}>>([]);

// 原参数值（默认值）
const originalParams = ref<Record<string, number | string | boolean>>({});
// 新参数值（用户修改）
const newParams = ref<Record<string, number | string | boolean>>({});

// 日期范围
const startDate = ref('');
const endDate = ref('');

// 回测状态
const isBacktesting = ref(false);
const backtestProgress = ref(0);

// 回测结果
interface BacktestMetrics {
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  tradesCount: number;
  calmarRatio?: number;
  sortinoRatio?: number;
  volatility?: number;
}

interface BacktestResultData {
  metrics: BacktestMetrics;
  equityCurve: Array<{ date: string; equity: number }>;
  benchmarkCurve?: Array<{ date: string; equity: number }>;
  trades?: Array<any>;
}

const originalResult = ref<BacktestResultData | null>(null);
const newResult = ref<BacktestResultData | null>(null);

// 消息
const errorMessage = ref('');
const successMessage = ref('');

// 当前回测的是哪一组参数
const currentBacktestType = ref<'original' | 'new' | null>(null);

// 中断控制器（用于停止正在进行的回测请求）
const originalAbortController = ref<AbortController | null>(null);
const newAbortController = ref<AbortController | null>(null);

// 工具函数
const showError = (msg: string) => {
  errorMessage.value = msg;
  setTimeout(() => errorMessage.value = '', 8000);
};

const showSuccess = (msg: string) => {
  successMessage.value = msg;
  setTimeout(() => successMessage.value = '', 5000);
};

// 获取策略列表
const fetchStrategies = async () => {
  isLoadingStrategies.value = true;
  try {
    const response = await fetch(`${API_BASE_URL}/strategies`);
    const data = await response.json();
    if (data.success && Array.isArray(data.data)) {
      availableStrategies.value = data.data.map((s: any) => ({
        id: String(s.id).trim(),
        name: String(s.name).trim()
      }));
      if (availableStrategies.value.length > 0 && !selectedStrategy.value) {
        const first = availableStrategies.value[0];
        if (first && typeof first.id === 'string') {
          selectedStrategy.value = first.id;
        }
      }
    }
  } catch (e) {
    showError('获取策略列表失败');
  } finally {
    isLoadingStrategies.value = false;
  }
};

// 获取策略参数
const fetchStrategyParams = async () => {
  if (!selectedStrategy.value) return;
  isLoadingParams.value = true;
  try {
    const response = await fetch(`${API_BASE_URL}/strategies/${encodeURIComponent(selectedStrategy.value)}/params`);
    if (response.ok) {
      const params = await response.json();
      if (Array.isArray(params)) {
        strategyParams.value = params;
        // 初始化原参数和新参数
        originalParams.value = {};
        newParams.value = {};
        params.forEach((p: any) => {
          const defaultVal = p.default ?? p.min ?? 0;
          originalParams.value[p.key] = defaultVal;
          newParams.value[p.key] = defaultVal;
        });
      }
    }
  } catch (e) {
    showError('获取策略参数失败');
  } finally {
    isLoadingParams.value = false;
  }
};

// 监听策略变化
watch(selectedStrategy, () => {
  fetchStrategyParams();
  // 清空之前的结果
  originalResult.value = null;
  newResult.value = null;
});

// 重置新参数为原参数
const resetNewParams = () => {
  newParams.value = { ...originalParams.value };
};

// 检查参数是否有变化
const hasParamChanges = computed(() => {
  return strategyParams.value.some(p => originalParams.value[p.key] !== newParams.value[p.key]);
});

// 获取变化的参数列表
const changedParams = computed(() => {
  return strategyParams.value.filter(p => originalParams.value[p.key] !== newParams.value[p.key]);
});

// 按分组组织参数
const paramGroups = computed(() => {
  const groups = new Map<string, { name: string; displayName: string; params: any[] }>();
  const DEFAULT_GROUP = 'default';
  
  groups.set(DEFAULT_GROUP, { name: DEFAULT_GROUP, displayName: '基本参数', params: [] });
  
  strategyParams.value.forEach(param => {
    const groupName = param.group || DEFAULT_GROUP;
    const displayName = param.group_label || (groupName === DEFAULT_GROUP ? '基本参数' : groupName);
    
    if (!groups.has(groupName)) {
      groups.set(groupName, { name: groupName, displayName, params: [] });
    }
    groups.get(groupName)!.params.push(param);
  });
  
  return Array.from(groups.values()).sort((a, b) => {
    if (a.name === DEFAULT_GROUP) return -1;
    if (b.name === DEFAULT_GROUP) return 1;
    return a.displayName.localeCompare(b.displayName);
  });
});

// 运行单次回测（HTTP 调用 /api/run_backtest）
const runBacktest = async (type: 'original' | 'new') => {
  if (!selectedStrategy.value || !startDate.value || !endDate.value) {
    showError('请选择策略和日期范围');
    return;
  }

  currentBacktestType.value = type;
  backtestProgress.value = type === 'original' ? 20 : 60;
  const params = type === 'original' ? originalParams.value : newParams.value;

  // 为本次请求创建 AbortController，方便外部中断
  const controller = new AbortController();
  const signal = controller.signal;
  if (type === 'original') {
    originalAbortController.value = controller;
  } else {
    newAbortController.value = controller;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/run_backtest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      signal,
      body: JSON.stringify({
        strategy_name: selectedStrategy.value,
        start_date: startDate.value,
        end_date: endDate.value,
        params
      })
    });

    const json = await response.json();
    if (!response.ok || !json?.success) {
      const msg = json?.error || `回测失败: HTTP ${response.status}`;
      throw new Error(msg);
    }

    const data = json.data || {};
    const m = data.metrics || {};
    let equityCurvePoints: Array<{ date: string; equity: number }> = [];
    let benchmarkCurvePoints: Array<{ date: string; equity: number }> = [];

    if (Array.isArray(data.equityCurve) && data.equityCurve.length > 0) {
      // 兼容旧格式：直接提供 equityCurve 数组
      equityCurvePoints = data.equityCurve
        .map((p: { date: string; equity: number }) => ({
          date: p.date,
          equity: typeof p.equity === 'number' ? p.equity : Number(p.equity ?? 0),
        }))
        .filter((p: { date: string; equity: number }) => !!p.date);
    } else if (
      data.equityCurveData &&
      Array.isArray(data.equityCurveData.dates) &&
      Array.isArray(data.equityCurveData.strategyReturns)
    ) {
      // 新格式：从 equityCurveData 中解析策略曲线
      equityCurvePoints = data.equityCurveData.dates.map((date: string, idx: number) => ({
        date,
        equity: Number(data.equityCurveData.strategyReturns[idx] ?? 0),
      }));

      // 如果有基准曲线，则一并解析
      if (Array.isArray(data.equityCurveData.benchmarkReturns)) {
        benchmarkCurvePoints = data.equityCurveData.dates.map((date: string, idx: number) => ({
          date,
          equity: Number(data.equityCurveData.benchmarkReturns[idx] ?? 0),
        }));
      }
    }

    const actualStart: string | undefined = data.actualStartDate;
    const actualEnd: string | undefined = data.actualEndDate;
    if (actualStart && actualEnd && (actualStart !== startDate.value || actualEnd !== endDate.value)) {
      startDate.value = actualStart;
      endDate.value = actualEnd;
      showSuccess(`回测日期已自动调整为 ${actualStart} ~ ${actualEnd}（数据库可用范围）`);
    }

    const normalizedResult: BacktestResultData = {
      metrics: {
        totalReturn: m.totalReturn ?? m.total_return ?? 0,
        annualizedReturn: m.annualizedReturn ?? m.annualized_return ?? 0,
        sharpeRatio: m.sharpeRatio ?? m.sharpe_ratio ?? 0,
        maxDrawdown: m.maxDrawdown ?? m.max_drawdown ?? 0,
        winRate: m.winRate ?? m.win_rate ?? 0,
        profitFactor: m.profitFactor ?? m.profit_factor ?? 0,
        tradesCount: m.tradesCount ?? m.trades_count ?? 0,
        calmarRatio: m.calmarRatio ?? m.calmar_ratio,
        sortinoRatio: m.sortinoRatio ?? m.sortino_ratio,
        volatility: m.volatility,
      },
      equityCurve: equityCurvePoints,
      benchmarkCurve: benchmarkCurvePoints.length ? benchmarkCurvePoints : undefined,
      trades: data.trades ?? []
    };

    if (type === 'original') {
      originalResult.value = normalizedResult;
      backtestProgress.value = 50;
      showSuccess('原参数回测完成');
    } else {
      newResult.value = normalizedResult;
      backtestProgress.value = 100;
      showSuccess('新参数回测完成');
    }
  } catch (e: any) {
    // 如果是用户主动取消，不弹错误提示
    if (e?.name === 'AbortError') {
      return;
    }
    showError(e?.message || '回测失败');
    throw e;
  }
};

// 同时运行两组回测进行对比
const runComparison = async () => {
  if (!selectedStrategy.value || !startDate.value || !endDate.value) {
    showError('请选择策略和日期范围');
    return;
  }

  originalResult.value = null;
  newResult.value = null;
  isBacktesting.value = true;
  backtestProgress.value = 0;

  // 清理上一次的中断控制器
  if (originalAbortController.value) {
    originalAbortController.value.abort();
    originalAbortController.value = null;
  }
  if (newAbortController.value) {
    newAbortController.value.abort();
    newAbortController.value = null;
  }

  try {
    const tasks: Promise<void>[] = [];
    // 原参数回测
    tasks.push(runBacktest('original'));
    // 如果参数有变化，则并行运行新参数回测
    if (hasParamChanges.value) {
      tasks.push(runBacktest('new'));
    }

    await Promise.all(tasks);
    backtestProgress.value = 100;
  } catch {
    // 错误已经在 runBacktest 中提示，这里只负责收尾
  } finally {
    isBacktesting.value = false;
    currentBacktestType.value = null;
  }
};

// 停止当前对比（中断请求）
const stopComparison = () => {
  if (!isBacktesting.value) return;

  if (originalAbortController.value) {
    originalAbortController.value.abort();
    originalAbortController.value = null;
  }
  if (newAbortController.value) {
    newAbortController.value.abort();
    newAbortController.value = null;
  }

  isBacktesting.value = false;
  currentBacktestType.value = null;
  backtestProgress.value = 0;
  showSuccess('已停止当前对比回测');
};

// 格式化数值
const formatPercent = (val: number | undefined) => {
  if (val === undefined || val === null) return '-';
  return val.toFixed(2) + '%';
};

const formatNumber = (val: number | undefined, decimals = 2) => {
  if (val === undefined || val === null) return '-';
  return val.toFixed(decimals);
};

// 计算指标差异
const getMetricDiff = (key: keyof BacktestMetrics) => {
  if (!originalResult.value?.metrics || !newResult.value?.metrics) return null;
  const orig = originalResult.value.metrics[key] as number;
  const newVal = newResult.value.metrics[key] as number;
  if (orig === undefined || newVal === undefined) return null;
  return newVal - orig;
};

// 判断指标是否改善（正向指标越大越好，maxDrawdown越小越好）
const isImproved = (key: keyof BacktestMetrics) => {
  const diff = getMetricDiff(key);
  if (diff === null) return null;
  if (key === 'maxDrawdown') return diff < 0;
  return diff > 0;
};

// 指标配置
const metricsConfig = [
  { key: 'totalReturn', label: '总收益率', format: 'percent' },
  { key: 'annualizedReturn', label: '年化收益', format: 'percent' },
  { key: 'sharpeRatio', label: '夏普比率', format: 'number' },
  { key: 'maxDrawdown', label: '最大回撤', format: 'percent', inverse: true },
  { key: 'winRate', label: '胜率', format: 'percent' },
  { key: 'profitFactor', label: '盈亏比', format: 'number' },
  { key: 'tradesCount', label: '交易次数', format: 'integer' },
  { key: 'calmarRatio', label: '卡尔玛比率', format: 'number' },
  { key: 'sortinoRatio', label: '索提诺比率', format: 'number' },
];

// 收益曲线版本数据（供 EquityCurve 使用）
const equityVersions = computed(() => {
  const versions: Array<{ versionId: string; versionName: string; data: { date: string; equity: number }[] }> = [];

  if (originalResult.value?.equityCurve?.length) {
    versions.push({
      versionId: 'original',
      versionName: '原参数',
      data: originalResult.value.equityCurve,
    });
  }

  if (newResult.value?.equityCurve?.length) {
    versions.push({
      versionId: 'new',
      versionName: '新参数',
      data: newResult.value.equityCurve,
    });
  }

  return versions;
});

// 基准收益曲线（供 EquityCurve 使用）
const benchmarkCurve = computed(() => {
  // 优先使用新参数回测的基准曲线，其次使用原参数
  const source = newResult.value?.benchmarkCurve?.length
    ? newResult.value
    : originalResult.value?.benchmarkCurve?.length
      ? originalResult.value
      : null;

  if (!source || !source.benchmarkCurve || !source.benchmarkCurve.length) {
    return [] as Array<{ date: string; equity: number }>;
  }

  return source.benchmarkCurve;
});

// 生命周期
onMounted(() => {
  fetchStrategies();
  
  // 设置默认日期
  const today = new Date();
  const lastYear = new Date();
  lastYear.setFullYear(today.getFullYear() - 1);
  const [startStr] = lastYear.toISOString().split('T');
  const [endStr] = today.toISOString().split('T');
  startDate.value = startStr || '';
  endDate.value = endStr || '';
});
</script>

<template>
  <div class="p-6 space-y-6 max-w-[1800px] mx-auto">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
            <i class="fas fa-balance-scale text-white"></i>
          </div>
          参数对比调参
        </h1>
        <p class="text-slate-400 mt-1">修改参数后回测，与原参数进行对比分析</p>
      </div>
    </div>
    
    <!-- 消息提示 -->
    <div v-if="errorMessage" class="bg-red-500/20 border border-red-500/50 text-red-300 px-4 py-3 rounded-lg flex items-center gap-2">
      <i class="fas fa-exclamation-circle"></i>
      {{ errorMessage }}
    </div>
    <div v-if="successMessage" class="bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 px-4 py-3 rounded-lg flex items-center gap-2">
      <i class="fas fa-check-circle"></i>
      {{ successMessage }}
    </div>
    
    <!-- 配置区域 -->
    <div class="bg-[#151925] rounded-xl border border-slate-800 p-5">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- 策略选择 -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">选择策略</label>
          <select
            v-model="selectedStrategy"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            :disabled="isLoadingStrategies || isBacktesting"
          >
            <option value="" disabled>请选择策略</option>
            <option v-for="s in availableStrategies" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </div>
        
        <!-- 开始日期 -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">开始日期</label>
          <input
            v-model="startDate"
            type="date"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            :disabled="isBacktesting"
          />
        </div>
        
        <!-- 结束日期 -->
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">结束日期</label>
          <input
            v-model="endDate"
            type="date"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            :disabled="isBacktesting"
          />
        </div>
        
        <!-- 操作按钮 -->
        <div class="flex items-end gap-2">
          <button
            @click="runComparison"
            :disabled="isBacktesting || !selectedStrategy || !startDate || !endDate"
            class="flex-1 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2"
          >
            <i v-if="isBacktesting" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-play"></i>
            {{ isBacktesting ? '回测中...' : '开始对比' }}
          </button>
          <button
            v-if="isBacktesting"
            @click="stopComparison"
            class="px-3 py-2.5 rounded-lg border border-slate-600 text-slate-200 text-sm hover:bg-slate-700/60 transition-colors flex items-center gap-2"
          >
            <i class="fas fa-stop"></i>
            停止对比
          </button>
        </div>
      </div>
      
      <!-- 回测进度 -->
      <div v-if="isBacktesting" class="mt-4">
        <div class="flex items-center justify-between text-sm text-slate-400 mb-1">
          <span>{{ hasParamChanges ? '两组参数并行回测中' : '原参数回测中' }}</span>
          <span>{{ backtestProgress.toFixed(0) }}%</span>
        </div>
        <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div 
            class="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-300"
            :style="{ width: backtestProgress + '%' }"
          ></div>
        </div>
      </div>
    </div>
    
    <!-- 参数对比区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 原参数 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800 bg-slate-800/30">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <i class="fas fa-cube text-slate-400"></i>
              原参数（默认值）
            </h2>
            <span class="text-xs text-slate-500 bg-slate-700 px-2 py-1 rounded">只读</span>
          </div>
        </div>
        <div class="p-5 max-h-[500px] overflow-y-auto">
          <div v-if="isLoadingParams" class="flex items-center justify-center py-8 text-slate-400">
            <i class="fas fa-spinner fa-spin mr-2"></i>
            加载参数中...
          </div>
          <div v-else-if="strategyParams.length === 0" class="text-center py-8 text-slate-500">
            请先选择策略
          </div>
          <div v-else class="space-y-4">
            <div v-for="group in paramGroups" :key="group.name" class="space-y-3">
              <h3 class="text-sm font-medium text-slate-400 border-b border-slate-700 pb-2">
                {{ group.displayName }}
              </h3>
              <div v-for="param in group.params" :key="param.key" class="flex items-center justify-between">
                <label class="text-sm text-slate-300">{{ param.label }}</label>
                <div class="bg-slate-700/50 px-3 py-1.5 rounded text-slate-300 text-sm min-w-[100px] text-right">
                  {{ originalParams[param.key] }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 新参数 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800 bg-emerald-500/10">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <i class="fas fa-edit text-emerald-400"></i>
              新参数（可修改）
            </h2>
            <button
              @click="resetNewParams"
              class="text-xs text-slate-400 hover:text-white bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded transition-colors"
              :disabled="isBacktesting"
            >
              <i class="fas fa-undo mr-1"></i>
              重置
            </button>
          </div>
        </div>
        <div class="p-5 max-h-[500px] overflow-y-auto">
          <div v-if="isLoadingParams" class="flex items-center justify-center py-8 text-slate-400">
            <i class="fas fa-spinner fa-spin mr-2"></i>
            加载参数中...
          </div>
          <div v-else-if="strategyParams.length === 0" class="text-center py-8 text-slate-500">
            请先选择策略
          </div>
          <div v-else class="space-y-4">
            <div v-for="group in paramGroups" :key="group.name" class="space-y-3">
              <h3 class="text-sm font-medium text-slate-400 border-b border-slate-700 pb-2">
                {{ group.displayName }}
              </h3>
              <div v-for="param in group.params" :key="param.key" class="flex items-center justify-between gap-4">
                <label class="text-sm text-slate-300 flex-shrink-0">{{ param.label }}</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model.number="newParams[param.key]"
                    type="number"
                    :min="param.min"
                    :max="param.max"
                    :step="param.step || 0.01"
                    class="w-28 bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-white text-sm text-right focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                    :class="{ 'border-emerald-500 bg-emerald-500/10': originalParams[param.key] !== newParams[param.key] }"
                    :disabled="isBacktesting"
                  />
                  <span 
                    v-if="originalParams[param.key] !== newParams[param.key]"
                    class="text-emerald-400 text-xs"
                  >
                    <i class="fas fa-asterisk"></i>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 变更摘要 -->
        <div v-if="changedParams.length > 0" class="px-5 py-3 border-t border-slate-800 bg-emerald-500/5">
          <div class="text-sm text-emerald-400">
            <i class="fas fa-info-circle mr-1"></i>
            已修改 {{ changedParams.length }} 个参数
          </div>
        </div>
      </div>
    </div>
    
    <!-- 结果对比区域 -->
    <div v-if="originalResult || newResult" class="space-y-6">
      <!-- 指标对比表格 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-chart-bar text-indigo-400"></i>
            指标对比
          </h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="bg-slate-800/50">
                <th class="px-5 py-3 text-left text-sm font-medium text-slate-400">指标</th>
                <th class="px-5 py-3 text-right text-sm font-medium text-slate-400">原参数</th>
                <th class="px-5 py-3 text-right text-sm font-medium text-slate-400">新参数</th>
                <th class="px-5 py-3 text-right text-sm font-medium text-slate-400">变化</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800">
              <tr v-for="metric in metricsConfig" :key="metric.key" class="hover:bg-slate-800/30">
                <td class="px-5 py-3 text-sm text-slate-300">{{ metric.label }}</td>
                <td class="px-5 py-3 text-sm text-right text-slate-300">
                  <template v-if="originalResult?.metrics">
                    <span v-if="metric.format === 'percent'">{{ formatPercent(originalResult.metrics[metric.key as keyof BacktestMetrics] as number) }}</span>
                    <span v-else-if="metric.format === 'integer'">{{ originalResult.metrics[metric.key as keyof BacktestMetrics] }}</span>
                    <span v-else>{{ formatNumber(originalResult.metrics[metric.key as keyof BacktestMetrics] as number) }}</span>
                  </template>
                  <span v-else class="text-slate-500">-</span>
                </td>
                <td class="px-5 py-3 text-sm text-right text-slate-300">
                  <template v-if="newResult?.metrics">
                    <span v-if="metric.format === 'percent'">{{ formatPercent(newResult.metrics[metric.key as keyof BacktestMetrics] as number) }}</span>
                    <span v-else-if="metric.format === 'integer'">{{ newResult.metrics[metric.key as keyof BacktestMetrics] }}</span>
                    <span v-else>{{ formatNumber(newResult.metrics[metric.key as keyof BacktestMetrics] as number) }}</span>
                  </template>
                  <span v-else class="text-slate-500">-</span>
                </td>
                <td class="px-5 py-3 text-sm text-right">
                  <template v-if="getMetricDiff(metric.key as keyof BacktestMetrics) !== null">
                    <span 
                      :class="[
                        isImproved(metric.key as keyof BacktestMetrics) ? 'text-emerald-400' : 'text-red-400',
                        'font-medium'
                      ]"
                    >
                      <i :class="isImproved(metric.key as keyof BacktestMetrics) ? 'fas fa-arrow-up' : 'fas fa-arrow-down'" class="mr-1"></i>
                      <span v-if="metric.format === 'percent'">{{ formatPercent(Math.abs(getMetricDiff(metric.key as keyof BacktestMetrics)!)) }}</span>
                      <span v-else-if="metric.format === 'integer'">{{ Math.abs(getMetricDiff(metric.key as keyof BacktestMetrics)!) }}</span>
                      <span v-else>{{ formatNumber(Math.abs(getMetricDiff(metric.key as keyof BacktestMetrics)!)) }}</span>
                    </span>
                  </template>
                  <span v-else class="text-slate-500">-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 参数变化详情 -->
      <div v-if="changedParams.length > 0" class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-sliders-h text-amber-400"></i>
            参数变化详情
          </h2>
        </div>
        <div class="p-5">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div 
              v-for="param in changedParams" 
              :key="param.key"
              class="bg-slate-800/50 rounded-lg p-4 border border-slate-700"
            >
              <div class="text-sm text-slate-400 mb-2">{{ param.label }}</div>
              <div class="flex items-center justify-between">
                <div class="text-slate-500">
                  <span class="text-slate-300">{{ originalParams[param.key] }}</span>
                </div>
                <i class="fas fa-arrow-right text-slate-600 mx-3"></i>
                <div class="text-emerald-400 font-medium">
                  {{ newParams[param.key] }}
                </div>
              </div>
              <div class="mt-2 text-xs text-slate-500">
                变化: {{ ((Number(newParams[param.key]) - Number(originalParams[param.key])) / Number(originalParams[param.key]) * 100).toFixed(1) }}%
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 收益曲线对比 -->
      <div v-if="originalResult?.equityCurve?.length || newResult?.equityCurve?.length" class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-chart-line text-blue-400"></i>
            收益曲线对比
          </h2>
        </div>
        <div class="p-5">
          <div v-if="equityVersions.length > 0" class="h-80">
            <EquityCurve
              :versions="equityVersions"
              :benchmark="benchmarkCurve"
              :kline-data="[]"
              :highlight-ranges="[]"
              mode="equity"
              scale="linear"
            />
          </div>
          <div v-else class="h-80 flex items-center justify-center text-slate-500">
            <!-- 这里可以集成 ECharts 或其他图表库 -->
            <div class="text-center">
              <i class="fas fa-chart-area text-4xl mb-3 text-slate-600"></i>
              <p>收益曲线图表</p>
              <p class="text-sm mt-1">
                原参数: {{ originalResult?.equityCurve?.length || 0 }} 个数据点 | 
                新参数: {{ newResult?.equityCurve?.length || 0 }} 个数据点
              </p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 总结卡片 -->
      <div v-if="originalResult && newResult" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- 收益变化 -->
        <div class="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-5 border border-slate-700">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <i class="fas fa-percentage text-blue-400"></i>
            </div>
            <div class="text-sm text-slate-400">收益变化</div>
          </div>
          <div class="text-2xl font-bold" :class="isImproved('totalReturn') ? 'text-emerald-400' : 'text-red-400'">
            <i :class="isImproved('totalReturn') ? 'fas fa-arrow-up' : 'fas fa-arrow-down'" class="mr-2 text-lg"></i>
            {{ formatPercent(Math.abs(getMetricDiff('totalReturn')!)) }}
          </div>
        </div>
        
        <!-- 风险变化 -->
        <div class="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-5 border border-slate-700">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <i class="fas fa-shield-alt text-amber-400"></i>
            </div>
            <div class="text-sm text-slate-400">回撤变化</div>
          </div>
          <div class="text-2xl font-bold" :class="isImproved('maxDrawdown') ? 'text-emerald-400' : 'text-red-400'">
            <i :class="isImproved('maxDrawdown') ? 'fas fa-arrow-down' : 'fas fa-arrow-up'" class="mr-2 text-lg"></i>
            {{ formatPercent(Math.abs(getMetricDiff('maxDrawdown')!)) }}
          </div>
        </div>
        
        <!-- 夏普变化 -->
        <div class="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-5 border border-slate-700">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <i class="fas fa-star text-purple-400"></i>
            </div>
            <div class="text-sm text-slate-400">夏普比率变化</div>
          </div>
          <div class="text-2xl font-bold" :class="isImproved('sharpeRatio') ? 'text-emerald-400' : 'text-red-400'">
            <i :class="isImproved('sharpeRatio') ? 'fas fa-arrow-up' : 'fas fa-arrow-down'" class="mr-2 text-lg"></i>
            {{ formatNumber(Math.abs(getMetricDiff('sharpeRatio')!)) }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 空状态 -->
    <div v-else-if="!isBacktesting && selectedStrategy" class="bg-[#151925] rounded-xl border border-slate-800 p-12 text-center">
      <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
        <i class="fas fa-flask text-2xl text-slate-500"></i>
      </div>
      <h3 class="text-lg font-medium text-slate-300 mb-2">准备就绪</h3>
      <p class="text-slate-500 mb-4">修改右侧的参数，然后点击"开始对比"查看效果</p>
      <div class="flex items-center justify-center gap-4 text-sm text-slate-400">
        <span><i class="fas fa-check-circle text-emerald-500 mr-1"></i>已选择策略</span>
        <span><i class="fas fa-check-circle text-emerald-500 mr-1"></i>已设置日期</span>
        <span v-if="hasParamChanges"><i class="fas fa-check-circle text-emerald-500 mr-1"></i>参数已修改</span>
        <span v-else><i class="fas fa-circle text-slate-600 mr-1"></i>参数未修改</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #1e293b;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #475569;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #64748b;
}

/* 输入框数字箭头样式 */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  opacity: 0.5;
}

input[type="number"]:hover::-webkit-inner-spin-button,
input[type="number"]:hover::-webkit-outer-spin-button {
  opacity: 1;
}
</style>
