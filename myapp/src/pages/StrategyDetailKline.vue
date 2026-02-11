<template>
  <div class="h-[calc(100vh-64px)] bg-[#131722] flex flex-col overflow-hidden">
    <!-- 顶部工具栏 -->
    <div class="h-14 px-4 bg-[#1E222D] border-b border-[#2A2E39] flex items-center justify-between shrink-0">
      <div class="flex items-center space-x-4">
        <div>
          <h2 class="text-base font-semibold text-[#D1D4DC] flex items-center">
            {{ selectedSymbolName || selectedSymbol || '--' }}
            <span class="ml-2 px-1.5 py-0.5 text-xs font-normal bg-[#2A2E39] text-[#787B86] rounded">DAY</span>
          </h2>
        </div>
        
        <!-- 交易标记示例（改为更紧凑的样式） -->
        <div class="h-6 w-px bg-[#2A2E39]"></div>
        <div class="flex items-center space-x-3">
          <div class="flex items-center space-x-1.5">
            <div class="w-2 h-2 bg-red-500 rounded-full"></div>
            <span class="text-xs text-[#787B86]">买入</span>
          </div>
          <div class="flex items-center space-x-1.5">
            <div class="w-2 h-2 bg-green-500 rounded-full"></div>
            <span class="text-xs text-[#787B86]">卖出</span>
          </div>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- Instruction A: Shadow Curve Toggle -->
        <div class="flex items-center bg-[#2A2E39] rounded px-2 py-1 gap-2 border border-[#363A45]">
          <span class="text-[11px] text-[#787B86] uppercase font-bold">影子曲线:</span>
          <button 
            @click="backtestStore.toggleAutoExcludeAlphaLoss()"
            :class="['text-[10px] px-2 py-0.5 rounded transition-all font-bold', 
              backtestStore.autoExcludeAlphaLoss ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' : 'text-[#D1D4DC] hover:bg-white/5']"
          >
            剔除 Alpha 亏损单
          </button>
        </div>

        <button
          @click="$emit('run-backtest')"
          class="px-3 py-1.5 text-sm font-medium text-white bg-[#2962FF] hover:bg-[#1E53E5] rounded transition-colors flex items-center shadow-lg shadow-blue-500/10"
        >
          <i class="fas fa-play mr-1.5 text-xs"></i>运行回测
        </button>
      </div>
    </div>

    <!--主要内容区域：图表 + 侧边/底部面板-->
    <div class="flex-1 flex overflow-hidden">
      <!-- 图表区域 -->
          <div class="flex-1 w-full h-full relative">
            <EquityCurve
              :kline-data="klineData"
              :highlight-ranges="highlightRanges"
              :trade-markers="tradeMarkersForKline"
              :versions="equityCurveVersions"
              :shadow-series="backtestStore.shadowEquitySeries"
              :benchmark="benchmarkSeries"
              :x-axis-min="fullRange.min"
              :x-axis-max="fullRange.max"
              mode="kline"
              class="w-full h-full"
            />
            
            <!-- Playback Controller Overlay -->
            <div class="absolute bottom-4 left-1/2 -translate-x-1/2 w-[90%] z-20">
              <PlaybackController v-if="backtestStore.hasData" />
            </div>
          </div>
      
      <!-- 右侧持仓面板/雷达 -->
      <div class="w-[340px] bg-[#1c202b] border-l border-[#2a2e39] flex flex-col shrink-0 z-10">
        <!-- New: Risk Radar -->
        <div class="h-[280px] p-4 border-b border-[#2a2e39]">
          <LiveRiskRadar />
        </div>
        
        <div class="flex-1 overflow-y-auto p-0">
          <PositionCard
            :holding-periods="currentHoldingPeriods"
            :current-date="currentDate"
            :latest-prices="latestPrices"
            :total-equity="currentDateEquity"
            @analyze="handlePositionAnalyze"
          />
        </div>
      </div>
    </div>

    <!-- 底部交易记录面板 (可调整高度) -->
    <div 
      class="bg-[#1E222D] border-t border-[#2A2E39] flex flex-col shrink-0 overflow-hidden relative"
      :style="{ height: isTradePanelExpanded ? `${tradePanelHeight}px` : '40px' }"
    >
      <!-- Resize Handle -->
      <div 
        class="absolute top-0 left-0 w-full h-2 cursor-ns-resize hover:bg-[#2962FF]/30 z-20 transition-all group"
        @mousedown="startResizing"
      >
        <div class="w-12 h-1 bg-[#2A2E39] group-hover:bg-[#2962FF] rounded-full mx-auto mt-0.5 transition-colors"></div>
      </div>

      <div class="h-10 px-4 border-b border-[#2A2E39] flex items-center justify-between shrink-0 cursor-pointer hover:bg-[#2A2E39]" 
           @click="toggleTradePanel">
        <div class="flex items-center space-x-2">
           <i :class="['fas', isTradePanelExpanded ? 'fa-chevron-down' : 'fa-chevron-up', 'text-[#787B86] text-xs']"></i>
           <h3 class="text-sm font-medium text-[#D1D4DC]">交易明细</h3>
        </div>
        
        <div v-if="strategyStore.isLoading" class="flex items-center space-x-2 text-xs text-[#787B86]">
          <i class="fas fa-spinner fa-spin"></i>
          <span>加载中...</span>
        </div>
      </div>
      
      <div v-show="isTradePanelExpanded" class="flex-1 overflow-hidden p-4 bg-[#1E222D]">
         <!-- 错误信息 -->
        <div v-if="strategyStore.error" class="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400">
          <i class="fas fa-exclamation-circle mr-2"></i>{{ strategyStore.error }}
        </div>
        
        <!-- 交易记录表格 -->
        <TradeTable
          v-if="trades.length > 0"
          :trades="trades"
          :highlight-date="normalizeDate(playbackCursor)"
          @trade-select="handleTradeSelect($event, true)"
        />
        
        <!-- 无交易记录提示 -->
        <div v-else-if="!strategyStore.isLoading" class="py-8 text-center">
          <div class="inline-flex items-center justify-center w-12 h-12 mb-3 rounded-full bg-[#2A2E39] text-[#787B86]">
            <i class="fas fa-exchange-alt text-lg"></i>
          </div>
          <h4 class="mb-1 text-sm font-medium text-[#D1D4DC]">暂无交易记录</h4>
          <p class="text-xs text-[#787B86]">
            {{ getNoTradesMessage() }}
          </p>
        </div>
      </div>
    </div>

    <!-- Deep Dive Modal -->
    <TradeDeepDive
      v-if="selectedDeepDiveTrade"
      :is-open="isDeepDiveOpen"
      :symbol-code="selectedDeepDiveTrade.symbolCode"
      :symbol-name="selectedDeepDiveTrade.symbol"
      :start-date="deepDiveStartDate"
      :end-date="deepDiveEndDate"
      :trades="backtestStore.trades"
      :benchmark-code="backtestStore.lastRunParams?.benchmarkCode"
      :playback-cursor="playbackCursor"
      @close="isDeepDiveOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute, useRouter } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useKlineStore } from '../store/klineStore';
import { useBacktestStore } from '../store/backtestStore';
import { useDashboardStore } from '../store/dashboardStore';
import { useSocketIO } from '../composables/useSocketIO';
import { getStrategyDetail, getLatestPrices, getAvailableVersions } from '../api/backtestApi';
import EquityCurve from '../components/EquityCurve.vue';
import TradeTable from '../components/tables/TradeTable.vue';
import PositionCard from '../components/PositionCard.vue';
import PlaybackController from '../components/PlaybackController.vue';
import TradeDeepDive from '../components/modals/TradeDeepDive.vue';
import LiveRiskRadar from '../components/LiveRiskRadar.vue';
import type { Trade, HoldingPeriod as HoldingPeriodType } from '../types/backtest';

const route = useRoute();
const router = useRouter();
const strategyStore = useStrategyStore();
const klineStore = useKlineStore();
const backtestStore = useBacktestStore();
const dashboardStore = useDashboardStore();
const { connect } = useSocketIO();
const isTradePanelExpanded = ref(true);
const tradePanelHeight = ref(256); // 默认高度
const isResizing = ref(false);

function startResizing(e: MouseEvent) {
  isResizing.value = true;
  document.addEventListener('mousemove', doResize);
  document.addEventListener('mouseup', stopResizing);
  // 防止在拖动时选中文本
  e.preventDefault();
}

function doResize(e: MouseEvent) {
  if (!isResizing.value) return;
  
  // 计算新的高度：视口高度 - 鼠标 y 坐标
  const newHeight = window.innerHeight - e.clientY;
  
  // 限制高度范围
  if (newHeight > 100 && newHeight < window.innerHeight * 0.8) {
    tradePanelHeight.value = newHeight;
    // 如果拖动了，确保面板是展开的
    isTradePanelExpanded.value = true;
  }
}

function stopResizing() {
  isResizing.value = false;
  document.removeEventListener('mousemove', doResize);
  document.removeEventListener('mouseup', stopResizing);
}

const selectedDeepDiveTrade = ref<Trade | null>(null);
const isDeepDiveOpen = ref(false);
const deepDiveStartDate = ref('');
const deepDiveEndDate = ref('');
const stockNames = ref<Record<string, string>>({}); // NEW: 缓存股票代码到中文名称的映射

const { 
  holdingPeriods: holdingPeriodsRef, 
  lastUpdated: lastUpdatedRef, 
  trades: tradesRef, 
  playbackMode, 
  playbackCursor 
} = storeToRefs(backtestStore);

// Consolidated trades: filtered by playback cursor and including complex fallbacks
const trades = computed<Trade[]>(() => {
  let baseTrades: Trade[] = backtestStore.trades;
  
  // Fallback to strategyStore if store is empty
  if (baseTrades.length === 0 && strategyStore.currentBacktestResult?.trades) {
    baseTrades = strategyStore.currentBacktestResult.trades;
  }
  
  // Fallback to derived trades from holdings if still empty
  if (baseTrades.length === 0 && mappedHoldingPeriods.value.length > 0) {
    baseTrades = mappedHoldingPeriods.value.flatMap(hp => {
      const arr = [];
      if (hp.entryDate) arr.push({ id: `${hp.positionId}-b`, symbol: hp.symbolName, symbolCode: hp.symbolCode, date: hp.entryDate, action: 'buy', price: hp.entryPrice || 0, quantity: hp.quantity || 0 } as Trade);
      if (hp.exitDate) arr.push({ id: `${hp.positionId}-s`, symbol: hp.symbolName, symbolCode: hp.symbolCode, date: hp.exitDate, action: 'sell', price: hp.exitPrice || 0, quantity: hp.quantity || 0, profitLoss: hp.profit } as Trade);
      return arr;
    });
  }

  // Apply playback filter with robust date normalization
  if (playbackMode.value && playbackCursor.value) {
    const cursor = normalizeDate(playbackCursor.value);
    baseTrades = baseTrades.filter(t => normalizeDate(t.date || t.entryDate) <= cursor);
  }

  return baseTrades.map(trade => {
    const normalizedCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
    
    // Attempt to lookup Chinese name from various sources
    let displayName = trade.symbol || normalizedCode;
    
    // Optimization: Only lookup if display name looks like a code
    if (/^\d{6}$/.test(displayName)) {
      // 1. 优先从 stockNames 缓存中获取（由 getLatestPrices API 提供）
      if (stockNames.value[normalizedCode]) {
        displayName = stockNames.value[normalizedCode];
      } 
      // 2. 其次从持仓记录中查找
      else {
        // Use a more direct lookup if possible, but for now we keep the find for simplicity 
        // unless trades array is massive
        const holding = mappedHoldingPeriods.value.find(hp => normalizeSymbolCode(hp.symbolCode) === normalizedCode);
        if (holding && holding.symbolName && !/^\d{6}$/.test(holding.symbolName)) {
          displayName = holding.symbolName;
        }
      }
    }

    return {
      ...trade,
      date: normalizeDate(trade.date),
      entryDate: trade.entryDate ? normalizeDate(trade.entryDate) : undefined,
      exitDate: trade.exitDate ? normalizeDate(trade.exitDate) : undefined,
      symbolCode: normalizedCode,
      symbol: displayName
    };
  });
});

const currentDate = computed(() => {
  if (playbackMode.value && playbackCursor.value) return normalizeDate(playbackCursor.value);
  const endDate = backtestStore.lastRunParams?.endDate || lastUpdatedRef.value;
  if (endDate) return normalizeDate(endDate);
  return new Date().toISOString().split('T')[0];
});

// NEW: 当前日期（或回放游标所在日期）的账户净值，用于同步持仓市值显示
const currentDateEquity = computed(() => {
  const date = currentDate.value;
  if (!date || backtestStore.equitySeries.length === 0) return 0;
  // 精确匹配日期点
  const point = backtestStore.equitySeries.find(p => normalizeDate(p.date) === date);
  return point ? point.equity : 0;
});

const equityCurveVersions = computed(() => {
  let series = backtestStore.equitySeries;
  
  // Fallback to strategyStore if backtestStore is empty
  if (series.length === 0 && strategyStore.currentBacktestResult?.equityCurve) {
    series = strategyStore.currentBacktestResult.equityCurve.map(p => ({
      date: p.date,
      equity: p.equity
    }));
  }

  if (playbackMode.value && playbackCursor.value) {
    const cursor = normalizeDate(playbackCursor.value);
    series = series.filter(p => normalizeDate(p.date) <= cursor);
  }
  
  if (series.length === 0) return [];
  
  return [{
    versionId: 'current',
    versionName: '策略净值',
    data: series
  }];
});

const benchmarkSeries = computed(() => {
  let series = backtestStore.benchmarkEquitySeries;
  
  // Fallback to strategyStore if backtestStore is empty
  if (series.length === 0 && strategyStore.currentBacktestResult?.equityCurve) {
    series = strategyStore.currentBacktestResult.equityCurve
      .filter(p => p.benchmarkEquity !== undefined && p.benchmarkEquity !== null)
      .map(p => ({
        date: p.date,
        equity: p.benchmarkEquity!
      }));
  }

  if (playbackMode.value && playbackCursor.value) {
    const cursor = normalizeDate(playbackCursor.value);
    series = series.filter(p => normalizeDate(p.date) <= cursor);
  }
  
  return series;
});

const fullRange = computed(() => {
  const series = backtestStore.equitySeries;
  if (series.length === 0) return { min: '', max: '' };
  return {
    min: normalizeDate(series[0].date),
    max: normalizeDate(series[series.length - 1].date)
  };
});

function normalizeSymbolCode(value?: string | null): string {
  if (!value) return '';
  const trimmed = value.trim().toUpperCase();
  const match = trimmed.match(/(\d+)/);
  if (match) {
    // CHANGED: Keep leading zeros for A-shares by padding to 6 digits
    // This fixed the issue where 001222 became 1222, breaking name lookups.
    const digits = match[1];
    return digits.length < 6 ? digits.padStart(6, '0') : digits;
  }
  return trimmed;
}

/**
 * Normalize date strings to YYYY-MM-DD for consistent comparison
 */
function normalizeDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  // Convert YYYY/MM/DD to YYYY-MM-DD
  return dateStr.replace(/\//g, '-').split(' ')[0];
}

const highlightRanges = ref<Array<{ start: string; end: string }>>([]);
const selectedTrade = ref<Trade | null>(null);
const realtimeTrades = ref<Trade[]>([]);

function toggleTradePanel() {
  isTradePanelExpanded.value = !isTradePanelExpanded.value;
}

const selectedSymbol = computed(() => klineStore.selectedSymbol);
const klineData = computed(() => {
  const data = klineStore.klineData;
  if (playbackMode.value && playbackCursor.value) {
    const cursor = normalizeDate(playbackCursor.value);
    return data.filter(d => normalizeDate(d.date) <= cursor);
  }
  return data;
});

// CHANGED: 计算当前选中标的的名称（用于显示）
const selectedSymbolName = computed(() => {
  const targetSymbol = normalizeSymbolCode(selectedSymbol.value);
  if (!targetSymbol) return '';
  
  // 优先从持仓记录中查找
  const holding = mappedHoldingPeriods.value.find(hp => 
    normalizeSymbolCode(hp.symbolCode || hp.symbol) === targetSymbol
  );
  if (holding && holding.symbolName) {
    return holding.symbolName;
  }
  
  // 从交易记录中查找
  const trade = trades.value.find(t => 
    normalizeSymbolCode(t.symbolCode || t.symbol) === targetSymbol
  );
  if (trade && trade.symbol) {
    // 如果 trade.symbol 是名称（包含中文），直接返回
    // 如果是代码，尝试从持仓记录中查找名称
    if (trade.symbol && !/^\d{6}$/.test(trade.symbol)) {
      return trade.symbol;
    }
  }
  
  // 如果都没找到，返回代码本身
  return targetSymbol;
});

// CHANGED: 计算当前选中标的的交易标记（用于 K 线图显示）
const tradeMarkersForKline = computed(() => {
  const targetSymbol = normalizeSymbolCode(selectedSymbol.value);
  if (!targetSymbol) return [];

  const openHoldingCodes = new Set(
    currentHoldingPeriods.value.map(hp => normalizeSymbolCode(hp.symbolCode || hp.symbol))
  );

  // 建立日期->前复权收盘价映射，确保买卖点价格与 K 线复权后价格一致
  const closeMap: Record<string, number> = {};
  klineData.value.forEach(item => {
    if (item?.date && typeof item.close === 'number') {
      closeMap[item.date] = item.close;
    }
  });
  
  // 获取当前标的的所有交易记录
  const symbolTrades = trades.value.filter(t => 
    normalizeSymbolCode(t.symbolCode || t.symbol) === targetSymbol
  );

  // 转换为交易标记格式；如果存在未卖出的持仓，则隐藏该标的没有 exitDate 的卖出点，避免虚假卖点
  return symbolTrades
    .filter(trade => {
      if (trade.action === 'sell' && openHoldingCodes.has(targetSymbol) && !trade.exitDate) {
        return false;
      }
      return true;
    })
    .map(trade => ({
      date: trade.date,
      action: trade.action,
      // 优先使用当前 K 线数据里的前复权价，避免显示未复权的成交价
      price: closeMap[trade.date] ?? trade.price,
      quantity: trade.quantity,
      symbol: trade.symbol,
      profitLoss: trade.profitLoss,
      entryDate: trade.entryDate,
      exitDate: trade.exitDate,
      holdingDays: trade.entryDate && trade.exitDate
        ? Math.floor((new Date(trade.exitDate).getTime() - new Date(trade.entryDate).getTime()) / (1000 * 60 * 60 * 24))
        : undefined
    }));
});

type RawHoldingPeriod = HoldingPeriodType & {
  position_id?: string;
  symbol_code?: string;
  symbol_name?: string;
  entry_date?: string;
  exit_date?: string | null;
  entry_price?: number;
  exit_price?: number;
  days?: number;
  quantity?: number;
};

const rawHoldingPeriods = computed<RawHoldingPeriod[]>(() => {
  if (Array.isArray(holdingPeriodsRef.value) && holdingPeriodsRef.value.length > 0) {
    return holdingPeriodsRef.value as unknown as RawHoldingPeriod[];
  }
  const fallback = (strategyStore.currentBacktestResult as any)?.holdingPeriods;
  return Array.isArray(fallback) ? fallback : [];
});

const mappedHoldingPeriods = computed<HoldingPeriodType[]>(() => {
  return rawHoldingPeriods.value.map((hp) => {
    const symbolCode = normalizeSymbolCode(hp.symbolCode || hp.symbol_code || hp.symbol || '');
    return {
      positionId: hp.positionId || hp.position_id || '',
      symbolCode,
      symbolName: hp.symbolName || hp.symbol_name || hp.symbolCode || hp.symbol_code || '',
      entryDate: hp.entryDate || hp.entry_date || (hp as any).buyDate || '',
      exitDate: hp.exitDate ?? hp.exit_date ?? (hp as any).sellDate ?? null,
      entryPrice: hp.entryPrice ?? hp.entry_price ?? undefined,
      exitPrice: hp.exitPrice ?? hp.exit_price ?? undefined,
      quantity: hp.quantity ?? (hp as any).shares ?? 0,
      profit: hp.profit ?? (hp as any).profitLoss ?? (hp as any).pnl ?? 0,
      holdingDays: hp.holdingDays ?? hp.days ?? (hp as any).holding_days ?? undefined
    };
  });
});

function isOpenHolding(hp: HoldingPeriodType): boolean {
  if (!hp.exitDate) return true;
  const exit = String(hp.exitDate).trim().toLowerCase();
  return exit === 'open' || exit === '未平仓' || exit === 'ongoing';
}

const derivedHoldingsFromTrades = computed<HoldingPeriodType[]>(() => {
  if (trades.value.length === 0) return [];
  const sortedTrades = [...trades.value].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const positionMap = new Map<string, {
    symbolCode: string;
    symbolName: string;
    quantity: number;
    totalCost: number;
    entryDate: string;
  }>();

  sortedTrades.forEach(trade => {
    const symbolCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
    if (!symbolCode || !trade.quantity) return;
    const symbolName = trade.symbol || symbolCode;
    const qty = trade.quantity;
    const price = trade.price || 0;

    if (trade.action === 'buy') {
      if (!positionMap.has(symbolCode)) {
        positionMap.set(symbolCode, {
          symbolCode,
          symbolName,
          quantity: 0,
          totalCost: 0,
          entryDate: trade.entryDate || trade.date
        });
      }
      const position = positionMap.get(symbolCode)!;
      position.totalCost += price * qty;
      position.quantity += qty;
      if (!position.entryDate) {
        position.entryDate = trade.entryDate || trade.date;
      }
    } else if (trade.action === 'sell') {
      const position = positionMap.get(symbolCode);
      if (!position || position.quantity <= 0) return;
      const sellQty = Math.min(qty, position.quantity);
      const avgCost = position.quantity > 0 ? position.totalCost / position.quantity : price;
      position.quantity -= sellQty;
      position.totalCost -= avgCost * sellQty;
      if (position.quantity <= 0) {
        positionMap.delete(symbolCode);
      }
    }
  });

  return Array.from(positionMap.values())
    .filter(position => position.quantity > 0)
    .map(position => ({
      positionId: `${position.symbolCode}-derived`,
      symbolCode: position.symbolCode,
      symbolName: position.symbolName,
      entryDate: position.entryDate,
      exitDate: null,
      entryPrice: position.quantity > 0 ? position.totalCost / position.quantity : undefined,
      quantity: position.quantity
    }));
});

const openHoldingPeriods = computed(() => mappedHoldingPeriods.value.filter(isOpenHolding));

const currentHoldingPeriods = computed<HoldingPeriodType[]>(() => {
  // If in playback mode, ALWAYS use derived holdings to show the time-travel state
  if (playbackMode.value) {
    return derivedHoldingsFromTrades.value;
  }
  
  if (openHoldingPeriods.value.length > 0) {
    return openHoldingPeriods.value;
  }
  return derivedHoldingsFromTrades.value;
});

// Removed duplicate trades and currentDate definitions for playback consolidation.

/**
 * 根据当前情况生成合适的无交易记录提示信息
 */
function getNoTradesMessage(): string {
  const versionId = route.params.id as string || route.params.versionId as string;
  
  if (!versionId || versionId === 'default') {
    return '请从总览页面选择一个有效的策略版本，或直接运行回测生成交易记录。';
  }
  
  if (strategyStore.error) {
    return `无法加载该策略版本的交易记录。${strategyStore.error}`;
  }
  
  return '该策略版本还没有交易记录，请运行回测生成交易数据。';
}

// 定义事件
const emit = defineEmits(['run-backtest']);

const fetchedLatestPrices = ref<Record<string, number>>({});
const requestedLatestPriceSymbols = new Set<string>();

// CHANGED: 优先使用从 API 获取的最新价格（前复权价格，回测结束日期的价格）
const latestPrices = computed<Record<string, number>>(() => {
  const normalized: Record<string, number> = {};

  // 只使用从 API 获取的价格（这是回测结束日期的前复权价格，最准确）
  // 不再使用 K 线数据或交易记录中的价格，因为这些不是回测结束日期的价格
  Object.entries(fetchedLatestPrices.value).forEach(([symbol, price]) => {
    const normalizedCode = normalizeSymbolCode(symbol);
    if (normalizedCode && typeof price === 'number' && !Number.isNaN(price) && price > 0) {
      normalized[normalizedCode] = price;
    }
  });

  return normalized;
});

// CHANGED: 增加防抖处理，避免在回测或播放过程中高频触发价格获取
let fetchTimeout: any = null;
watch([currentHoldingPeriods, trades, playbackCursor], ([holdings, allTrades, cursor]) => {
  if (fetchTimeout) clearTimeout(fetchTimeout);
  
  fetchTimeout = setTimeout(() => {
    const symbolsToFetch: string[] = [];
    
    // 收集持仓中的标的
    holdings.forEach(hp => {
      const symbolCode = normalizeSymbolCode(hp.symbolCode || hp.symbol);
      if (symbolCode) symbolsToFetch.push(symbolCode);
    });
    
    // 收集交易记录中的标的
    allTrades.forEach(t => {
      const symbolCode = normalizeSymbolCode(t.symbolCode || t.symbol);
      if (symbolCode) symbolsToFetch.push(symbolCode);
    });
    
    // CHANGED: 如果在回放模式下日期变了，即使持仓没变也要重新获取该日期的价格
    const uniqueSymbols = [...new Set(symbolsToFetch)];

    if (uniqueSymbols.length > 0) {
      // 在回放模式下，我们允许重复请求，因为日期变了价格就变了
      if (!playbackMode.value) {
        const filteredSymbols = uniqueSymbols.filter(symbolCode => {
          if (fetchedLatestPrices.value[symbolCode] && stockNames.value[symbolCode]) return false;
          if (requestedLatestPriceSymbols.has(symbolCode)) return false;
          return true;
        });
        if (filteredSymbols.length > 0) {
          filteredSymbols.forEach(s => requestedLatestPriceSymbols.add(s));
          fetchLatestPrices(filteredSymbols);
        }
      } else {
        fetchLatestPrices(uniqueSymbols);
      }
    }
  }, 1000); // 1秒防抖
}, { immediate: true, deep: true });

async function fetchLatestPrices(symbols: string[]) {
  if (!symbols.length) return;
  try {
    // CHANGED: 使用回测结束日期获取价格，确保获取的是回测结束时的价格（前复权）
    // 优先使用回测结束日期，确保是日期格式（YYYY-MM-DD）而不是时间格式
    // CHANGED: 在回放模式下，优先使用回放游标所在日期
    let targetDate: string | undefined = playbackMode.value && playbackCursor.value 
      ? normalizeDate(playbackCursor.value)
      : backtestStore.lastRunParams?.endDate;
    
    // 如果回测结束日期不存在，尝试从策略详情中获取
    if (!targetDate && strategyStore.currentBacktestResult) {
      const result = strategyStore.currentBacktestResult as any;
      if (result.endDate) {
        targetDate = result.endDate;
      } else if (result.dateRange) {
        // 从 dateRange 中提取结束日期（格式：YYYY-MM-DD ~ YYYY-MM-DD）
        const match = String(result.dateRange).match(/~\s*(\d{4}-\d{2}-\d{2})/);
        if (match) {
          targetDate = match[1];
        }
      }
    }
    
    // CHANGED: 如果还是没有，尝试从路由参数或页面顶部的时间选择器中获取
    if (!targetDate) {
      // 检查是否有其他来源的回测参数
      const routeParams = route.params;
      // 这里可以添加从路由参数中提取日期的逻辑
    }
    
    // 验证日期格式：必须是 YYYY-MM-DD 格式
    if (targetDate && !/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
      console.warn(`[价格获取] 日期格式无效: ${targetDate}，跳过价格获取`);
      return;
    }
    
    // CHANGED: 在流式回测过程中，如果没有结束日期，暂时跳过价格获取（会在回测完成后自动获取）
    if (!targetDate) {
      // 如果正在运行回测，不打印警告（这是正常的，因为参数可能还没设置）
      if (!backtestStore.running) {
        console.warn('[价格获取] 没有回测结束日期，无法获取价格');
      }
      return;
    }
    
    console.log(`[价格获取] 开始获取 ${symbols.length} 个标的的价格（目标日期: ${targetDate}）:`, symbols);
    const response = await getLatestPrices(symbols, targetDate);
    console.log(`[价格获取] API 响应:`, response);
    const priceMap: Record<string, number> = {};
    const nameMap: Record<string, string> = {};
    
    Object.entries(response || {}).forEach(([symbol, payload]) => {
      const price = (payload as any)?.price;
      const date = (payload as any)?.date;
      const name = (payload as any)?.name;
      const normalizedCode = normalizeSymbolCode(symbol);
      
      if (typeof price === 'number' && !Number.isNaN(price) && price > 0) {
        priceMap[normalizedCode] = price;
        console.log(`[价格获取] ${symbol}: 价格=${price}, 名称=${name}, 日期=${date}`);
      }
      
      if (name && normalizedCode) {
        nameMap[normalizedCode] = name;
      }
    });

    if (Object.keys(priceMap).length > 0 || Object.keys(nameMap).length > 0) {
      // 更新价格和名称，同时清除请求标记
      symbols.forEach(symbol => {
        const normalizedCode = normalizeSymbolCode(symbol);
        if (normalizedCode) {
          requestedLatestPriceSymbols.delete(normalizedCode);
        }
      });
      
      fetchedLatestPrices.value = {
        ...fetchedLatestPrices.value,
        ...priceMap
      };
      
      stockNames.value = {
        ...stockNames.value,
        ...nameMap
      };
      
      console.log(`[价格信息] 更新了 ${Object.keys(priceMap).length} 个价格和 ${Object.keys(nameMap).length} 个名称`);
    } else {
      // 如果获取失败，清除请求标记以便重试
      symbols.forEach(symbol => {
        const normalizedCode = normalizeSymbolCode(symbol);
        if (normalizedCode) {
          requestedLatestPriceSymbols.delete(normalizedCode);
        }
      });
      console.warn(`[价格获取] 未能获取价格（日期: ${targetDate}）`);
    }
  } catch (error) {
    console.error('获取价格失败:', error);
    // 清除请求标记以便重试
    symbols.forEach(symbol => {
      const normalizedCode = normalizeSymbolCode(symbol);
      if (normalizedCode) {
        requestedLatestPriceSymbols.delete(normalizedCode);
      }
    });
  }
}

async function handleTradeSelect(trade: Trade, openModal = false) {
  selectedTrade.value = trade;
  // 更新 K 线 Store 中的选中标的，让主图表切换
  klineStore.setSelectedSymbol(trade.symbolCode || trade.symbol);
  
  if (!openModal) return;

  selectedDeepDiveTrade.value = trade;
  isDeepDiveOpen.value = true;
  
  const symbolCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
  if (!symbolCode) return;

  // Calculate -20/+10 window (Instruction B)
  const entry = new Date(trade.entryDate || trade.date);
  const exit = trade.exitDate ? new Date(trade.exitDate) : new Date(entry);
  if (!trade.exitDate) exit.setDate(entry.getDate() + 5); // Default buffer for open trades

  const start = new Date(entry);
  start.setDate(start.getDate() - 20);
  const end = new Date(exit);
  end.setDate(end.getDate() + 10);

  const formatDate = (date: Date) => date.toISOString().split('T')[0];
  deepDiveStartDate.value = formatDate(start);
  deepDiveEndDate.value = formatDate(end);

  // Still load into primary K-line store for full context if needed
  // ... but for the modal, we use the specific deepDiveDates
  
  // Ensure we scroll the trade panel or make it visible if needed
  if (!isTradePanelExpanded.value) {
    isTradePanelExpanded.value = true;
  }
}

async function handlePositionAnalyze(pos: any) {
  // 为当前持仓构建一个“虚构”的成交记录，以便复用分析逻辑
  // 入场日期使用持仓的 entryDate，现价作为“模拟”平仓价
  const syntheticTrade: Trade = {
    id: `current-pos-${pos.symbolCode}`,
    date: pos.entryDate, // 入场日期
    symbol: pos.symbolName,
    symbolCode: pos.symbolCode,
    action: 'buy', // 标记为 buy 进入点，分析窗口会自动包含后续走势
    price: pos.cost,
    quantity: pos.quantity,
    entryPrice: pos.cost,
    entryDate: pos.entryDate
  };
  
  // 直接以“分析模式”打开
  await handleTradeSelect(syntheticTrade, true);
}





async function loadStrategyDetail() {
  let versionId = route.params.id as string || route.params.versionId as string;
  
  // 如果没有 ID，尝试获取可用列表并默认选中第一个
  if (!versionId || versionId === 'default') {
    try {
      strategyStore.setLoading(true);
      const versions = await getAvailableVersions();
      if (versions && versions.length > 0) {
        // 使用第一个有效的策略 ID
        const firstId = versions[0].id || versions[0].version || (versions[0] as any).name;
        if (firstId) {
          console.log(`[自动重定向] 无效 ID，自动跳转到策略: ${firstId}`);
          router.replace({ name: 'StrategyDetail', params: { id: firstId } });
          versionId = firstId;
          // IMPORTANT: replace 后组件可能会重载，但为了保险起见，继续执行加载逻辑
        } else {
            throw new Error('无法获取有效的策略ID');
        }
      } else {
        throw new Error('系统未找到任何可用策略，请先创建或从代码库加载策略');
      }
    } catch (e) {
      console.error('自动加载策略失败:', e);
      realtimeTrades.value = [];
      const msg = e instanceof Error ? e.message : '请提供有效的策略版本ID';
      strategyStore.setError(msg);
      strategyStore.setLoading(false);
      return;
    }
  }
  
  try {
    strategyStore.setLoading(true);
    strategyStore.setError(null);
    
    try {
      const result = await getStrategyDetail(versionId);
      if (result) {
        strategyStore.setCurrentBacktestResult(result);
        strategyStore.setCurrentVersion(versionId);
        // 同步全局选中的策略 ID
        dashboardStore.setSelectedStrategy(versionId);
      } else {
        strategyStore.setError('未找到该策略版本的回测结果');
      }
    } catch (apiError) {
      const errorMessage = apiError instanceof Error ? apiError.message : '加载策略详情失败';
      strategyStore.setError(errorMessage);
      strategyStore.setLoading(false);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '加载失败';
    strategyStore.setError(errorMessage);
  } finally {
    strategyStore.setLoading(false);
  }
}

watch(() => route.params, () => {
  loadStrategyDetail();
  realtimeTrades.value = [];
}, { immediate: true });

watch(trades, (newTrades) => {
  if (newTrades.length > 0 && !selectedTrade.value && newTrades[0]) {
    // 策略切换后的首次加载，只选中不开启弹窗
    handleTradeSelect(newTrades[0], false);
  }
}, { immediate: true });

onMounted(() => {
  // CHANGED: 从 localStorage 恢复回测数据，而不是清空
  // 这样用户在回测完成后返回页面时，数据仍然存在
  backtestStore.hydrateFromStorage();
  
  // 通过 Vite 代理连接，避免 CORS
  connect(window.location.origin);
  loadStrategyDetail();
});
</script>
