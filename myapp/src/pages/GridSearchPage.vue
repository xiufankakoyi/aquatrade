<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useStrategyStore, type ParameterSearchResult } from "@/store/strategyStore";
import { useOptimization } from '@/composables/useOptimization';
import { useAlgorithmParams } from '@/composables/useAlgorithmParams';
import { useDateRange } from '@/composables/useDateRange';
import { useStrategyParams } from '@/composables/useStrategyParams';
import OptimizationVisualizer from '@/components/OptimizationVisualizer.vue';
import RangeSlider from '@/components/RangeSlider.vue';
import ThreeSegmentTimeSlider from '@/components/ThreeSegmentTimeSlider.vue';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import { 
  CUSTOM_PARAM_CONFIG, 
  ALGO_CONFIGS, 
  type AlgorithmKey 
} from '@/config/strategyConfig';
import {
  getParamUnit,
  toUiValue,
  toBackendValue,
  formatParamDisplayValue,
  getParamLabel
} from '@/utils/paramUtils';

type SearchResult = ParameterSearchResult;

const API_BASE_URL = 'http://localhost:5000/api';

// ==================== Composables ====================
// 优化状态管理
const {
  isOptimizing,
  progress,
  optimizationStatus,
  evaluatedCount,
  totalIterations,
  bestMetric,
  bestParams,
  evaluationResults,
  optimizationHistory,
  candidates,
  finalSelected,
  startOptimization: startOpt,
  stopOptimization: stopOpt,
  setupSocketListeners,
  cleanup: cleanupOptimization,
} = useOptimization();

// 策略参数管理
const selectedStrategy = ref('');
const {
  availableParams,
  selectedParamKeys,
  paramLocked,
  paramRangeValues,
  isLoadingParams,
  fetchStrategyParams,
} = useStrategyParams(selectedStrategy);

// 算法参数管理
const selectedAlgorithm = ref<AlgorithmKey>('ga');
const {
  algorithmParams,
  currentAlgoConfig,
  currentAlgoParams,
  loadAlgorithmParams,
} = useAlgorithmParams(selectedAlgorithm);

// 日期范围管理
const {
  startDate,
  endDate,
  trainStartDate,
  trainEndDate,
  valStartDate,
  valEndDate,
  testStartDate,
  testEndDate,
  applyInitialDates,
} = useDateRange();

// Store
const strategyStore = useStrategyStore();
const { parameterSearchResults } = storeToRefs(strategyStore);
const searchResults = parameterSearchResults;

// ==================== UI State ====================
const availableStrategies = ref<Array<{id: string, name: string}>>([]);
const isLoadingStrategies = ref(false);
const maxIterations = ref(100);
const populationSize = ref(50);
const selectedMetric = ref('sharpeRatio');
const optimizationMode = ref<'quick_explore' | 'robust' | 'aggressive'>('robust');
const optimizationObjective = ref<'robust_trend_score' | 'rr_risk_score' | 'multi_period_robust' | 'calmar' | 'sharpe'>('robust_trend_score');
const selectedResult = ref<SearchResult | null>(null);
const candidateDetail = ref<any | null>(null);
const showSensitivity = ref(false);
const sensitivityParamKey = ref('');
const sensitivityPoints = ref<Array<{ value: number; score: number }>>([]);
const sensitivityChartContainer = ref<HTMLElement | null>(null);
let sensitivityChartInstance: echarts.ECharts | null = null;
const showEvaluationDetails = ref(false);
const isSavingProfile = ref(false);
const enableDiversity = ref(true);
const diversityThreshold = ref(0.15);
const maxDiverseResults = ref(10);
const errorMessage = ref('');
const successMessage = ref('');
const confirmationDialog = ref({
  visible: false,
  title: '',
  message: '',
  confirmAction: () => {},
  cancelAction: () => {}
});

// ==================== Utility Functions ====================
const toNumeric = (value: any): number => {
  if (typeof value === 'number') return value;
  if (value === null || value === undefined || value === '') return NaN;
  const n = Number(value);
  return Number.isNaN(n) ? NaN : n;
};

const formatNumber = (value: any, digits = 2): string => {
  const n = toNumeric(value);
  if (Number.isNaN(n)) return '—';
  return n.toFixed(digits);
};

const formatPercent = (value: any, digits = 2): string => {
  const n = toNumeric(value);
  if (Number.isNaN(n)) return '—';
  return `${n.toFixed(digits)}%`;
};

const formatScore = (value: any, digits = 4): string => {
  const n = toNumeric(value);
  if (Number.isNaN(n)) return '—';
  // 检查是否为惩罚值（-1e9或更小）
  if (n < -10000) return '无效';
  return n.toFixed(digits);
};

// 检查分数是否为有效值（非惩罚值）
const isValidScore = (value: any): boolean => {
  const n = toNumeric(value);
  if (Number.isNaN(n)) return false;
  return n > -10000; // 惩罚值通常是-1e9
};

