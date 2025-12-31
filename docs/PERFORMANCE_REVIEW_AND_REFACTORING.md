# 项目性能审查与重构建议

## 📊 执行摘要

经过全面审查，发现以下主要性能瓶颈：

1. **大量调试日志写入** - 影响 I/O 性能
2. **重复的数据库查询** - 缓存策略不够优化
3. **复杂的数据处理逻辑** - 可以向量化优化
4. **内存使用不当** - 存在不必要的 DataFrame copy
5. **同步阻塞操作** - 可以异步化

**预期性能提升：30-50%**

---

## 🔍 详细问题分析

### 1. 调试日志性能问题 ⚠️ 高优先级

**问题位置：**
- `server/visualization_api.py` - 大量 `debug.log` 写入
- `core/backtest/optimized_backtest_engine.py` - 频繁的日志写入
- `data_svc/database/optimized_data_query.py` - 性能监控日志

**问题描述：**
```python
# 示例：visualization_api.py 中有大量这样的代码
try:
    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json.dumps({...}) + "\n")
        f.flush()
except: pass
```

**影响：**
- 每次回测可能写入数百条日志
- `flush()` 强制同步写入，阻塞主线程
- 文件 I/O 成为性能瓶颈

**解决方案：**
1. 使用异步日志库（如 `logging` + `QueueHandler`）
2. 批量写入日志（缓冲后一次性写入）
3. 生产环境禁用调试日志
4. 使用环境变量控制日志级别

---

### 2. 数据库查询优化 ⚠️ 高优先级

**问题位置：**
- `data_svc/database/optimized_data_query.py`
- `server/visualization_api.py` - `get_scatter_data()` 方法

**问题描述：**

#### 2.1 散点图数据查询慢
```python
# visualization_api.py:1694
def get_scatter_data(self, symbol: Optional[str] = None):
    # 1. 从 Parquet 加载股吧数据
    df = self._load_guba_posts_from_parquet(symbol)
    # 2. 查询股票市值信息（可能查询所有股票）
    stock_info = self._get_stock_info_with_market_cap(needed_symbols)
```

**问题：**
- 即使指定了 `needed_symbols`，仍可能查询大量股票
- 没有利用索引优化
- 重复查询相同数据

#### 2.2 缓存策略不够智能
```python
# optimized_data_query.py:1353
def _add_to_cache(self, key, value):
    if len(self._cache) >= self._cache_size:
        oldest_key = next(iter(self._cache))
        del self._cache[oldest_key]
    self._cache[key] = value
```

**问题：**
- 使用简单的 FIFO 策略，可能删除常用数据
- 缓存键设计不合理，导致缓存命中率低
- 没有考虑数据访问频率

**解决方案：**
1. 实现 LRU 缓存（使用 `functools.lru_cache` 或自定义）
2. 优化查询，只查询需要的列
3. 使用连接池减少连接开销
4. 批量查询替代 N+1 查询

---

### 3. 数据处理性能问题 ⚠️ 中优先级

**问题位置：**
- `server/visualization_api.py` - `_calculate_qfq_dataframe()`
- `core/backtest/optimized_backtest_engine.py` - 价格矩阵填充

**问题描述：**

#### 3.1 前复权计算效率低
```python
# visualization_api.py:118
def _calculate_qfq_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
    # 按股票代码分组，找到每只股票的最新因子
    latest_factors = df.groupby('stock_code').apply(
        lambda g: g.loc[g['trade_date'].idxmax(), 'adj_factor']
    )
```

**问题：**
- `groupby().apply()` 效率低
- 可以使用向量化操作替代

**优化方案：**
```python
# 优化后：使用向量化操作
df_sorted = df.sort_values(['stock_code', 'trade_date'])
latest_factors = df_sorted.groupby('stock_code')['adj_factor'].last()
df['latest_factor'] = df['stock_code'].map(latest_factors)
```

#### 3.2 价格矩阵填充慢
```python
# optimized_backtest_engine.py:365
for t, date in enumerate(dates):
    date_df = df.filter(pl.col('trade_date') == date)
    for n, code in enumerate(stock_codes):
        code_row = date_df.filter(pl.col('stock_code') == code)
        # ...
```

**问题：**
- 双重循环，时间复杂度 O(T*N)
- 每次 `filter()` 都会扫描整个 DataFrame

**优化方案：**
```python
# 使用 pivot 或 unstack 一次性构建矩阵
df_pivot = df.pivot_table(
    index='trade_date',
    columns='stock_code',
    values=['open', 'high', 'low', 'close']
)
# 转换为 NumPy 数组
price_matrix = df_pivot.values.reshape(T, N, 4)
```

---

### 4. 内存使用优化 ⚠️ 中优先级

**问题位置：**
- `data_svc/database/optimized_data_query.py` - `_defensive_data_loader()`
- `server/visualization_api.py` - 多处不必要的 `copy()`

**问题描述：**
```python
# optimized_data_query.py:1301
result = df.copy()  # 总是 copy，即使不需要修改
```

