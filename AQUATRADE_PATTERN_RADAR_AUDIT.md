# AQUATRADE PatternRadar Phase 0 Audit

审计日期：2026-05-16

本审计仅记录当前项目事实，用于后续“短线形态雷达 + 概念研究库”分阶段实现。审计阶段未修改业务代码。

## 1. 后端入口文件

- Flask 主入口：`server/app.py`
  - 创建 `Flask` app、配置 CORS、初始化 `Flask-SocketIO`。
  - 调用 `server.routes.register_routes(app)` 注册 HTTP 蓝图。
  - 调用 `server.socketio_handlers.register_socketio_handlers(socketio)` 注册 Socket.IO 事件。
  - 提供 `get_api()` 懒加载 `server.visualization_api.BacktestVisualizationAPI`。
- ASGI/Granian 入口：`server/asgi_entry.py`
  - 设置 `USE_GRANIAN=true`。
  - 从 `server.app` 导入 Flask app。
  - 创建 `python-socketio.AsyncServer`，注册 `server.asgi_socketio_handlers`。
  - 导出 `asgi_app`。
- 另有入口：`run.py`
  - 同样包装 Flask app 和 Socket.IO 为 ASGI 应用。
- 进程配置：`Procfile`
  - `web: granian --interface asgi server.asgi_entry:asgi_app --host 0.0.0.0 --port 5000`
  - `worker: python server/worker.py`

结论：项目没有 `backend/` 目录。新增后端研究模块应放入现有 `server/` 包，例如 `server/event_engine`、`server/pattern_lab`、`server/concept_lab`、`server/news_lab`，避免重构目录。

## 2. 当前 API 路由结构

统一注册点：`server/routes/__init__.py`

当前注册蓝图：

- `server.routes.strategy_routes` -> `/api`
- `server.routes.backtest_routes` -> `/api`
- `server.routes.data_routes` -> `/api/db`
- `server.routes.scatter_routes` -> `/api`
- `server.routes.sentiment_routes` -> `/api`
- `server.routes.optimization_routes` -> `/api`
- `server.routes.system_routes` -> `/api`
- `server.routes.dragon_eye_routes` -> `/api/dragon`
- `server.routes.portfolio_routes` -> `/api/portfolio`
- `server.routes.game_routes` -> `/api/game`
- `server.routes.screener_routes` -> `/api/screener`
- `server.routes.export_routes` -> `/api/export`
- `server.routes.similarity_routes` -> `/api/similarity`

Socket.IO 相关：

- `server/socketio_handlers.py`
- `server/asgi_socketio_handlers.py`
- 现有事件包括 `connect`、`disconnect`、`run_streaming_backtest`、`cancel_streaming_backtest`、`request_kline`、`run_optimization`、`stop_optimization`。

结论：新增 PatternRadar/ConceptResearch REST API 应以独立蓝图接入 `server/routes/__init__.py`，不改 Socket.IO 事件。

## 3. 当前数据查询模块

主要数据查询入口：

- `data_svc/database/optimized_data_query.py`
  - 类：`OptimizedStockDataQuery`
  - 常用方法：
    - `get_trading_dates(start_date, end_date)`
    - `get_stock_pool(date, filters=None, use_cache=True, columns=None)`
    - `get_stock_history(stock_code, start_date, end_date, use_cache=True, columns=None)`
    - `load_stock_panel(codes, start_date, end_date, cols)`
    - `get_all_daily_data_for_period(start_date, end_date, filters=None)`
  - 实际热路径以 Polars 直接读取 Parquet 为主。
- `data_svc/unified_data_query.py`
  - 类：`UnifiedDataQuery`
  - 通过 LanceDB reader 读取 `daily_ohlcv`、`stock_info`、`index_daily`。
- `data_svc/storage/lancedb_reader.py`
  - 类：`LanceDBDataReader`
  - LanceDB 读取层，部分列表/统计函数会尝试 DuckDB fallback。
- `data_svc/parquet_data_manager.py`
  - 类：`ParquetDataManager`
  - 通用 Parquet 读写管理器。

结论：后续批量事件生成应优先离线读取 Parquet/Polars，生成结果持久化，前端查询不应实时全市场重算。

## 4. DuckDB / Parquet / LanceDB 接入方式

配置：

- `config/config.py`
  - `Config.PARQUET_DIR = data/parquet_data`
  - `Config.LANCEDB_PATH = data/lancedb`
  - `Config.DB_PATH = data/database/stock_data.db`
- `config/setting.py`
  - `DB_BACKEND` 默认值为 `lancedb`

实际文件：

- `data/parquet_data/stock_daily.parquet`
- `data/parquet_data/stock_info.parquet`
- `data/parquet_data/stock_limit_status.parquet`
- `data/parquet_data/benchmark_daily.parquet`
- `data/lancedb/daily_ohlcv.lance`
- `data/lancedb/stock_info.lance`

注意：

- `requirements.txt` 包含 `pyarrow`、`polars`，未包含 `duckdb`。
- 代码中仍有少量 `import duckdb` fallback，但主数据链路不是稳定 DuckDB 主链路。
- 本地 SQLite `data/database/stock_data.db` 有 `stock_daily`、`stock_info` 表结构，但审计时行数为 0。

## 5. 当前日线字段

`docs/reference/parquet_schema_utf8.txt` 记录的 `stock_daily.parquet` 字段：

