# 旧版更新入口归档

归档日期：2026-06-11。

## 背景

AquaTrader 数据架构收敛后，项目内**唯一**的权威数据更新入口已迁移到：

- `scripts/update/update_market_data_incremental.py`

本目录仅用于历史追溯，不应再被任何脚本/文档/CI 引用。

## 归档内容

- `update_market_data_incremental.py`
  原 `tools/update_market_data_incremental.py`，与 `scripts/update/update_market_data_incremental.py` 在
  收敛前存在两份入口，功能上有重叠但实现路径不同。

  新入口已合并以下能力：

  - `tools/update_market_data_incremental.py` 的 LanceDB `daily_ohlcv` 写入逻辑
  - 旧 `scripts/update/update_market_data_incremental.py` 的 `matrix_cache` 重建逻辑
  - 新增的 `target` 行为分流：`lancedb / matrix-cache / sqlite-meta / parquet-snapshot / all`

## 新入口的等效命令

| 旧命令 | 新入口等效 |
| --- | --- |
| `python tools/update_market_data_incremental.py` | `python scripts/update/update_market_data_incremental.py --target lancedb` |
| `python tools/update_market_data_incremental.py --only daily` | `python scripts/update/update_market_data_incremental.py --target lancedb --only daily` |
| `python tools/update_market_data_incremental.py --only factors` | `python scripts/update/update_market_data_incremental.py --target lancedb --only factors` |
| `python tools/update_market_data_incremental.py --dry-run` | `python scripts/update/update_market_data_incremental.py --target lancedb --dry-run` |

## 复原说明

如确需回退到旧行为，请先评估是否违反当前数据架构（具体见 RUNBOOK.md 的"数据架构"小节），
再将本文件 `mv` 回 `tools/update_market_data_incremental.py`，并同步更新 RUNBOOK 引用。
