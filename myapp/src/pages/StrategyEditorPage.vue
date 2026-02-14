<template>
  <div class="strategy-editor-page">
    <!-- 顶部工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <!-- 面包屑导航 -->
        <div class="breadcrumb">
          <router-link to="/dashboard" class="breadcrumb-link">
            <LeftOutlined /> 返回
          </router-link>
        </div>
        
        <!-- 策略名称输入 -->
        <div class="strategy-name-wrapper">
          <EditOutlined class="name-icon" />
          <a-input
            v-model:value="strategyName"
            placeholder="输入策略名称"
            class="strategy-name-input"
            :bordered="false"
          />
        </div>
      </div>
      
      <div class="toolbar-center">
        <!-- 运行状态指示器 -->
        <div v-if="backtestRunning" class="running-indicator">
          <a-spin size="small" />
          <span>回测运行中...</span>
        </div>
      </div>
      
      <div class="toolbar-right">
        <a-button @click="formatCode" class="toolbar-btn" size="small">
          <FormatPainterOutlined /> 格式化
        </a-button>
        <a-button @click="resetCode" class="toolbar-btn" size="small">
          <ReloadOutlined /> 重置
        </a-button>
        <a-button type="primary" @click="saveStrategy" :loading="saving" class="toolbar-btn" size="small">
          <SaveOutlined /> 保存
        </a-button>
        <a-button type="primary" danger @click="runBacktest" :loading="backtestRunning" class="toolbar-btn run-btn" size="small">
          <PlayCircleOutlined /> 运行回测
        </a-button>
      </div>
    </div>

    <!-- 主编辑区 -->
    <div class="editor-main">
      <!-- 左侧代码编辑区 -->
      <div class="left-panel" :style="{ width: leftPanelWidth + '%' }">
        <!-- 文档面板（可折叠） -->
        <div class="doc-panel-container" :class="{ collapsed: isDocCollapsed }">
          <div class="doc-panel-header">
            <span class="doc-title">📚 开发文档</span>
            <a-button 
              type="text" 
              size="small" 
              class="collapse-btn"
              @click="toggleDocPanel"
            >
              <MenuFoldOutlined v-if="!isDocCollapsed" />
              <MenuUnfoldOutlined v-else />
            </a-button>
          </div>
          <div v-show="!isDocCollapsed" class="doc-panel-content">
            <StrategyDocPanel @insert="insertCode" />
          </div>
        </div>
        
        <!-- 代码编辑器 -->
        <div class="code-editor-wrapper">
          <div class="editor-header">
            <span class="editor-label">
              <CodeOutlined /> 策略代码
            </span>
            <span class="editor-status" :class="{ unsaved: hasUnsavedChanges }">
              {{ hasUnsavedChanges ? '● 未保存' : '已保存' }}
            </span>
          </div>
          <MonacoEditor
            ref="editorRef"
            v-model="code"
            language="python"
            theme="vs-dark"
            :options="editorOptions"
          />
        </div>
      </div>

      <!-- 拖拽调整条 -->
      <div class="resize-bar" @mousedown="startResize"></div>

      <!-- 右侧回测结果面板 -->
      <div class="right-panel" :style="{ width: (100 - leftPanelWidth) + '%' }">
        <!-- KPI 仪表盘 -->
        <div class="kpi-dashboard">
          <div class="kpi-item">
            <div class="kpi-label">策略收益</div>
            <div class="kpi-value" :class="getValueClass(backtestResult?.totalReturn)">
              {{ formatPercent(backtestResult?.totalReturn) }}
            </div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">基准收益</div>
            <div class="kpi-value" :class="getValueClass(backtestResult?.benchmarkReturn)">
              {{ formatPercent(backtestResult?.benchmarkReturn) }}
            </div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Alpha</div>
            <div class="kpi-value" :class="getValueClass(backtestResult?.alpha)">
              {{ formatNumber(backtestResult?.alpha) }}
            </div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Beta</div>
            <div class="kpi-value">{{ formatNumber(backtestResult?.beta) }}</div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Sharpe</div>
            <div class="kpi-value" :class="getValueClass(backtestResult?.sharpeRatio)">
              {{ formatNumber(backtestResult?.sharpeRatio) }}
            </div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">最大回撤</div>
            <div class="kpi-value negative">
              {{ formatPercent(backtestResult?.maxDrawdown) }}
            </div>
          </div>
        </div>

        <!-- 回测参数设置 -->
        <div class="backtest-params-section">
          <div class="section-header">
            <SettingOutlined /> 回测参数
          </div>
          <div class="params-grid">
            <div class="param-item">
              <span class="param-label">初始资金</span>
              <a-input-number
                v-model:value="backtestConfig.initialCapital"
                :min="10000"
                :max="100000000"
                :step="10000"
                :formatter="value => `¥ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')"
                :parser="value => value.replace(/\¥\s?|(,*)/g, '')"
                size="small"
                style="width: 100%;"
              />
            </div>
            <div class="param-item">
              <span class="param-label">开始日期</span>
              <a-date-picker
                v-model:value="backtestConfig.startDate"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                :disabled-date="disabledStartDate"
                size="small"
                style="width: 100%;"
              />
            </div>
            <div class="param-item">
              <span class="param-label">结束日期</span>
              <a-date-picker
                v-model:value="backtestConfig.endDate"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                :disabled-date="disabledEndDate"
                size="small"
                style="width: 100%;"
              />
            </div>
            <div class="param-item">
              <span class="param-label">股票池</span>
              <a-select
                v-model:value="backtestConfig.stockPool"
                size="small"
                style="width: 100%;"
              >
                <a-select-option value="all">全市场</a-select-option>
                <a-select-option value="hs300">沪深300</a-select-option>
                <a-select-option value="zz500">中证500</a-select-option>
                <a-select-option value="zz1000">中证1000</a-select-option>
              </a-select>
            </div>
            <div class="param-item">
              <span class="param-label">基准指数</span>
              <a-select
                v-model:value="backtestConfig.benchmark"
                size="small"
                style="width: 100%;"
              >
                <a-select-option value="000300.SH">沪深300</a-select-option>
                <a-select-option value="000905.SH">中证500</a-select-option>
                <a-select-option value="000001.SH">上证指数</a-select-option>
                <a-select-option value="399001.SZ">深证成指</a-select-option>
              </a-select>
            </div>
            <div class="param-item reset-item">
              <a-button @click="resetConfig" size="small" type="dashed">
                <UndoOutlined /> 重置
              </a-button>
            </div>
          </div>
        </div>

        <!-- 回测结果图表区域 -->
        <div class="chart-section">
          <div class="section-header">
            <LineChartOutlined /> 回测图表
          </div>
          <div class="chart-container">
            <div v-if="!backtestResult && !backtestRunning" class="chart-placeholder">
              <AreaChartOutlined class="placeholder-icon" />
              <p>点击「运行回测」查看收益曲线</p>
            </div>
            <div v-else-if="backtestRunning" class="chart-loading">
              <a-spin size="large" />
              <p>正在计算回测结果...</p>
              <a-progress :percent="backtestProgress" size="small" />
            </div>
            <div v-else class="chart-content">
              <!-- 这里可以集成 ECharts 显示收益曲线 -->
              <div class="equity-curve-placeholder">
                <div class="curve-mock">
                  <div class="mock-line" :style="{ height: '60%' }"></div>
                  <div class="mock-line" :style="{ height: '75%' }"></div>
                  <div class="mock-line" :style="{ height: '55%' }"></div>
                  <div class="mock-line" :style="{ height: '80%' }"></div>
                  <div class="mock-line" :style="{ height: '70%' }"></div>
                  <div class="mock-line" :style="{ height: '85%' }"></div>
                  <div class="mock-line" :style="{ height: '90%' }"></div>
                  <div class="mock-line" :style="{ height: '78%' }"></div>
                </div>
                <p class="chart-hint">收益曲线预览（实际数据）</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 日志与错误控制台 -->
        <div class="console-section">
          <a-tabs v-model:activeKey="activeConsoleTab" size="small" class="console-tabs">
            <a-tab-pane key="logs" tab="📋 日志">
              <div class="console-content">
                <div v-if="logs.length === 0" class="empty-console">
                  暂无日志输出
                </div>
                <div v-else class="log-list">
                  <div v-for="(log, index) in logs" :key="index" class="log-item">
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-message">{{ log.message }}</span>
                  </div>
                </div>
              </div>
            </a-tab-pane>
            <a-tab-pane key="errors" tab="❌ 错误">
              <div class="console-content">
                <div v-if="errors.length === 0" class="empty-console">
                  暂无错误信息
                </div>
                <div v-else class="error-list">
                  <div v-for="(error, index) in errors" :key="index" class="error-item">
                    <span class="error-time">{{ error.time }}</span>
                    <span class="error-message">{{ error.message }}</span>
                  </div>
                </div>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>
    </div>

    <!-- 保存策略弹窗 -->
    <a-modal
      v-model:open="saveModalVisible"
      title="保存策略"
      @ok="confirmSave"
      :confirmLoading="saving"
      width="500px"
    >
      <a-form :model="saveForm" layout="vertical">
        <a-form-item label="策略名称" required>
          <a-input v-model:value="saveForm.name" placeholder="请输入策略名称" />
        </a-form-item>
        <a-form-item label="策略描述">
          <a-textarea v-model:value="saveForm.description" :rows="3" placeholder="请输入策略描述（可选）" />
        </a-form-item>
        <a-form-item label="保存路径">
          <a-input v-model:value="saveForm.path" disabled />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { message } from 'ant-design-vue';
