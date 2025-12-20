import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiService } from '../services/api';
import { useSocketIO } from '../composables/useSocketIO';
import type { KlineData } from '../types/api';

export interface TradeMarker {
  date: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  symbol: string;
}

export const useKlineStore = defineStore('kline', () => {
  const klineData = ref<KlineData[]>([]);
  const selectedSymbol = ref<string>('');
  const tradeMarkers = ref<TradeMarker[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const dateRange = ref<{ start: string; end: string } | null>(null);

  const { onEvent } = useSocketIO();

  async function loadKlineData(
    symbolCode: string,
    startDate: string,
    endDate: string
  ) {
    try {
      isLoading.value = true;
      error.value = null;
      selectedSymbol.value = symbolCode;
      dateRange.value = { start: startDate, end: endDate };

      const data = await apiService.getKlineData(symbolCode, startDate, endDate);
      klineData.value = data;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载K线数据失败';
      klineData.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  function addTradeMarker(marker: TradeMarker) {
    const existingIndex = tradeMarkers.value.findIndex(
      m => m.date === marker.date && m.action === marker.action
    );
    if (existingIndex >= 0) {
      tradeMarkers.value[existingIndex] = marker;
    } else {
      tradeMarkers.value.push(marker);
    }
  }

  function clearTradeMarkers() {
    tradeMarkers.value = [];
  }

  function clearKlineData() {
    klineData.value = [];
    selectedSymbol.value = '';
    dateRange.value = null;
  }

  const markersForDate = computed(() => {
    return (date: string) => {
      return tradeMarkers.value.filter(m => m.date === date);
    };
  });

  return {
    klineData,
    selectedSymbol,
    tradeMarkers,
    isLoading,
    error,
    dateRange,
    loadKlineData,
    addTradeMarker,
    clearTradeMarkers,
    clearKlineData,
    markersForDate,
  };
});

