# AquaTrade 运行手册

> 数据架构收敛版（2026-06-11）。项目**只保留一个**数据更新入口，请以本文档为准。

## 数据架构

| 角色 | 数据源 | 阻塞主流程 | 备注 |
| --- | --- | :---: | --- |
| `primary_market_store` | LanceDB（`daily_ohlcv` / `factors` / `stock_info`） | **是** | 唯一行情与因子主源 |
| `metadata_store` | SQLite（策略/组合/任务/系统设置） | 否 | 空库只提示 `metadata_empty` |
| `backtest_cache` | `data/matrix_cache` / `data/factor_matrix_cache` | 否 | 缺失时可从 LanceDB 重建 |
| `optional_snapshot` | `data/parquet_data/*.parquet` | 否 | `snapshot_stale` 不阻塞 |
| `derived_evidence` | `data/spider_data` / `data/industry` | 否 | 仅供研究查阅 |

总体状态以 `blocking=true` 的数据集为裁决依据，详见 `server/services/data_health_service.py`。

## 环境

- 项目目录：`C:\Users\Liu\Desktop\projects\aquatrade`
- 后端默认端口：`5000`
- 前端默认端口：`5173`
- Windows 终端建议设置：`$env:PYTHONIOENCODING='utf-8'`

## 启动

后端：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m server.app
```

前端：

```powershell
cd myapp
npm run dev -- --host 127.0.0.1 --port 5173
```

访问：`http://127.0.0.1:5173/dashboard`

## 数据更新（唯一入口）

> 所有行情、因子、缓存刷新必须经此入口。历史重复入口已归档，禁止再被任何脚本或 CI 引用。

```powershell
# 默认：更新 LanceDB（daily_ohlcv / stock_info / trade_status / factors）
python scripts/update/update_market_data_incremental.py

# 完整链路：lancedb + factors + matrix-cache + data_health
python scripts/update/update_market_data_incremental.py --target all

# 仅重建 matrix_cache（从 LanceDB 主源）
python scripts/update/update_market_data_incremental.py --target matrix-cache

# 手动导出 Parquet 快照（不参与默认闭环）
python scripts/update/update_market_data_incremental.py --target parquet-snapshot

# dry-run：只跑缺失检查，不写数据
python scripts/update/update_market_data_incremental.py --dry-run --target all
```

### DragonEye 证据更新

先检查最新交易日的本地证据完整性：

```powershell
python scripts/update/update_dragon_eye_evidence.py --target-date 2026-06-10 --inspect-only
```

执行爬取并写入 LanceDB 派生表：

```powershell
python scripts/update/update_dragon_eye_evidence.py --target-date 2026-06-10
```

DragonEye 只有同时具备龙头与情绪结构化数据时才视为完整。局部证据不会覆盖
QuantFlow 中的完整证据日期。

### 通用参数

| 参数 | 说明 |
| --- | --- |
| `--target` | `lancedb`（默认）/ `matrix-cache` / `sqlite-meta` / `parquet-snapshot` / `all` |
| `--start-date` / `--end-date` | 时间窗口（默认 end_date - 30 天 ~ 今天） |
| `--dry-run` | 只检查不写入 |
| `--only daily` / `--only factors` | 收紧 stage 集合 |
| `--max-symbols` | 限制单次抓取的 symbol 数（0 = 全部） |
| `--request-delay` | baostock 单股请求间隔秒数 |

### target 行为

- `--target lancedb`：更新 `daily_ohlcv` / `stock_info` / `trade_status` / `factors`。
- `--target matrix-cache`：从 LanceDB 或 Arrow 重建 `data/matrix_cache`。
- `--target sqlite-meta`：只刷新策略/组合/任务/系统配置等元信息，不写行情。
- `--target parquet-snapshot`：手动导出快照，不默认执行。
- `--target all`：执行 lancedb + factors + matrix-cache + data_health，**不**包含 parquet-snapshot。

## 数据健康

```powershell
python scripts/generate_data_health.py
```

输出：

- `data/reports/data_health_latest.json`
- `data/reports/data_health_latest.md`
- `DATA_MAP.generated.md`

接口：`GET http://127.0.0.1:5000/api/data/health`

报告中每个数据集都会带 `role` / `blocking` / `status` 三个字段，阻塞级别
决策见 `server/services/data_health_service.py::_compute_overall_status`。

## QuantFlow

```powershell
python -m core.pipeline.quant_flow_pipeline
```

输出：

- `data/reports/quant_flow_latest.json`
- `data/reports/quant_flow_latest.md`

行为约束：

- `global_latest_trade_date` 以 LanceDB `daily_ohlcv` 最新日期为准。
- 每个 stage 必须输出 `data_date`；落后于 `global_latest_trade_date` 一律降级为 warning，并记入 `stale_modules`。
- DragonEye 旧证据不再冒充今日，summary 中显式标注 data_date。

接口：

- `GET /api/quant-flow/latest`
- `POST /api/quant-flow/run`

## QMT/QNT Dry-run

```powershell
python -m integrations.qmt_bridge.dry_run_demo
```

输出：`data/reports/qmt_bridge_dry_run_latest.json`

必须确认：

- `dry_run` 为 `true`
- `real_broker_connected` 为 `false`
- 订单来源为 `mock_broker`

## 验证

```powershell
# 1) 收敛后的唯一更新入口（dry-run 验证 target 路由）
python scripts/update/update_market_data_incremental.py --dry-run --target all

# 2) 数据健康报告（带 role/blocking 字段）
python scripts/generate_data_health.py

# 3) QuantFlow（以 LanceDB latest_date 为准）
python -m core.pipeline.quant_flow_pipeline

# 4) 路由烟雾测试
python scripts/smoke_api_routes.py

# 5) 前端构建
cd myapp
npm run build
```

附加单元/烟雾测试：

```powershell
python -m compileall server core data_svc integrations scripts
python -m pytest sandbox/test_update_market_data_incremental.py -q
```

## 数据降级规则

- 本地证据为空：显示“暂无本地证据”。
- 无回测结果：不自动加载 Mock。
- 交易次数为 0：胜率和盈亏比显示 `N/A`。
- 真实 broker：当前不可用，调用时抛出 `NotImplementedError`。
- 旧 DragonEye 证据：data_date 早于 LanceDB latest_date 时自动降级为 warning，记入 `stale_modules`，禁止冒充今日。
- matrix_cache 缺失：data_health 提示 `backtest_cache_missing`，可执行 `python scripts/update/update_market_data_incremental.py --target matrix-cache` 重建。
- Parquet stale：data_health 提示 `snapshot_stale`，不阻塞主流程。