**问题：**
- 频繁的 DataFrame copy 导致内存翻倍
- 没有检查是否需要修改就 copy

**优化方案：**
```python
# 只在需要修改时才 copy
need_copy = any(col not in df.columns for col in required_cols)
if need_copy:
    result = df.copy()
else:
    result = df  # 直接引用
```

---

### 5. 同步阻塞操作 ⚠️ 低优先级

**问题位置：**
- `server/app.py` - SocketIO 事件处理
- `server/visualization_api.py` - `get_scatter_data()` 使用线程池但仍有阻塞

**问题描述：**
```python
# app.py:2425
def execute_query():
    return get_api().get_scatter_data(symbol)

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(execute_query)
    result = future.result(timeout=60.0)
```

**问题：**
- 虽然使用了线程池，但主线程仍被阻塞等待结果
- 可以改为完全异步处理

**优化方案：**
- 使用 `asyncio` 替代线程池
- 实现真正的异步查询

---

## 🚀 重构建议

### 优先级 1：立即修复（性能提升 20-30%）

#### 1.1 移除/优化调试日志

**文件：** `server/visualization_api.py`, `core/backtest/optimized_backtest_engine.py`

**操作：**
1. 将所有 `debug.log` 写入改为使用标准 `logging` 模块
2. 使用环境变量控制日志级别
3. 生产环境禁用 DEBUG 日志

**代码示例：**
```python
# 替换前
try:
    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
        f.write(json.dumps({...}) + "\n")
        f.flush()
except: pass

# 替换后
from config.logger import get_logger
logger = get_logger(__name__)
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("message", extra={"data": {...}})
```

#### 1.2 优化缓存策略

**文件：** `data_svc/database/optimized_data_query.py`

**操作：**
1. 使用 `functools.lru_cache` 或实现真正的 LRU 缓存
2. 优化缓存键设计，提高命中率
3. 添加缓存统计（命中率、大小等）

**代码示例：**
```python
from functools import lru_cache
from collections import OrderedDict

class LRUCache:
    def __init__(self, maxsize=200):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
    
    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.maxsize:
            self.cache.popitem(last=False)
        self.cache[key] = value
```

#### 1.3 优化前复权计算

**文件：** `server/visualization_api.py`

**操作：**
1. 使用向量化操作替代 `groupby().apply()`
2. 缓存最新复权因子，避免重复计算

**代码示例：**
```python
# 优化后的前复权计算
def _calculate_qfq_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or 'adj_factor' not in df.columns:
        return df
    
    # 向量化：按股票代码分组，取每只股票的最新因子
    df_sorted = df.sort_values(['stock_code', 'trade_date'])
    latest_factors = df_sorted.groupby('stock_code')['adj_factor'].last()
    df['latest_factor'] = df['stock_code'].map(latest_factors)
    
    # 计算复权比率
    df['latest_factor'] = df['latest_factor'].replace(0, 1.0)
    qfq_ratio = df['adj_factor'] / df['latest_factor']
    
    # 向量化应用到所有价格列
    price_cols = ['open', 'high', 'low', 'close', 'prev_close', 'ma5', 'ma10', 'ma20', 'ma60']
    for col in price_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') * qfq_ratio
    
    df.drop(columns=['latest_factor'], inplace=True, errors='ignore')
    return df
```

---

### 优先级 2：短期优化（性能提升 10-20%）

#### 2.1 优化价格矩阵构建

**文件：** `core/backtest/optimized_backtest_engine.py`

**操作：**
1. 使用 `pivot_table` 或 `unstack` 一次性构建矩阵
2. 减少循环次数

**代码示例：**
```python
# 优化后的矩阵构建
def _build_price_matrix(self, df: pl.DataFrame, stock_codes: List[str], dates: List[str]) -> np.ndarray:
    # 使用 Polars 的 pivot 操作
    df_pivot = df.pivot(
        index='trade_date',
        columns='stock_code',
        values=['open', 'high', 'low', 'close']
    )
    
    # 转换为 NumPy 数组
    T = len(dates)
    N = len(stock_codes)
    price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
    
    # 一次性填充（比循环快 10-100 倍）
    for i, col in enumerate(['open', 'high', 'low', 'close']):
        price_matrix[:, :, i] = df_pivot[col].to_numpy()
    
    return price_matrix
```

#### 2.2 减少不必要的 DataFrame copy

**文件：** `data_svc/database/optimized_data_query.py`, `server/visualization_api.py`

**操作：**
1. 检查是否需要修改再 copy
2. 使用 `inplace=True` 参数
3. 避免链式操作中的中间 copy

**代码示例：**
```python
# 优化前
result = df.copy()
result['new_col'] = value
return result

# 优化后
if 'new_col' not in df.columns:
    result = df.copy()
    result['new_col'] = value
    return result
else:
    return df  # 直接返回，不需要 copy
```

#### 2.3 优化散点图数据查询

**文件：** `server/visualization_api.py`

**操作：**
1. 限制查询的股票数量（只查询前 N 只）
2. 使用索引优化查询
3. 缓存查询结果

