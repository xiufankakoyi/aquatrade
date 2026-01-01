# 架构监控功能

## 概述

已添加架构监控功能，用于检测回测时每个环节使用的架构，帮助识别是否使用了新架构（LanceDB + NumPy + Numba）还是回退到了老架构（DuckDB + Pandas）。

## 监控内容

### 1. 数据后端
- **LanceDB**: 新架构，零拷贝到Polars，性能最优
- **DuckDB**: 老架构，性能中等
- **SQLite/其他**: 性能较差

### 2. 数据格式
- **NumPy Array**: 新架构，内存高效，计算快速
- **Polars DataFrame/LazyFrame**: 新架构，列式存储，快速查询
- **Pandas DataFrame**: 老架构，性能较差

### 3. 计算后端
- **Numba JIT**: 新架构，JIT编译的快速循环
- **Python**: 老架构，解释执行

### 4. 数据预加载
- **是**: 数据已预加载到内存，避免逐日查询
- **否**: 未预加载，每次查询数据库，性能较差

## 输出格式

### FlexibleBacktestEngine

每天输出性能信息和架构信息：

```
[PERF][Day 1] 2024-01-01: 总耗时=450.2ms | 数据加载=380.5ms | 信号生成=25.3ms | 交易执行=2.1ms | 价值计算=1.8ms | 数据传输=40.5ms | 架构: LanceDB/Pandas DataFrame [预加载]
```

第一天会输出详细的架构信息：

```
[ARCH] 引擎: FlexibleBacktestEngine
[ARCH] 数据后端: LanceDB
[ARCH] 数据格式: Pandas DataFrame
[ARCH] 计算后端: Python (无Numba)
[ARCH] 数据预加载: 是
[ARCH] ⚠️  警告: 使用Pandas DataFrame，建议使用Polars或NumPy！
```

### OptimizedBacktestEngine

在数据加载完成后输出架构信息：

```
[ARCH] 引擎: OptimizedBacktestEngine
[ARCH] 数据后端: LanceDB
[ARCH] 数据格式: NumPy Array
[ARCH] 计算后端: Numba JIT
[ARCH] Numba JIT: 是
[ARCH] 数据预加载: 是
```

在执行快速循环后输出性能信息：

```
[PERF] 快速匹配循环完成: 总耗时=19.5ms, 平均=1.03ms/天
[ARCH] 使用Numba JIT编译循环: 是
```

## 性能目标

### 新架构（LanceDB + NumPy + Numba）
- **目标**: <1ms/天
- **实际**: 应该能达到 0.5-1ms/天

### 老架构（DuckDB + Pandas）
- **实际**: 通常 50-500ms/天

## 如何确保使用新架构

### 1. 检查环境变量
```bash
# 确保使用LanceDB后端
export DB_BACKEND=lancedb
```

### 2. 使用OptimizedBacktestEngine
```python
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
engine = OptimizedBacktestEngine(data_query)
```

### 3. 启用数据预加载
```python
data_query.preload_backtest_data(start_date, end_date)
```

### 4. 检查依赖
```bash
pip install lancedb polars numba numpy
```

## 警告信息

如果检测到未使用最优架构，会输出警告：

- `⚠️  警告: 未使用数据预加载，性能可能较差！`
- `⚠️  警告: 未使用LanceDB后端（当前: DuckDB），性能可能较差！`
- `⚠️  警告: Numba不可用，未使用JIT编译，性能可能较差！`
- `⚠️  警告: 使用Pandas DataFrame，建议使用Polars或NumPy！`

## 诊断步骤

1. **运行回测**，查看架构输出
2. **检查警告信息**，识别问题
3. **根据警告修复**：
   - 如果未使用LanceDB → 设置 `DB_BACKEND=lancedb`
   - 如果未预加载 → 调用 `preload_backtest_data()`
   - 如果使用Pandas → 切换到 `OptimizedBacktestEngine`
   - 如果Numba不可用 → 安装 `pip install numba`

## 预期输出示例

### 新架构（OptimizedBacktestEngine + LanceDB + Numba）

```
[ARCH] 引擎: OptimizedBacktestEngine
[ARCH] 数据后端: LanceDB
[ARCH] 数据格式: NumPy Array
[ARCH] 计算后端: Numba JIT
[ARCH] Numba JIT: 是
[ARCH] 数据预加载: 是
[PERF] 快速匹配循环完成: 总耗时=19.5ms, 平均=1.03ms/天
[ARCH] 使用Numba JIT编译循环: 是
```

### 老架构（FlexibleBacktestEngine + DuckDB + Pandas）

```
[ARCH] 引擎: FlexibleBacktestEngine
[ARCH] 数据后端: DuckDB
[ARCH] 数据格式: Pandas DataFrame
[ARCH] 计算后端: Python (无Numba)
[ARCH] 数据预加载: 否
[ARCH] ⚠️  警告: 未使用数据预加载，性能可能较差！
[ARCH] ⚠️  警告: 未使用LanceDB后端（当前: DuckDB），性能可能较差！
[ARCH] ⚠️  警告: 使用Pandas DataFrame，建议使用Polars或NumPy！
[PERF][Day 1] 2024-01-01: 总耗时=450.2ms | 数据加载=380.5ms | ...
```

