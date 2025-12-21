<template>
  <div class="p-6 space-y-6">
    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <div class="mb-4">
        <h2 class="text-xl font-semibold text-white mb-2">K线回放 & 买卖点</h2>
        <p class="text-sm text-slate-400">
          标的: {{ selectedSymbolName || selectedSymbol || '--' }} | 周期: day
        </p>
      </div>
      <div class="flex items-center space-x-4 mb-4">
        <div class="flex items-center space-x-2">
          <div class="w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
            <span class="text-xs font-bold text-white">B</span>
          </div>
          <span class="text-sm text-slate-300">买入</span>
        </div>
        <div class="flex items-center space-x-2">
          <div class="w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
            <span class="text-xs font-bold text-white">S</span>
          </div>
          <span class="text-sm text-slate-300">卖出</span>
        </div>
      </div>
      <div class="h-96">
        <EquityCurve
          :kline-data="klineData"
          :highlight-ranges="highlightRanges"
          :trade-markers="tradeMarkersForKline"
          :versions="[]"
          :benchmark="[]"
          mode="kline"
        />
      </div>
    </div>

    <PositionCard
      :holding-periods="currentHoldingPeriods"
      :current-date="currentDate"
      :latest-prices="latestPrices"
    />

    <div class="bg-[#151925] rounded-lg p-6 border border-slate-800">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-white">交易明细</h3>
        <div v-if="strategyStore.isLoading" class="flex items-center space-x-2 text-sm text-slate-400">
          <i class="fas fa-spinner fa-spin"></i>
          <span>加载中...</span>
        </div>
      </div>
      <div v-if="strategyStore.error" class="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-sm text-red-400">
        {{ strategyStore.error }}
      </div>
      <TradeTable
        v-if="trades.length > 0"
        :trades="trades"
        @trade-select="handleTradeSelect"
      />
      <div v-else-if="!strategyStore.isLoading" class="flex items-center justify-center h-48 text-slate-500">
        <div class="text-center">
          <i class="fas fa-exchange-alt text-4xl mb-2"></i>
          <p>暂无交易记录</p>
          <p class="text-sm mt-1">请运行回测以查看交易数据</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { useStrategyStore } from '../store/strategyStore';
import { useKlineStore } from '../store/klineStore';
import { useBacktestStore } from '../store/backtestStore';
import { useSocketIO } from '../composables/useSocketIO';
import { getStrategyDetail, getLatestPrices } from '../api/backtestApi';
import EquityCurve from '../components/EquityCurve.vue';
import TradeTable from '../components/tables/TradeTable.vue';
import PositionCard from '../components/PositionCard.vue';
import type { Trade, HoldingPeriod as HoldingPeriodType } from '../types/backtest';

const route = useRoute();
const strategyStore = useStrategyStore();
const klineStore = useKlineStore();
const backtestStore = useBacktestStore();
const { connect } = useSocketIO();
const { holdingPeriods: holdingPeriodsRef, lastUpdated: lastUpdatedRef, trades: tradesRef } = storeToRefs(backtestStore);

function normalizeSymbolCode(value?: string | null): string {
  if (!value) return '';
  const trimmed = value.trim().toUpperCase();
  const match = trimmed.match(/(\d{6})/);
  return match ? match[1] : trimmed;
}

const highlightRanges = ref<Array<{ start: string; end: string }>>([]);
const selectedTrade = ref<Trade | null>(null);
const realtimeTrades = ref<Trade[]>([]);

const selectedSymbol = computed(() => klineStore.selectedSymbol);
const klineData = computed(() => klineStore.klineData);

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
  if (openHoldingPeriods.value.length > 0) {
    return openHoldingPeriods.value;
  }
  return derivedHoldingsFromTrades.value;
});

