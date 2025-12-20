<template>
  <div class="trade-table-container">
    <!-- Tab 切换 -->
    <div class="flex items-center space-x-4 mb-4">
      <button
        @click="activeTab = 'orders'"
        :class="activeTab === 'orders' ? 'bg-indigo-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50'"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2"
      >
        <span>📋</span>
        <span>委托流水</span>
      </button>
      <button
        @click="activeTab = 'closed'"
        :class="activeTab === 'closed' ? 'bg-indigo-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50'"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2"
      >
        <span>💰</span>
        <span>平仓记录</span>
      </button>
    </div>

    <!-- 委托流水 Tab -->
    <div v-if="activeTab === 'orders'" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/50">
          <tr>
            <th class="px-4 py-3 text-left text-slate-400 font-semibold">时间</th>
            <th class="px-4 py-3 text-left text-slate-400 font-semibold">标的</th>
            <th class="px-4 py-3 text-left text-slate-400 font-semibold">方向</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">成交价</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">数量</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">手续费</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">发生金额</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="trade in displayedOrders"
            :key="trade.id"
            @click="$emit('trade-select', trade)"
            class="border-b border-slate-800 hover:bg-slate-800/30 cursor-pointer transition-colors"
          >
            <td class="px-4 py-3 text-slate-300">{{ trade.date }}</td>
            <td class="px-4 py-3">
              <div class="text-slate-300 font-medium">{{ trade.symbol }}</div>
              <div class="text-xs text-slate-500">{{ trade.symbolCode }}</div>
            </td>
            <td class="px-4 py-3">
              <span
                class="px-2 py-1 text-xs rounded-full font-medium"
                :class="trade.action === 'buy' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'"
              >
                {{ trade.action === 'buy' ? '买入' : '卖出' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right text-slate-300">¥{{ trade.price.toFixed(2) }}</td>
            <td class="px-4 py-3 text-right text-slate-500">{{ trade.quantity }}</td>
            <td class="px-4 py-3 text-right text-slate-400">¥{{ (trade.commission || 0).toFixed(2) }}</td>
            <td class="px-4 py-3 text-right text-slate-300 font-medium">
              {{ trade.action === 'buy' ? '-' : '+' }}¥{{ (trade.price * trade.quantity).toFixed(2) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 平仓记录 Tab -->
    <div v-if="activeTab === 'closed'" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/50">
          <tr>
            <th class="px-4 py-3 text-left text-slate-400 font-semibold">平仓时间</th>
            <th class="px-4 py-3 text-left text-slate-400 font-semibold">标的</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">开仓价</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">平仓价</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">持有天数</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">最终盈亏</th>
            <th class="px-4 py-3 text-right text-slate-400 font-semibold">收益率</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="trade in closedTrades"
            :key="trade.id"
            @click="$emit('trade-select', trade)"
            class="border-b border-slate-800 hover:bg-slate-800/30 cursor-pointer transition-colors"
          >
            <td class="px-4 py-3 text-slate-300">{{ trade.date }}</td>
            <td class="px-4 py-3">
              <div class="text-slate-300 font-medium">{{ trade.symbol }}</div>
              <div class="text-xs text-slate-500">{{ trade.symbolCode }}</div>
            </td>
            <!-- 优先显示后端返回的 entry_price -->
            <td class="px-4 py-3 text-right text-slate-400">
              {{ trade.entry_price ? `¥${trade.entry_price.toFixed(2)}` : '-' }}
            </td>
            <td class="px-4 py-3 text-right text-slate-300">¥{{ trade.price.toFixed(2) }}</td>
            <!-- 优先显示后端返回的 holding_days -->
            <td class="px-4 py-3 text-right text-slate-400">
              {{ trade.holdingDays !== undefined ? `${trade.holdingDays}天` : '-' }}
            </td>
            <!-- 优先显示后端返回的 profit_loss -->
            <td 
              class="px-4 py-3 text-right font-medium"
              :class="(trade.profitLoss || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
            >
              {{ (trade.profitLoss || 0) >= 0 ? '+' : '' }}¥{{ (trade.profitLoss || 0).toFixed(2) }}
            </td>
            <td 
              class="px-4 py-3 text-right"
              :class="(trade.roi || 0) >= 0 ? 'text-red-400' : 'text-green-400'"
            >
              {{ (trade.roi || 0) >= 0 ? '+' : '' }}{{ (trade.roi || 0).toFixed(2) }}%
            </td>
          </tr>
          <tr v-if="closedTrades.length === 0">
            <td colspan="7" class="px-4 py-8 text-center text-slate-500">暂无平仓记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { Trade } from '../../types/backtest';

const props = defineProps<{
  trades: Trade[];
}>();

const activeTab = ref<'orders' | 'closed'>('orders');

const displayedOrders = computed(() => {
  // CHANGED: 增加过滤，排除无效数据（价格<=0 或 数量<=0）防止显示脏数据
  return [...props.trades]
    .filter(t => t.price > 0 && t.quantity > 0)
    .sort((a, b) => b.date.localeCompare(a.date));
});

// 筛选出所有卖出操作，且后端已经计算好盈亏的记录
const closedTrades = computed(() => {
  return props.trades
    .filter(t => t.action === 'sell' && t.entry_price) // CHANGED: 仅显示包含开仓价（即成功匹配闭环）的卖出记录，过滤掉"奇怪的卖点"
    .sort((a, b) => b.date.localeCompare(a.date));
});
</script>