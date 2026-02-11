<template>
  <div class="dragon-eye-page p-6 space-y-6 bg-[#0b0e14] min-h-full">
    <!-- Header -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-2">
          <i class="fas fa-dragon text-orange-500"></i>
          DragonEye 龙虎榜监控
        </h1>
        <p class="text-slate-400 text-sm mt-1">深度监控市场高标股动态、题材热度及龙虎榜资金流向</p>
      </div>
      
      <div class="flex items-center gap-3">
        <div class="bg-slate-800/50 backdrop-blur rounded-lg px-3 py-1.5 border border-slate-700 flex items-center gap-2">
          <span class="text-xs text-slate-400">数据日期:</span>
          <input 
            type="date" 
            v-model="targetDate" 
            class="bg-transparent text-sm text-indigo-400 outline-none border-none cursor-pointer"
          />
        </div>
        <button 
          @click="startCrawl"
          :disabled="isCrawling"
          class="px-4 py-2 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white rounded-lg text-sm font-semibold transition-all shadow-lg shadow-orange-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <i class="fas" :class="isCrawling ? 'fa-spinner fa-spin' : 'fa-spider'"></i>
          {{ isCrawling ? '抓取中...' : '启动数据抓取' }}
        </button>
      </div>
    </div>

    <!-- Quick Stats & Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Sentiment Chart -->
      <div class="lg:col-span-2 bg-[#151925] rounded-xl border border-slate-800 p-5 shadow-sm">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-sm font-semibold text-white">市场情绪走势</h2>
          <div class="flex gap-2">
            <span class="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20">炸板率</span>
            <span class="text-[10px] bg-red-500/10 text-red-400 px-2 py-0.5 rounded border border-red-500/20">最高板</span>
          </div>
        </div>
        <div ref="chartRef" class="h-[280px] w-full"></div>
      </div>

      <!-- AI Summary Workflow -->
      <div class="bg-gradient-to-br from-[#1e2330] to-[#151925] rounded-xl border border-slate-700 p-5 relative overflow-hidden flex flex-col">
        <div class="relative z-10 flex flex-col h-full">
          <h2 class="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <i class="fas fa-brain text-purple-400"></i>
            AI 每日复盘简报
          </h2>
          
          <div v-if="aiBrief" class="flex-1 overflow-y-auto text-xs text-slate-300 leading-relaxed bg-black/20 p-3 rounded-lg border border-slate-800/50 mb-4 whitespace-pre-wrap">
            {{ aiBrief }}
          </div>
          <div v-else class="flex-1 flex items-center justify-center border border-dashed border-slate-700 rounded-lg mb-4">
            <p class="text-slate-500 text-xs">暂无抓取数据，请先启动抓取</p>
          </div>

          <div class="flex gap-2">
            <button 
              @click="fetchBrief"
              class="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors border border-slate-700"
            >
              更新简报
            </button>
            <button 
              @click="confirmAndPush"
              :disabled="!aiBrief || isPushing"
              class="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <i class="fas" :class="isPushing ? 'fa-spinner fa-spin' : 'fa-paper-plane'"></i>
              推送至飞书
            </button>
          </div>
        </div>
        <!-- Decorative element -->
        <div class="absolute -bottom-4 -right-4 w-32 h-32 bg-indigo-500/10 blur-3xl rounded-full"></div>
      </div>
    </div>

    <!-- Data Table -->
    <div class="bg-[#151925] rounded-xl border border-slate-800 overflow-hidden shadow-sm">
      <div class="p-5 border-b border-slate-800 flex justify-between items-center">
        <h2 class="text-sm font-semibold text-white">龙头股实时因子矩阵板</h2>
        <div class="flex gap-4 text-xs">
          <div class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-red-500"></span>
            <span class="text-slate-400">高连板</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-green-500"></span>
            <span class="text-slate-400">机构买入</span>
          </div>
        </div>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="bg-slate-800/30 text-slate-400 text-[11px] uppercase tracking-wider">
              <th class="px-6 py-3 font-medium">个股</th>
              <th class="px-6 py-3 font-medium">连板数</th>
              <th class="px-6 py-3 font-medium">封单额</th>
              <th class="px-6 py-3 font-medium">换手率</th>
              <th class="px-6 py-3 font-medium">监管</th>
              <th class="px-6 py-3 font-medium">机构</th>
              <th class="px-6 py-3 font-medium">题材标签</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800">
            <tr v-for="stock in dragonStocks" :key="stock.stock_code" class="hover:bg-slate-800/50 transition-colors">
              <td class="px-6 py-4">
                <div class="flex flex-col">
                  <span class="text-indigo-400 font-medium">{{ stock.stock_name }}</span>
                  <span class="text-[10px] text-slate-500">{{ stock.stock_code }}</span>
                </div>
              </td>
              <td class="px-6 py-4">
                <span class="px-2 py-0.5 rounded text-xs" 
                   :class="stock.continue_num >= 4 ? 'bg-red-500/20 text-red-500' : 'bg-orange-500/10 text-orange-400'">
                  {{ stock.continue_num }} 连板
                </span>
              </td>
              <td class="px-6 py-4 text-slate-300">{{ (stock.order_amount / 100000000).toFixed(2) }} 亿</td>
              <td class="px-6 py-4 text-slate-300">{{ stock.turnover_rate.toFixed(2) }}%</td>
              <td class="px-6 py-4">
                <i v-if="stock.is_regulation" class="fas fa-exclamation-triangle text-yellow-500" title="处于监管监控"></i>
                <span v-else class="text-slate-600">-</span>
              </td>
              <td class="px-6 py-4">
                <i v-if="stock.is_institution_buy" class="fas fa-university text-green-500" title="机构专用买入"></i>
                <span v-else class="text-slate-600">-</span>
              </td>
              <td class="px-6 py-4">
                <span class="text-xs text-slate-400 truncate max-w-[200px] block">{{ stock.leader_tag }}</span>
              </td>
            </tr>
            <tr v-if="dragonStocks.length === 0">
              <td colspan="7" class="px-6 py-12 text-center text-slate-500 italic">
                暂无当日龙头个股数据...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import axios from 'axios';
