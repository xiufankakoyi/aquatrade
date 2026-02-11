# Aquatrade Database Schema

此文档由 `scripts/generate_schema_doc.py` 自动生成，用于记录当前数据库的所有字段，方便策略开发。

## 数据表: `stock_daily`
| 序号 | 字段名 (Column Name) | 备注 (Notes) |
| :--- | :--- | :--- |
| 1 | `adj_factor` | 复权因子 |
| 2 | `amount` |  |
| 3 | `change_amount` |  |
| 4 | `change_pct` |  |
| 5 | `close` |  |
| 6 | `dividend_yield` |  |
| 7 | `dividend_yield_ttm` |  |
| 8 | `float_mv` |  |
| 9 | `float_shares` |  |
| 10 | `free_float_shares` |  |
| 11 | `high` |  |
| 12 | `id` |  |
| 13 | `limit_down` |  |
| 14 | `limit_up` |  |
| 15 | `low` |  |
| 16 | `ma10` |  |
| 17 | `ma10_avg_price` |  |
| 18 | `ma20` |  |
| 19 | `ma3_avg_price` |  |
| 20 | `ma5` |  |
| 21 | `ma5_avg_price` |  |
| 22 | `open` |  |
| 23 | `pb` |  |
| 24 | `pe` |  |
| 25 | `pe_ttm` |  |
| 26 | `prev_close` |  |
| 27 | `ps` |  |
| 28 | `ps_ttm` |  |
| 29 | `stock_code` |  |
| 30 | `total_mv` | 总市值 (策略核心过滤字段) |
| 31 | `total_shares` |  |
| 32 | `trade_date` | 交易日期 (格式: YYYY-MM-DD) |
| 33 | `ts_code` |  |
| 34 | `turnover_free` |  |
| 35 | `turnover_rate` |  |
| 36 | `volume` |  |
| 37 | `volume_ma5` |  |
| 38 | `volume_ratio` | 量比 (策略核心过滤字段) |

## 数据表: `stock_info`
| 序号 | 字段名 (Column Name) | 备注 (Notes) |
| :--- | :--- | :--- |
| 1 | `industry` |  |
| 2 | `is_cy` |  |
| 3 | `is_kc` |  |
| 4 | `is_st` |  |
| 5 | `list_date` |  |
| 6 | `region` |  |
| 7 | `stock_code` |  |
| 8 | `stock_name` |  |

## 数据表: `benchmark_data`
| 序号 | 字段名 (Column Name) | 备注 (Notes) |
| :--- | :--- | :--- |
| 1 | `close` |  |
| 2 | `code` |  |
| 3 | `date` |  |
| 4 | `id` |  |

## 数据表: `stock_limit_status`
> [!WARNING]
> 该表在当前后端（LanceDB/DuckDB）中为空或未找到。