const trades = computed<Trade[]>(() => {
  let baseTrades: Trade[] = [];
  if (tradesRef.value.length > 0) {
    baseTrades = tradesRef.value;
  }
  if (baseTrades.length === 0 && strategyStore.currentBacktestResult?.trades && strategyStore.currentBacktestResult.trades.length > 0) {
    baseTrades = strategyStore.currentBacktestResult.trades;
  }
  if (baseTrades.length === 0 && mappedHoldingPeriods.value.length > 0) {
    const tradesFromHoldings: Trade[] = [];
    mappedHoldingPeriods.value.forEach(hp => {
      if (hp.entryDate) {
        tradesFromHoldings.push({
          id: `${hp.positionId}-entry`,
          symbol: hp.symbolName || hp.symbolCode || '',
          symbolCode: hp.symbolCode || '',
          date: hp.entryDate,
          action: 'buy',
          price: hp.entryPrice || 0,
          quantity: hp.quantity || 0,
          value: (hp.entryPrice || 0) * (hp.quantity || 0),
          entryDate: hp.entryDate,
        });
      }
      if (hp.exitDate) {
        tradesFromHoldings.push({
          id: `${hp.positionId}-exit`,
          symbol: hp.symbolName || hp.symbolCode || '',
          symbolCode: hp.symbolCode || '',
          date: hp.exitDate,
          action: 'sell',
          price: hp.exitPrice || hp.entryPrice || 0,
          quantity: hp.quantity || 0,
          value: (hp.exitPrice || hp.entryPrice || 0) * (hp.quantity || 0),
          profitLoss: hp.profit || 0,
          entryDate: hp.entryDate,
          exitDate: hp.exitDate,
        });
      }
    });
    baseTrades = tradesFromHoldings;
  }
  return baseTrades.map(trade => {
    const normalizedCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
    return {
      ...trade,
      symbolCode: normalizedCode,
      symbol: trade.symbol || normalizedCode
    };
  });
});

const currentDate = computed(() => {
  // CHANGED: 优先使用回测结束日期，确保返回的是日期格式（YYYY-MM-DD）
  const endDate = backtestStore.lastRunParams?.endDate;
  if (endDate && /^\d{4}-\d{2}-\d{2}$/.test(endDate)) {
    return endDate;
  }
  // 如果回测结束日期不存在或格式不正确，返回今天的日期
  return new Date().toISOString().split('T')[0];
});

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

// CHANGED: 监听持仓变化，自动获取所有持仓股票的回测结束日期价格
watch(currentHoldingPeriods, (holdings) => {
  const symbolsToFetch: string[] = [];
  holdings.forEach(hp => {
    const symbolCode = normalizeSymbolCode(hp.symbolCode || hp.symbol);
    if (!symbolCode) return;
    // 如果已经有价格且价格有效，跳过
    if (fetchedLatestPrices.value[symbolCode] !== undefined && 
        typeof fetchedLatestPrices.value[symbolCode] === 'number' && 
        fetchedLatestPrices.value[symbolCode] > 0) {
      return;
    }
    // 如果正在请求中，跳过
    if (requestedLatestPriceSymbols.has(symbolCode)) return;
    symbolsToFetch.push(symbolCode);
    requestedLatestPriceSymbols.add(symbolCode);
  });

  if (symbolsToFetch.length > 0) {
    fetchLatestPrices(symbolsToFetch);
  }
}, { immediate: true, deep: true });