import { message } from 'ant-design-vue'; // 假设使用了 A-Design-Vue 或类似的通知库

const targetDate = ref(new Date().toISOString().split('T')[0]);
const isCrawling = ref(false);
const isPushing = ref(false);
const dragonStocks = ref<any[]>([]);
const aiBrief = ref('');
const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const fetchStocks = async () => {
  try {
    const res = await axios.get('/api/dragon/stocks', {
      params: { start_date: targetDate.value, end_date: targetDate.value }
    });
    dragonStocks.value = res.data;
  } catch (e) {
    console.error('Fetch stocks failed:', e);
  }
};

const fetchBrief = async () => {
  try {
    const res = await axios.get('/api/dragon/brief', { params: { date: targetDate.value } });
    aiBrief.value = res.data.content;
  } catch (e) {
    console.error('Fetch brief failed:', e);
  }
};

const fetchSentimentHistory = async () => {
  try {
    const end = targetDate.value;
    const start = new Date(new Date(end).getTime() - 15 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const res = await axios.get('/api/dragon/sentiment', { params: { start_date: start, end_date: end } });
    updateChart(res.data);
  } catch (e) {
    console.error('Fetch sentiment history failed:', e);
  }
};

const updateChart = (data: any[]) => {
  if (!chartInstance) return;
  
  const options = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { textStyle: { color: '#64748b', fontSize: 10 }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map(d => d.trade_date.slice(5)),
      axisLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#64748b', fontSize: 10 }
    },
    yAxis: [
      {
        type: 'value',
        name: '最高板',
        min: 0,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1e293b' } }
      },
      {
        type: 'value',
        name: '炸板率',
        max: 1,
        axisLabel: { color: '#64748b', fontSize: 10, formatter: (v: number) => (v * 100).toFixed(0) + '%' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '最高板',
        type: 'line',
        data: data.map(d => d.max_height),
        smooth: true,
        lineStyle: { color: '#ef4444', width: 2 },
        symbol: 'none',
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(239, 68, 68, 0.2)' }, { offset: 1, color: 'transparent' }]) }
      },
      {
        name: '炸板率',
        type: 'bar',
        yAxisIndex: 1,
        data: data.map(d => d.broken_ratio),
        itemStyle: { color: '#6366f1', borderRadius: [2, 2, 0, 0] },
        barWidth: '20%'
      }
    ]
  };
  chartInstance.setOption(options);
};

const startCrawl = async () => {
  isCrawling.value = true;
  try {
    await axios.post('/api/dragon/crawl', { date: targetDate.value });
    message.success('抓取任务已启动，请稍后刷新结果');
    // 轮询或延迟刷新
    setTimeout(() => {
        fetchStocks();
        fetchBrief();
        fetchSentimentHistory();
        isCrawling.value = false;
    }, 10000); 
  } catch (e) {
    message.error('启动抓取失败');
    isCrawling.value = false;
  }
};

const confirmAndPush = async () => {
  isPushing.value = true;
  try {
    await axios.post('/api/dragon/confirm', { date: targetDate.value });
    message.success('已成功推送至飞书');
  } catch (e: any) {
    message.error('推送失败: ' + (e.response?.data?.error || e.message));
  } finally {
    isPushing.value = false;
  }
};

onMounted(() => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value);
    const resizeHandler = () => chartInstance?.resize();
    window.addEventListener('resize', resizeHandler);
  }
  fetchStocks();
  fetchBrief();
  fetchSentimentHistory();
});

watch(targetDate, () => {
  fetchStocks();
  fetchBrief();
  fetchSentimentHistory();
});

onUnmounted(() => {
  chartInstance?.dispose();
});
</script>

<style scoped>
.dragon-eye-page {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
