# AquaTrade Round 0 基线审计

审计日期：2026-06-11

## 基线结果

- 前端构建：通过（`cd myapp && npm run build`）。
- 现有接口静态审计：通过（`python -m pytest test/test_frontend_api_integration.py -q`，24 passed）。
- 工作区状态：审计开始时无未提交改动。

## 已确认风险

### P0 接口

- `/api/strategies/{id}/params` 已存在，但 `myapp/src/api/backtestApi.ts` 仍调用旧路径 `/api/strategy/{id}/parameters`。
- 前端调用 `POST /api/screener/field_stats`，后端当前仅实现 `GET /api/screener/stats`。
- 前端调用 `POST /api/screener/export`，当前未发现对应路由。
- 需要用运行时 smoke test 验证 `/api/latest_price`、`/api/stock_posts_by_keyword`、`/api/benchmark/{code}/equity` 是否真实注册且不返回 404。

### Mock / fallback / random

- `DashboardOverview.vue` 的快速开始无条件调用 `generateMockBacktestData()`。
- `/api/lda_topics` 使用 `random.uniform()` 生成主题权重。
- `fetchMock.ts`、`mockAdapter.ts`、`mockSocketIO.ts` 各自维护数据，尚未统一 registry。
- `industryChainFallback.ts` 的示例证据需要显式 fallback 标记，并限制在 dev/mock 模式。

### 前端状态

- Dashboard、IndustryChain、Similarity 等关键页面仍存在仅 `console.error` 的失败分支。
- 通用 `LoadingState`、`EmptyState`、`ErrorState`、`DataStatusBadge` 尚未形成统一覆盖。

### 数据与流程

- 尚无完整 `/api/data/health`、数据健康报告和 `DATA_MAP.generated.md`。
- 尚无可独立运行并生成报告的七阶段 QuantFlowPipeline。
- 尚无 `integrations/qmt_bridge/` dry-run 风控桥接实现。

### 构建警告

- `MACDChart.vue` 从 `lightweight-charts` 引入了运行时不存在的类型导出。
- Vite 存在大 chunk 警告；不阻塞本次验收。

## 基线结论

项目可以构建，但当前静态测试不足以覆盖任务要求。后续验收必须增加运行时 API smoke、CLI 报告验证、QMT dry-run 验证和浏览器端到端验证。
