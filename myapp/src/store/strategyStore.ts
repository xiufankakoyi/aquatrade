/**
 * 策略状态管理 Store
 * 使用 Pinia 管理当前版本、可选版本列表、回测数据、搜索结果
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Strategy, Metrics, MonthlyReturn, Trade, StrategySession } from '../types/backtest';

// 策略版本接口
export interface StrategyVersion {
  id: string;
  name: string;
  version: string;
  createdAt: string;
  description?: string;
}

// 回测结果接口
export interface BacktestResult {
  versionId: string;
  metrics: Metrics;
  equityCurve: Array<{ date: string; equity: number; benchmarkEquity?: number }>;
  monthlyReturns: MonthlyReturn[];
  trades: Trade[];
  radarScores?: {
    excessReturn: number;
    riskConsistency: number;
    maxDrawdown: number;
    tradingQuality: number;
    antiOverfitting: number;
  };
}

// 参数搜索结果接口
export interface ParameterSearchResult {
  id: string;
  params: Record<string, number | boolean | string>;
  metrics: Metrics;
  rank: number;
}

export const useStrategyStore = defineStore('strategy', () => {
  // 当前选中的版本 ID
  const currentVersionId = ref<string | null>(null);
  
  // 可用的策略版本列表
  const availableVersions = ref<StrategyVersion[]>([]);
  
  // 当前版本的回测结果
  const currentBacktestResult = ref<BacktestResult | null>(null);
  
  // 参数搜索结果列表
  const parameterSearchResults = ref<ParameterSearchResult[]>([]);
  
  // Dashboard 数据（可能包含多个版本）
  const dashboardData = ref<{
    versions: Array<{
      versionId: string;
      versionName: string;
      equityCurve: Array<{ date: string; equity: number }>;
      metrics: Metrics;
    }>;
    benchmark: Array<{ date: string; equity: number }>;
  } | null>(null);
  
  // 加载状态
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  
  // 策略会话历史（用于历史记录页面）
  const strategySessions = ref<Record<string, StrategySession[]>>({});

  // 计算属性：当前版本信息
  const currentVersion = computed(() => {
    if (!currentVersionId.value) return null;
    return availableVersions.value.find(v => v.id === currentVersionId.value) || null;
  });

  // 计算属性：当前版本的雷达图分数
  const currentRadarScores = computed(() => {
    return currentBacktestResult.value?.radarScores || null;
  });

  // Actions: 设置当前版本
  function setCurrentVersion(versionId: string) {
    currentVersionId.value = versionId;
  }

  // Actions: 设置可用版本列表
  function setAvailableVersions(versions: StrategyVersion[]) {
    availableVersions.value = versions;
  }

  // Actions: 设置当前回测结果
  function setCurrentBacktestResult(result: BacktestResult) {
    currentBacktestResult.value = result;
  }

  // Actions: 设置参数搜索结果
  function setParameterSearchResults(results: ParameterSearchResult[]) {
    parameterSearchResults.value = results;
  }

  // Actions: 设置 Dashboard 数据
  function setDashboardData(data: typeof dashboardData.value) {
    dashboardData.value = data;
  }

  // Actions: 设置加载状态
  function setLoading(loading: boolean) {
    isLoading.value = loading;
  }

  // Actions: 设置错误信息
  function setError(errorMessage: string | null) {
    error.value = errorMessage;
  }

  // Actions: 重置状态
  function reset() {
    currentVersionId.value = null;
    currentBacktestResult.value = null;
    parameterSearchResults.value = [];
    dashboardData.value = null;
    error.value = null;
  }

  return {
    // State
    currentVersionId,
    availableVersions,
    currentBacktestResult,
    parameterSearchResults,
    dashboardData,
    strategySessions,
    isLoading,
    error,
    // Computed
    currentVersion,
    currentRadarScores,
    // Actions
    setCurrentVersion,
    setAvailableVersions,
    setCurrentBacktestResult,
    setParameterSearchResults,
    setDashboardData,
    setLoading,
    setError,
    reset
  };
});