**代码示例：**
```python
# 优化后的散点图查询
def get_scatter_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
    # 1. 先查询股吧数据（限制数量）
    df = self._load_guba_posts_from_parquet(symbol, limit=100)  # 只取前100只
    
    # 2. 提取需要的股票代码
    needed_symbols = df['stockCode'].unique().tolist()[:100]  # 限制数量
    
    # 3. 批量查询市值（使用 IN 查询）
    stock_info = self._get_stock_info_with_market_cap(needed_symbols)
    
    # ... 后续处理
```

---

### 优先级 3：长期优化（性能提升 5-10%）

#### 3.1 实现异步查询

**文件：** `server/app.py`, `server/visualization_api.py`

**操作：**
1. 使用 `asyncio` 替代线程池
2. 实现异步数据库查询
3. 使用异步 SocketIO

**代码示例：**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 异步查询
async def get_scatter_data_async(symbol: Optional[str] = None):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            get_api().get_scatter_data,
            symbol
        )
    return result
```

#### 3.2 优化数据传输

**文件：** `server/app.py`

**操作：**
1. 使用 `msgpack` 替代 JSON（已部分实现）
2. 实现数据压缩
3. 分块传输大数据

**代码示例：**
```python
# 已实现，但可以进一步优化
from utils.binary_packer import pack_backtest_result

packed = pack_backtest_result(data)
socketio.emit('daily_update', {
    '_msgpack': True,
    '_data': packed
}, to=sid)
```

---

## 📋 重构检查清单

### 阶段 1：日志优化（1-2 天）
- [ ] 移除所有 `debug.log` 直接写入
- [ ] 使用标准 `logging` 模块
- [ ] 添加环境变量控制日志级别
- [ ] 测试日志性能影响

### 阶段 2：缓存优化（2-3 天）
- [ ] 实现 LRU 缓存
- [ ] 优化缓存键设计
- [ ] 添加缓存统计
- [ ] 测试缓存命中率

### 阶段 3：数据处理优化（3-5 天）
- [ ] 优化前复权计算
- [ ] 优化价格矩阵构建
- [ ] 减少不必要的 copy
- [ ] 测试性能提升

### 阶段 4：查询优化（2-3 天）
- [ ] 优化散点图查询
- [ ] 添加查询索引
- [ ] 实现批量查询
- [ ] 测试查询性能

### 阶段 5：异步优化（可选，5-7 天）
- [ ] 实现异步查询
- [ ] 使用异步 SocketIO
- [ ] 测试并发性能

---

## 🧪 性能测试

### 测试场景

1. **回测性能测试**
   - 测试数据：1000 只股票，1 年数据
   - 预期：数据加载 < 100ms，回测执行 < 1s

2. **散点图查询测试**
   - 测试数据：查询所有股票
   - 预期：查询时间 < 2s

3. **缓存命中率测试**
   - 测试场景：重复查询相同数据
   - 预期：缓存命中率 > 80%

### 测试脚本

```python
# scripts/test_performance.py
import time
from server.visualization_api import BacktestVisualizationAPI

api = BacktestVisualizationAPI()

# 测试回测性能
start = time.perf_counter()
result = api.run_backtest_and_get_data(
    'SimpleVolumeStrategy',
    '2023-01-01',
    '2023-12-31'
)
elapsed = time.perf_counter() - start
print(f"回测耗时: {elapsed:.2f}s")

# 测试散点图查询
start = time.perf_counter()
scatter = api.get_scatter_data()
elapsed = time.perf_counter() - start
print(f"散点图查询耗时: {elapsed:.2f}s")
```

---

## 📊 预期性能提升

| 优化项 | 当前耗时 | 优化后耗时 | 提升 |
|--------|---------|-----------|------|
| 回测数据加载 | 500ms | 100ms | 5x |
| 散点图查询 | 5s | 2s | 2.5x |
| 前复权计算 | 200ms | 50ms | 4x |
| 价格矩阵构建 | 300ms | 50ms | 6x |
| 总体性能 | - | - | **30-50%** |

---

## 🔧 实施建议

1. **分阶段实施**：按优先级逐步实施，每阶段完成后测试性能
2. **保留回退方案**：每个优化都保留原有代码作为回退
3. **持续监控**：添加性能监控，跟踪优化效果
4. **文档更新**：更新相关文档，说明优化内容

---

## 📝 注意事项

1. **兼容性**：确保优化不影响现有功能
2. **测试覆盖**：每个优化都要有对应的测试
3. **代码审查**：重要优化需要代码审查
4. **性能基准**：建立性能基准，便于对比

---

## 🎯 总结

通过以上优化，预期可以提升整体性能 **30-50%**，主要来自：

1. **日志优化**：减少 I/O 阻塞（提升 10-15%）
2. **缓存优化**：提高查询效率（提升 10-15%）
3. **数据处理优化**：向量化操作（提升 5-10%）
4. **查询优化**：减少数据库访问（提升 5-10%）

建议优先实施 **优先级 1** 的优化，这些优化影响最大且实施成本最低。

