# 可交易性过滤层说明

## 功能概述

在买入执行前增加了"可交易性过滤层"，通过 join `stock_limit_status.parquet` 实现，不允许修改或重写任何已有的 signal / alpha / 选股逻辑。

## 过滤规则

买入前会过滤以下不可交易状态：

1. **当日涨停（未开板）**：`is_limit_up = 1` 且 `is_opened = 0`
2. **当日跌停**：`is_limit_down = 1`
3. **当日停牌**：`is_suspended = 1`

### 特殊规则

- **当日封板但盘中开过板**：`is_limit_up = 1` 且 `is_opened = 1` → **允许买入/卖出**

## 数据源

- **文件路径**：`parquet_data/stock_limit_status.parquet`
- **粒度**：`stock_code + trade_date`
- **字段**：
  - `stock_code`: 股票代码
  - `trade_date`: 交易日期
  - `is_limit_up`: 是否涨停 (1=涨停, 0=非涨停)
  - `is_limit_down`: 是否跌停 (1=跌停, 0=非跌停)
  - `is_opened`: 是否开过板 (1=开过板, 0=未开板或非涨跌停)
  - `is_suspended`: 是否停牌 (1=停牌, 0=正常交易)

## 统计输出

回测完成后会输出以下统计信息：

```json
{
  "filterStats": {
    "limitUpBlocked": 0,      // 因涨停(未开板)被拦截的次数
    "limitDownBlocked": 0,    // 因跌停被拦截的次数
    "suspendedBlocked": 0,    // 因停牌被拦截的次数
    "totalBlocked": 0         // 总拦截次数
  }
}
```

同时会在日志中输出：

```
=== 可交易性过滤统计 ===
因涨停(未开板)被拦截: X 次
因跌停被拦截: Y 次
因停牌被拦截: Z 次
总拦截次数: N 次
```

## 实现细节

1. **数据加载**：使用 `_load_limit_status_data(date)` 方法加载指定日期的状态数据
2. **过滤位置**：在 `execute_trades` 方法的买入逻辑前，策略信号生成之后
3. **性能优化**：使用字典映射提高查找效率，支持 DuckDB 和 pandas 两种读取方式
4. **容错处理**：如果 `stock_limit_status.parquet` 文件不存在，会跳过过滤（默认允许交易）

## 注意事项

- 过滤层**不会修改**策略生成的信号，只是在执行买入前进行过滤
- 如果某只股票在 `stock_limit_status` 中找不到数据，默认允许交易（保守策略）
- 过滤统计会在每次回测开始时重置