- `id`
- `stock_code`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `prev_close`
- `change_amount`
- `change_pct`
- `volume`
- `amount`
- `total_mv`
- `float_mv`
- `turnover_rate`
- `turnover_free`
- `volume_ratio`
- `pe`
- `pe_ttm`
- `pb`
- `ps`
- `ps_ttm`
- `dividend_yield`
- `dividend_yield_ttm`
- `total_shares`
- `float_shares`
- `free_float_shares`
- `limit_up`
- `limit_down`
- `adj_factor`
- `ts_code`
- `ma3_avg_price`
- `ma5_avg_price`
- `ma10_avg_price`
- `ma5`
- `ma10`
- `ma20`
- `volume_ma5`

`stock_info.parquet` 字段：

- `stock_code`
- `stock_name`
- `industry`
- `region`
- `list_date`
- `is_st`
- `is_kc`
- `is_cy`

`stock_limit_status.parquet` 字段：

- `stock_code`
- `trade_date`
- `is_limit_up`
- `is_limit_down`
- `is_opened`
- `is_suspended`

字段兼容映射：

| 目标字段 | 当前实际字段 |
| --- | --- |
| `date` | `trade_date` |
| `symbol` | `stock_code`，另有 `ts_code` |
| `pct_chg` | `change_pct` |
| `market_cap` | `total_mv`，另有 `float_mv` |
| `turnover` | `turnover_rate`，另有 `turnover_free` |
| `limit_up` | `limit_up`，含义是涨停价 |
| `limit_down` | `limit_down`，含义是跌停价 |
| `stock_name` | `stock_info.stock_name` |
| 涨跌停布尔 | `stock_limit_status.is_limit_up/is_limit_down` |

阶段 1 兼容要求：

- `change_pct` 作为涨跌幅主字段，缺失时使用 `close / prev_close - 1` 推导。
- `limit_up/limit_down` 是价格，不是布尔。
- `is_limit_up/is_limit_down` 可来自 `stock_limit_status`，缺失时按 `close` 与涨跌停价或涨跌幅近似推断。
- `is_failed_limit_up` 可用 `high >= limit_up` 且 `close < limit_up` 推断；没有涨停价时降级为 `False` 或配置化近似。
- `market_cap` 参数应映射到 `total_mv`。
- `turnover` 参数应映射到 `turnover_rate`。

## 6. 前端页面、路由、组件结构

前端目录：`myapp/`

- 入口：`myapp/src/main.ts`
- 根组件：`myapp/src/App.vue`
- 路由：`myapp/src/router/index.ts`
- 主布局：`myapp/src/layout/MainLayout.vue`
- 侧边栏：`myapp/src/components/layout/Sidebar.vue`

页面目录：

- `myapp/src/pages`
  - `DashboardOverview.vue`
  - `ParamOptimizationPage.vue`
  - `PortfolioAnalysisPage.vue`
  - `DragonEyePage.vue`
  - `KlineGamePage.vue`
  - `StrategyCenterPage.vue`
  - `StrategyDetailKline.vue`
  - 等
- `myapp/src/views`
  - `SimilarityPage.vue`
  - `StockScreenerPage.vue`

API 封装：

- `myapp/src/api/index.ts`：Axios 实例。
- `myapp/src/api/similarity.ts`：相似度页面 API。
- `myapp/src/api/screener.ts`：筛选器 API。
- `myapp/src/services/api.ts`：另一套 fetch 封装，主要用于已有回测/策略接口。

结论：新增前端 API 更适合沿用 `myapp/src/api/*.ts` feature 文件模式。

## 7. 当前 ECharts / K 线封装方式

ECharts 没有统一全局 wrapper，常见组件直接：

1. `import * as echarts from 'echarts'`
2. `echarts.init(dom)`
3. `chart.setOption(option)`
4. `window.resize` 调 `chart.resize()`
5. `onUnmounted` 调 `dispose()`

相关组件：

- `myapp/src/components/charts/DrawdownChart.vue`
- `myapp/src/components/charts/LimitUpTrendChart.vue`
- `myapp/src/components/charts/ThemeFlowChart.vue`
- `myapp/src/views/SimilarityPage.vue`

K 线主要使用 `lightweight-charts`：

- `myapp/src/components/charts/TVKlineChart.vue`
- `myapp/src/components/charts/KLineChart.vue`
- `myapp/src/components/charts/KLineChartV2.vue`

结论：PatternRadar 案例复盘可先复用 `TVKlineChart.vue`，如需命中窗口高亮和事件标记，再新增 `PatternKLineChart.vue`。

## 8. 启动和测试命令

后端：

```powershell
granian --interface asgi server.asgi_entry:asgi_app --host 0.0.0.0 --port 5000
```

前端：

```powershell
cd myapp
npm run dev
```

后端测试：

```powershell
pytest
```

前端构建：

```powershell
cd myapp
npm run build
```

## 9. 阶段 1 实现建议

- 新增模块放入 `server/event_engine`。
- 新增路由放入 `server/routes/event_routes.py`，并在 `server/routes/__init__.py` 注册。
- 生成结果不要回写大 Parquet 主表。
- 为避免引入额外服务，阶段 1 可使用 SQLite 表 `daily_event_tags` 持久化到 `Config.DB_PATH`。
- 标签生成函数应独立于 Flask，可被后续 PatternRadar 后端直接复用。
- 前端查询必须读已生成标签，不做全市场实时重算。
- 所有阈值集中在 schema/config 中。