import dayjs from 'dayjs';
import {
  SaveOutlined,
  PlayCircleOutlined,
  FormatPainterOutlined,
  ReloadOutlined,
  UndoOutlined,
  LeftOutlined,
  EditOutlined,
  CodeOutlined,
  SettingOutlined,
  LineChartOutlined,
  AreaChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons-vue';
import MonacoEditor from '../components/editor/MonacoEditor.vue';
import StrategyDocPanel from '../components/editor/StrategyDocPanel.vue';
import { apiService } from '../services/api';
import { useSocketIO } from '../composables/useSocketIO';

// 编辑器引用
const editorRef = ref<InstanceType<typeof MonacoEditor>>();

// 策略代码
const defaultCode = `from core.strategies.strategy_framework import StrategyBase

class MyStrategy(StrategyBase):
    """
    我的策略描述
    """
    strategy_name = "我的策略"
    
    def __init__(self, name=None):
        super().__init__(name)
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        策略逻辑实现
        
        参数:
            current_date: 当前日期，如 '2024-01-15'
            stock_pool_today: DataFrame，包含当日所有股票数据
            data_query: 数据查询对象
        
        返回:
            Dict[str, str]: {股票代码: 'buy'/'sell'/'hold'}
        """
        signals = {}
        
        for _, row in stock_pool_today.iterrows():
            code = row['stock_code']
            
            # 买入条件：突破均线 + 放量 + 非ST
            if (row['close'] > row['ma20'] and 
                row['volume_ratio'] > 2.0 and
                not row['is_st'] and
                not row['is_limit_up']):
                signals[code] = 'buy'
            
            # 卖出条件：跌破短期均线
            elif row['close'] < row['ma5']:
                signals[code] = 'sell'
            
            else:
                signals[code] = 'hold'
        
        return signals
`;

const code = ref(defaultCode);
const originalCode = ref(defaultCode);
const strategyName = ref('');

// 是否有未保存的更改
const hasUnsavedChanges = computed(() => {
  return code.value !== originalCode.value;
});

// 编辑器选项
const editorOptions = {
  fontSize: 14,
  minimap: { enabled: true },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  automaticLayout: true,
};

// 左侧面板宽度（百分比）
const leftPanelWidth = ref(55);
const isResizing = ref(false);

// 文档面板折叠状态
const isDocCollapsed = ref(false);

const toggleDocPanel = () => {
  isDocCollapsed.value = !isDocCollapsed.value;
};

// 拖拽调整面板宽度
const startResize = (e: MouseEvent) => {
  isResizing.value = true;
  const startX = e.clientX;
  const startWidth = leftPanelWidth.value;
  const containerWidth = window.innerWidth;

  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing.value) return;
    const delta = ((e.clientX - startX) / containerWidth) * 100;
    leftPanelWidth.value = Math.max(40, Math.min(70, startWidth + delta));
  };

  const handleMouseUp = () => {
    isResizing.value = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

// 回测参数配置
const defaultConfig = {
  initialCapital: 1000000,
  startDate: dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
  endDate: dayjs().format('YYYY-MM-DD'),
  stockPool: 'all',
  benchmark: '000300.SH',
};

const backtestConfig = ref({ ...defaultConfig });

// 日期禁用函数
const disabledStartDate = (current: dayjs.Dayjs) => {
  return current && current > dayjs(backtestConfig.value.endDate);
};

const disabledEndDate = (current: dayjs.Dayjs) => {
  return current && current < dayjs(backtestConfig.value.startDate);
};

// 重置配置
const resetConfig = () => {
  backtestConfig.value = { ...defaultConfig };
  message.success('参数已重置');
};

// 插入代码
const insertCode = (insertCode: string) => {
  editorRef.value?.insertCode(insertCode);
};

// 格式化代码
const formatCode = () => {
  editorRef.value?.formatCode();
  message.success('代码已格式化');
};

// 重置代码
const resetCode = () => {
  code.value = defaultCode;
  message.success('代码已重置');
};

// 保存策略
const saving = ref(false);
const saveModalVisible = ref(false);
const saveForm = ref({
  name: '',
  description: '',
  path: 'core/strategies/user/',
});

const saveStrategy = () => {
  if (!strategyName.value) {
    message.warning('请先输入策略名称');
    return;
  }
  saveForm.value.name = strategyName.value;
  saveModalVisible.value = true;
};

const confirmSave = async () => {
  if (!saveForm.value.name) {
    message.warning('请输入策略名称');
    return;
  }

  saving.value = true;
  try {
    // 更新代码中的 strategy_name 为用户输入的名称
    const updatedCode = updateStrategyNameInCode(code.value, saveForm.value.name);
    
    const result = await apiService.saveStrategy({
      name: saveForm.value.name,
      description: saveForm.value.description,
      code: updatedCode,
    });
    
    // result 已经是解包后的数据 { filename, filepath, message }
    if (result && result.filename) {
      message.success(`策略已保存: ${result.filename}`);
      code.value = updatedCode; // 更新编辑器中的代码
      originalCode.value = updatedCode;
      saveModalVisible.value = false;
      addLog(`策略已保存: ${result.filename}`);
    } else {
      message.error('保存失败: 返回数据格式错误');
      addError('保存失败: 返回数据格式错误');
    }
  } catch (error) {
    const errorMsg = '保存策略失败: ' + (error as Error).message;
    message.error(errorMsg);
    addError(errorMsg);
  } finally {
    saving.value = false;
  }
};

// 更新代码中的 strategy_name
const updateStrategyNameInCode = (code: string, name: string): string => {
  // 匹配 strategy_name = "..." 或 strategy_name = '...'
  const regex = /(strategy_name\s*=\s*)["'][^"']*["']/;
  if (regex.test(code)) {
    return code.replace(regex, `$1"${name}"`);
  }
  // 如果没有找到，在类定义后添加
  const classRegex = /(class\s+\w+\s*\([^)]*\):)/;
  if (classRegex.test(code)) {
    return code.replace(classRegex, `$1\n    strategy_name = "${name}"`);
  }
  return code;
};

