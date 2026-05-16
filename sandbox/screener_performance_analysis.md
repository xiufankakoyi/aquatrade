# Stock Screener 性能分析报告

## 分析时间
2026-03-03

## 测试环境
- 平台: Windows
- Python: 3.x
- 数据规模: 5441 只股票

---

## 性能瓶颈分析

### 总耗时: 2987.36ms (~3秒)

### 各步骤耗时分布

| 步骤名称 | 耗时(ms) | 占比 | 优化优先级 |
|---------|---------|------|-----------|
| merge_factor_data | 2198.79 | 73.6% | 🔴 最高 |
| get_all_stocks_daily_df | 749.46 | 25.1% | 🟠 高 |
| add_stock_names | 30.80 | 1.0% | 🟡 中 |
| convert_to_dict | 4.62 | 0.2% | 🟢 低 |
| apply_filter_conditions | 1.93 | 0.1% | 🟢 低 |
| sort_results | 1.27 | 0.0% | 🟢 低 |
| pagination | 0.16 | 0.0% | 🟢 低 |
| get_date | 0.24 | 0.0% | 🟢 低 |
| add_stock_code | 0.09 | 0.0% | 🟢 低 |

---

## 主要瓶颈详解

### 1. merge_factor_data (2198.79ms, 73.6%)

**问题分析:**
- 从 Parquet 加载因子数据耗时较长
- 合并 36 个因子列到 5441 只股票数据
- 使用了 join 操作

**当前实现:**
```python
def merge_factor_data(stock_df: pl.DataFrame, target_date: str) -> pl.DataFrame:
    factor_df = get_factor_data_for_date(target_date)  # 从 Parquet 读取
    # ... join 操作
```

**优化建议:**
1. **预合并存储**: 将因子数据预合并到 stock_daily.parquet 中，避免运行时 join
2. **内存缓存**: 将因子数据缓存到内存，避免重复读取
3. **延迟加载**: 只在需要特定因子时才加载
4. **Arrow 零拷贝**: 确保使用 Arrow 格式避免数据复制

---

### 2. get_all_stocks_daily_df (749.46ms, 25.1%)

**问题分析:**
- 从 Parquet 文件读取 5441 行数据耗时 749ms
- 使用了 `pl.scan_parquet().filter().collect()` 模式

**当前实现:**
```python
df = pl.scan_parquet(parquet_path).filter(pl.col('trade_date') == target_date).collect()
```

**优化建议:**
1. **内存缓存**: 启动时将数据加载到内存字典
2. **分区存储**: 按日期分区存储 Parquet 文件
3. **索引优化**: 为 trade_date 列添加索引
4. **Arrow 直接读取**: 避免不必要的格式转换

---

## 具体优化方案

### 方案1: 内存缓存 (推荐)

在应用启动时将数据加载到内存，避免每次请求都读取文件：

```python
class ScreenerDataCache:
    """股票筛选器数据缓存"""
    
    def __init__(self):
        self._stock_data: Dict[str, pl.DataFrame] = {}  # 按日期缓存
        self._factor_data: Dict[str, pl.DataFrame] = {}  # 按日期缓存
        self._merged_data: Dict[str, pl.DataFrame] = {}  # 预合并数据
    
    def load_data(self, date: str):
        """预加载指定日期的数据"""
        if date not in self._merged_data:
            # 读取并合并数据
            stock_df = self._load_stock_data(date)
            factor_df = self._load_factor_data(date)
            merged = self._merge_data(stock_df, factor_df)
            self._merged_data[date] = merged
    
    def get_data(self, date: str) -> pl.DataFrame:
        """获取缓存的数据"""
        return self._merged_data.get(date)
```

**预期效果**: 从 2987ms 降至 <100ms (30倍提升)

---

### 方案2: 预合并存储

修改数据生成流程，将因子数据预合并到主数据文件：

```python
def precompute_merged_data(date: str):
    """预计算合并后的数据"""
    stock_df = load_stock_data(date)
    factor_df = load_factor_data(date)
    merged = merge_data(stock_df, factor_df)
    
    # 存储到 Parquet
    merged.write_parquet(f"data/merged/{date}.parquet")
```

**预期效果**: 消除 merge_factor_data 的 2198ms 耗时

---

### 方案3: 延迟加载因子

只在筛选条件需要时才加载相应因子：

```python
def get_data_with_lazy_factors(date: str, required_fields: List[str]):
    """按需加载因子"""
    base_df = load_stock_data(date)
    
    # 只加载需要的因子
    factor_fields = [f for f in required_fields if f not in base_df.columns]
    if factor_fields:
        factor_df = load_factor_data(date, columns=factor_fields)
        base_df = base_df.join(factor_df, on='stock_code')
    
    return base_df
```

**预期效果**: 减少不必要的因子加载

---

### 方案4: 数据库索引优化

如果使用 ArcticDB，确保：
1. 使用统一的 symbol 存储（已完成）
2. 为常用查询列创建索引
3. 使用 Arrow 格式直接读取

---

## 快速优化代码

以下是可以立即应用的优化：

### 1. 添加内存缓存到 screener_routes.py

```python
# 在文件顶部添加缓存
_screener_cache: Dict[str, pl.DataFrame] = {}

def get_cached_data(date: str) -> pl.DataFrame:
    """获取缓存的数据"""
    if date not in _screener_cache:
        # 加载并缓存数据
        df = get_all_stocks_daily_df(date)
        if df is not None:
            df = merge_factor_data(df, date)
            _screener_cache[date] = df
    return _screener_cache.get(date)
```

### 2. 优化 merge_factor_data

```python
def merge_factor_data_optimized(stock_df: pl.DataFrame, target_date: str) -> pl.DataFrame:
    """优化的因子合并 - 使用缓存"""
    cache_key = f"factor_{target_date}"
    
    if cache_key not in _screener_cache:
        factor_df = get_factor_data_for_date(target_date)
        _screener_cache[cache_key] = factor_df
    else:
        factor_df = _screener_cache[cache_key]
    
    if factor_df is None or factor_df.is_empty():
        return stock_df
    
    # 执行合并
    exclude_cols = {'stock_code', 'trade_date', 'date'}
    factor_cols = [c for c in factor_df.columns if c not in exclude_cols]
    factor_select = factor_df.select(['stock_code'] + factor_cols)
    
    return stock_df.join(factor_select, on='stock_code', how='left')
```

---

## 性能监控

建议在生产环境添加性能监控：

```python
# 在 filter_stocks 函数中添加
import time

start_time = time.perf_counter()
# ... 处理逻辑
total_ms = (time.perf_counter() - start_time) * 1000

if total_ms > 1000:  # 超过1秒记录警告
    logger.warning(f"[Screener] 慢查询: {total_ms:.2f}ms, date={date}")
```

---

## 总结

### 当前性能
- 总耗时: ~3秒
- 主要瓶颈: 因子数据合并 (73.6%) 和数据加载 (25.1%)

### 优化目标
- 目标耗时: <500ms
- 主要手段: 内存缓存 + 预合并存储

### 实施优先级
1. 🔴 立即实施: 添加内存缓存 (预计提升 10-30倍)
2. 🟠 短期实施: 预合并数据存储
3. 🟡 中期实施: 延迟加载因子
4. 🟢 长期优化: 数据库索引和分区
