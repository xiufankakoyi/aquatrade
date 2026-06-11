<template>
  <div class="strategy-compare-page p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <button
          @click="$router.push('/dashboard')"
          class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:text-gray-900 dark:hover:text-slate-100 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
        >
          ← 返回 Dashboard
        </button>
        <h1 class="text-3xl font-bold text-gray-800 dark:text-slate-100">
          策略回测对比
        </h1>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="errorMessage" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{{ errorMessage }}</p>
    </div>
    <div v-if="successMessage" class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 mb-6">
      <p class="text-green-800 dark:text-green-200">{{ successMessage }}</p>
    </div>

    <!-- 配置区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <!-- 左侧：策略选择 -->
      <div class="lg:col-span-1">
        <div class="bg-[#151925] rounded-xl border border-slate-800 p-5 space-y-5">
          <!-- 选择要对比的策略数量 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">对比策略数量</label>
            <select
              v-model.number="compareCount"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              :disabled="isLoadingResults"
            >
              <option :value="2">2个策略</option>
              <option :value="3">3个策略</option>
              <option :value="4">4个策略</option>
            </select>
          </div>

          <!-- 策略选择器 -->
          <div v-for="i in compareCount" :key="i" class="space-y-2">
            <label class="block text-sm font-medium text-slate-300">策略 {{ i }}</label>
            <select
              v-model="selectedStrategies[i-1]"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              :disabled="isLoadingResults"
            >
              <option value="" disabled>请选择策略</option>
              <option v-for="s in availableStrategies" :key="s.id" :value="s.id">
                {{ s.name }}
              </option>
            </select>
          </div>

          <!-- 日期范围 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">回测日期</label>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-slate-500 mb-1">开始日期</label>
                <input
                  v-model="startDate"
                  type="date"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isLoadingResults"
                />
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">结束日期</label>
                <input
                  v-model="endDate"
                  type="date"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isLoadingResults"
                />
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="pt-2">
            <button
              @click="compareStrategies"
              :disabled="isLoadingResults || selectedStrategies.some(s => !s)"
              class="w-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2"
            >
              <i v-if="isLoadingResults" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-chart-line"></i>
              {{ isLoadingResults ? '加载中...' : '开始对比' }}
            </button>
          </div>

          <!-- 加载进度 -->
          <div v-if="isLoadingResults" class="mt-3">
            <div class="flex items-center justify-between text-sm text-slate-400 mb-1">
              <span>加载进度</span>
              <span>{{ loadingProgress.toFixed(0) }}%</span>
            </div>
            <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
              <div 
                class="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                :style="{ width: loadingProgress + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：对比配置 -->
      <div class="lg:col-span-2">
        <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
          <div class="px-5 py-4 border-b border-slate-800">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <i class="fas fa-sliders-h text-purple-400"></i>
              对比配置
            </h2>
          </div>
          <div class="p-5">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <!-- 绩效指标选择 -->
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">绩效指标</label>
                <div class="space-y-2">
                  <div v-for="metric in metricsConfig" :key="metric.key" class="flex items-center gap-2">
                    <input
                      v-model="selectedMetrics[metric.key]"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">{{ metric.label }}</label>
                  </div>
                </div>
              </div>

              <!-- 图表类型选择 -->
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">图表类型</label>
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <input
                      v-model="showEquityCurve"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">收益曲线</label>
                  </div>
                  <div class="flex items-center gap-2">
                    <input
                      v-model="showDrawdown"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">最大回撤</label>
                  </div>
                  <div class="flex items-center gap-2">
                    <input
                      v-model="showMonthlyReturns"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">月度收益</label>
                  </div>
                </div>
              </div>

              <!-- 比较基准 -->
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">比较基准</label>
                <select
                  v-model="benchmark"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isLoadingResults"
                >
                  <option value="">无基准</option>
                  <option value="000300">沪深300</option>
                  <option value="000001">上证指数</option>
                  <option value="399006">创业板指</option>
                </select>
              </div>

              <!-- 显示选项 -->
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">显示选项</label>
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <input
                      v-model="showBenchmark"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">显示基准线</label>
                  </div>
                  <div class="flex items-center gap-2">
                    <input
                      v-model="showLegend"
                      type="checkbox"
                      class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                      :disabled="isLoadingResults"
                    />
                    <label class="text-sm text-slate-300">显示图例</label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 对比结果 -->
    <div v-if="strategyResults.length > 0" class="space-y-6">
      <!-- 关键指标对比表格 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-chart-bar text-green-400"></i>
            关键指标对比
          </h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="bg-slate-800/50">
                <th class="px-5 py-3 text-left text-sm font-medium text-slate-400">指标</th>
                <th v-for="(result, index) in strategyResults" :key="index" class="px-5 py-3 text-right text-sm font-medium text-slate-400">
                  <div class="flex items-center justify-end gap-1">
                    <span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: strategyColors[index] }"></span>
                    <span>{{ result.strategyName }}</span>
                  </div>
                </th>
                <th v-if="showBenchmark" class="px-5 py-3 text-right text-sm font-medium text-slate-400">基准</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800">
              <tr v-for="metric in displayMetrics" :key="metric.key" class="hover:bg-slate-800/30">
                <td class="px-5 py-3 text-sm text-slate-300">{{ metric.label }}</td>
                <td v-for="(result, index) in strategyResults" :key="index" class="px-5 py-3 text-sm text-right">
                  <span :class="getMetricColor(metric.key, result.metrics[metric.key])">
                    {{ formatMetric(metric, result.metrics[metric.key]) }}
                  </span>
                </td>
                <td v-if="showBenchmark" class="px-5 py-3 text-sm text-right text-slate-400">
                  {{ formatMetric(metric, benchmarkMetrics[metric.key]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 收益曲线对比 -->
      <div v-if="showEquityCurve" class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-chart-line text-blue-400"></i>
            收益曲线对比
          </h2>
        </div>
        <div class="p-5 h-80">
          <EquityCurve
            :versions="equityVersions"
            :benchmark="benchmarkEquity"
            mode="equity"
            scale="linear"
          />
        </div>
      </div>

      <!-- 月度收益对比 -->
      <div v-if="showMonthlyReturns" class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-calendar-alt text-amber-400"></i>
            月度收益对比
          </h2>
        </div>
        <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="(result, index) in strategyResults" :key="index">
            <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
              <div class="flex items-center gap-2 mb-3">
                <span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: strategyColors[index] }"></span>
                <h3 class="text-sm font-medium text-white">{{ result.strategyName }} - 月度收益</h3>
              </div>
              <div class="h-60">
                <!-- 这里可以添加月度收益图表 -->
                <div class="flex items-center justify-center h-full text-slate-500">
                  <i class="fas fa-chart-bar text-4xl mb-2 mr-2"></i>
                  <p>月度收益图表</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 差异分析报告 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-file-alt text-purple-400"></i>
            差异分析报告
          </h2>
        </div>
        <div class="p-5">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- 最佳表现策略 -->
            <div>
              <h3 class="text-lg font-semibold text-white mb-4">最佳表现策略</h3>
              <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                <div v-if="bestStrategy" class="space-y-3">
                  <div class="flex items-center gap-2">
                    <span class="inline-block w-3 h-3 rounded-full" :style="{ backgroundColor: bestStrategyColor }"></span>
                    <h4 class="text-xl font-bold text-white">{{ bestStrategy.strategyName }}</h4>
                  </div>
                  <div class="space-y-2">
                    <div v-for="metric in topMetrics" :key="metric.key" class="flex justify-between">
                      <span class="text-sm text-slate-400">{{ metric.label }}</span>
                      <span class="text-sm font-bold text-green-400">{{ formatMetric(metric, bestStrategy.metrics[metric.key]) }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="text-slate-500 text-center py-4">
                  分析中...
                </div>
              </div>
            </div>

            <!-- 策略对比总结 -->
            <div>
              <h3 class="text-lg font-semibold text-white mb-4">对比总结</h3>
              <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3">
                <div v-for="summary in comparisonSummary" :key="summary.key" class="flex items-start gap-2">
                  <i :class="summary.icon" class="text-lg mt-1" :style="{ color: summary.color }"></i>
                  <div>
                    <div class="text-sm text-white font-medium">{{ summary.title }}</div>
                    <div class="text-sm text-slate-400">{{ summary.description }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!isLoadingResults" class="bg-[#151925] rounded-xl border border-slate-800 p-12 text-center">
      <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
        <i class="fas fa-chart-line text-2xl text-slate-500"></i>
      </div>
      <h3 class="text-lg font-medium text-slate-300 mb-2">准备开始对比</h3>
      <p class="text-slate-500 mb-4">选择要对比的策略和配置，然后点击"开始对比"</p>
      <div class="flex items-center justify-center gap-2 text-sm text-slate-400">
        <span><i class="fas fa-check-circle text-green-500 mr-1"></i>选择策略</span>
        <span><i class="fas fa-check-circle text-green-500 mr-1"></i>设置日期</span>
        <span><i class="fas fa-circle text-slate-600 mr-1"></i>开始对比</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import EquityCurve from '../components/EquityCurve.vue';

// 使用相对路径，让 Vite 代理可以正确代理请求到后端
const API_BASE_URL = '/api';

// 策略相关
const availableStrategies = ref<Array<{ id: string; name: string }>>([]);
const selectedStrategies = ref<string[]>(['', '']);
const compareCount = ref(2);
const isLoadingStrategies = ref(false);
const isLoadingResults = ref(false);
const loadingProgress = ref(0);

// 日期范围
const startDate = ref('');
const endDate = ref('');

// 图表配置
const showEquityCurve = ref(true);
const showDrawdown = ref(false);
const showMonthlyReturns = ref(true);
const showBenchmark = ref(true);
const showLegend = ref(true);
const benchmark = ref('000300');

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
  { key: 'volatility', label: '波动率', format: 'percent' }
];

const selectedMetrics = ref({
  totalReturn: true,
  annualizedReturn: true,
  sharpeRatio: true,
  maxDrawdown: true,
  winRate: true,
  profitFactor: true,
  tradesCount: true
});

// 策略结果
const strategyResults = ref<Array<{
  strategyId: string;
  strategyName: string;
  metrics: any;
  equityCurve: Array<{ date: string; equity: number }>;
  trades: Array<any>;
  monthlyReturns: Array<any>;
}>>([]);

const benchmarkMetrics = ref<any>({
  totalReturn: 0,
  annualizedReturn: 0,
  sharpeRatio: 0,
  maxDrawdown: 0,
  winRate: 0,
  profitFactor: 0,
  tradesCount: 0,
  calmarRatio: 0,
  sortinoRatio: 0,
  volatility: 0
});

const benchmarkEquity = ref<Array<{ date: string; equity: number }>>([]);

// 策略颜色
const strategyColors = ['#8b5cf6', '#6366f1', '#3b82f6', '#06b6d4', '#10b981'];

// 消息
const errorMessage = ref('');
const successMessage = ref('');

// 监听策略数量变化
watch(compareCount, (newCount, oldCount) => {
  const currentStrategies = [...selectedStrategies.value];
  if (newCount > oldCount) {
    // 添加新的策略选择
    for (let i = oldCount; i < newCount; i++) {
      currentStrategies.push('');
    }
  } else {
    // 移除多余的策略选择
    currentStrategies.splice(newCount);
  }
  selectedStrategies.value = currentStrategies;
});

// 获取指标颜色
const getMetricColor = (key: string, value: number) => {
  if (key === 'maxDrawdown' || key === 'volatility') {
    return value < 0 ? 'text-green-400' : 'text-red-400';
  }
  return value > 0 ? 'text-green-400' : 'text-red-400';
};

// 收益曲线版本数据
const equityVersions = computed(() => {
  return strategyResults.value.map((result, index) => ({
    versionId: result.strategyId,
    versionName: result.strategyName,
    data: result.equityCurve
  }));
});

// 最佳策略
const bestStrategy = computed(() => {
  if (strategyResults.value.length === 0) return null;
  return strategyResults.value.reduce((best, current) => {
    return current.metrics.sharpeRatio > best.metrics.sharpeRatio ? current : best;
  });
});

// 最佳策略颜色
const bestStrategyColor = computed(() => {
  if (!bestStrategy.value) return '#8b5cf6';
  const index = strategyResults.value.findIndex(r => r.strategyId === bestStrategy.value?.strategyId);
  return strategyColors[index];
});

// 对比总结
const comparisonSummary = computed(() => {
  if (strategyResults.value.length < 2) return [];
  
  const summaries = [];
  const bestSharpe = Math.max(...strategyResults.value.map(r => r.metrics.sharpeRatio));
  const worstDrawdown = Math.min(...strategyResults.value.map(r => r.metrics.maxDrawdown));
  const bestReturn = Math.max(...strategyResults.value.map(r => r.metrics.totalReturn));
  
  summaries.push({
    key: 'sharpe',
    title: '最佳夏普比率',
    description: `${strategyResults.value.find(r => r.metrics.sharpeRatio === bestSharpe)?.strategyName} 表现最佳，夏普比率为 ${bestSharpe.toFixed(4)}`,
    icon: 'fas fa-trophy',
    color: '#fbbf24'
  });
  
  summaries.push({
    key: 'drawdown',
    title: '最小最大回撤',
    description: `${strategyResults.value.find(r => r.metrics.maxDrawdown === worstDrawdown)?.strategyName} 表现最佳，最大回撤为 -${Math.abs(worstDrawdown).toFixed(2)}%`,
    icon: 'fas fa-shield-alt',
    color: '#34d399'
  });
  
  summaries.push({
    key: 'return',
    title: '最高总收益率',
    description: `${strategyResults.value.find(r => r.metrics.totalReturn === bestReturn)?.strategyName} 表现最佳，总收益率为 ${bestReturn.toFixed(2)}%`,
    icon: 'fas fa-chart-line',
    color: '#60a5fa'
  });
  
  return summaries;
});

// 最佳指标列表
const topMetrics = computed(() => {
  return metricsConfig.slice(0, 5);
});

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
    }
  } catch (e) {
    errorMessage.value = '获取策略列表失败';
  } finally {
    isLoadingStrategies.value = false;
  }
};

// 对比策略
const compareStrategies = async () => {
  if (!selectedStrategies.some(s => s)) {
    errorMessage.value = '请至少选择一个策略';
    return;
  }
  
  if (!startDate.value || !endDate.value) {
    errorMessage.value = '请选择日期范围';
    return;
  }
  
  isLoadingResults.value = true;
  loadingProgress.value = 0;
  strategyResults.value = [];
  errorMessage.value = '';
  
  const selectedStrategyIds = selectedStrategies.value.filter(s => s);
  
  try {
    // 并行获取每个策略的回测结果
    const promises = selectedStrategyIds.map((strategyId, index) => 
      fetchStrategyResult(strategyId, index, selectedStrategyIds.length)
    );
    
    await Promise.all(promises);
    
    // 加载基准数据
    if (showBenchmark.value && benchmark.value) {
      await fetchBenchmarkData();
    }
    
    loadingProgress.value = 100;
    showSuccess('策略对比完成！');
  } catch (e) {
    errorMessage.value = '策略对比失败';
  } finally {
    isLoadingResults.value = false;
  }
};

// 获取单个策略结果
const fetchStrategyResult = async (strategyId: string, index: number, total: number) => {
  try {
    const response = await fetch(`${API_BASE_URL}/run_backtest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        strategy_name: strategyId,
        start_date: startDate.value,
        end_date: endDate.value
      })
    });
    
    const data = await response.json();
    if (data.success) {
      const strategy = availableStrategies.value.find(s => s.id === strategyId);
      
      strategyResults.value.push({
        strategyId,
        strategyName: strategy?.name || strategyId,
        metrics: data.data.metrics,
        equityCurve: data.data.equityCurve,
        trades: data.data.trades || [],
        monthlyReturns: data.data.monthlyReturns || []
      });
      
      // 更新进度
      loadingProgress.value = Math.round(((index + 1) / total) * 100);
    }
  } catch (e) {
    throw new Error(`获取策略 ${strategyId} 结果失败`);
  }
};

// 获取基准数据
const fetchBenchmarkData = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/benchmark/${benchmark.value}/equity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        start_date: startDate.value,
        end_date: endDate.value
      })
    });
    
    const data = await response.json();
    if (data.success) {
      benchmarkEquity.value = data.data;
      // 计算基准指标
      // 这里简化处理，实际应该根据基准数据计算
      benchmarkMetrics.value = {
        totalReturn: data.data.length > 0 ? ((data.data[data.data.length - 1].equity / data.data[0].equity - 1) * 100) : 0,
        annualizedReturn: 0,
        sharpeRatio: 0,
        maxDrawdown: 0,
        winRate: 0,
        profitFactor: 0,
        tradesCount: 0,
        calmarRatio: 0,
        sortinoRatio: 0,
        volatility: 0
      };
    }
  } catch (e) {
    console.error('获取基准数据失败', e);
  }
};

// 工具函数
const showSuccess = (msg: string) => {
  successMessage.value = msg;
  setTimeout(() => successMessage.value = '', 5000);
};

const showError = (msg: string) => {
  errorMessage.value = msg;
  setTimeout(() => errorMessage.value = '', 8000);
};

const formatMetric = (metric: any, value: number) => {
  if (value === undefined || value === null) return '-';
  
  switch (metric.format) {
    case 'percent':
      return `${value.toFixed(2)}%`;
    case 'integer':
      return value.toFixed(0);
    case 'number':
      return value.toFixed(4);
    default:
      return value.toString();
  }
};

// 设置默认日期
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
</style>