// 回测相关
const backtestRunning = ref(false);
const backtestProgress = ref(0);
const backtestResult = ref<any>(null);
const { onEvent } = useSocketIO();

// 日志和错误
const logs = ref<Array<{ time: string; message: string }>>([]);
const errors = ref<Array<{ time: string; message: string }>>([]);
const activeConsoleTab = ref('logs');

const addLog = (message: string) => {
  logs.value.push({
    time: dayjs().format('HH:mm:ss'),
    message,
  });
};

const addError = (message: string) => {
  errors.value.push({
    time: dayjs().format('HH:mm:ss'),
    message,
  });
  activeConsoleTab.value = 'errors';
};

// 格式化数字
const formatNumber = (value: number | undefined) => {
  if (value === undefined || value === null) return '--';
  return value.toFixed(2);
};

// 格式化百分比
const formatPercent = (value: number | undefined) => {
  if (value === undefined || value === null) return '--';
  return (value * 100).toFixed(2) + '%';
};

// 获取数值样式类
const getValueClass = (value: number | undefined) => {
  if (value === undefined || value === null) return '';
  return value > 0 ? 'positive' : value < 0 ? 'negative' : '';
};

// 存储取消监听的函数
let unsubscribeProgress: (() => void) | null = null;
let unsubscribeComplete: (() => void) | null = null;
let unsubscribeError: (() => void) | null = null;

