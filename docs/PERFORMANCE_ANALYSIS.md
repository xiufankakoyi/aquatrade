# 回测性能分析

## 问题描述

买入信号逻辑只需要 **2-3ms**，但整体回测一天需要 **~500ms**。性能差距巨大，需要定位瓶颈。

## 性能分析工具

已在 `core/backtest/flexible_backtest_engine.py` 中添加详细的性能监控，会输出每个步骤的耗时：

```
[PERF][Day 1] 2024-01-01: 总耗时=450.2ms | 数据加载=380.5ms | 信号生成=25.3ms | 交易执行=2.1ms | 价值计算=1.8ms | 数据传输=40.5ms
```

## 可能的性能瓶颈

### 1. 数据加载 (`_get_stock_pool_at_time`) - **最可能的瓶颈**

**位置**: `core/backtest/flexible_backtest_engine.py:133`

**问题**:
- 每天都要调用 `data_query.get_stock_pool(date)` 查询数据库
- 如果使用 DuckDB/LanceDB，每次查询可能有 I/O 开销
- 如果数据未预加载，每次查询都需要从磁盘读取

**优化建议**:
1. **使用预加载**: 在回测开始前一次性加载所有需要的数据
   ```python
   data_query.preload_backtest_data(start_date, end_date)
   ```
2. **使用缓存**: 确保 `get_stock_pool` 使用缓存机制
3. **批量查询**: 使用批量查询替代逐日查询

### 2. 信号生成 (`strategy.generate_signals`) - **次要瓶颈**

**位置**: `core/backtest/flexible_backtest_engine.py:146`

**问题**:
- 虽然买入逻辑只需要 2-3ms，但 `generate_signals` 可能包含：
  - 获取昨日股票池（可能需要数据库查询）
  - 预筛选股票（可能有大量计算）
  - 卖出信号生成（未profile，可能耗时）
  - 其他策略逻辑

**优化建议**:
1. **添加更细粒度的性能监控**:
   - 在策略的 `generate_signals` 方法中添加性能分析
   - 分别监控买入和卖出信号生成时间
2. **优化数据查询**:
   - 如果策略需要获取历史数据，使用批量查询
   - 使用缓存避免重复查询

### 3. 数据传输 (`yield`) - **可能的瓶颈**

**位置**: `core/backtest/flexible_backtest_engine.py:174`

**问题**:
- 流式回测需要实时发送数据给前端
- 数据序列化（JSON/MsgPack）可能有开销
- Socket.IO 传输可能有延迟

**优化建议**:
1. **批量发送**: 不是每天都发送，而是累积几天后批量发送
2. **压缩数据**: 使用 MsgPack 或 gzip 压缩
3. **异步发送**: 使用后台线程发送数据，不阻塞回测

### 4. 其他操作

- **交易执行** (`_execute_trades`): 通常很快（<5ms），除非持仓很多
- **价值计算** (`_calculate_portfolio_value`): 通常很快（<5ms），除非持仓很多
- **日志记录**: 如果日志很多，可能有 I/O 开销

## 诊断步骤

1. **运行回测并查看性能输出**:
   ```
   [PERF][Day 1] 2024-01-01: 总耗时=450.2ms | 数据加载=380.5ms | ...
   ```

2. **识别最大瓶颈**:
   - 如果 `数据加载` > 300ms → 优化数据加载
   - 如果 `信号生成` > 100ms → 优化信号生成
   - 如果 `数据传输` > 50ms → 优化数据传输

3. **使用预加载**:
   ```python
   # 在回测开始前
   data_query.preload_backtest_data(start_date, end_date)
   ```

4. **检查是否使用 OptimizedBacktestEngine**:
   - `OptimizedBacktestEngine` 已经实现了数据预加载
   - 如果使用 `FlexibleBacktestEngine`，考虑切换到优化版本

## 预期优化效果

- **使用预加载**: 数据加载时间从 ~380ms 降低到 ~5ms（减少 98%）
- **优化信号生成**: 如果瓶颈在数据查询，优化后可减少 50-80%
- **优化数据传输**: 批量发送可减少 30-50% 的传输时间

**总体预期**: 从 ~500ms/天 降低到 ~50-100ms/天（5-10倍提升）

## 下一步

1. 运行回测，查看性能分析输出
2. 根据输出识别最大瓶颈
3. 应用相应的优化措施
4. 重新测试，验证优化效果

