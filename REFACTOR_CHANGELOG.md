# AquaTrade 八合一重构变更日志

日期：2026-06-11

## 接口与数据

- 新增研究工作台接口：最新价、帖子关键词、筛选统计、CSV 导出、基准净值、数据健康和 QuantFlow。
- 修正策略参数主调用路径为 `/api/strategies/{id}/params`，参数元数据不可用时降级为空数组。
- 前端响应判断兼容 `success/data`、`ok/data` 和 `status/result/error`。
- 新增数据健康扫描器和报告生成脚本，覆盖 SQLite、LanceDB、Parquet、缓存、爬虫与产业链数据。

## 投研流水线

- 新增可独立运行的七阶段 `QuantFlowPipeline`。
- 流水线只读取本地结构化数据；数据不足时记录 warning/skipped，不生成随机结论。
- 新增 latest/run API，并在 Dashboard 展示运行时间、阶段状态、原因和最终简报。

## 前端

- 重构 Dashboard 为浅色卡片式工作台，包含 Header、KPI、主图、辅助图表、明细页签和数据状态。
- 无交易记录时，胜率和盈亏比显示 `N/A` 并说明原因。
- 新增 `LoadingState`、`EmptyState`、`ErrorState`、`DataStatusBadge`。
- 股票筛选器、DragonEye、产业链、相似形态、历史记录和 Dashboard 接入可见状态。
- 百分比统一为 2 位、分数 4 位、金额使用万/亿。

## Mock 与证据治理

- 新增统一 `mockDataRegistry.ts`，Mock 响应带 `source: "mock"` 和 `is_mock: true`。
- Dashboard 仅在显式 Mock 开关开启时使用 Mock，真实接口失败不自动回退。
- 产业链 fallback 带 `source: "fallback"` 和 `is_fallback: true`，生产环境无证据时显示“暂无本地证据”。
- `/api/lda_topics` 移除随机主题，无本地结果时返回空数组和“暂无本地证据”。

## Legacy 与 QMT/QNT

- 无路由、无引用的旧页面和调试 e2e specs 移入 `legacy_archive/`，未直接删除。
- 新增 `integrations/qmt_bridge/`：抽象接口、Mock broker、RiskGuard、TradePlan 和 dry-run demo。
- 真实 broker 方法统一抛出 `NotImplementedError`，当前没有真实账户连接或真实下单能力。

## 验证修复

- 修复既有 `analysis_service.py` 游离缩进代码导致的编译失败。
- 修复 `game_service.py` 受损类型名导致的后端导入失败。
- 修复 `MACDChart.vue` 类型被当作运行时导入的构建警告。
- LanceDB 健康扫描切换到 `list_tables()` 新接口。
- 相似形态表格空数据文案完成中文化。