onMounted(() => {
  // 监听回测进度
  unsubscribeProgress = onEvent('backtest_progress', (data: any) => {
    backtestProgress.value = data.progress || 0;
  });

  unsubscribeComplete = onEvent('backtest_complete', (data: any) => {
    backtestRunning.value = false;
    backtestResult.value = data;
    message.success('回测完成');
    addLog(`回测完成 - 总收益: ${formatPercent(data.totalReturn)}`);
  });

  unsubscribeError = onEvent('backtest_error', (data: any) => {
    backtestRunning.value = false;
    const errorMsg = '回测失败: ' + data.message;
    message.error(errorMsg);
    addError(errorMsg);
  });
});

onBeforeUnmount(() => {
  unsubscribeProgress?.();
  unsubscribeComplete?.();
  unsubscribeError?.();
});

// 从代码中提取 strategy_name
const extractStrategyNameFromCode = (code: string): string => {
  const match = code.match(/strategy_name\s*=\s*["']([^"']+)["']/);
  return match ? match[1] : '';
};

// 运行回测
const runBacktest = async () => {
  // 从代码中提取 strategy_name
  const strategyNameFromCode = extractStrategyNameFromCode(code.value);
  
  if (!strategyNameFromCode) {
    message.warning('代码中未找到 strategy_name，请先设置策略名称');
    return;
  }

  addLog('开始保存策略...');
  
  try {
    await apiService.saveStrategy({
      name: strategyNameFromCode,
      code: code.value,
      temp: true,
    });
    addLog('策略保存成功');
  } catch (error) {
    const errorMsg = '策略保存失败: ' + (error as Error).message;
    addError(errorMsg);
    return;
  }

  backtestRunning.value = true;
  backtestProgress.value = 0;
  backtestResult.value = null;
  activeConsoleTab.value = 'logs';
  
  addLog('启动回测...');
  addLog(`策略: ${strategyNameFromCode}`);
  addLog(`参数: 初始资金 ¥${backtestConfig.value.initialCapital.toLocaleString()}, 日期范围 ${backtestConfig.value.startDate} ~ ${backtestConfig.value.endDate}`);

  try {
    await apiService.runStreamingBacktest({
      strategy_name: strategyNameFromCode,
      start_date: backtestConfig.value.startDate,
      end_date: backtestConfig.value.endDate,
      initial_capital: backtestConfig.value.initialCapital,
      stock_pool: backtestConfig.value.stockPool,
      benchmark: backtestConfig.value.benchmark,
    });
  } catch (error) {
    backtestRunning.value = false;
    const errorMsg = '启动回测失败: ' + (error as Error).message;
    message.error(errorMsg);
    addError(errorMsg);
  }
};
</script>