async function fetchLatestPrices(symbols: string[]) {
  if (!symbols.length) return;
  try {
    // CHANGED: 使用回测结束日期获取价格，确保获取的是回测结束时的价格（前复权）
    // 优先使用回测结束日期，确保是日期格式（YYYY-MM-DD）而不是时间格式
    let targetDate: string | undefined = backtestStore.lastRunParams?.endDate;
    
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
    Object.entries(response || {}).forEach(([symbol, payload]) => {
      const price = (payload as any)?.price;
      const date = (payload as any)?.date;
      if (typeof price === 'number' && !Number.isNaN(price) && price > 0) {
        priceMap[symbol] = price;
        console.log(`[价格获取] ${symbol}: 价格=${price}, 日期=${date}`);
      } else {
        console.warn(`[价格获取] ${symbol}: 价格无效`, payload);
      }
    });
    if (Object.keys(priceMap).length > 0) {
      // 更新价格，同时清除请求标记
      symbols.forEach(symbol => {
        const normalizedCode = normalizeSymbolCode(symbol);
        if (normalizedCode && priceMap[normalizedCode] !== undefined) {
          requestedLatestPriceSymbols.delete(normalizedCode);
        }
      });
      fetchedLatestPrices.value = {
        ...fetchedLatestPrices.value,
        ...priceMap
      };
      console.log(`[价格获取] 已获取 ${Object.keys(priceMap).length} 个标的的价格（日期: ${targetDate}）:`, priceMap);
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

async function handleTradeSelect(trade: Trade) {
  selectedTrade.value = trade;
  
  if (trade.symbolCode || trade.symbol) {
    try {
      const symbolCode = normalizeSymbolCode(trade.symbolCode || trade.symbol);
      if (!symbolCode) {
        console.warn('无法识别标的代码', trade);
        return;
      }
      
      // CHANGED: K线图默认展示持有周期+前后二十天
      let startDate: string = trade.entryDate || '2024-01-01';
      let endDate: string = trade.exitDate || '2025-01-01';
      
      if (trade.entryDate) {
        const entryDate = new Date(trade.entryDate);
        const formatDate = (date: Date) => date.toISOString().split('T')[0];
      
        if (trade.exitDate) {
          // 标准逻辑：持有周期前后二十天，但不限制结束日期
          const start = new Date(entryDate);
          start.setDate(start.getDate() - 20);
          startDate = formatDate(start);

          const exitDate = new Date(trade.exitDate);
          exitDate.setDate(exitDate.getDate() + 20);
          // CHANGED: 不再限制结束日期，允许显示更长时间范围
          endDate = formatDate(exitDate);

          highlightRanges.value = [{
            start: trade.entryDate,
            end: trade.exitDate
          }];
        } else {
          // CHANGED: 没有卖出日期（买入记录）：显示买入日期前10天到买入日期后更长时间
          const start = new Date(entryDate);
          start.setDate(start.getDate() - 10);
          startDate = formatDate(start);

          // CHANGED: 右边界：买入日期+更长时间（例如90天），不再限制在回测结束日期
          const end = new Date(entryDate);
          end.setDate(end.getDate() + 90); // 扩展到90天后
          endDate = formatDate(end);

          highlightRanges.value = [{
            start: trade.entryDate,
            end: formatDate(end)
          }];
        }
      } else {
        // 如果没有 entryDate，使用默认的宽时间范围
        startDate = '2024-01-01';
        endDate = new Date().toISOString().split('T')[0]; // 扩展到今天
      }
      
      await klineStore.loadKlineData(symbolCode, startDate, endDate);
    } catch (error) {
    }
  }
}

async function loadStrategyDetail() {
  const versionId = route.params.id as string || route.params.versionId as string;
  
  if (!versionId || versionId === 'default') {
    realtimeTrades.value = [];
    strategyStore.setError(null);
    strategyStore.setLoading(false);
    return;
  }
  
  try {
    strategyStore.setLoading(true);
    strategyStore.setError(null);
    
    try {
      const result = await getStrategyDetail(versionId);
      if (result) {
        strategyStore.setCurrentBacktestResult(result);
        strategyStore.setCurrentVersion(versionId);
      }
    } catch (apiError) {
      strategyStore.setLoading(false);
      strategyStore.setError(null);
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
    handleTradeSelect(newTrades[0]);
  }
}, { immediate: true });

onMounted(() => {
  // CHANGED: 从 localStorage 恢复回测数据，而不是清空
  // 这样用户在回测完成后返回页面时，数据仍然存在
  backtestStore.hydrateFromStorage();
  
  connect('http://localhost:5000');
  loadStrategyDetail();
});
</script>
