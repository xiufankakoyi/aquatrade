# 数据库开发常见问题与解决方案

## 概述

本文档记录了在 AquaTrade 项目数据库开发过程中遇到的常见问题及解决方案，供后续开发参考。

---

## 1. 数据存储架构

### 1.1 库（Library）设计

```
ArcticDB
├── stock_daily      # 股票日线数据（单 symbol，用于筛选器和回测）
├── market_data      # 股票日线数据（按股票分 symbol，完整历史数据）
├── stock_basic      # 股票基本信息
├── benchmark_daily  # 指数/基准数据
├── fund_nav         # 基金净值数据
├── limit_status     # 涨跌停数据
└── factor           # 其他因子数据
```

### 1.2 关键区别

| 库名 | 存储方式 | 用途 | 数据完整性 |
|------|----------|------|-----------|
| `stock_daily` | 单 symbol (`stock_daily`) | 股票筛选器、回测 | 可能不完整 |
| `market_data` | 多 symbol (每只股票一个) | 原始数据存储 | 完整历史数据 |

**重要**：`stock_daily` 和 `market_data` 都存储日线数据，但用途不同。如果 `stock_daily` 数据不完整，需要从 `market_data` 迁移。

---

## 2. 常见问题

### 问题 1：日期类型不匹配

**错误信息**：
```
cannot compare 'date/datetime/time' to a string value 
(create native python { 'date', 'datetime', 'time' } or compare to a temporal column)
```

**原因**：
- Polars DataFrame 中的 `trade_date` 列是 `datetime` 类型
- 直接用字符串进行过滤会导致类型不匹配

**解决方案**：
```python
import pandas as pd

# ✅ 正确做法：将字符串日期转换为 datetime
start_dt = pd.to_datetime(start_date)  # '2020-01-01' -> datetime
end_dt = pd.to_datetime(end_date)

df = df.filter(pl.col('trade_date') >= start_dt)
df = df.filter(pl.col('trade_date') <= end_dt)

# ❌ 错误做法：直接用字符串比较
df = df.filter(pl.col('trade_date') >= start_date)  # 会报错！
```

---

### 问题 2：stock_daily 库数据不完整

**现象**：
- 查询 `stock_daily` 库只有 10 天的数据
- 但 `market_data` 库有完整的历史数据

**原因**：
- `unified_updater.py` 默认是增量更新模式
- 只更新最近的数据到 `stock_daily` 库
- 不会自动从 `market_data` 迁移历史数据

**解决方案**：

**方案 A：从 market_data 迁移数据（推荐）**
```bash
python sandbox/migrate_market_data_to_stock_daily.py
```

**方案 B：全量更新（从 Tushare 重新拉取）**
```bash
python sandbox/fetch_historical_data.py --start-date 20200101 --end-date 20260228
```

---

### 问题 3：缺少 stock_code 列

**现象**：
- 数据只有 `ts_code` 列（如 `000001.SZ`）
- 但计算因子需要 `stock_code` 列（如 `000001`）

**解决方案**：
```python
# 从 ts_code 提取 stock_code
if 'stock_code' not in df.columns and 'ts_code' in df.columns:
    df = df.with_columns(
        pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
    )
```

---

### 问题 4：market_data 库的 trade_date 是索引

**现象**：
- `market_data` 库中 `trade_date` 是 Pandas 索引，不是列
- 读取后需要重置索引才能使用

**解决方案**：
```python
data = market_lib.read(symbol)
df = data.data.to_pandas()  # 转换为 pandas

# 重置索引，将 trade_date 转为列
df = df.reset_index()

# 确保日期类型正确
df['trade_date'] = pd.to_datetime(df['trade_date'])
```

---

### 问题 5：写入 ArcticDB 的数据格式

**现象**：
- 直接写入 Polars DataFrame 或 PyArrow Table 报错

**解决方案**：

**方式 A：使用 UnifiedDataManager（推荐）**
```python
from data_svc.unified_data_manager import UnifiedDataManager

manager = UnifiedDataManager()
pl_df = pl.from_pandas(df)  # 转换为 Polars

result = manager.write('stock_daily', 'stock_daily', pl_df)
if result.success:
    print(f"写入成功: {result.rows} 行")
```