<style scoped>
.strategy-editor-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0d1117;
  overflow: hidden;
}

/* 顶部工具栏 */
.editor-toolbar {
  height: 48px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.breadcrumb {
  display: flex;
  align-items: center;
}

.breadcrumb-link {
  color: #8b949e;
  text-decoration: none;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: color 0.2s;
}

.breadcrumb-link:hover {
  color: #58a6ff;
}

.strategy-name-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #21262d;
  border-radius: 6px;
  padding: 4px 12px;
  border: 1px solid #30363d;
}

.name-icon {
  color: #8b949e;
  font-size: 14px;
}

.strategy-name-input {
  background: transparent;
  border: none;
  color: #c9d1d9;
  font-size: 14px;
  font-weight: 500;
  width: 200px;
  padding: 0;
}

.strategy-name-input::placeholder {
  color: #6e7681;
}

.toolbar-center {
  display: flex;
  align-items: center;
}

.running-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #58a6ff;
  font-size: 13px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 4px;
}

.run-btn {
  background: #238636;
  border-color: #238636;
}

.run-btn:hover {
  background: #2ea043;
  border-color: #2ea043;
}

/* 主编辑区 */
.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  overflow: hidden;
  background: #0d1117;
}

/* 文档面板 */
.doc-panel-container {
  width: 260px;
  flex-shrink: 0;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.doc-panel-container.collapsed {
  width: 40px;
}

.doc-panel-header {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #30363d;
  background: #21262d;
}

.doc-title {
  font-size: 13px;
  font-weight: 500;
  color: #c9d1d9;
}

.doc-panel-container.collapsed .doc-title {
  display: none;
}

.collapse-btn {
  color: #8b949e;
  padding: 4px;
}

.collapse-btn:hover {
  color: #c9d1d9;
  background: #30363d;
}

.doc-panel-content {
  flex: 1;
  overflow: hidden;
}

/* 代码编辑器 */
.code-editor-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-header {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
}

.editor-label {
  font-size: 12px;
  color: #8b949e;
  display: flex;
  align-items: center;
  gap: 6px;
}

.editor-status {
  font-size: 11px;
  color: #6e7681;
}

.editor-status.unsaved {
  color: #f0883e;
}

/* 拖拽调整条 */
.resize-bar {
  width: 4px;
  background: #21262d;
  cursor: col-resize;
  transition: background 0.2s;
  flex-shrink: 0;
}

.resize-bar:hover {
  background: #58a6ff;
}

/* 右侧面板 */
.right-panel {
  background: #161b22;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid #30363d;
}

/* KPI 仪表盘 */
.kpi-dashboard {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1px;
  background: #30363d;
  border-bottom: 1px solid #30363d;
}

.kpi-item {
  background: #161b22;
  padding: 12px 8px;
  text-align: center;
}

.kpi-label {
  font-size: 11px;
  color: #8b949e;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 16px;
  font-weight: 600;
  font-family: 'Consolas', monospace;
  color: #c9d1d9;
}

.kpi-value.positive {
  color: #3fb950;
}

.kpi-value.negative {
  color: #f85149;
}

/* 回测参数区域 */
.backtest-params-section {
  padding: 12px 16px;
  border-bottom: 1px solid #30363d;
  background: #0d1117;
}

.section-header {
  font-size: 12px;
  font-weight: 500;
  color: #c9d1d9;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-label {
  font-size: 11px;
  color: #8b949e;
}

.reset-item {
  display: flex;
  align-items: flex-end;
}

/* 图表区域 */
.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-bottom: 1px solid #30363d;
}

