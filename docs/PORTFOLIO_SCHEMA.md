# Portfolio Schema 规范

> 本文档定义 AquaTrader 持仓文件的统一字段标准。
> 适用于 `data/parquet_data/portfolio_positions.parquet` 以及任何需要与
> `quant_flow_pipeline.portfolio_risk_check` 交互的持仓数据源。

## 1. 字段总览

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | int | 是 | 唯一编号，自增。 |
| `stock_code` | str(6) | 是 | 股票代码（6 位数字，例如 `000001`）。 |
| `stock_name` | str | 是 | 股票名称，例如 `平安银行`。 |
| `quantity` | float | **是（主字段）** | 持仓数量，单位为"股"。0 或 NULL 视为缺字段。 |
| `shares` | float | 否（兼容字段） | 历史字段名，等价于 `quantity`。当 `quantity` 缺失时回退使用。 |
| `buy_price` | float | 否 | 买入单价。 |
| `cost` | float | 否 | 总买入成本。缺省时 `unrealized_pnl` 计算结果为 NULL。 |
| `buy_date` | str(10) | 否 | 买入日期 `YYYY-MM-DD`。 |
| `stop_loss` | float | 否 | 止损价。 |
| `take_profit` | float | 否 | 止盈价。 |
| `notes` | str | 否 | 备注。 |
| `is_active` | bool/int | 否 | 是否活跃，`True/1` 表示纳入估值。 |
| `created_at` | str | 否 | 创建时间。 |
| `updated_at` | str | 否 | 更新时间。 |

### 1.1 字段优先级与兼容规则

1. 读取时：**`quantity` 优先**，仅在 `quantity` 缺失或为 0 时回退到 `shares`。
2. 写入时：新数据**必须**写入 `quantity` 字段；`shares` 字段允许保留但不再增长。
3. 解析器：
   - `core.portfolio.position_manager.Position.effective_quantity()` 是统一入口。
   - 任何下游（`portfolio_risk_check`、`/api/portfolio/analysis` 等）都应通过此入口获取数量。
4. 缺字段判定：若一行记录的 `quantity` 与 `shares` 同时为 0/NULL，视为数量缺失。

## 2. 估值口径

`quant_flow_pipeline.portfolio_risk_check` 在满足下列条件时返回 `valuation_complete=True`：

1. 持仓文件存在且至少一行活跃记录。
2. 每一行都能解析到有效 `quantity`（`quantity > 0` 或 `shares > 0`）。
3. 每一行对应的最新价都已从 LanceDB `daily_ohlcv` 命中，且 `valuation_date` 一致。

### 2.1 估值字段

| 输出字段 | 计算 | 来源 |
| --- | --- | --- |
| `market_value` | `latest_price * quantity` | LanceDB `daily_ohlcv.close` × 持仓数量 |
| `unrealized_pnl` | `market_value - cost`（当 `cost > 0`） | 否则为 NULL |
| `weight` | `market_value / total_market_value` | 仅在 `total_market_value > 0` 时计算 |
| `valuation_date` | LanceDB 命中的 `trade_date` | 与最新价同源 |

## 3. 错误降级

| 场景 | 行为 |
| --- | --- |
| 整个文件缺失 | stage 状态 `skipped`，`message="缺少 portfolio_positions.parquet"`。 |
| 缺 `quantity`/`shares` 字段 | stage 状态 `warning`，`errors=["持仓文件缺少 shares/quantity，不能计算完整市值"]`。 |
| 部分行缺 `quantity`/`shares` | stage 状态 `warning`，`errors=["部分持仓行 quantity/shares 缺失，无法准确估值"]`。 |
| 缺最新价 | stage 状态 `warning`，`errors=["缺少最新价: 600000.SH, ..."]`。 |
| 全部满足 | stage 状态 `ok`，`valuation_complete=True`。 |

> 任何 `warning` 都不让 portfolio 估值崩溃，前端可以安全展示 `market_value=None` 的行。

## 4. 与 API/前端约定

* `GET /api/portfolio/positions`：返回驼峰字段，**同时**输出 `quantity` 与 `shares`，让前端自由选择展示。
* `GET /api/portfolio/analysis`：估值口径与 `portfolio_risk_check` 完全一致。
* 前端写入持仓：POST/PUT 持仓时，**必须**传 `quantity` 字段；不传则服务层将 `shares` 拷贝到 `quantity` 兜底。

## 5. 版本与变更

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-06-12 | v1.0 | 引入 `quantity` 为主字段；`shares` 兼容；`portfolio_risk_check` 输出 `market_value/unrealized_pnl/weight/valuation_date`。 |
