<template>
  <div class="param-optimization-page p-4 md:p-6 bg-gray-50 dark:bg-slate-900 dark:text-slate-100 min-h-screen">
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
          策略参数优化
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
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-6 mb-6">
      <!-- 左侧：策略和日期配置 -->
      <div class="md:col-span-1">
        <div class="bg-[#151925] rounded-xl border border-slate-800 p-4 md:p-5 space-y-4 md:space-y-5 max-h-[80vh] overflow-y-auto">
          <!-- 策略选择 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">选择策略</label>
            <select
              v-model="selectedStrategy"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              :disabled="isOptimizing || isLoadingStrategies"
            >
              <option value="" disabled>请选择策略</option>
              <option v-for="s in availableStrategies" :key="s.id" :value="s.id">
                {{ s.name }}
              </option>
            </select>
          </div>

          <!-- 日期范围 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">日期范围</label>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-slate-500 mb-1">开始日期</label>
                <input
                  v-model="startDate"
                  type="date"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isOptimizing"
                />
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">结束日期</label>
                <input
                  v-model="endDate"
                  type="date"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isOptimizing"
                />
              </div>
            </div>
          </div>

          <!-- 优化算法选择 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">优化算法</label>
            <select
              v-model="optimizationMethod"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              :disabled="isOptimizing"
            >
              <option value="genetic">遗传算法 (Genetic)</option>
              <option value="grid">网格搜索 (Grid Search)</option>
              <option value="particle">粒子群算法 (PSO)</option>
              <option value="simulatedAnnealing">模拟退火 (SA)</option>
              <option value="bayesian">贝叶斯优化 (Bayesian)</option>
            </select>
          </div>

          <!-- 优化目标 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">优化目标</label>
            <select
              v-model="optimizationTarget"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              :disabled="isOptimizing"
            >
              <option value="sharpe_ratio">夏普比率 (Sharpe Ratio)</option>
              <option value="total_return">总收益率 (Total Return)</option>
              <option value="calmar_ratio">卡尔玛比率 (Calmar Ratio)</option>
              <option value="win_rate">胜率 (Win Rate)</option>
              <option value="max_drawdown">最小化最大回撤 (Min Max Drawdown)</option>
            </select>
          </div>

          <!-- 优化配置 -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">优化配置</label>
            <div class="space-y-3">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-slate-500 mb-1">种群大小</label>
                  <input
                    v-model.number="optimizationConfig.population"
                    type="number"
                    min="5"
                    max="200"
                    class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    :disabled="isOptimizing"
                  />
                </div>
                <div>
                  <label class="block text-xs text-slate-500 mb-1">迭代次数</label>
                  <input
                    v-model.number="optimizationConfig.iterations"
                    type="number"
                    min="10"
                    max="500"
                    class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    :disabled="isOptimizing"
                  />
                </div>
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">变异率</label>
                <input
                  v-model.number="optimizationConfig.mutationRate"
                  type="number"
                  min="0.01"
                  max="1"
                  step="0.01"
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  :disabled="isOptimizing"
                />
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="pt-2 sticky bottom-0 bg-[#151925] pt-3 pb-1">
            <button
              @click="startOptimization"
              :disabled="isOptimizing || !selectedStrategy || !startDate || !endDate"
              class="w-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-all flex items-center justify-center gap-2"
            >
              <i v-if="isOptimizing" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-play"></i>
              {{ isOptimizing ? '优化中...' : '开始优化' }}
            </button>
            <button
              v-if="isOptimizing"
              @click="stopOptimization"
              class="mt-2 w-full text-slate-200 border border-slate-600 hover:bg-slate-700/60 transition-colors py-2 px-4 rounded-lg flex items-center justify-center gap-2"
            >
              <i class="fas fa-stop"></i>
              停止优化
            </button>
          </div>

          <!-- 优化进度 -->
          <div v-if="isOptimizing" class="mt-3">
            <div class="flex items-center justify-between text-sm text-slate-400 mb-1">
              <span>优化进度</span>
              <span>{{ optimizationProgress.toFixed(0) }}%</span>
            </div>
            <div class="h-2 bg-slate-700 rounded-full overflow-hidden">
              <div 
                class="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                :style="{ width: optimizationProgress + '%' }"
              ></div>
            </div>
            <div v-if="currentGeneration > 0" class="mt-2 text-xs text-slate-500">
              当前代数: {{ currentGeneration }} / {{ optimizationConfig.iterations }} | 
              最佳适应度: {{ bestFitness.toFixed(4) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：参数范围配置 -->
      <div class="md:col-span-2">
        <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
          <div class="px-4 md:px-5 py-3 md:py-4 border-b border-slate-800">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <i class="fas fa-sliders-h text-purple-400"></i>
              参数范围配置
            </h2>
          </div>
          <div class="p-4 md:p-5 max-h-[600px] overflow-y-auto">
            <div v-if="isLoadingParams" class="flex items-center justify-center py-8 text-slate-400">
              <i class="fas fa-spinner fa-spin mr-2"></i>
              加载参数中...
            </div>
            <div v-else-if="strategyParams.length === 0" class="text-center py-8 text-slate-500">
              请先选择策略
            </div>
            <div v-else class="space-y-5">
              <div v-for="group in paramGroups" :key="group.name" class="space-y-3">
                <h3 class="text-sm font-medium text-slate-400 border-b border-slate-700 pb-2">
                  {{ group.displayName }}
                </h3>
                <div v-for="param in group.params" :key="param.key" class="grid grid-cols-1 md:grid-cols-6 gap-3 md:gap-4 items-center">
                  <div class="col-span-1 md:col-span-2">
                    <label class="text-sm text-slate-300 flex items-center gap-2">
                      <input
                        v-model="param.isSelected"
                        type="checkbox"
                        class="w-4 h-4 text-purple-500 bg-slate-800 border-slate-600 rounded focus:ring-purple-500"
                        :disabled="isOptimizing"
                      />
                      <span>{{ param.label }}</span>
                    </label>
                    <p v-if="param.description" class="text-xs text-slate-500 mt-1">{{ param.description }}</p>
                  </div>
                  <div class="col-span-1 md:col-span-2">
                    <label class="block text-xs text-slate-500 mb-1">最小值</label>
                    <input
                      v-model.number="param.min"
                      type="number"
                      :step="param.step || 0.01"
                      class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      :disabled="isOptimizing || !param.isSelected"
                    />
                  </div>
                  <div class="col-span-1 md:col-span-2">
                    <label class="block text-xs text-slate-500 mb-1">最大值</label>
                    <input
                      v-model.number="param.max"
                      type="number"
                      :step="param.step || 0.01"
                      class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      :disabled="isOptimizing || !param.isSelected"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 优化结果 -->
    <div v-if="optimizationResults.length > 0" class="space-y-6">
      <!-- 结果概览 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 p-5">
        <h2 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <i class="fas fa-trophy text-yellow-400"></i>
          优化结果概览
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3 md:gap-4">
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">最佳参数组合</div>
            <div class="text-2xl font-bold text-yellow-400">{{ optimizationResults.length }}</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">最优夏普比率</div>
            <div class="text-2xl font-bold text-green-400">{{ bestResult?.sharpeRatio.toFixed(4) || '-' }}</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">总收益率</div>
            <div class="text-2xl font-bold text-green-400">{{ bestResult?.totalReturn.toFixed(2) || '-' }}%</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">最大回撤</div>
            <div class="text-2xl font-bold text-red-400">{{ bestResult?.maxDrawdown.toFixed(2) || '-' }}%</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">年化收益</div>
            <div class="text-2xl font-bold text-green-400">{{ bestResult?.annualizedReturn.toFixed(2) || '-' }}%</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">胜率</div>
            <div class="text-2xl font-bold text-white">{{ bestResult?.winRate.toFixed(2) || '-' }}%</div>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div class="text-sm text-slate-400 mb-2">盈亏比</div>
            <div class="text-2xl font-bold text-white">{{ bestResult?.profitFactor.toFixed(2) || '-' }}</div>
          </div>
        </div>
      </div>

      <!-- 参数敏感性分析 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 p-5">
        <h2 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <i class="fas fa-chart-line text-blue-400"></i>
          参数敏感性分析
        </h2>
        <div class="h-48 md:h-64">
          <WaterfallChart
            v-if="sensitivityData.length > 0"
            :data="sensitivityData"
            title="参数敏感性"
            subtitle="各参数对优化目标的影响程度"
            unit="%"
          />
          <div v-else class="h-full flex items-center justify-center text-slate-500">
            <i class="fas fa-chart-bar text-4xl mb-2 mr-2"></i>
            <p>优化完成后显示敏感性分析</p>
          </div>
        </div>
      </div>

      <!-- 优化结果列表 -->
      <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden">
        <div class="px-4 md:px-5 py-3 md:py-4 border-b border-slate-800">
          <h2 class="text-lg font-semibold text-white flex items-center gap-2">
            <i class="fas fa-table text-green-400"></i>
            优化结果详情
          </h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="bg-slate-800/50">
                <th class="px-3 py-2 text-left text-xs md:text-sm font-medium text-slate-400">排名</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">夏普比率</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">总收益</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">年化收益</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">最大回撤</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">胜率</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">盈亏比</th>
                <th class="px-3 py-2 text-right text-xs md:text-sm font-medium text-slate-400">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800">
              <tr v-for="(result, index) in optimizationResults" :key="index" class="hover:bg-slate-800/30">
                <td class="px-3 py-2 text-xs md:text-sm text-slate-300 font-medium">
                  <span :class="index === 0 ? 'text-yellow-400' : index === 1 ? 'text-gray-400' : index === 2 ? 'text-amber-700' : 'text-slate-300'">
                    {{ index + 1 }}
                  </span>
                </td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-slate-300">{{ result.sharpeRatio.toFixed(4) }}</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-green-400">{{ result.totalReturn.toFixed(2) }}%</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-green-400">{{ result.annualizedReturn.toFixed(2) }}%</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-red-400">{{ result.maxDrawdown.toFixed(2) }}%</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-slate-300">{{ result.winRate.toFixed(2) }}%</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right text-slate-300">{{ result.profitFactor.toFixed(2) }}</td>
                <td class="px-3 py-2 text-xs md:text-sm text-right">
                  <button
                    @click="showResultDetails(result)"
                    class="text-indigo-400 hover:text-indigo-300 transition-colors flex items-center justify-end gap-1"
                  >
                    <span>查看</span>
                    <i class="fas fa-chevron-right text-xs"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!isOptimizing && selectedStrategy" class="bg-[#151925] rounded-xl border border-slate-800 p-12 text-center">
      <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
        <i class="fas fa-flask text-2xl text-slate-500"></i>
      </div>
      <h3 class="text-lg font-medium text-slate-300 mb-2">准备优化</h3>
      <p class="text-slate-500 mb-4">选择要优化的参数并设置范围，然后点击"开始优化"</p>
      <div class="flex items-center justify-center gap-2 text-sm text-slate-400">
        <span><i class="fas fa-check-circle text-green-500 mr-1"></i>已选择策略</span>
        <span><i class="fas fa-check-circle text-green-500 mr-1"></i>已设置日期</span>
        <span><i class="fas fa-circle text-slate-600 mr-1"></i>等待优化</span>
      </div>
    </div>

    <!-- 结果详情弹窗 -->
    <div v-if="selectedResult" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 md:p-4">
      <div class="bg-[#151925] rounded-lg shadow-xl max-w-4xl w-full max-h-[95vh] flex flex-col">
        <!-- 弹窗头部 -->
        <div class="flex items-center justify-between p-4 md:p-6 border-b border-slate-700">
          <h2 class="text-2xl font-bold text-white">参数详情</h2>
          <button
            @click="selectedResult = null"
            class="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <!-- 弹窗内容 -->
        <div class="flex-1 overflow-y-auto p-4 md:p-6">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
            <!-- 绩效指标 -->
            <div>
              <h3 class="text-lg font-semibold text-white mb-4">绩效指标</h3>
              <div class="space-y-3">
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">夏普比率</div>
                  <div class="text-2xl font-bold text-white">{{ selectedResult.sharpeRatio.toFixed(4) }}</div>
                </div>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">总收益率</div>
                  <div class="text-2xl font-bold text-green-400">{{ selectedResult.totalReturn.toFixed(2) }}%</div>
                </div>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">年化收益率</div>
                  <div class="text-2xl font-bold text-green-400">{{ selectedResult.annualizedReturn.toFixed(2) }}%</div>
                </div>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">最大回撤</div>
                  <div class="text-2xl font-bold text-red-400">{{ selectedResult.maxDrawdown.toFixed(2) }}%</div>
                </div>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">胜率</div>
                  <div class="text-2xl font-bold text-white">{{ selectedResult.winRate.toFixed(2) }}%</div>
                </div>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">盈亏比</div>
                  <div class="text-2xl font-bold text-white">{{ selectedResult.profitFactor.toFixed(2) }}</div>
                </div>
              </div>
            </div>

            <!-- 参数值 -->
            <div>
              <h3 class="text-lg font-semibold text-white mb-4">优化参数</h3>
              <div class="space-y-3">
                <div v-for="(value, key) in selectedResult.params" :key="key" class="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div class="text-sm text-slate-400 mb-1">{{ getParamLabel(key) }}</div>
                  <div class="text-2xl font-bold text-purple-400">{{ value }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 弹窗底部 -->
        <div class="p-4 md:p-6 border-t border-slate-700 flex justify-end gap-3">
          <button
            @click="selectedResult = null"
            class="px-6 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
          >
            关闭
          </button>
          <button
            @click="applyOptimizedParams(selectedResult)"
            class="ml-3 px-6 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-colors"
          >
            应用参数
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import WaterfallChart from '../components/charts/WaterfallChart.vue';

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
  description?: string;
  group?: string;
  group_label?: string;
  isSelected: boolean;
}>>([]);

// 日期范围
const startDate = ref('');
const endDate = ref('');

// 优化配置
const optimizationMethod = ref('genetic');
const optimizationTarget = ref('sharpe_ratio');
const optimizationConfig = ref({
  population: 30,
  iterations: 100,
  mutationRate: 0.1,
  crossoverRate: 0.7
});

// 优化状态
const isOptimizing = ref(false);
const optimizationProgress = ref(0);
const currentGeneration = ref(0);
const bestFitness = ref(0);
const optimizationResults = ref<Array<{
  params: Record<string, any>;
  sharpeRatio: number;
  totalReturn: number;
  annualizedReturn: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  tradesCount: number;
}>>([]);

// 敏感性分析数据
const sensitivityData = ref<Array<{
  name: string;
  value: number;
}>>([]);

// 消息
const errorMessage = ref('');
const successMessage = ref('');

// 中断控制器
let abortController: AbortController | null = null;

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
        selectedStrategy.value = availableStrategies.value[0].id;
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
        strategyParams.value = params.map((p: any) => ({
          ...p,
          isSelected: true
        }));
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
  optimizationResults.value = [];
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

// 计算最佳结果
const bestResult = computed(() => {
  if (optimizationResults.value.length === 0) return null;
  return optimizationResults.value[0];
});

// 开始优化
const startOptimization = async () => {
  if (!selectedStrategy.value || !startDate.value || !endDate.value) {
    showError('请选择策略和日期范围');
    return;
  }

  const selectedParams = strategyParams.value.filter(p => p.isSelected);
  if (selectedParams.length === 0) {
    showError('请至少选择一个参数进行优化');
    return;
  }

  const paramRanges = selectedParams.map(p => ({
    name: p.key,
    bounds: [p.min, p.max],
    type: p.type === 'integer' ? 'int' : 'float',
    step: p.step
  }));

  isOptimizing.value = true;
  optimizationProgress.value = 0;
  currentGeneration.value = 0;
  bestFitness.value = 0;
  optimizationResults.value = [];
  errorMessage.value = '';

  // 创建 WebSocket 连接进行实时优化
  const ws = new WebSocket(`ws://localhost:5000/ws/optimize`);
  
  ws.onopen = () => {
    ws.send(JSON.stringify({
      type: 'start_optimization',
      data: {
        strategy_name: selectedStrategy.value,
        start_date: startDate.value,
        end_date: endDate.value,
        method: optimizationMethod.value,
        param_ranges: paramRanges,
        options: {
          target: optimizationTarget.value,
          population: optimizationConfig.value.population,
          iterations: optimizationConfig.value.iterations,
          mutation_rate: optimizationConfig.value.mutationRate,
          crossover_rate: optimizationConfig.value.crossoverRate
        }
      }
    }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'optimization_progress') {
      optimizationProgress.value = data.progress;
      currentGeneration.value = data.generation;
      bestFitness.value = data.best_fitness;
    } else if (data.type === 'new_generation') {
      // 处理新一代结果
      if (data.results && Array.isArray(data.results)) {
        optimizationResults.value = data.results.map((result: any) => ({
          params: result.params,
          sharpeRatio: result.metrics.sharpe_ratio || 0,
          totalReturn: result.metrics.total_return || 0,
          annualizedReturn: result.metrics.annualized_return || 0,
          maxDrawdown: result.metrics.max_drawdown || 0,
          winRate: result.metrics.win_rate || 0,
          profitFactor: result.metrics.profit_factor || 0,
          tradesCount: result.metrics.trades_count || 0
        }));
      }
    } else if (data.type === 'optimization_complete') {
      isOptimizing.value = false;
      optimizationProgress.value = 100;
      showSuccess('参数优化完成！');
      calculateSensitivity();
      ws.close();
    } else if (data.type === 'optimization_error') {
      isOptimizing.value = false;
      showError(data.message || '优化失败');
      ws.close();
    }
  };

  ws.onerror = () => {
    isOptimizing.value = false;
    showError('优化连接失败，请确保后端服务正在运行');
  };

  ws.onclose = () => {
    isOptimizing.value = false;
  };
};

// 停止优化
const stopOptimization = () => {
  // 这里可以添加停止优化的逻辑
  showSuccess('优化已停止');
  isOptimizing.value = false;
};

// 计算参数敏感性
const calculateSensitivity = () => {
  // 简单的敏感性计算：比较不同参数值对结果的影响
  if (optimizationResults.value.length === 0) return;
  
  const sensitivityMap = new Map<string, number>();
  const bestParams = optimizationResults.value[0].params;
  
  // 初始化敏感性为0
  Object.keys(bestParams).forEach(key => {
    sensitivityMap.set(key, 0);
  });
  
  // 计算每个参数的敏感性
  optimizationResults.value.forEach(result => {
    Object.entries(result.params).forEach(([key, value]) => {
      const diff = Math.abs((value as number) - (bestParams[key] as number));
      sensitivityMap.set(key, (sensitivityMap.get(key) || 0) + diff);
    });
  });
  
  // 转换为瀑布图数据
  sensitivityData.value = Array.from(sensitivityMap.entries())
    .map(([key, value]) => ({
      name: getParamLabel(key),
      value: (value / optimizationResults.value.length) * 100 // 归一化
    }))
    .sort((a, b) => b.value - a.value);
};

// 获取参数标签
const getParamLabel = (key: string) => {
  const param = strategyParams.value.find(p => p.key === key);
  return param?.label || key;
};

// 显示结果详情
const showResultDetails = (result: any) => {
  selectedResult.value = result;
};

// 应用优化后的参数
const applyOptimizedParams = async (result: any) => {
  try {
    // 调用热重载 API 更新配置
    const response = await fetch(
      `${API_BASE_URL}/strategies/${selectedStrategy.value}/config`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result.params)
      }
    );
    
    const data = await response.json();
    
    if (data.success) {
      showSuccess('✨ 参数已应用并自动重载！无需重启服务器。');
      selectedResult.value = null;
    } else {
      showError(data.error || '应用参数失败');
    }
  } catch (error) {
    console.error('应用参数失败:', error);
    showError('应用参数失败，请检查网络连接');
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