**方式 B：直接使用 ArcticDB（底层）**
```python
import pyarrow as pa

# 转换为 Arrow Table
arrow_table = pa.Table.from_pandas(df)

# 获取 native version store
lib = arctic['stock_daily']
nvs = lib._nvs

# 写入
result = nvs.write('stock_daily', arrow_table)
```

---

## 3. 数据验证脚本

### 检查数据范围
```bash
python sandbox/check_data_range.py
```

### 检查所有库
```bash
python sandbox/check_all_libraries.py
```

### 验证因子数据
```bash
python sandbox/verify_factors.py
```

### 检查 market_data 结构
```bash
python sandbox/check_market_data_structure.py
```

---

## 4. 最佳实践

### 4.1 数据读取流程
```python
from data_svc.storage.arcticdb_manager import get_arctic_instance
import polars as pl

arctic = get_arctic_instance()
lib = arctic['stock_daily']

# 读取数据
data = lib.read('stock_daily')

# 转换为 Polars（如果需要）
if hasattr(data.data, 'to_pandas'):
    df = pl.from_pandas(data.data.to_pandas())
else:
    df = pl.from_pandas(data.data)

# 检查必要列
assert 'trade_date' in df.columns, "缺少 trade_date 列"
assert 'stock_code' in df.columns, "缺少 stock_code 列"
assert 'close' in df.columns, "缺少 close 列"
```

### 4.2 日期过滤流程
```python
import pandas as pd

# 转换日期参数
start_dt = pd.to_datetime(start_date) if start_date else None
end_dt = pd.to_datetime(end_date) if end_date else None

# 过滤数据
if start_dt:
    df = df.filter(pl.col('trade_date') >= start_dt)
if end_dt:
    df = df.filter(pl.col('trade_date') <= end_dt)
```

### 4.3 数据写入流程
```python
from data_svc.unified_data_manager import UnifiedDataManager
import polars as pl

# 转换为 Polars
pl_df = pl.from_pandas(df)

# 写入
manager = UnifiedDataManager()
result = manager.write('stock_daily', 'stock_daily', pl_df)

if not result.success:
    raise Exception(f"写入失败: {result.error}")
```

---

## 5. 调试技巧

### 5.1 检查库是否存在
```python
libraries = arctic.list_libraries()
print(f"可用库: {libraries}")
```

### 5.2 检查 symbol 列表
```python
lib = arctic['stock_daily']
symbols = lib.list_symbols()
print(f"Symbols: {symbols}")
```

### 5.3 查看数据版本
```python
versions = lib.list_versions('stock_daily')
print(f"版本历史: {versions}")
```

### 5.4 检查数据形状
```python
data = lib.read('stock_daily')
df = pl.from_pandas(data.data.to_pandas())
print(f"形状: {df.shape}")
print(f"列名: {df.columns}")
print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
```

---

## 6. 相关脚本

| 脚本 | 用途 |
|------|------|
| `sandbox/migrate_market_data_to_stock_daily.py` | 从 market_data 迁移数据到 stock_daily |
| `sandbox/fetch_historical_data.py` | 从 Tushare 拉取历史数据 |
| `sandbox/check_data_range.py` | 检查 stock_daily 数据范围 |
| `sandbox/check_all_libraries.py` | 检查所有库的结构 |
| `sandbox/verify_factors.py` | 验证因子数据完整性 |
| `sandbox/precompute_all_factors.py` | 预计算所有因子 |

---

## 7. 总结

开发时遇到数据问题，按以下顺序排查：

1. **检查数据来源**：确认使用的是 `stock_daily` 还是 `market_data`
2. **检查数据完整性**：运行 `check_data_range.py` 查看实际数据范围
3. **检查列完整性**：确认必要的列（trade_date, stock_code, close）是否存在
4. **检查数据类型**：确认日期列是 datetime 类型，不是字符串
5. **检查写入方式**：使用 `UnifiedDataManager.write()` 而不是直接写入

如有其他问题，参考本文档或查看具体代码中的注释。