// ==================== API Functions ====================
const fetchStrategies = async () => {
  isLoadingStrategies.value = true;
  try {
    const response = await fetch(`${API_BASE_URL}/strategies`);
    const data = await response.json();
    if (data.success && Array.isArray(data.data)) {
      availableStrategies.value = data.data.map((s: any) => ({
        id: String(s.id).trim(),
        name: String(s.name).trim(),
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

const syncCommonControls = (algo?: AlgorithmKey) => {
  const key = algo || selectedAlgorithm.value;
  const params = currentAlgoParams.value;
  if (key === 'ga') {
    populationSize.value = params.pop_size ?? 50;
    maxIterations.value = params.generations ?? 100;
  } else if (key === 'pso') {
    populationSize.value = params.particle_count ?? 40;
    maxIterations.value = params.iterations ?? 100;
  } else if (key === 'cmaes') {
    populationSize.value = params.population ?? 30;
    maxIterations.value = params.max_evaluations ?? 200;
  } else if (key === 'simulatedAnnealing') {
    populationSize.value = params.steps_per_temp ?? 10;
    maxIterations.value = params.steps_per_temp ?? 10;
  } else if (key === 'bayesian') {
    populationSize.value = params.random_init_points ?? 10;
    maxIterations.value = params.iterations ?? 50;
  } else if (key === 'grid') {
    populationSize.value = params.grid_density ?? 10;
    maxIterations.value = params.grid_density ?? 10;
  }
};

// ==================== Computed Properties ====================

const isAllSelected = computed(() => selectedParamKeys.value.length === availableParams.value.length);
const MAX_OPTIMIZABLE_PARAMS = 4;

watch(selectedParamKeys, (newKeys) => {
  if (newKeys.length > MAX_OPTIMIZABLE_PARAMS) {
    // 保留前 MAX_OPTIMIZABLE_PARAMS 个，其余自动关闭
    const trimmed = newKeys.slice(0, MAX_OPTIMIZABLE_PARAMS);
    selectedParamKeys.value = trimmed;
    showConfirmationDialog(
      '参数数量过多',
      `一次优化太多参数极易过拟合，最多只能选择 ${MAX_OPTIMIZABLE_PARAMS} 个。`,
      () => {
        // 仅用于提示，不执行额外操作
      }
    );
  }
});

const algorithmSummary = computed(() => {
  const alg = selectedAlgorithm.value;
  const params = currentAlgoParams.value;
  if (alg === 'ga') {
    return `代数 ${params.generations ?? 100} × 种群 ${params.pop_size ?? 50}`;
  }
  if (alg === 'pso') {
    return `迭代 ${params.iterations ?? 100} × 粒子 ${params.particle_count ?? 40}`;
  }
  if (alg === 'cmaes') {
    return `评估 ${params.max_evaluations ?? 200} / 种群 ${params.population ?? 30}`;
  }
  if (alg === 'simulatedAnnealing') {
    return `初温 ${params.initial_temp ?? 100} · 每温迭代 ${params.steps_per_temp ?? 10}`;
  }
  if (alg === 'bayesian') {
    return `随机初始 ${params.random_init_points ?? 10} + 迭代 ${params.iterations ?? 50}`;
  }
  if (alg === 'grid') {
    return `网格密度 ${params.grid_density ?? 10}（在参数空间中设置步长）`;
  }
  return '';
});

// 日期管理已移到 useDateRange composable

// 优化历史记录已移到 useOptimization composable

// 按分组组织参数
const paramGroups = computed(() => {
  const groups = new Map<string, { name: string; displayName: string; params: any[] }>();
  
  // 定义默认分组名称
  const DEFAULT_GROUP_NAME = 'default';
  const DEFAULT_GROUP_DISPLAY_NAME = '基本参数';
  
  // 初始化默认分组
  groups.set(DEFAULT_GROUP_NAME, {
    name: DEFAULT_GROUP_NAME,
    displayName: DEFAULT_GROUP_DISPLAY_NAME,
    params: []
  });
  
  // 遍历所有参数，按group分组
  availableParams.value.forEach(param => {
    const groupName = param.group || DEFAULT_GROUP_NAME;
    const displayName = param.group_label || 
                        (groupName === DEFAULT_GROUP_NAME ? DEFAULT_GROUP_DISPLAY_NAME : groupName);
    
    if (!groups.has(groupName)) {
      groups.set(groupName, {
        name: groupName,
        displayName: displayName,
        params: []
      });
    }
    
    groups.get(groupName)!.params.push(param);
  });
  
  // 转换为数组并排序（默认分组放在最前面）
  const result = Array.from(groups.values());
  return result.sort((a, b) => {
    if (a.name === DEFAULT_GROUP_NAME) return -1;
    if (b.name === DEFAULT_GROUP_NAME) return 1;
    return a.displayName.localeCompare(b.displayName);
  });
});

// 检查指定分组是否全被选中
const isGroupSelected = (groupName: string) => {
  const group = paramGroups.value.find(g => g.name === groupName);
  if (!group) return false;
  
  return group.params.every(param => selectedParamKeys.value.includes(param.key));
};

// 获取分组中已选择的参数数量
const getSelectedCountInGroup = (groupName: string) => {
  const group = paramGroups.value.find(g => g.name === groupName);
  if (!group) return 0;
  
  return group.params.filter(param => selectedParamKeys.value.includes(param.key)).length;
};

// 切换分组的选择状态
const toggleGroupParams = (groupName: string) => {
  const group = paramGroups.value.find(g => g.name === groupName);
  if (!group) return;
  
  const isCurrentlySelected = isGroupSelected(groupName);
  
  if (isCurrentlySelected) {
    // 如果当前全选，则取消所有参数的选择
    group.params.forEach(param => {
      const index = selectedParamKeys.value.indexOf(param.key);
      if (index > -1) {
        selectedParamKeys.value.splice(index, 1);
      }
    });
  } else {
    // 如果当前未全选，则选择所有参数
    group.params.forEach(param => {
      if (!selectedParamKeys.value.includes(param.key)) {
        selectedParamKeys.value.push(param.key);
      }
    });
  }
};

// 更新参数值的方法
const parseNumericInput = (value: any): number => {
  if (value && typeof value === 'object' && 'target' in value) {
    const target = value.target as HTMLInputElement;
    return target.value === '' ? NaN : Number(target.value);
  }
  return value === '' ? NaN : Number(value);
};

// 监听算法变化
watch(selectedAlgorithm, (newAlgorithm) => {
  const key = newAlgorithm;
  if (!algorithmParams.value[key]) {
    // 使用 ALGO_CONFIGS 构建默认值
    const cfg = ALGO_CONFIGS[key];
    if (cfg) {
      const defaults: Record<string, any> = {};
      cfg.fields.forEach((field) => {
        defaults[field.key] = field.default;
      });
      if (key === 'grid') {
        defaults.grid_density = 10;
      }
      algorithmParams.value[key] = defaults;
    }
  }
  syncCommonControls(key);
});

// 监听通用参数变化并同步到对应算法配置（自动保存已在 composable 中处理）
watch(populationSize, (newValue) => {
  const key = selectedAlgorithm.value;
  const params = { ...(algorithmParams.value[key] || {}) };
  if (key === 'ga') params.pop_size = newValue;
  else if (key === 'pso') params.particle_count = newValue;
  else if (key === 'cmaes') params.population = newValue;
  else if (key === 'bayesian') params.random_init_points = newValue;
  else if (key === 'grid') params.grid_density = newValue;
  algorithmParams.value[key] = params;
});

watch(selectedStrategy, () => {
  fetchStrategyParams();
});

watch(maxIterations, (newValue) => {
  const key = selectedAlgorithm.value;
  const params = { ...(algorithmParams.value[key] || {}) };
  if (key === 'ga') params.generations = newValue;
  else if (key === 'pso') params.iterations = newValue;
  else if (key === 'cmaes') params.max_evaluations = newValue;
  else if (key === 'simulatedAnnealing') params.steps_per_temp = newValue;
  else if (key === 'bayesian') params.iterations = newValue;
  else if (key === 'grid') params.grid_density = newValue;
  algorithmParams.value[key] = params;
});

const updateAlgoField = (fieldKey: string, rawValue: any) => {
  const algoKey = selectedAlgorithm.value;
  const params = { ...(algorithmParams.value[algoKey] || {}) };
  const field = currentAlgoConfig.value?.fields.find(f => f.key === fieldKey);

  if (field?.type === 'select') {
    params[fieldKey] = rawValue;
  } else {
    const numeric = typeof rawValue === 'string' ? Number(rawValue) : rawValue;
    params[fieldKey] = Number.isNaN(numeric) ? rawValue : numeric;
  }

  algorithmParams.value[algoKey] = params;
  // 自动保存已在 composable 中处理
};

const robustnessLevel = (c: any): 'good' | 'medium' | 'bad' => {
  if (!c) return 'medium';
  const t = Number(c.score_train ?? 0);
  const v = Number(c.score_val ?? t);
  const gap = Math.abs(v - t);
  const scale = Math.max(Math.abs(t), 1);
  const r = scale === 0 ? 0 : gap / scale;
  if (r <= 0.1) return 'good';
  if (r <= 0.3) return 'medium';
  return 'bad';
};

const robustnessClass = (c: any): string => {
  const level = robustnessLevel(c);
  if (level === 'good') return 'text-emerald-400';
  if (level === 'medium') return 'text-amber-300';
  return 'text-rose-400';
};

const robustnessIcon = (c: any): string => {
  const level = robustnessLevel(c);
  if (level === 'good') return '🟢';
  if (level === 'medium') return '🟡';
  return '🔴';
};

const robustnessText = (c: any): string => {
  const level = robustnessLevel(c);
  if (level === 'good') return '稳健';
  if (level === 'medium') return '中等';
  return '疑似过拟合';
};

const buildSensitivityPoints = () => {
  const source = finalSelected.value || (candidates.value.length ? candidates.value[0] : null);
  if (!source) {
    sensitivityPoints.value = [];
    updateSensitivityChart();
    return;
  }
  const base = Number(source.score_train ?? 0);
  const deltas = [-0.2, -0.1, 0, 0.1, 0.2];
  sensitivityPoints.value = deltas.map((d) => ({
    value: d,
    score: base * (1 - 0.2 * Math.abs(d)),
  }));
  updateSensitivityChart();
};

// 更新敏感度折线图
function updateSensitivityChart() {
  if (!sensitivityChartContainer.value || sensitivityPoints.value.length === 0) {
    if (sensitivityChartInstance) {
      sensitivityChartInstance.dispose();
      sensitivityChartInstance = null;
    }
    return;
  }
  
  if (!sensitivityChartInstance) {
    sensitivityChartInstance = echarts.init(sensitivityChartContainer.value);
  }
  
  const xData = sensitivityPoints.value.map(p => `Δ${(p.value * 100).toFixed(0)}%`);
  const yData = sensitivityPoints.value.map(p => p.score);
  
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: {
      top: '10%',
      right: '5%',
      bottom: '15%',
      left: '10%',
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      textStyle: {
        color: '#f1f5f9',
        fontSize: 12
      },
      formatter: (params: any) => {
        const p = params[0];
        if (!p) return '';
        const index = p.dataIndex;
        const point = sensitivityPoints.value[index];
        if (!point) return '';
        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${p.name}</div>
            <div>参数变化: ${(point.value * 100).toFixed(0)}%</div>
            <div>目标得分: <span style="color: #10b981; font-weight: bold;">${point.score.toFixed(4)}</span></div>
          </div>
        `;
      }
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: {
        lineStyle: {
          color: '#334155'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11
      }
    },
    yAxis: {
      type: 'value',
      name: '目标得分',
      axisLine: {
        lineStyle: {
          color: '#334155'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11
      },
      nameTextStyle: {
        color: '#94a3b8',
        fontSize: 11
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.1)',
          type: 'dashed'
        }
      }
    },
    series: [{
      name: '目标得分',
      type: 'line',
      data: yData,
      smooth: true,
      lineStyle: {
        color: '#6366f1',
        width: 2
      },
      itemStyle: {
        color: '#6366f1',
        borderColor: '#fff',
        borderWidth: 2
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99, 102, 241, 0.3)' },
          { offset: 1, color: 'rgba(99, 102, 241, 0)' }
        ])
      },
      symbol: 'circle',
      symbolSize: 8,
      emphasis: {
        itemStyle: {
          color: '#8b5cf6',
          borderColor: '#fff',
          borderWidth: 3,
          shadowBlur: 10,
          shadowColor: '#6366f1'
        }
      }
    }],
    animationDuration: 500,
    animationEasing: 'cubicOut'
  };
  
  sensitivityChartInstance.setOption(option, { notMerge: true, lazyUpdate: false });
}

// 监听敏感度数据变化
watch(() => sensitivityPoints.value, () => {
  updateSensitivityChart();
}, { deep: true });

watch(() => showSensitivity.value, (newVal) => {
  if (newVal) {
    nextTick(() => {
      updateSensitivityChart();
    });
  }
});

const openCandidateDetail = (c: any) => {
  candidateDetail.value = c;
};

const closeCandidateDetail = () => {
  candidateDetail.value = null;
};

const isDateRangeValid = computed(() => {
  if (!trainStartDate.value && !valStartDate.value && !testStartDate.value) {
    return true;
  }
  const toNum = (d: string) => (d ? Number(d.replace(/-/g, '')) : NaN);
  const ts = toNum(trainStartDate.value || startDate.value);
  const te = toNum(trainEndDate.value || endDate.value);
  const vs = valStartDate.value ? toNum(valStartDate.value) : NaN;
  const ve = valEndDate.value ? toNum(valEndDate.value) : NaN;
  const ss = testStartDate.value ? toNum(testStartDate.value) : NaN;
  const se = testEndDate.value ? toNum(testEndDate.value) : NaN;

  if (!(ts <= te)) return false;
  if (!Number.isNaN(vs) && !Number.isNaN(ve)) {
    if (!(te <= vs && vs <= ve)) return false;
  }
  if (!Number.isNaN(ss) && !Number.isNaN(se)) {
    const left = !Number.isNaN(ve) ? ve : te;
    if (!(left <= ss && ss <= se)) return false;
  }
  return true;
});

// 计算总日期范围（用于90天验证）
const totalDateRangeDays = computed(() => {
  if (!startDate.value || !endDate.value) return 0;
  const start = new Date(startDate.value);
  const end = new Date(endDate.value);
  const diffTime = end.getTime() - start.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
});

// 检查日期范围是否满足90天最小要求
const isDateRangeSufficient = computed(() => {
  return totalDateRangeDays.value >= 90;
});

const dateRangeWarning = computed(() => {
  if (totalDateRangeDays.value === 0) return '';
  if (totalDateRangeDays.value < 90) {
    return '优化需要至少3个月（90天）的数据才能产生有效结果。';
  }
  return '';
});

const canStartOptimization = computed(() => {
  if (!isDateRangeValid.value) return false;
  if (!isDateRangeSufficient.value) return false; // 添加90天验证
  return (
    selectedParamKeys.value.length > 0 &&
    !isOptimizing.value &&
    selectedStrategy.value &&
    startDate.value &&
    endDate.value
  );
});

const showError = (msg: string) => {
  errorMessage.value = msg;
  setTimeout(() => {
    if (errorMessage.value === msg) errorMessage.value = '';
  }, 6000);
};

const showSuccess = (msg: string) => {
  successMessage.value = msg;
  setTimeout(() => {
    if (successMessage.value === msg) successMessage.value = '';
  }, 4000);
};

const showConfirmationDialog = (
  title: string,
  message: string,
  confirmAction: () => void,
  cancelAction: () => void = () => {},
) => {
  confirmationDialog.value = {
    visible: true,
    title,
    message,
    confirmAction,
    cancelAction,
  };
};

const confirmDialog = () => {
  confirmationDialog.value.confirmAction();
  confirmationDialog.value.visible = false;
};

const cancelDialog = () => {
  confirmationDialog.value.cancelAction();
  confirmationDialog.value.visible = false;
};

const toggleAllParams = () => {
  if (isAllSelected.value) {
    selectedParamKeys.value = [];
  } else {
    selectedParamKeys.value = availableParams.value.map((p) => p.key);
  }
};

const startOptimization = () => {
  if (!canStartOptimization.value) {
    if (!isDateRangeValid.value) {
      showError('三段区间顺序或重叠不合法，请检查训练/验证/测试日期设置。');
    }
    return;
  }

  showConfirmationDialog(
    '确认开始优化',
    `将对 ${selectedParamKeys.value.length} 个参数进行优化（模式：${optimizationMode.value}）。`,
    () => {
      const method = currentAlgoConfig.value?.method || 'ga';
      const algoParamPayload = algorithmParams.value[selectedAlgorithm.value] || {};

      const searchSpace = availableParams.value
        .filter((p: any) => selectedParamKeys.value.includes(p.key))
        .map((p: any) => {
          const range = paramRangeValues.value[p.key] || { min: p.min, max: p.max };
          return {
            name: p.key,
            type: p.type || 'float',
            min: range.min,
            max: range.max,
          };
        });

      const metricMap: Record<string, string> = {
        sharpeRatio: 'sharpe',
        totalReturn: 'returns',
        maxDrawdown: 'max_drawdown',
        calmarRatio: 'calmar',
      };

      const optimizationPayload = {
        task_id: `opt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        strategy_name: selectedStrategy.value,
        optimization_engine: {
          method,
          params: algoParamPayload,
        },
        search_space: searchSpace,
        objective: {
          target: optimizationObjective.value,
          metric: metricMap[selectedMetric.value] || selectedMetric.value,
          constraints: {},
        },
        backtest: {
          start_date: startDate.value,
          end_date: endDate.value,
          train_start_date: trainStartDate.value || startDate.value,
          train_end_date: trainEndDate.value || endDate.value,
          val_start_date: valStartDate.value || '',
          val_end_date: valEndDate.value || '',
          test_start_date: testStartDate.value || '',
          test_end_date: testEndDate.value || '',
        },
        validation: {
          enabled: true,
          mode: optimizationMode.value,
        },
        mode: optimizationMode.value,
        enabled_params: [...selectedParamKeys.value],
      };

      startOpt(optimizationPayload);
      showSuccess('优化已开始');
    },
  );
};

const stopOptimization = () => {
  if (!isOptimizing.value) return;
  showConfirmationDialog(
    '确认停止优化',
    '正在进行的优化将会被中止，是否继续？',
    () => {
      stopOpt();
    },
  );
};

// Socket 监听已移到 useOptimization composable

onMounted(() => {
  // 初始化敏感度图表
  nextTick(() => {
    if (showSensitivity.value && sensitivityChartContainer.value) {
      updateSensitivityChart();
    }
  });
  applyInitialDates();
  fetchStrategies();
  loadAlgorithmParams();
  syncCommonControls();

  setupSocketListeners({
    onComplete: () => {
      buildSensitivityPoints();
    },
    onError: (data: any) => {
      showError(data?.message || '优化过程中出现错误');
    },
  });
});

onUnmounted(() => {
  if (sensitivityChartInstance) {
    sensitivityChartInstance.dispose();
    sensitivityChartInstance = null;
  }
  cleanupOptimization();
});

</script>

<template>
  <div class="p-6 space-y-6 max-w-[1800px] mx-auto">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
            <i class="fas fa-dna text-white"></i>
          </div>
          参数智能优化
        </h1>
        <p class="text-slate-400 mt-1">通过多区间稳健性与智能搜索，找到更抗过拟合的参数组合。</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 hover:text-white"
          @click="stopOptimization"
          :disabled="!isOptimizing"
        >
          停止优化
        </button>
        <div class="flex flex-col items-end gap-2">
          <button
            class="rounded-2xl bg-gradient-to-r from-indigo-500 to-purple-600 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/30 disabled:opacity-60 disabled:cursor-not-allowed"
            @click="startOptimization"
            :disabled="!canStartOptimization"
          >
            {{ isOptimizing ? '优化进行中...' : '开始优化' }}
          </button>
          <p v-if="dateRangeWarning" class="text-xs text-amber-400 max-w-xs text-right">
            {{ dateRangeWarning }}
          </p>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      <section class="space-y-6">
        <div class="rounded-3xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl shadow-black/30">
          <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-white/5 pb-4">
            <div>
              <h2 class="text-xl font-semibold text-slate-100">基础设置</h2>
              <p class="text-sm text-slate-400">选择策略、时间区间与算法，定义优化目标与模式。</p>
            </div>
          </div>

          <div class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <label class="space-y-2 text-sm">
              <span class="text-slate-300">选择策略</span>
              <select
                v-model="selectedStrategy"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option value="" disabled>请选择策略</option>
                <option v-for="s in availableStrategies" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </label>

            <label class="space-y-2 text-sm">
              <span class="text-slate-300">主回测开始日期</span>
              <input
                type="date"
                v-model="startDate"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              />
            </label>

            <label class="space-y-2 text-sm">
              <span class="text-slate-300">主回测结束日期</span>
              <input
                type="date"
                v-model="endDate"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              />
            </label>

            <label class="space-y-2 text-sm">
              <span class="text-slate-300">优化算法</span>
              <select
                v-model="selectedAlgorithm"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option value="ga">遗传算法</option>
                <option value="pso">粒子群优化</option>
                <option value="cmaes">CMA-ES</option>
                <option value="simulatedAnnealing">模拟退火</option>
                <option value="grid">网格搜索</option>
                <option value="bayesian">贝叶斯优化</option>
              </select>
            </label>


            <label class="space-y-2 text-sm">
              <span class="text-slate-300">回测指标</span>
              <select
                v-model="selectedMetric"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option value="sharpeRatio">夏普比率</option>
                <option value="totalReturn">总收益率</option>
                <option value="maxDrawdown">最大回撤</option>
                <option value="calmarRatio">Calmar 比率</option>
              </select>
            </label>

            <label class="space-y-2 text-sm">
              <span class="text-slate-300">优化模式</span>
              <select
                v-model="optimizationMode"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option value="quick_explore">快速探索模式（仅训练区）</option>
                <option value="robust">稳健优化模式（训练+验证）【推荐】</option>
                <option value="aggressive">高风险最大化（仅训练区）⚠</option>
              </select>
            </label>

            <label class="space-y-2 text-sm">
              <span class="text-slate-300">优化目标</span>
              <select
                v-model="optimizationObjective"
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option value="robust_trend_score">稳健收益比（趋势策略默认）</option>
                <option value="rr_risk_score">风险调整盈亏比（低胜率策略专用）</option>
                <option value="multi_period_robust">多周期稳健性</option>
                <option value="calmar">Calmar 比率</option>
                <option value="sharpe">夏普比率（传统，可能不适合主升浪）</option>
              </select>
            </label>
          </div>

          <div class="mt-6 rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4 space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-sm font-medium text-slate-200">优化区间设置（防过拟合）</h3>
                <p class="text-xs text-slate-400">建议拆分训练 / 验证 / 测试三段区间，评估参数稳定性。</p>
              </div>
              <span
                class="text-xs font-medium px-2 py-1 rounded-full border"
                :class="isDateRangeValid ? 'border-emerald-500/60 text-emerald-300' : 'border-rose-500/60 text-rose-300'"
              >
                {{ isDateRangeValid ? '区间合法' : '区间有冲突' }}
              </span>
            </div>

            <!-- 三段式时间轴滑块 -->
            <ThreeSegmentTimeSlider
              :start-date="startDate"
              :end-date="endDate"
              :train-start-date="trainStartDate"
              :train-end-date="trainEndDate"
              :val-start-date="valStartDate"
              :val-end-date="valEndDate"
              :test-start-date="testStartDate"
              :test-end-date="testEndDate"
              @update:train-start-date="trainStartDate = $event"
              @update:train-end-date="trainEndDate = $event"
              @update:val-start-date="valStartDate = $event"
              @update:val-end-date="valEndDate = $event"
              @update:test-start-date="testStartDate = $event"
              @update:test-end-date="testEndDate = $event"
            />
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl shadow-black/30">
          <div class="flex flex-col gap-3 border-b border-white/5 pb-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 class="text-xl font-semibold text-slate-100">算法引擎配置</h2>
              <p class="text-sm text-slate-400">根据所选算法微调引擎参数。</p>
              <p v-if="algorithmSummary" class="mt-1 text-xs text-indigo-300/80">{{ algorithmSummary }}</p>
            </div>
          </div>

          <div class="mt-6">
            <div v-if="selectedAlgorithm === 'grid'" class="space-y-4">
              <div class="bg-blue-900/20 rounded-xl border border-blue-800/30 p-4 text-xs text-blue-100">
                网格搜索不需要单独配置引擎参数，请在下方“可优化参数”区域设置每个参数的搜索范围。
              </div>
            </div>
            <div v-else-if="currentAlgoConfig && currentAlgoConfig.fields.length" class="space-y-4">
              <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div v-for="field in currentAlgoConfig.fields" :key="field.key" class="space-y-1 text-sm">
                  <label class="text-slate-300">{{ field.label }}</label>
                  <input
                    v-if="field.type === 'int' || field.type === 'float'"
                    :type="'number'"
                    :step="field.step ?? (field.type === 'float' ? 0.01 : 1)"
                    :min="field.min"
                    :max="field.max"
                    :value="currentAlgoParams[field.key] ?? field.default"
                    @input="updateAlgoField(field.key, ($event.target as HTMLInputElement).value)"
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                  />
                  <select
                    v-else-if="field.type === 'select' && field.options"
                    :value="currentAlgoParams[field.key] ?? field.default"
                    @change="updateAlgoField(field.key, ($event.target as HTMLSelectElement).value)"
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                  >
                    <option
                      v-for="option in field.options"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
            <div v-else class="py-8 text-center text-sm text-slate-500">
              请选择优化算法以显示配置选项。
            </div>
          </div>
        </div>

        <details class="group rounded-3xl border border-slate-800/80 bg-slate-900/60 shadow-xl shadow-black/30 overflow-hidden open:bg-slate-900/80 transition-all">
          <summary class="flex cursor-pointer items-center justify-between p-6 transition hover:bg-slate-800/50 list-none select-none">
            <div class="flex items-center gap-3">
              <h2 class="text-xl font-semibold text-slate-100">高级设置</h2>
              <span class="text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded-md group-open:hidden">包含搜索空间与多样性配置</span>
            </div>
            <div class="flex items-center gap-4">
               <p class="hidden text-sm text-slate-400 group-open:block">控制搜索空间与解的多样性，防止过拟合。</p>
               <span class="text-slate-400 transition-transform duration-200 group-open:rotate-180">▼</span>
            </div>
          </summary>

          <div class="border-t border-white/5 p-6 pt-0">
            <div class="mb-6 flex flex-col gap-3 border-b border-white/5 py-4 md:flex-row md:items-center md:justify-between">
              <div>
                 <h3 class="text-sm font-medium text-slate-200">多样性控制</h3>
              </div>
              <label class="inline-flex items-center gap-3 text-sm text-slate-300">
                <span class="text-slate-400">启用参数多样性</span>
                <input
                  type="checkbox"
                  v-model="enableDiversity"
                  class="h-5 w-10 cursor-pointer rounded-full border border-slate-600 bg-slate-800 checked:bg-gradient-to-r checked:from-indigo-500 checked:to-purple-500"
                />
              </label>
            </div>

            <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <label class="space-y-2 text-sm">
                <span class="text-slate-300">多样性阈值</span>
                <input
                  type="number"
                  v-model.number="diversityThreshold"
                  min="0"
                  max="1"
                  step="0.01"
                  class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                />
                <span class="text-xs text-slate-500">参数向量平均差异需达到该比例才视为有效多样体。</span>
              </label>

              <label class="space-y-2 text-sm">
                <span class="text-slate-300">最大多样化结果数</span>
                <input
                  type="number"
                  v-model.number="maxDiverseResults"
                  min="1"
                  class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                />
                <span class="text-xs text-slate-500">保留的多样性样本数量，用于后续对比与候选推送。</span>
              </label>
            </div>
          </div>
        </details>

        <div class="rounded-3xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl shadow-black/30">
          <div class="flex flex-col gap-3 border-b border-white/5 pb-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 class="text-xl font-semibold text-slate-100">可优化参数</h2>
              <p class="text-sm text-slate-400">最多同时优化 {{ MAX_OPTIMIZABLE_PARAMS }} 个参数，避免严重过拟合。</p>
            </div>
            <label class="inline-flex items-center gap-3 text-sm text-slate-300">
              <input
                type="checkbox"
                :checked="isAllSelected"
                @change="toggleAllParams"
                class="h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500"
              />
              <span>全选 / 取消</span>
            </label>
          </div>

          <div v-if="isLoadingParams" class="mt-6 space-y-3">
            <div
              v-for="n in 4"
              :key="n"
              class="animate-pulse rounded-2xl border border-slate-800/60 bg-slate-900/40 p-4"
            >
              <div class="h-4 w-1/3 rounded bg-slate-800/80"></div>
              <div class="mt-3 grid grid-cols-3 gap-3">
                <div class="h-3 rounded bg-slate-800/70"></div>
                <div class="h-3 rounded bg-slate-800/70"></div>
                <div class="h-3 rounded bg-slate-800/70"></div>
              </div>
            </div>
          </div>
          <div
            v-else-if="!availableParams.length"
            class="mt-6 rounded-2xl border border-dashed border-slate-700/80 bg-slate-900/30 p-6 text-center text-sm text-slate-400"
          >
            {{ selectedStrategy ? '该策略暂无可优化参数' : '请选择策略以加载可优化参数' }}
          </div>
          <div v-else class="mt-6 space-y-6">
            <div
              v-for="group in paramGroups"
              :key="group.name"
              class="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 shadow-inner shadow-black/30"
            >
              <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="text-sm uppercase tracking-[0.25em] text-indigo-400/70">{{ group.displayName }}</p>
                  <p class="text-xs text-slate-500">
                    {{ getSelectedCountInGroup(group.name) }}/{{ group.params.length }} selected
                  </p>
                </div>
                <label class="inline-flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    :checked="isGroupSelected(group.name)"
                    @change="toggleGroupParams(group.name)"
                    class="h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500"
                  />
                  <span>Toggle group</span>
                </label>
              </div>

              <div class="space-y-6">
                <div
                  v-for="param in group.params"
                  :key="param.key"
                  class="rounded-2xl border border-slate-800/70 bg-gradient-to-br from-slate-950/60 to-slate-900/40 p-5 shadow-lg transition hover:border-indigo-500/60 hover:shadow-indigo-500/10"
                >
                  <div class="flex items-center justify-between mb-4">
                    <label class="inline-flex items-center gap-3 text-base font-semibold text-slate-100">
                      <input
                        type="checkbox"
                        :value="param.key"
                        v-model="selectedParamKeys"
                        class="h-5 w-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-2 focus:ring-indigo-500"
                      />
                      <span>{{ getParamLabel(param) }}</span>
                      <span class="text-xs font-normal text-slate-400 font-mono">({{ param.key }})</span>
                    </label>
                    <button
                      @click="paramLocked[param.key] = !paramLocked[param.key]"
                      :class="[
                        'px-3 py-1.5 rounded-lg text-xs font-medium transition',
                        paramLocked[param.key]
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50'
                          : 'bg-slate-800/50 text-slate-400 border border-slate-700/50 hover:bg-slate-700/50',
                      ]"
                    >
                      {{ paramLocked[param.key] ? '🔒 已锁定' : '🔓 未锁定' }}
                    </button>
                  </div>

                  <div class="mb-4">
                    <div class="flex items-center justify-between mb-2 text-sm">
                      <div class="flex flex-col">
                        <span class="text-slate-200 font-semibold">
                          {{ getParamLabel(param) }}
                        </span>
                        <span class="text-xs text-slate-500 font-mono">({{ param.key }})</span>
                      </div>
                      <div class="text-xs text-slate-400">
                        <span>当前区间：</span>
                        <span class="font-mono text-indigo-300">
                          {{ formatParamDisplayValue(param.key, paramRangeValues[param.key]?.min ?? param.min) }}{{ getParamUnit(param.key) || param.unit || '' }}
                        </span>
                        <span class="mx-1 text-slate-500">~</span>
                        <span class="font-mono text-purple-300">
                          {{ formatParamDisplayValue(param.key, paramRangeValues[param.key]?.max ?? param.max) }}{{ getParamUnit(param.key) || param.unit || '' }}
                        </span>
                      </div>
                    </div>

                    <!-- 使用配置表控制的滑块参数 -->
                    <div v-if="CUSTOM_PARAM_CONFIG[param.key]?.useSlider" class="mt-4">
                      <RangeSlider
                                  :label="getParamLabel(param)"
                                  :unit="getParamUnit(param.key) || param.unit || '亿'"
                                  
                                  :absolute-min="Math.max(0.01, toUiValue(param.key, param.min) || 0.01)"
                                  :absolute-max="toUiValue(param.key, param.max) || 100"
                                  
                                  :min-value="Math.max(0.01, toUiValue(param.key, paramRangeValues[param.key]?.min) || 0.01)"
                                  :max-value="Math.max(0.01, toUiValue(param.key, paramRangeValues[param.key]?.max) || 100)"
                                  
                                  :step="CUSTOM_PARAM_CONFIG[param.key]?.step ?? 0.01"
                                  :locked="paramLocked[param.key]"
                                  :use-log-scale="CUSTOM_PARAM_CONFIG[param.key]?.useLogScale ?? false"
                                  
                                  @update:min-value="(v) => { 
                                    const safeV = Math.max(0.0001, v); 
                                    const backendVal = toBackendValue(param.key, safeV) || 0;
                                    // 修复：增加 || { min: 0, max: 0 } 兜底，消除 TS 类型错误
                                    const oldVal = paramRangeValues[param.key] || { min: 0, max: 0 };
                                    paramRangeValues[param.key] = { 
                                      ...oldVal, 
                                      min: backendVal 
                                    }; 
                                  }"
                                  @update:max-value="(v) => { 
                                    const safeV = Math.max(0.0001, v);
                                    const backendVal = toBackendValue(param.key, safeV) || 0;
                                    // 修复：增加 || { min: 0, max: 0 } 兜底，消除 TS 类型错误
                                    const oldVal = paramRangeValues[param.key] || { min: 0, max: 0 };
                                    paramRangeValues[param.key] = { 
                                      ...oldVal, 
                                      max: backendVal 
                                    }; 
                                  }"
                                />
                    </div>
                    <!-- 其他参数使用数字输入框 -->
                    <div v-else class="mt-2 flex justify-between items-center text-[10px] text-[#94a3b8] font-mono">
                      <span>
                        {{ formatParamDisplayValue(param.key, paramRangeValues[param.key]?.min ?? param.min) }}{{ getParamUnit(param.key) || param.unit || '' }}
                      </span>
                      <div class="flex items-center gap-2 text-[11px]">
                        <input
                          type="number"
                          class="w-20 rounded border border-slate-700 bg-slate-900/80 px-2 py-1 text-[11px] text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                          :value="formatParamDisplayValue(param.key, paramRangeValues[param.key]?.min ?? param.min)"
                          @change="(e) => {
                            const backendVal = Number(toBackendValue(param.key, Number((e.target as HTMLInputElement).value || 0)) || 0);
                            const existing = paramRangeValues[param.key];
                            const currentMax = existing?.max ?? param.max ?? 1000000;
                            paramRangeValues[param.key] = {
                              min: Math.max(param.min || 0, Math.min(backendVal, currentMax - 1)),
                              max: currentMax
                            };
                          }"
                        />
                        <span class="text-slate-500">~</span>
                        <input
                          type="number"
                          class="w-20 rounded border border-slate-700 bg-slate-900/80 px-2 py-1 text-[11px] text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                          :value="formatParamDisplayValue(param.key, paramRangeValues[param.key]?.max ?? param.max)"
                          @change="(e) => {
                            const backendVal = Number(toBackendValue(param.key, Number((e.target as HTMLInputElement).value || 0)) || 0);
                            const existing = paramRangeValues[param.key];
                            const currentMin = existing?.min ?? param.min ?? 0;
                            paramRangeValues[param.key] = {
                              min: currentMin,
                              max: Math.min(param.max || 1000000, Math.max(backendVal, currentMin + 1))
                            };
                          }"
                        />
                      </div>
                      <span class="text-slate-500 text-[10px]">{{ param.unit || '' }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-3xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl shadow-black/30">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-xl font-semibold text-slate-100">关键参数敏感度分析</h2>
              <p class="text-sm text-slate-400">观察关键参数小幅变化对目标得分的影响。</p>
            </div>
            <button
              class="text-xs text-indigo-400 hover:text-indigo-300"
              @click="() => { showSensitivity = !showSensitivity; if (showSensitivity && !sensitivityParamKey && selectedParamKeys.length) sensitivityParamKey = selectedParamKeys[0]; buildSensitivityPoints(); }"
            >
              {{ showSensitivity ? '收起' : '展开' }}
            </button>
          </div>
          <div v-if="showSensitivity" class="mt-4 space-y-4">
            <div class="rounded-lg border border-slate-700/50 bg-slate-950/40 p-3 text-xs text-slate-400">
              <p class="font-semibold text-slate-300 mb-1">💡 检测过拟合</p>
              <p>观察参数小幅变动时策略表现的稳定性。如果曲线剧烈抖动，说明策略可能过拟合；如果曲线平缓，说明策略稳健。</p>
            </div>
            <div class="flex items-center gap-3 text-sm">
              <span class="text-slate-300">关键参数</span>
              <select
                v-model="sensitivityParamKey"
                @change="buildSensitivityPoints()"
                class="flex-1 rounded-2xl border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              >
                <option
                  v-for="key in selectedParamKeys"
                  :key="key"
                  :value="key"
                >
                  {{ key }}
                </option>
              </select>
            </div>
            <!-- 折线图 -->
            <div v-if="sensitivityPoints.length" class="h-64">
              <div ref="sensitivityChartContainer" class="w-full h-full"></div>
            </div>
            <div v-else class="text-xs text-slate-500 text-center py-8">
              请选择关键参数并点击展开，即可查看稳健性曲线。
            </div>
          </div>
        </div>
      </section>

      <section class="space-y-6">
        <div class="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-xl shadow-black/40">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-xl font-semibold text-slate-100">运行状态</h2>
              <p class="text-sm text-slate-400">实时跟踪优化引擎进度与当前最佳表现。</p>
            </div>
            <span
              class="rounded-full border border-slate-800 px-3 py-1 text-xs uppercase tracking-wide"
              :class="{
                'border-emerald-500/50 text-emerald-300/90': optimizationStatus === 'finished',
                'border-amber-500/50 text-amber-300/90': optimizationStatus === 'starting' || optimizationStatus === 'running',
                'border-rose-500/50 text-rose-300/90': optimizationStatus === 'error',
              }"
            >
              {{ 
                optimizationStatus === 'finished' ? '已完成' :
                optimizationStatus === 'starting' ? '启动中' :
                optimizationStatus === 'running' ? '运行中' :
                optimizationStatus === 'error' ? '出错' : '空闲'
              }}
            </span>
          </div>

          <!-- KPI Cards -->
          <div class="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div class="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 flex flex-col justify-between hover:border-indigo-500/30 transition-colors">
              <div class="text-xs text-slate-500 font-medium uppercase tracking-wider">综合得分</div>
              <div class="mt-2 text-xl font-bold font-mono">
                <span v-if="bestMetric !== null && isValidScore(bestMetric)" class="text-indigo-400">
                  {{ formatScore(bestMetric) }}
                </span>
                <span v-else-if="bestMetric !== null" class="px-2 py-1 rounded text-sm bg-rose-500/20 text-rose-400 border border-rose-500/50">
                  无效
                </span>
                <span v-else class="text-slate-500">—</span>
              </div>
            </div>
            <div class="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 flex flex-col justify-between hover:border-red-500/30 transition-colors">
              <div class="text-xs text-slate-500 font-medium uppercase tracking-wider">训练收益</div>
              <div class="mt-2 text-xl font-bold font-mono" :class="((finalSelected?.train_metrics?.totalReturn ?? finalSelected?.train_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                 {{ (finalSelected?.train_metrics?.totalReturn !== undefined && finalSelected?.train_metrics?.totalReturn !== null) || (finalSelected?.train_metrics?.total_return !== undefined && finalSelected?.train_metrics?.total_return !== null) ? formatPercent(finalSelected.train_metrics.totalReturn ?? finalSelected.train_metrics.total_return) : '—' }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 flex flex-col justify-between hover:border-rose-500/30 transition-colors">
              <div class="text-xs text-slate-500 font-medium uppercase tracking-wider">验证回撤</div>
              <div class="mt-2 text-xl font-bold text-rose-400 font-mono">
                 {{ finalSelected?.val_metrics?.max_drawdown ? formatPercent(finalSelected.val_metrics.max_drawdown) : '—' }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 flex flex-col justify-between hover:border-amber-500/30 transition-colors">
              <div class="text-xs text-slate-500 font-medium uppercase tracking-wider">盈亏比</div>
              <div class="mt-2 text-xl font-bold text-amber-400 font-mono">
                 {{ finalSelected?.train_metrics?.profit_factor ? formatNumber(finalSelected.train_metrics.profit_factor) : '—' }}
              </div>
            </div>
          </div>

          <dl class="mt-6 grid grid-cols-2 gap-4 text-sm text-slate-300 sm:grid-cols-4">
            <div class="flex flex-col gap-1 rounded-xl border border-slate-800/50 bg-slate-950/20 px-4 py-3">
              <dt class="text-xs text-slate-500">当前策略</dt>
              <dd class="font-semibold text-slate-200 truncate" :title="selectedStrategy">
                {{ selectedStrategy || '未选择' }}
              </dd>
            </div>
            <div class="flex flex-col gap-1 rounded-xl border border-slate-800/50 bg-slate-950/20 px-4 py-3">
              <dt class="text-xs text-slate-500">优化算法</dt>
              <dd class="font-semibold text-slate-200">{{ currentAlgoConfig?.label || selectedAlgorithm.toUpperCase() }}</dd>
            </div>
            <div class="flex flex-col gap-1 rounded-xl border border-slate-800/50 bg-slate-950/20 px-4 py-3">
              <dt class="text-xs text-slate-500">优化目标</dt>
              <dd class="font-semibold text-slate-200 truncate">
                {{ 
                  optimizationObjective === 'robust_trend_score' ? '稳健收益比' :
                  optimizationObjective === 'rr_risk_score' ? '风险调整盈亏比' :
                  optimizationObjective === 'multi_period_robust' ? '多周期稳健性' :
                  optimizationObjective === 'calmar' ? 'Calmar 比率' :
                  optimizationObjective === 'sharpe' ? '夏普比率' : optimizationObjective
                }}
              </dd>
            </div>
            <div class="flex flex-col gap-1 rounded-xl border border-slate-800/50 bg-slate-950/20 px-4 py-3">
              <dt class="text-xs text-slate-500">评估进度</dt>
              <dd class="font-semibold text-slate-200 font-mono">
                {{ evaluatedCount }} <span class="text-slate-500 text-xs font-normal">/ {{ totalIterations || '∞' }}</span>
              </dd>
            </div>
          </dl>

          <OptimizationVisualizer
            :optimizer="selectedAlgorithm"
            :progress="progress"
            :iteration="evaluatedCount"
            :total-iterations="totalIterations"
            :best-score="bestMetric"
            :history="optimizationHistory"
            metric-label="得分"
          />

          <div class="mt-6 space-y-2">
            <div class="flex items-center justify-between text-xs text-slate-400">
              <span>总体进度</span>
              <span>{{ Math.round(progress) }}%</span>
            </div>
            <div class="h-2 w-full overflow-hidden rounded-full bg-slate-800/70">
              <div
                class="h-full rounded-full bg-gradient-to-r from-indigo-500 via-sky-500 to-emerald-400 transition-all duration-300 shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                :style="{ width: `${Math.max(progress, isOptimizing ? 2 : 0)}%` }"
              ></div>
            </div>
          </div>

          <!-- Final Results / Best So Far -->
          <div v-if="finalSelected || bestParams" class="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.5fr]">
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <p class="text-sm font-medium text-slate-300">最佳参数组合</p>
                <span class="text-xs text-slate-500 font-mono">ID: {{ finalSelected?.run_id || 'current' }}</span>
              </div>
              <div class="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                <div class="flex flex-wrap gap-2">
                  <div
                    v-for="(val, key) in (finalSelected?.params || bestParams || {})"
                    :key="key"
                    class="flex items-center gap-2 rounded-lg bg-slate-900/70 px-3 py-1.5 border border-slate-800/80 hover:border-slate-700/80 transition-colors"
                  >
                    <span class="text-slate-400 text-[11px]">{{ getParamLabel({ key, label: key }) }}</span>
                    <span class="text-xs font-mono text-indigo-300 font-medium">
                      {{ formatParamDisplayValue(key, val) }}{{ getParamUnit(key) || '' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="space-y-3">
              <p class="text-sm font-medium text-slate-300">三段区间表现对比</p>
              <div class="rounded-2xl border border-slate-800/70 bg-slate-950/40 overflow-hidden">
                <table class="w-full text-xs text-slate-200 whitespace-nowrap">
                  <thead>
                    <tr class="bg-slate-900/50 border-b border-slate-800/60 text-slate-400">
                      <th class="py-3 px-4 text-left font-medium">指标</th>
                      <th class="py-3 px-4 text-right font-medium">训练集 (Train)</th>
                      <th class="py-3 px-4 text-right font-medium border-l border-slate-800/50">验证集 (Val)</th>
                      <th class="py-3 px-4 text-right font-medium border-l border-slate-800/50">测试集 (Test)</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-800/40">
                    <tr class="hover:bg-slate-800/20 transition-colors">
                      <td class="py-2.5 px-4 text-slate-400">期间收益</td>
                      <td class="py-2.5 px-4 text-right font-mono font-medium" :class="((finalSelected?.train_metrics?.totalReturn ?? finalSelected?.train_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                        {{ (finalSelected?.train_metrics?.totalReturn !== undefined && finalSelected?.train_metrics?.totalReturn !== null) || (finalSelected?.train_metrics?.total_return !== undefined && finalSelected?.train_metrics?.total_return !== null) ? formatPercent(finalSelected.train_metrics.totalReturn ?? finalSelected.train_metrics.total_return) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono font-medium border-l border-slate-800/50" :class="((finalSelected?.val_metrics?.totalReturn ?? finalSelected?.val_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                        {{ (finalSelected?.val_metrics?.totalReturn !== undefined && finalSelected?.val_metrics?.totalReturn !== null) || (finalSelected?.val_metrics?.total_return !== undefined && finalSelected?.val_metrics?.total_return !== null) ? formatPercent(finalSelected.val_metrics.totalReturn ?? finalSelected.val_metrics.total_return) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono font-medium border-l border-slate-800/50" :class="((finalSelected?.test_metrics?.totalReturn ?? finalSelected?.test_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                        {{ (finalSelected?.test_metrics?.totalReturn !== undefined && finalSelected?.test_metrics?.totalReturn !== null) || (finalSelected?.test_metrics?.total_return !== undefined && finalSelected?.test_metrics?.total_return !== null) ? formatPercent(finalSelected.test_metrics.totalReturn ?? finalSelected.test_metrics.total_return) : '—' }}
                      </td>
                    </tr>
                    <tr class="hover:bg-slate-800/20 transition-colors">
                      <td class="py-2.5 px-4 text-slate-400">最大回撤</td>
                      <td class="py-2.5 px-4 text-right font-mono text-rose-300">
                        {{ finalSelected?.train_metrics?.max_drawdown ? formatPercent(finalSelected.train_metrics.max_drawdown) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono text-rose-300 border-l border-slate-800/50">
                        {{ finalSelected?.val_metrics?.max_drawdown ? formatPercent(finalSelected.val_metrics.max_drawdown) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono text-rose-300 border-l border-slate-800/50">
                        {{ finalSelected?.test_metrics?.max_drawdown ? formatPercent(finalSelected.test_metrics.max_drawdown) : '—' }}
                      </td>
                    </tr>
                    <tr class="hover:bg-slate-800/20 transition-colors">
                      <td class="py-2.5 px-4 text-slate-400">盈亏比</td>
                      <td class="py-2.5 px-4 text-right font-mono">
                        {{ finalSelected?.train_metrics?.profit_factor ? formatNumber(finalSelected.train_metrics.profit_factor) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                        {{ finalSelected?.val_metrics?.profit_factor ? formatNumber(finalSelected.val_metrics.profit_factor) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                        {{ finalSelected?.test_metrics?.profit_factor ? formatNumber(finalSelected.test_metrics.profit_factor) : '—' }}
                      </td>
                    </tr>
                    <tr class="hover:bg-slate-800/20 transition-colors">
                      <td class="py-2.5 px-4 text-slate-400">夏普比率</td>
                      <td class="py-2.5 px-4 text-right font-mono">
                        {{ finalSelected?.train_metrics?.sharpe ? formatNumber(finalSelected.train_metrics.sharpe) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                        {{ finalSelected?.val_metrics?.sharpe ? formatNumber(finalSelected.val_metrics.sharpe) : '—' }}
                      </td>
                      <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                        {{ finalSelected?.test_metrics?.sharpe ? formatNumber(finalSelected.test_metrics.sharpe) : '—' }}
                      </td>
                    </tr>
                    <tr class="bg-slate-800/30 font-semibold">
                      <td class="py-3 px-4 text-indigo-200">综合得分</td>
                      <td class="py-3 px-4 text-right font-mono">
                        <span v-if="isValidScore(finalSelected?.train_metrics?.composite_score ?? finalSelected?.score_train)" class="text-indigo-300">
                          {{ finalSelected?.train_metrics?.composite_score ? formatScore(finalSelected.train_metrics.composite_score) : (finalSelected ? formatScore(finalSelected.score_train) : '—') }}
                        </span>
                        <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      </td>
                      <td class="py-3 px-4 text-right font-mono border-l border-slate-800/50">
                        <span v-if="isValidScore(finalSelected?.val_metrics?.composite_score ?? finalSelected?.score_val)" class="text-indigo-300">
                          {{ finalSelected?.val_metrics?.composite_score ? formatScore(finalSelected.val_metrics.composite_score) : (finalSelected ? formatScore(finalSelected.score_val) : '—') }}
                        </span>
                        <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      </td>
                      <td class="py-3 px-4 text-right font-mono border-l border-slate-800/50">
                        <span v-if="isValidScore(finalSelected?.test_metrics?.composite_score ?? finalSelected?.score_test)" class="text-indigo-300">
                          {{ finalSelected?.test_metrics?.composite_score ? formatScore(finalSelected.test_metrics.composite_score) : (finalSelected ? formatScore(finalSelected.score_test) : '—') }}
                        </span>
                        <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <!-- Candidates Table -->
        <div v-if="candidates && candidates.length" class="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-xl shadow-black/40">
           <div class="flex items-center justify-between mb-6">
             <div>
               <h2 class="text-xl font-semibold text-slate-100">候选结果 ({{ candidates.length }})</h2>
               <p class="text-sm text-slate-400 mt-1">Top 优选参数组合列表</p>
             </div>
           </div>
           <div class="overflow-hidden rounded-2xl border border-slate-800/60 bg-slate-950/30">
             <table class="w-full text-xs text-slate-200">
               <thead>
                 <tr class="bg-slate-900/80 border-b border-slate-800/60 text-slate-400">
                   <th class="py-3 pl-4 text-left font-medium">ID</th>
                   <th class="py-3 px-2 text-right font-medium">训练得分</th>
                   <th class="py-3 px-2 text-right font-medium">验证得分</th>
                   <th class="py-3 px-2 text-right font-medium">测试得分</th>
                   <th class="py-3 px-2 text-center font-medium">状态</th>
                   <th class="py-3 pr-4 text-right font-medium">操作</th>
                 </tr>
               </thead>
               <tbody class="divide-y divide-slate-800/60">
                 <tr v-for="(c, idx) in candidates" :key="idx" class="hover:bg-slate-800/40 transition-colors group">
                   <td class="py-3 pl-4 text-slate-500 font-mono group-hover:text-slate-300">#{{ idx + 1 }}</td>
                  <td class="py-3 px-2 text-right font-mono">
                    <div class="flex flex-col items-end gap-1">
                      <span v-if="isValidScore(c.score_train)" class="font-medium">{{ formatScore(c.score_train) }}</span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      <div v-if="isValidScore(c.score_train)" class="h-1 w-16 rounded-full bg-slate-800/80 overflow-hidden">
                        <div class="h-full bg-emerald-500" :style="{ width: `${Math.min(Math.max(c.score_train * 20, 0), 100)}%` }"></div>
                      </div>
                    </div>
                  </td>
                  <td class="py-3 px-2 text-right font-mono">
                    <div class="flex flex-col items-end gap-1">
                      <span v-if="isValidScore(c.score_val)" class="text-slate-300">{{ formatScore(c.score_val) }}</span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      <div v-if="isValidScore(c.score_val)" class="h-1 w-16 rounded-full bg-slate-800/80 overflow-hidden">
                        <div class="h-full bg-indigo-500" :style="{ width: `${Math.min(Math.max(c.score_val * 20, 0), 100)}%` }"></div>
                      </div>
                    </div>
                  </td>
                  <td class="py-3 px-2 text-right font-mono">
                    <div class="flex flex-col items-end gap-1">
                      <span v-if="isValidScore(c.score_test)" class="text-slate-300">{{ formatScore(c.score_test) }}</span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                      <div v-if="isValidScore(c.score_test)" class="h-1 w-16 rounded-full bg-slate-800/80 overflow-hidden">
                        <div class="h-full bg-purple-500" :style="{ width: `${Math.min(Math.max(c.score_test * 20, 0), 100)}%` }"></div>
                      </div>
                    </div>
                  </td>
                   <td class="py-3 px-2 text-center">
                     <span class="text-[10px] px-2 py-1 rounded-full border font-medium" :class="[
                       robustnessLevel(c) === 'good' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' :
                       robustnessLevel(c) === 'medium' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                       'border-rose-500/30 text-rose-400 bg-rose-500/10'
                     ]">
                       {{ robustnessText(c) }}
                     </span>
                   </td>
                   <td class="py-3 pr-4 text-right">
                     <button 
                       @click="openCandidateDetail(c)" 
                       class="rounded-lg px-3 py-1.5 bg-slate-800/50 text-slate-300 text-xs hover:bg-indigo-600 hover:text-white transition-colors"
                     >
                       详情
                     </button>
                   </td>
                 </tr>
               </tbody>
             </table>
           </div>
        </div>
      </section>
    </div>

    <div class="pointer-events-none fixed bottom-6 right-6 z-50 space-y-3">
      <transition
        enter-active-class="transition duration-200"
        enter-from-class="translate-y-2 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="successMessage"
          class="pointer-events-auto rounded-2xl border border-emerald-500/40 bg-emerald-900/90 px-4 py-3 text-sm text-emerald-100 shadow-lg shadow-emerald-900/50 backdrop-blur-md"
        >
          {{ successMessage }}
        </div>
      </transition>
      <transition
        enter-active-class="transition duration-200"
        enter-from-class="translate-y-2 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="errorMessage"
          class="pointer-events-auto rounded-2xl border border-rose-500/40 bg-rose-900/90 px-4 py-3 text-sm text-rose-100 shadow-lg shadow-rose-900/50 backdrop-blur-md"
        >
          {{ errorMessage }}
        </div>
      </transition>
    </div>

    <div
      v-if="confirmationDialog.visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
    >
      <div class="w-full max-w-md rounded-3xl border border-slate-800/80 bg-slate-950/90 p-6 shadow-2xl shadow-black/60">
        <h3 class="text-lg font-semibold text-slate-100">
          {{ confirmationDialog.title }}
        </h3>
        <p class="mt-3 text-sm text-slate-300 whitespace-pre-line leading-relaxed">
          {{ confirmationDialog.message }}
        </p>
        <div class="mt-8 flex justify-end gap-3 text-sm">
          <button
            class="rounded-xl border border-slate-700 px-4 py-2.5 text-slate-300 hover:border-slate-500 hover:text-white transition-colors"
            @click="cancelDialog"
          >
            取消
          </button>
          <button
            class="rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-5 py-2.5 font-medium text-white shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all"
            @click="confirmDialog"
          >
            确认
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="candidateDetail"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
    >
      <div class="w-full max-w-3xl rounded-3xl border border-slate-800/80 bg-slate-950/95 p-8 shadow-2xl shadow-black/60 flex flex-col max-h-[90vh]">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-2xl font-bold text-slate-100">候选详情</h3>
            <div class="flex items-center gap-3 mt-2">
              <span class="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-400 border border-slate-700">ID: {{ candidateDetail.run_id || '-' }}</span>
              <span class="text-xs px-2 py-0.5 rounded border font-medium" :class="[
                robustnessLevel(candidateDetail) === 'good' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' :
                robustnessLevel(candidateDetail) === 'medium' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                'border-rose-500/30 text-rose-400 bg-rose-500/10'
              ]">
                {{ robustnessText(candidateDetail) }}
              </span>
            </div>
          </div>
          <button
            class="p-2 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            @click="closeCandidateDetail"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        
        <div class="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-6 overflow-y-auto px-1">
          <!-- Params Column -->
          <div class="space-y-4">
            <h4 class="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <span class="w-1 h-4 rounded-full bg-indigo-500"></span>
              参数组合
            </h4>
            <div class="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 space-y-2">
              <div
                v-for="(val, key) in candidateDetail.params || {}"
                :key="key"
                class="flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/50 transition-colors"
              >
                <span class="text-slate-400 text-xs">{{ getParamLabel({ key, label: key }) }}</span>
                <span class="text-sm font-mono text-slate-200">
                  {{ formatParamDisplayValue(key, val) }} <span class="text-xs text-slate-500">{{ getParamUnit(key) || '' }}</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Metrics Column -->
          <div class="space-y-4">
            <h4 class="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <span class="w-1 h-4 rounded-full bg-emerald-500"></span>
              区间表现
            </h4>
            <div class="rounded-2xl border border-slate-800/80 bg-slate-900/60 overflow-hidden">
              <table class="w-full text-xs text-slate-200">
                <thead>
                  <tr class="bg-slate-900/80 border-b border-slate-800/60 text-slate-400">
                    <th class="py-3 px-4 text-left">指标</th>
                    <th class="py-3 px-4 text-right">训练</th>
                    <th class="py-3 px-4 text-right border-l border-slate-800/50">验证</th>
                    <th class="py-3 px-4 text-right border-l border-slate-800/50">测试</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/40">
                  <tr class="hover:bg-slate-800/20">
                      <td class="py-2.5 px-4 text-slate-400">期间收益</td>
                    <td class="py-2.5 px-4 text-right font-mono font-medium" :class="((candidateDetail.train_metrics?.totalReturn ?? candidateDetail.train_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                      {{ (candidateDetail.train_metrics?.totalReturn !== undefined && candidateDetail.train_metrics?.totalReturn !== null) || (candidateDetail.train_metrics?.total_return !== undefined && candidateDetail.train_metrics?.total_return !== null) ? formatPercent(candidateDetail.train_metrics.totalReturn ?? candidateDetail.train_metrics.total_return) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono font-medium border-l border-slate-800/50" :class="((candidateDetail.val_metrics?.totalReturn ?? candidateDetail.val_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                      {{ (candidateDetail.val_metrics?.totalReturn !== undefined && candidateDetail.val_metrics?.totalReturn !== null) || (candidateDetail.val_metrics?.total_return !== undefined && candidateDetail.val_metrics?.total_return !== null) ? formatPercent(candidateDetail.val_metrics.totalReturn ?? candidateDetail.val_metrics.total_return) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono font-medium border-l border-slate-800/50" :class="((candidateDetail.test_metrics?.totalReturn ?? candidateDetail.test_metrics?.total_return ?? 0) >= 0 ? 'text-red-400' : 'text-green-400')">
                      {{ (candidateDetail.test_metrics?.totalReturn !== undefined && candidateDetail.test_metrics?.totalReturn !== null) || (candidateDetail.test_metrics?.total_return !== undefined && candidateDetail.test_metrics?.total_return !== null) ? formatPercent(candidateDetail.test_metrics.totalReturn ?? candidateDetail.test_metrics.total_return) : '—' }}
                    </td>
                  </tr>
                  <tr class="hover:bg-slate-800/20">
                    <td class="py-2.5 px-4 text-slate-400">最大回撤</td>
                    <td class="py-2.5 px-4 text-right font-mono text-rose-300">
                      {{ candidateDetail.train_metrics?.max_drawdown ? formatPercent(candidateDetail.train_metrics.max_drawdown) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono text-rose-300 border-l border-slate-800/50">
                      {{ candidateDetail.val_metrics?.max_drawdown ? formatPercent(candidateDetail.val_metrics.max_drawdown) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono text-rose-300 border-l border-slate-800/50">
                      {{ candidateDetail.test_metrics?.max_drawdown ? formatPercent(candidateDetail.test_metrics.max_drawdown) : '—' }}
                    </td>
                  </tr>
                  <tr class="hover:bg-slate-800/20">
                    <td class="py-2.5 px-4 text-slate-400">盈亏比</td>
                    <td class="py-2.5 px-4 text-right font-mono">
                      {{ candidateDetail.train_metrics?.profit_factor ? formatNumber(candidateDetail.train_metrics.profit_factor) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                      {{ candidateDetail.val_metrics?.profit_factor ? formatNumber(candidateDetail.val_metrics.profit_factor) : '—' }}
                    </td>
                    <td class="py-2.5 px-4 text-right font-mono border-l border-slate-800/50">
                      {{ candidateDetail.test_metrics?.profit_factor ? formatNumber(candidateDetail.test_metrics.profit_factor) : '—' }}
                    </td>
                  </tr>
                  <tr class="bg-slate-800/30 font-semibold">
                    <td class="py-3 px-4 text-indigo-200">综合得分</td>
                    <td class="py-3 px-4 text-right font-mono">
                      <span v-if="isValidScore(candidateDetail.train_metrics?.composite_score ?? candidateDetail.score_train)" class="text-indigo-300">
                        {{ candidateDetail.train_metrics?.composite_score ? formatScore(candidateDetail.train_metrics.composite_score) : formatScore(candidateDetail.score_train) }}
                      </span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                    </td>
                    <td class="py-3 px-4 text-right font-mono border-l border-slate-800/50">
                      <span v-if="isValidScore(candidateDetail.val_metrics?.composite_score ?? candidateDetail.score_val)" class="text-indigo-300">
                        {{ candidateDetail.val_metrics?.composite_score ? formatScore(candidateDetail.val_metrics.composite_score) : formatScore(candidateDetail.score_val) }}
                      </span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                    </td>
                    <td class="py-3 px-4 text-right font-mono border-l border-slate-800/50">
                      <span v-if="isValidScore(candidateDetail.test_metrics?.composite_score ?? candidateDetail.score_test)" class="text-indigo-300">
                        {{ candidateDetail.test_metrics?.composite_score ? formatScore(candidateDetail.test_metrics.composite_score) : formatScore(candidateDetail.score_test) }}
                      </span>
                      <span v-else class="px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-400 border border-rose-500/50">无效</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        
        <div class="mt-8 flex justify-end">
          <button
            class="rounded-xl border border-slate-700 px-6 py-2.5 text-sm text-slate-300 hover:border-slate-500 hover:text-white hover:bg-slate-800 transition-all"
            @click="closeCandidateDetail"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
