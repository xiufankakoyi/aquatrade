# Performance Optimization Plan

## 1. Core Performance: Reactive System Optimization

### 1.1 Kline Store Optimization
- **File**: `src/store/klineStore.ts`
- **Issue**: Large `klineData` array is wrapped in `ref()`, causing Vue to proxy every element
- **Fix**: Replace `ref()` with `shallowRef()` for `klineData`

### 1.2 Backtest Store Optimization
- **File**: `src/store/backtestStore.ts`
- **Issue**: Multiple large arrays (`equitySeries`, `benchmarkEquitySeries`, `monthlyReturns`, `holdingPeriods`, `trades`) use `ref()`
- **Fix**: Replace `ref()` with `shallowRef()` for all large datasets

## 2. ECharts Instance Handling

### 2.1 Chart Components Optimization
- **Files**: All ECharts components (`src/components/charts/*.vue`, `HeatmapChart.vue`, etc.)
- **Issue**: ECharts instances are stored directly without `markRaw`
- **Fix**: Import `markRaw` from Vue and wrap ECharts instances when initializing: `chartInstance = markRaw(echarts.init(dom))`

## 3. Real-time Data Flow: Socket.IO Optimization

### 3.1 Streaming Backtest Buffering
- **File**: `src/composables/useStreamingBacktest.ts`
- **Issue**: Every socket event triggers immediate store updates
- **Fix**: Implement data buffering with `requestAnimationFrame` or `setInterval` (500ms interval) to batch updates

### 3.2 Socket Event Handling
- **File**: `src/composables/useSocketIO.ts`
- **Issue**: Potential over-processing of frequent events
- **Fix**: Add optional debounce/throttle options for event listeners

## 4. Trade Table Virtual Scrolling

### 4.1 TradeTable Optimization
- **File**: `src/components/tables/TradeTable.vue`
- **Issue**: Direct `v-for` on potentially thousands of trades
- **Fix**: Implement virtual scrolling using `vue-virtual-scroller` library

## 5. Additional Improvements

### 5.1 Type Safety Check
- **File**: `src/types/backtest.ts`
- **Issue**: Potential `any` types in API response handling
- **Fix**: Audit and ensure strict type definitions for all API responses

### 5.2 Web Worker Consideration
- **Investigation**: Evaluate if complex calculations should be moved to Web Workers
- **Focus**: Identify CPU-intensive operations in chart rendering or data processing

## Implementation Steps

1. **Update Store Reactive Handling** (Priority: High)
   - Modify `klineStore.ts` and `backtestStore.ts` to use `shallowRef`
   - Test with large datasets to verify performance improvement

2. **Fix ECharts Instance Handling** (Priority: High)
   - Update all chart components to use `markRaw` for ECharts instances
   - Ensure proper cleanup in `onUnmounted`

3. **Implement Data Buffering** (Priority: Medium)
   - Add buffering mechanism to `useStreamingBacktest.ts`
   - Configure 500ms update interval for UI refreshes

4. **Add Virtual Scrolling** (Priority: Medium)
   - Install `vue-virtual-scroller`
   - Update `TradeTable.vue` to use virtual scrolling

5. **Type Safety Audit** (Priority: Low)
   - Review and improve type definitions
   - Remove unnecessary `any` types

## Expected Outcomes

- Reduced memory usage by avoiding deep reactivity on large datasets
- Improved UI responsiveness during real-time data updates
- Better handling of frequent socket events
- Smooth scrolling for large trade tables
- Enhanced type safety throughout the codebase