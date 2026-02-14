<template>
  <div class="kline-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="symbol-info">
          <h2 class="symbol-name">
            {{ selectedSymbolName || selectedSymbol || '--' }}
            <span class="symbol-badge">DAY</span>
          </h2>
        </div>
        
        <div class="divider"></div>
        <div class="legend">
          <div class="legend-item">
            <div class="legend-dot buy"></div>
            <span class="legend-text">买入</span>
          </div>
          <div class="legend-item">
            <div class="legend-dot sell"></div>
            <span class="legend-text">卖出</span>
          </div>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- Shadow Curve Toggle -->
        <div class="shadow-toggle">
          <span class="toggle-label">影子曲线:</span>
          <button 
            @click="backtestStore.toggleAutoExcludeAlphaLoss()"
            :class="['toggle-btn', { 'active': backtestStore.autoExcludeAlphaLoss }]"
          >
            剔除 Alpha 亏损单
          </button>
        </div>

        <button
          @click="$emit('run-backtest')"
          class="run-btn"
        >
          <i class="fas fa-play"></i>运行回测
        </button>
      </div>
    </div>

    <!--主要内容区域：图表 + 侧边/底部面板-->
    <div class="main-area">
      <!-- 图表区域 -->
      <div class="chart-area">
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
          class="kline-chart"
        />
        
        <!-- Playback Controller Overlay -->
        <div class="playback-overlay">
          <PlaybackController v-if="backtestStore.hasData" />
        </div>
      </div>
      
      <!-- 右侧持仓面板/雷达 -->
      <div class="side-panel">
        <!-- Risk Radar -->
        <div class="radar-section">
          <LiveRiskRadar />
        </div>
        
        <div class="position-section">
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
      class="trade-panel"
      :style="{ height: isTradePanelExpanded ? `${tradePanelHeight}px` : '40px' }"
    >
      <!-- Resize Handle -->
      <div 
        class="resize-handle"
        @mousedown="startResizing"
      >
        <div class="resize-indicator"></div>
      </div>

      <div class="panel-header" @click="toggleTradePanel">
        <div class="header-left">
           <i :class="['fas', isTradePanelExpanded ? 'fa-chevron-down' : 'fa-chevron-up', 'toggle-icon']"></i>
           <h3 class="panel-title">交易明细</h3>
        </div>
        
        <div v-if="strategyStore.isLoading" class="loading-indicator">
          <i class="fas fa-spinner fa-spin"></i>
          <span>加载中...</span>
        </div>
      </div>
      
      <div v-show="isTradePanelExpanded" class="panel-content">
         <!-- 错误信息 -->
        <div v-if="strategyStore.error" class="error-message">
          <i class="fas fa-exclamation-circle"></i>{{ strategyStore.error }}
        </div>
        
        <!-- 交易记录表格 -->
        <TradeTable
          v-if="trades.length > 0"
          :trades="trades"
          :highlight-date="normalizeDate(playbackCursor)"
          @trade-select="handleTradeSelect($event, true)"
        />
        
        <!-- 无交易记录提示 -->
        <div v-else-if="!strategyStore.isLoading" class="empty-state">
          <div class="empty-icon">
            <i class="fas fa-exchange-alt"></i>
          </div>
          <h4 class="empty-title">暂无交易记录</h4>
          <p class="empty-hint">
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
const tradePanelHeight = ref(256);
const isResizing = ref(false);

function startResizing(e: MouseEvent) {
  isResizing.value = true;
  document.addEventListener('mousemove', doResize);
  document.addEventListener('mouseup', stopResizing);
  e.preventDefault();
}

