<!--
  Dashboard 页面
  显示收益曲线、雷达图、热力图和版本切换下拉菜单
-->
<template>
  <div class="dashboard-page p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen">
    <!-- 页面标题和版本选择 -->
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-3xl font-bold text-gray-800 dark:text-slate-100">回测 Dashboard</h1>
      
      <!-- 版本切换下拉菜单 -->
      <div class="flex items-center space-x-4">
        <label class="text-sm font-medium text-gray-700 dark:text-slate-300">选择版本：</label>
        <select
          v-model="selectedVersionId"
          @change="handleVersionChange"
          class="px-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">全部版本</option>
          <option
            v-for="version in availableVersions"
            :key="version.id"
            :value="version.id"
          >
            {{ version.name }} ({{ version.version }})
          </option>
        </select>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="text-center py-12">
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      <p class="mt-4 text-gray-600 dark:text-slate-400">加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- 主要内容 -->
    <div v-else class="space-y-6">
      <!-- 收益曲线 -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">收益曲线</h2>
        <EquityCurve
          :versions="equityCurveData"
          :benchmark="benchmarkData"
          @hover="handleEquityHover"
        />
      </div>

      <!-- 雷达图和热力图 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 雷达图 -->
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
          <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">策略雷达图</h2>
          <RadarChart
            v-if="currentRadarScores"
            :scores="currentRadarScores"
          />
          <div v-else class="text-center py-12 text-gray-500 dark:text-slate-400">
            暂无雷达图数据
          </div>
        </div>

        <!-- 热力图 -->
        <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
          <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100 mb-4">月度收益热力图</h2>
          <HeatmapChart
            v-if="monthlyReturnsData.length > 0"
            :data="monthlyReturnsData"
          />
          <div v-else class="text-center py-12 text-gray-500 dark:text-slate-400">
            暂无热力图数据
          </div>
        </div>
      </div>

      <!-- 防守仓模块（默认隐藏，可展开） -->
      <div class="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-semibold text-gray-800 dark:text-slate-100">防守仓仓位分析</h2>
          <button
            @click="showDefensePortfolio = !showDefensePortfolio"
            class="px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
          >
            {{ showDefensePortfolio ? '隐藏' : '显示' }}
          </button>
        </div>
        <PortfolioDefense
          v-if="showDefensePortfolio && currentBacktestResult"
          :trades="currentBacktestResult.trades || []"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { getDashboardResult, getAvailableVersions } from '../api/backtestApi';
import EquityCurve from '../components/EquityCurve.vue';
import RadarChart from '../components/RadarChart.vue';
import HeatmapChart from '../components/HeatmapChart.vue';
import PortfolioDefense from '../components/PortfolioDefense.vue';
import type { StrategyVersion } from '../store/strategyStore';

const router = useRouter();
const strategyStore = useStrategyStore();

// 状态
const selectedVersionId = ref<string>('');
const showDefensePortfolio = ref(false);

// 从 store 获取数据
const isLoading = computed(() => strategyStore.isLoading);
const error = computed(() => strategyStore.error);
const availableVersions = computed(() => strategyStore.availableVersions);
const dashboardData = computed(() => strategyStore.dashboardData);
const currentBacktestResult = computed(() => strategyStore.currentBacktestResult);
const currentRadarScores = computed(() => strategyStore.currentRadarScores);

// 收益曲线数据
const equityCurveData = computed(() => {
  if (!dashboardData.value) return [];
  return dashboardData.value.versions.map(v => ({
    versionId: v.versionId,
    versionName: v.versionName,
    data: v.equityCurve
  }));
});

// 基准数据
const benchmarkData = computed(() => {
  return dashboardData.value?.benchmark || [];
});

// 月度收益数据
const monthlyReturnsData = computed(() => {
  if (!currentBacktestResult.value?.monthlyReturns) return [];
  return currentBacktestResult.value.monthlyReturns;
});

// 版本切换处理
function handleVersionChange() {
  if (selectedVersionId.value) {
    router.push(`/strategy/${selectedVersionId.value}`);
  }
}

// 收益曲线 hover 事件
function handleEquityHover(data: {
  date: string;
  version?: string;
  equity: number;
  monthlyReturn?: number;
}) {
  // 可以在这里显示 tooltip 或其他交互
  console.log('Hover data:', data);
}

// 加载数据
async function loadDashboardData() {
  try {
    strategyStore.setLoading(true);
    strategyStore.setError(null);

    // 加载可用版本列表
    const versions = await getAvailableVersions();
    strategyStore.setAvailableVersions(versions);

    // 加载 Dashboard 数据
    const dashboardResult = await getDashboardResult();
    strategyStore.setDashboardData(dashboardResult);

    // 如果有选中的版本，加载该版本的详情
    if (selectedVersionId.value) {
      const version = versions.find(v => v.id === selectedVersionId.value);
      if (version) {
        // 可以在这里加载该版本的详细数据
      }
    }
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : '加载数据失败';
    strategyStore.setError(errorMessage);
    console.error('加载 Dashboard 数据失败:', err);
  } finally {
    strategyStore.setLoading(false);
  }
}

// 监听版本变化
watch(selectedVersionId, (newVersionId) => {
  if (newVersionId && dashboardData.value) {
    // 更新当前版本的回测结果
    const versionData = dashboardData.value.versions.find(v => v.versionId === newVersionId);
    if (versionData) {
      strategyStore.setCurrentVersion(newVersionId);
    }
  }
});

onMounted(() => {
  loadDashboardData();
});
</script>

<style scoped>
.dashboard-page {
  transition: background-color 0.3s ease;
}
</style>

