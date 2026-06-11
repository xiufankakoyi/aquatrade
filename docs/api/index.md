# API Documentation

## 研究工作台接口

以下接口只读取本地结构化数据；无数据时返回明确 `message`，不使用随机或未标记的示例数据。

- `GET /api/latest_price?symbols=000001.SZ&date=2026-01-01`
- `GET /api/stock_posts_by_keyword?keyword=关键词`
- `POST /api/screener/field_stats`
- `POST /api/screener/export`
- `POST /api/benchmark/{code}/equity`
- `GET /api/strategies/{id}/params`
- `GET /api/data/health`
- `GET /api/quant-flow/latest`
- `POST /api/quant-flow/run`

## Automatic API Docs (Swagger UI)
The backend provides automatic API documentation using Swagger UI.

- **URL**: `http://localhost:8000/apidocs` (or whatever port the server runs on)
- **Spec**: `http://localhost:8000/apispec_1.json`

## REST API
### Strategies
- `GET /api/strategies`: List all available strategies
- `GET /api/strategies/<id>/params`: Get parameters for a strategy
  - Returns an empty array with HTTP 200 when parameter metadata is unavailable.

### Data
- `GET /api/kline`: Get K-line data
- `GET /api/latest_price`: Get current prices

### Industry Chain Radar
- `GET /api/industry-chain/chains`: List local industry chain definitions from `knowledge/industry_chains`.
- `GET /api/industry-chain/graph?chain_id=optical_communication`: Return ECharts graph data with nodes, edges, layers, and summary.
- `GET /api/industry-chain/node/<node_id>?chain_id=optical_communication`: Return node detail, upstream/downstream nodes, auto-updated metrics, and stocks.
- `GET /api/industry-chain/node/<node_id>/stocks?chain_id=optical_communication`: Return verified local mappings, manual overrides, and auto candidates. Auto candidates are marked separately and use `system_relevance_score`; they are not treated as verified evidence.
- `GET /api/industry-chain/data-sources/status`: Return provider availability, last sync time, parquet file status, and recent source logs.
- `GET /api/industry-chain/debug`: Return diagnostic paths and counts including `project_root`, `knowledge_path`, `industry_chain_files`, `loaded_chains`, `optical_communication_exists`, `node_count`, `edge_count`, and `stock_mapping_count`.
- `POST /api/industry-chain/sync?chain_id=optical_communication&trade_date=2026-05-16`: Trigger Data Auto Update v1 once for diagnostics. Normal operation uses the backend scheduler.

### Industry Chain Data Auto Update v1
- Backend startup starts the scheduler automatically by default. It runs a catch-up check after startup and then runs daily at local `16:30`. Weekend startup falls back to the previous weekday trade date.
- `GET /api/industry-chain/data-sources/status` also starts a background catch-up when core parquet tables have zero rows, so opening the page can recover missing local data after the computer was offline.
- CLI remains available for diagnostics: `python tools/update_industry_data_daily.py --all`
- Single chain: `python tools/update_industry_data_daily.py --chain optical_communication --date today`
- Scheduler status is included in `GET /api/industry-chain/data-sources/status` as `auto_update_scheduler`.
- Scheduler environment variables:
  - `INDUSTRY_AUTO_UPDATE_ENABLED=true|false`
  - `INDUSTRY_AUTO_UPDATE_ON_STARTUP=true|false`
  - `INDUSTRY_AUTO_UPDATE_HOUR=16`
  - `INDUSTRY_AUTO_UPDATE_MINUTE=30`
  - `INDUSTRY_AUTO_UPDATE_CHAIN=optical_communication` to limit one chain; empty means all chains
  - `INDUSTRY_AUTO_UPDATE_SKIP_WEEKENDS=true|false`
- Provider failover:
  - Realtime quotes: Efinance -> AKShare -> Tushare
  - Daily bars: local parquet -> Tushare -> Efinance -> AKShare -> Baostock
  - Concept boards and members: AKShare -> Tushare
  - Limit-up pool: AKShare
  - Fund flow: Efinance -> AKShare -> Tushare where supported
- If realtime quotes are unavailable, Data Auto Update v1 builds candidates from concept/board data first and then pulls daily bars for those candidate symbols to populate `market_snapshot.parquet`, preventing the page from showing an empty market snapshot.
- Outputs under `data/industry/`: `market_snapshot.parquet`, `daily_bars_latest.parquet`, `concept_boards.parquet`, `concept_board_members.parquet`, `limit_up_pool.parquet`, `board_fund_flow.parquet`, `stock_fund_flow.parquet`, `stock_basic_info.parquet`, `industry_node_candidates.parquet`, `industry_node_metrics.parquet`, `industry_graph_cache.parquet`, and `data_source_log.parquet`.

## Socket.IO Events
- `connect`: Client connection
- `start_backtest`: Trigger a backtest
- `backtest_update`: Real-time backtest progress