.chart-section .section-header {
  padding: 12px 16px 0;
  margin-bottom: 0;
}

.chart-container {
  flex: 1;
  padding: 12px 16px;
  overflow: hidden;
}

.chart-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6e7681;
  background: #0d1117;
  border-radius: 6px;
  border: 1px dashed #30363d;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.chart-placeholder p {
  font-size: 13px;
}

.chart-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #8b949e;
}

.chart-content {
  height: 100%;
  background: #0d1117;
  border-radius: 6px;
  border: 1px solid #30363d;
  padding: 16px;
}

.equity-curve-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.curve-mock {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 150px;
  padding: 20px;
}

.mock-line {
  width: 24px;
  background: linear-gradient(to top, #238636, #3fb950);
  border-radius: 3px 3px 0 0;
  min-height: 20px;
}

.chart-hint {
  color: #6e7681;
  font-size: 12px;
  margin-top: 16px;
}

/* 日志控制台 */
.console-section {
  height: 180px;
  background: #0d1117;
  flex-shrink: 0;
}

.console-tabs {
  height: 100%;
}

.console-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
  padding: 0 12px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
}

.console-tabs :deep(.ant-tabs-content) {
  height: calc(100% - 36px);
}

.console-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
}

.console-content {
  height: 100%;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.empty-console {
  color: #6e7681;
  text-align: center;
  padding: 40px;
}

.log-list, .error-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item, .error-item {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid #21262d;
}

.log-time, .error-time {
  color: #6e7681;
  flex-shrink: 0;
}

.log-message {
  color: #c9d1d9;
}

.error-message {
  color: #f85149;
}

/* 深色主题覆盖 */
:deep(.ant-input),
:deep(.ant-input-number),
:deep(.ant-picker),
:deep(.ant-select-selector) {
  background: #21262d !important;
  border-color: #30363d !important;
  color: #c9d1d9 !important;
}

:deep(.ant-input::placeholder),
:deep(.ant-input-number-input::placeholder) {
  color: #6e7681 !important;
}

:deep(.ant-select-selection-item) {
  color: #c9d1d9 !important;
}

:deep(.ant-picker-suffix),
:deep(.ant-select-arrow) {
  color: #8b949e !important;
}

:deep(.ant-btn) {
  background: #21262d;
  border-color: #30363d;
  color: #c9d1d9;
}

:deep(.ant-btn:hover) {
  background: #30363d;
  border-color: #8b949e;
  color: #c9d1d9;
}

:deep(.ant-btn-primary) {
  background: #1f6feb;
  border-color: #1f6feb;
  color: #fff;
}

:deep(.ant-btn-primary:hover) {
  background: #388bfd;
  border-color: #388bfd;
}

:deep(.ant-btn-dashed) {
  background: transparent;
  border-color: #30363d;
  color: #8b949e;
}

:deep(.ant-btn-dashed:hover) {
  border-color: #58a6ff;
  color: #58a6ff;
}

:deep(.ant-tabs-tab) {
  color: #8b949e;
}

:deep(.ant-tabs-tab-active) {
  color: #c9d1d9;
}

:deep(.ant-tabs-ink-bar) {
  background: #1f6feb;
}

:deep(.ant-progress-bg) {
  background: #238636;
}

:deep(.ant-progress-text) {
  color: #c9d1d9;
}

:deep(.ant-modal-content),
:deep(.ant-modal-header) {
  background: #161b22;
  border-color: #30363d;
}

:deep(.ant-modal-title) {
  color: #c9d1d9;
}

:deep(.ant-form-item-label > label) {
  color: #c9d1d9;
}
</style>
