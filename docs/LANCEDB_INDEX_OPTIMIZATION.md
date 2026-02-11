# LanceDB 索引优化说明

## 问题描述

日志显示 "Load Limit: 2.038s"，虽然已建立索引，但查询可能未使用索引，导致性能问题。

## 可能的原因

1. **查询未使用索引列作为过滤条件**：即使建立了索引，如果查询语句没有显式使用索引列作为过滤条件，LanceDB 可能忽略索引
2. **小表全表扫描更快**：对于小型表，LanceDB 可能认为全表扫描比使用索引更快
3. **查询缓存被挤出**：OS Cache 可能被其他进程或数据挤出，导致查询性能下降

## 已实施的优化

### 1. 优化索引创建 (`data.py`)

- **改进索引类型**：尝试使用 BTREE 索引类型（对范围查询更高效）
- **添加复合索引支持**：为 `stock_limit_status` 表额外创建 `stock_code` 索引，优化 JOIN 查询性能
- **错误处理**：如果 BTREE 索引不支持，自动回退到默认索引类型

```python
# 优化前
tbl.create_scalar_index(date_col)

# 优化后
try:
    tbl.create_scalar_index(date_col, index_type="btree")
except (TypeError, ValueError):
    tbl.create_scalar_index(date_col)  # 回退到默认类型
```

### 2. 优化查询语法 (`data_svc/lance_manager.py`)

- **明确使用日期列过滤**：对于日期范围查询，使用更明确的 BETWEEN 语法，确保触发索引
- **性能监控**：添加查询时间监控，如果查询时间超过 1 秒，发出警告
- **查询优化**：优先使用日期索引，然后再应用其他过滤条件

```python
# 优化前
arrow_table = table.search().where(where_clause).to_arrow()

# 优化后
if start_date and end_date and not stock_codes:
    # 明确使用日期列过滤，触发索引
    date_filter = f"{date_column} >= '{start_date}' AND {date_column} <= '{end_date}'"
    arrow_table = search_query.where(date_filter).to_arrow()
else:
    arrow_table = search_query.where(where_clause).to_arrow()
```

### 3. 添加性能监控 (`data_svc/database/optimized_data_query.py`)

- **查询时间监控**：在 `preload_stock_limit_status` 和 `get_all_daily_data_for_period` 方法中添加查询时间监控
- **性能警告**：如果查询时间超过 1 秒，记录警告日志，提示可能索引未被使用
- **明确传入日期范围**：确保所有查询都明确传入 `start_date` 和 `end_date`，触发索引使用

## 验证索引是否被使用

### 方法 1：查看日志

运行查询后，查看日志输出：

1. **正常情况**（索引被使用）：
   ```
   [性能] LanceDB limit_status 加载耗时: 0.123s, 行数: 12345
   ```

2. **警告情况**（索引可能未被使用）：
   ```
   ⚠️ [性能] LanceDB limit_status 加载耗时较长 (2.038s)，可能索引未被使用。日期范围: 2024-01-01 到 2024-12-31，行数: 12345
   ```

### 方法 2：重新创建索引

如果怀疑索引未被使用，可以重新运行索引创建脚本：

```bash
python data.py
```

这将：
1. 压缩表文件（`compact_files()`）
2. 创建/重建标量索引（`create_scalar_index()`）
3. 为 `stock_limit_status` 表创建额外的 `stock_code` 索引

### 方法 3：检查索引是否存在

可以通过 LanceDB Python API 检查索引：

```python
import lancedb
from config.config import Config
import os

parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
lance_dir = os.path.join(parquet_dir, 'lance_db')
db = lancedb.connect(lance_dir)

table = db.open_table('stock_limit_status')
# 检查表信息（索引信息可能包含在 schema 或 metadata 中）
print(f"表名: {table.table_name}")
print(f"Schema: {table.schema}")
```

## 进一步优化建议

### 1. 确保数据已排序

LanceDB 的索引性能依赖于数据的物理排序。在转换 Parquet 到 LanceDB 时，确保数据已按 `trade_date` 排序：

```python
# 在 convert_parquet_to_lance 中已实现
lf = lf.sort(['trade_date', 'stock_code'])
```

### 2. 定期压缩表

定期运行 `compact_files()` 可以：
- 合并小文件，减少碎片
- 提高查询性能
- 确保索引有效性

```bash
python data.py  # 运行优化脚本
```

### 3. 监控系统资源

- **内存使用**：确保系统有足够内存维持查询缓存
- **磁盘 I/O**：使用 SSD/NVMe 存储可以显著提升查询性能
- **CPU 使用**：LanceDB 查询会使用 CPU，确保系统有足够资源

### 4. 查询缓存优化

如果查询缓存被挤出，可以考虑：

1. **增加系统内存**：为 OS Cache 分配更多内存
2. **减少并发查询**：避免同时运行多个大型查询
3. **预加载数据**：在回测开始前预加载所有需要的数据

## 性能基准

### 预期性能（索引被正确使用）

- **小范围查询**（1-30 天）：< 0.1 秒
- **中等范围查询**（1-3 个月）：< 0.5 秒
- **大范围查询**（1 年）：< 1.0 秒

### 如果性能不达标

1. 检查日志中的性能警告
2. 重新运行 `python data.py` 重建索引
3. 检查系统资源（内存、磁盘 I/O）
4. 考虑使用更快的存储（SSD/NVMe）

## 相关文件

- `data.py` - 索引创建和表优化脚本
- `data_svc/lance_manager.py` - LanceDB 查询实现
- `data_svc/database/optimized_data_query.py` - 数据查询接口

## 更新日志

- **2024-12-XX**: 添加索引类型优化（BTREE）
- **2024-12-XX**: 添加查询语法优化（明确使用日期列）
- **2024-12-XX**: 添加性能监控和警告机制