function doResize(e: MouseEvent) {
  if (!isResizing.value) return;
  
  const newHeight = window.innerHeight - e.clientY;
  
  if (newHeight > 100 && newHeight < window.innerHeight * 0.8) {
    tradePanelHeight.value = newHeight;
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
const stockNames = ref<Record<string, string>>({});

const { 
  holdingPeriods: holdingPeriodsRef, 
  lastUpdated: lastUpdatedRef, 
  trades: tradesRef, 
  playbackMode, 
  playbackCursor 
} = storeToRefs(backtestStore);

const trades = computed<Trade[]>(() => {
  let baseTrades: Trade[] = backtestStore.trades;
  
  if (baseTrades.length === 0 && strategyStore.currentBacktestResult?.trades) {
    baseTrades = strategyStore.currentBacktestResult.trades;
  }
  
  if (baseTrades.length === 0 && mappedHoldingPeriods.value.length > 0) {
    baseTrades = mappedHoldingPeriods.value.flatMap(hp => {
      const arr = [];
      if (hp.entryDate) arr.push({ id: `${hp.positionId}-b`, symbol: hp.symbolName, symbolCode: hp.symbolCode, date: hp.entryDate, action: 'buy', price: hp.entryPrice || 0, quantity: hp.quantity || 0 } as Trade);
      if (hp.exitDate) arr.push({ id: `${hp.positionId}-s`, symbol: hp.symbolName, symbolCode: hp.symbolCode, date: hp.exitDate, action: 'sell', price: hp.exitPrice || 0, quantity: hp.quantity || 0, profitLoss: hp.profit } as Trade);
      return arr;
    });
  }

  if (playbackMode.value && playbackCursor.value) {
    const cursor = normalizeDate(playbackCursor.value);
    baseTrades = baseTrades.filter(t => normalizeDate(t.date || t.entryDate) <= cursor);
  }

  return baseTrades.map(trade => {
    const normalizedCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
    
    let displayName = trade.symbol || normalizedCode;
    
    if (/^\d{6}$/.test(displayName)) {
      if (stockNames.value[normalizedCode]) {
        displayName = stockNames.value[normalizedCode];
      } else {
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

const currentDateEquity = computed(() => {
  const date = currentDate.value;
  if (!date || backtestStore.equitySeries.length === 0) return 0;
  const point = backtestStore.equitySeries.find(p => normalizeDate(p.date) === date);
  return point ? point.equity : 0;
});

const equityCurveVersions = computed(() => {
  let series = backtestStore.equitySeries;
  
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
    const digits = match[1];
    return digits.length < 6 ? digits.padStart(6, '0') : digits;
  }
  return trimmed;
}

function normalizeDate(dateStr?: string | null): string {
  if (!dateStr) return '';
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

const selectedSymbolName = computed(() => {
  const targetSymbol = normalizeSymbolCode(selectedSymbol.value);
  if (!targetSymbol) return '';
  
  const holding = mappedHoldingPeriods.value.find(hp => 
    normalizeSymbolCode(hp.symbolCode || hp.symbol) === targetSymbol
  );
  if (holding && holding.symbolName) {
    return holding.symbolName;
  }
  
  const trade = trades.value.find(t => 
    normalizeSymbolCode(t.symbolCode || t.symbol) === targetSymbol
  );
  if (trade && trade.symbol) {
    if (trade.symbol && !/^\d{6}$/.test(trade.symbol)) {
      return trade.symbol;
    }
  }
  
  return targetSymbol;
});

const tradeMarkersForKline = computed(() => {
  const targetSymbol = normalizeSymbolCode(selectedSymbol.value);
  if (!targetSymbol) return [];

  const openHoldingCodes = new Set(
    currentHoldingPeriods.value.map(hp => normalizeSymbolCode(hp.symbolCode || hp.symbol))
  );

  const closeMap: Record<string, number> = {};
  klineData.value.forEach(item => {
    if (item?.date && typeof item.close === 'number') {
      closeMap[item.date] = item.close;
    }
  });
  
  const symbolTrades = trades.value.filter(t => 
    normalizeSymbolCode(t.symbolCode || t.symbol) === targetSymbol
  );

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
  if (playbackMode.value) {
    return derivedHoldingsFromTrades.value;
  }
  
  if (openHoldingPeriods.value.length > 0) {
    return openHoldingPeriods.value;
  }
  return derivedHoldingsFromTrades.value;
});

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

const emit = defineEmits(['run-backtest']);

const fetchedLatestPrices = ref<Record<string, number>>({});
const requestedLatestPriceSymbols = new Set<string>();

const latestPrices = computed<Record<string, number>>(() => {
  const normalized: Record<string, number> = {};

  Object.entries(fetchedLatestPrices.value).forEach(([symbol, price]) => {
    const normalizedCode = normalizeSymbolCode(symbol);
    if (normalizedCode && typeof price === 'number' && !Number.isNaN(price) && price > 0) {
      normalized[normalizedCode] = price;
    }
  });

  return normalized;
});

let fetchTimeout: any = null;
watch([currentHoldingPeriods, trades, playbackCursor], ([holdings, allTrades, cursor]) => {
  if (fetchTimeout) clearTimeout(fetchTimeout);
  
  fetchTimeout = setTimeout(() => {
    const symbolsToFetch: string[] = [];
    
    holdings.forEach(hp => {
      const symbolCode = normalizeSymbolCode(hp.symbolCode || hp.symbol);
      if (symbolCode) symbolsToFetch.push(symbolCode);
    });
    
    allTrades.forEach(t => {
      const symbolCode = normalizeSymbolCode(t.symbolCode || t.symbol);
      if (symbolCode) symbolsToFetch.push(symbolCode);
    });
    
    const uniqueSymbols = [...new Set(symbolsToFetch)];

    if (uniqueSymbols.length > 0) {
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
  }, 1000);
}, { immediate: true, deep: true });

async function fetchLatestPrices(symbols: string[]) {
  if (!symbols.length) return;
  try {
    let targetDate: string | undefined = playbackMode.value && playbackCursor.value 
      ? normalizeDate(playbackCursor.value)
      : backtestStore.lastRunParams?.endDate;
    
    if (!targetDate && strategyStore.currentBacktestResult) {
      const result = strategyStore.currentBacktestResult as any;
      if (result.endDate) {
        targetDate = result.endDate;
      } else if (result.dateRange) {
        const match = String(result.dateRange).match(/~\s*(\d{4}-\d{2}-\d{2})/);
        if (match) {
          targetDate = match[1];
        }
      }
    }
    
    if (targetDate && !/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
      console.warn(`[价格获取] 日期格式无效: ${targetDate}，跳过价格获取`);
      return;
    }
    
    if (!targetDate) {
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
  klineStore.setSelectedSymbol(trade.symbolCode || trade.symbol);
  
  if (!openModal) return;

  selectedDeepDiveTrade.value = trade;
  isDeepDiveOpen.value = true;
  
  const symbolCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
  if (!symbolCode) return;

  const entry = new Date(trade.entryDate || trade.date);
  const exit = trade.exitDate ? new Date(trade.exitDate) : new Date(entry);
  if (!trade.exitDate) exit.setDate(entry.getDate() + 5);

  const start = new Date(entry);
  start.setDate(start.getDate() - 20);
  const end = new Date(exit);
  end.setDate(end.getDate() + 10);

  const formatDate = (date: Date) => date.toISOString().split('T')[0];
  deepDiveStartDate.value = formatDate(start);
  deepDiveEndDate.value = formatDate(end);

  if (!isTradePanelExpanded.value) {
    isTradePanelExpanded.value = true;
  }
}

async function handlePositionAnalyze(pos: any) {
  const syntheticTrade: Trade = {
    id: `current-pos-${pos.symbolCode}`,
    date: pos.entryDate,
    symbol: pos.symbolName,
    symbolCode: pos.symbolCode,
    action: 'buy',
    price: pos.cost,
    quantity: pos.quantity,
    entryPrice: pos.cost,
    entryDate: pos.entryDate
  };
  
  await handleTradeSelect(syntheticTrade, true);
}

async function loadStrategyDetail() {
  let versionId = route.params.id as string || route.params.versionId as string;
  
  if (!versionId || versionId === 'default') {
    try {
      strategyStore.setLoading(true);
      const versions = await getAvailableVersions();
      if (versions && versions.length > 0) {
        const firstId = versions[0].id || versions[0].version || (versions[0] as any).name;
        if (firstId) {
          console.log(`[自动重定向] 无效 ID，自动跳转到策略: ${firstId}`);
          router.replace({ name: 'StrategyDetail', params: { id: firstId } });
          versionId = firstId;
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
    handleTradeSelect(newTrades[0], false);
  }
}, { immediate: true });

onMounted(() => {
  backtestStore.hydrateFromStorage();
  connect(window.location.origin);
  loadStrategyDetail();
});
</script>

<style scoped>
.kline-page {
  height: calc(100vh - clamp(2.5rem, 8vh, 2.75rem));
  background: #131722;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部工具栏 */
.toolbar {
  height: clamp(3rem, 9vh, 3.5rem);
  padding: 0 clamp(0.75rem, 2vw, 1rem);
  background: #1E222D;
  border-bottom: 1px solid #2A2E39;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: clamp(0.5rem, 1vw, 1rem);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: clamp(0.75rem, 1.5vw, 1rem);
  flex: 1;
  min-width: 0;
}

.symbol-info {
  flex-shrink: 0;
}

.symbol-name {
  font-size: clamp(0.9375rem, 1.2vw, 1rem);
  font-weight: 600;
  color: #D1D4DC;
  margin: 0;
  display: flex;
  align-items: center;
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
}

.symbol-badge {
  padding: clamp(0.125rem, 0.3vh, 0.25rem) clamp(0.25rem, 0.5vw, 0.375rem);
  font-size: clamp(0.625rem, 0.7vw, 0.75rem);
  font-weight: normal;
  background: #2A2E39;
  color: #787B86;
  border-radius: 0.25rem;
}

.divider {
  width: 1px;
  height: clamp(1.25rem, 3vh, 1.5rem);
  background: #2A2E39;
  flex-shrink: 0;
}

.legend {
  display: flex;
  align-items: center;
  gap: clamp(0.5rem, 1vw, 0.75rem);
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: clamp(0.25rem, 0.5vw, 0.375rem);
}

.legend-dot {
  width: clamp(0.5rem, 1vw, 0.625rem);
  height: clamp(0.5rem, 1vw, 0.625rem);
  border-radius: 50%;
}

.legend-dot.buy {
  background: #ef4444;
}

.legend-dot.sell {
  background: #22c55e;
}

.legend-text {
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #787B86;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: clamp(0.5rem, 1vw, 0.75rem);
  flex-shrink: 0;
}

.shadow-toggle {
  display: none;
  align-items: center;
  background: #2A2E39;
  border-radius: 0.25rem;
  padding: clamp(0.25rem, 0.5vw, 0.375rem) clamp(0.375rem, 0.75vw, 0.5rem);
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
  border: 1px solid #363A45;
}

@media (min-width: 768px) {
  .shadow-toggle {
    display: flex;
  }
}

.toggle-label {
  font-size: clamp(0.625rem, 0.7vw, 0.75rem);
  color: #787B86;
  text-transform: uppercase;
  font-weight: 600;
}

.toggle-btn {
  font-size: clamp(0.625rem, 0.7vw, 0.75rem);
  padding: clamp(0.125rem, 0.3vh, 0.25rem) clamp(0.25rem, 0.5vw, 0.375rem);
  border-radius: 0.25rem;
  transition: all 0.15s ease;
  font-weight: 600;
  background: transparent;
  border: none;
  color: #D1D4DC;
  cursor: pointer;
}

.toggle-btn:hover {
  background: rgba(255, 255, 255, 0.05);
}

.toggle-btn.active {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.run-btn {
  padding: clamp(0.375rem, 1vh, 0.5rem) clamp(0.5rem, 1vw, 0.75rem);
  font-size: clamp(0.75rem, 0.9vw, 0.875rem);
  font-weight: 500;
  color: white;
  background: #2962FF;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: clamp(0.25rem, 0.5vw, 0.375rem);
  box-shadow: 0 4px 12px rgba(41, 98, 255, 0.15);
  flex-shrink: 0;
}

.run-btn:hover {
  background: #1E53E5;
}

.run-btn i {
  font-size: clamp(0.625rem, 0.7vw, 0.75rem);
}

/* 主要内容区域 */
.main-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chart-area {
  flex: 1;
  position: relative;
  min-width: 0;
}

.kline-chart {
  width: 100%;
  height: 100%;
}

.playback-overlay {
  position: absolute;
  bottom: clamp(0.75rem, 2vh, 1rem);
  left: 50%;
  transform: translateX(-50%);
  width: min(90%, 600px);
  z-index: 20;
}

/* 侧边面板 */
.side-panel {
  width: clamp(17.5rem, 25vw, 21.25rem);
  min-width: 280px;
  max-width: 400px;
  background: #1c202b;
  border-left: 1px solid #2a2e39;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 10;
}

@media (max-width: 991px) {
  .side-panel {
    width: clamp(16rem, 22vw, 18rem);
    min-width: 260px;
  }
}

@media (max-width: 767px) {
  .side-panel {
    display: none;
  }
}

.radar-section {
  height: clamp(15rem, 35vh, 17.5rem);
  padding: clamp(0.75rem, 2vw, 1rem);
  border-bottom: 1px solid #2a2e39;
  flex-shrink: 0;
}

.position-section {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* 底部交易记录面板 */
.trade-panel {
  background: #1E222D;
  border-top: 1px solid #2A2E39;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
}

.resize-handle {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 8px;
  cursor: ns-resize;
  z-index: 20;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resize-handle:hover {
  background: rgba(41, 98, 255, 0.1);
}

.resize-indicator {
  width: 3rem;
  height: 3px;
  background: #2A2E39;
  border-radius: 2px;
  transition: background 0.15s ease;
}

.resize-handle:hover .resize-indicator {
  background: #2962FF;
}

.panel-header {
  height: clamp(2rem, 6vh, 2.5rem);
  padding: 0 clamp(0.75rem, 2vw, 1rem);
  border-bottom: 1px solid #2A2E39;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  cursor: pointer;
  transition: background 0.15s ease;
}

.panel-header:hover {
  background: #2A2E39;
}

.header-left {
  display: flex;
  align-items: center;
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
}

.toggle-icon {
  color: #787B86;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
}

.panel-title {
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
  font-weight: 500;
  color: #D1D4DC;
  margin: 0;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: clamp(0.25rem, 0.5vw, 0.375rem);
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #787B86;
}

.panel-content {
  flex: 1;
  overflow: hidden;
  padding: clamp(0.75rem, 2vw, 1rem);
  background: #1E222D;
}

.error-message {
  margin-bottom: clamp(0.75rem, 2vw, 1rem);
  padding: clamp(0.5rem, 1.5vw, 0.75rem);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.25rem;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #f87171;
  display: flex;
  align-items: center;
  gap: clamp(0.375rem, 0.75vw, 0.5rem);
}

.empty-state {
  padding: clamp(1.5rem, 5vh, 2rem);
  text-align: center;
}

.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: clamp(2.5rem, 6vw, 3rem);
  height: clamp(2.5rem, 6vw, 3rem);
  margin-bottom: clamp(0.5rem, 1.5vh, 0.75rem);
  border-radius: 50%;
  background: #2A2E39;
  color: #787B86;
}

.empty-icon i {
  font-size: clamp(1rem, 2vw, 1.25rem);
}

.empty-title {
  margin: 0 0 clamp(0.25rem, 0.75vh, 0.375rem) 0;
  font-size: clamp(0.8125rem, 1vw, 0.875rem);
  font-weight: 500;
  color: #D1D4DC;
}

.empty-hint {
  margin: 0;
  font-size: clamp(0.6875rem, 0.8vw, 0.75rem);
  color: #787B86;
}

/* 响应式适配 */
@media (max-width: 1199px) {
  .side-panel {
    width: clamp(16rem, 22vw, 18rem);
  }
}

@media (max-width: 991px) {
  .toolbar {
    padding: 0 clamp(0.5rem, 1.5vw, 0.75rem);
  }
  
  .legend {
    display: none;
  }
}

@media (max-width: 767px) {
  .kline-page {
    height: calc(100vh - clamp(2.25rem, 7vh, 2.5rem));
  }
  
  .toolbar {
    height: auto;
    min-height: clamp(2.5rem, 8vh, 3rem);
    flex-wrap: wrap;
    padding: clamp(0.375rem, 1vh, 0.5rem) clamp(0.5rem, 1.5vw, 0.75rem);
  }
  
  .toolbar-left {
    width: 100%;
  }
  
  .toolbar-right {
    width: 100%;
    justify-content: flex-end;
  }
  
  .main-area {
    flex-direction: column;
  }
  
  .trade-panel {
    min-height: 150px;
  }
}

@media (max-width: 575px) {
  .symbol-badge {
    display: none;
  }
  
  .run-btn span {
    display: none;
  }
}
</style>
