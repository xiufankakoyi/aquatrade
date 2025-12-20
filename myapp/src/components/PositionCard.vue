<template>
  <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-white">当日持仓</h3>
      <div v-if="positions.length === 0" class="text-base text-slate-400">
        暂无持仓
      </div>
    </div>
    
    <div v-if="positions.length > 0" class="space-y-4">
      <!-- 表头 -->
      <div class="grid grid-cols-4 gap-4 text-sm text-slate-400 pb-2 border-b border-slate-700/50">
        <div class="font-medium">市值</div>
        <div class="font-medium">收益率</div>
        <div class="font-medium">可用数量</div>
        <div class="font-medium">现价</div>
      </div>
      
      <!-- 持仓数据 -->
      <div
        v-for="position in positions"
        :key="position.symbolCode"
        class="bg-[#1a1f2e] rounded-lg p-4 border border-slate-700/50"
        :class="getColorClass(position.profitLoss)"
      >
        <div class="grid grid-cols-4 gap-4 text-base">
          <!-- 第一行 -->
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">标的名称</p>
            <p class="text-lg font-bold text-white">{{ position.symbolName || position.symbolCode }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">浮动盈亏</p>
            <p class="text-lg font-semibold">{{ formatCurrency(position.profitLoss) }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">持仓数量</p>
            <p class="text-base font-medium text-slate-300">{{ formatQuantity(position.quantity) }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">成本价</p>
            <p class="text-base font-medium text-slate-300">¥{{ position.cost.toFixed(2) }} <span class="text-xs text-slate-500">(前复权)</span></p>
          </div>
          
          <!-- 第二行 -->
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">市值</p>
            <p class="text-base font-medium text-slate-300">¥{{ position.positionValue.toFixed(2) }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">收益率</p>
            <p class="text-base font-semibold">{{ formatPercent(position.profitRatio) }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">可用数量</p>
            <p class="text-base font-medium text-slate-300">{{ formatQuantity(position.availableQuantity) }}</p>
          </div>
          
          <div class="space-y-1">
            <p class="text-xs text-slate-500 mb-1">现价</p>
            <p class="text-base font-medium text-slate-300">¥{{ position.currentPrice.toFixed(2) }} <span class="text-xs text-slate-500">(前复权)</span></p>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else class="flex items-center justify-center h-32 text-slate-500">
      <div class="text-center">
        <i class="fas fa-box-open text-4xl mb-2"></i>
        <p>暂无持仓</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { HoldingPeriod } from '../types/backtest';

type HoldingPeriodWithPricing = HoldingPeriod & {
  quantity?: number;
  entryPrice?: number;
  availableQuantity?: number;
};

interface Position {
  symbolCode: string;
  symbolName: string;
  quantity: number;
  cost: number;
  currentPrice: number;
  positionValue: number;
  profitLoss: number;
  profitRatio: number;
  availableQuantity: number;
}

interface Props {
  holdingPeriods?: HoldingPeriodWithPricing[];
  currentDate: string;
  latestPrices?: Record<string, number>; // symbolCode -> latest price
}

const props = withDefaults(defineProps<Props>(), {
  holdingPeriods: () => [],
  currentDate: () => new Date().toISOString().slice(0, 10),
  latestPrices: () => ({})
});

// 统一代码格式，避免大小写/前后缀差异导致价格查不到
const normalizeSymbolCode = (value?: string): string => {
  if (!value) return '';
  const trimmed = value.trim().toUpperCase();
  const match = trimmed.match(/(\d{6})/);
  return match ? match[1] : trimmed;
};

// 计算当前持仓（exitDate 为 null 或未卖出的持仓）
const positions = computed<Position[]>(() => {
  const currentPositions: Position[] = [];
  
  // 筛选出当前持仓（exitDate 为 null 或空）
  const openPositions = props.holdingPeriods.filter(
    hp => !hp.exitDate || hp.exitDate === null
  );
  
  // 按 symbolCode 分组，处理同一标的的多次买入
  const positionMap = new Map<string, {
    symbolCode: string;
    symbolName: string;
    totalQuantity: number;
    totalCost: number;
    entryDates: string[];
  }>();
  
  openPositions.forEach(hp => {
    const rawSymbolCode = hp.symbolCode || '';
    const symbolCode = normalizeSymbolCode(rawSymbolCode);
    const symbolName = hp.symbolName || rawSymbolCode || symbolCode;
    const quantity = hp.quantity || 0;
    const entryPrice = hp.entryPrice || 0;
    const entryDate = hp.entryDate || '';
    
    if (!symbolCode || quantity <= 0) return;
    
    if (positionMap.has(symbolCode)) {
      const existing = positionMap.get(symbolCode)!;
      existing.totalQuantity += quantity;
      existing.totalCost += quantity * entryPrice;
      existing.entryDates.push(entryDate);
    } else {
      positionMap.set(symbolCode, {
        symbolCode,
        symbolName,
        totalQuantity: quantity,
        totalCost: quantity * entryPrice,
        entryDates: [entryDate]
      });
    }
  });
  
  // 转换为 Position 数组
  positionMap.forEach((pos, symbolCode) => {
    const avgCost = pos.totalQuantity > 0 ? pos.totalCost / pos.totalQuantity : 0;
    // CHANGED: 优先使用 API 获取的回测结束日期前复权价格
    // 如果还没有获取到价格，暂时使用成本价（但会在价格获取后自动更新）
    const currentPrice = props.latestPrices[normalizeSymbolCode(symbolCode)] ?? avgCost;
    const positionValue = pos.totalQuantity * currentPrice;
    const profitLoss = positionValue - pos.totalCost;
    const profitRatio = avgCost > 0 ? (profitLoss / pos.totalCost) * 100 : 0;
    
    currentPositions.push({
      symbolCode,
      symbolName: pos.symbolName,
      quantity: pos.totalQuantity,
      cost: avgCost,
      currentPrice,
      positionValue,
      profitLoss,
      profitRatio,
      availableQuantity: pos.totalQuantity // 假设全部可用（T+1 规则已在后端处理）
    });
  });
  
  return currentPositions.sort((a, b) => b.positionValue - a.positionValue);
});

// 格式化货币
function formatCurrency(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}¥${Math.abs(value).toFixed(2)}`;
}

// 格式化百分比
function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

// 格式化数量（确保是100的整数倍显示）
function formatQuantity(value: number): string {
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
}

function getColorClass(value: number): string {
  return value >= 0 ? 'text-red-400' : 'text-green-400';
}
</script>

<style scoped>
/* 确保 Grid 布局正确显示 */
.grid {
  display: grid;
}
</style>
