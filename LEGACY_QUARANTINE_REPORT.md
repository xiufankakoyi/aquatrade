# Legacy Quarantine Report

日期：2026-06-11

## 已归档

- `legacy_archive/frontend_pages/`：8 个无路由、无 import 的旧前端页面。
- `legacy_archive/e2e_debug/`：13 个重复的分页/滚动调试 specs。
- `scripts/legacy/`：项目原有历史启动脚本，继续保留在既有隔离目录。

## 保留

- `quant/`：数据状态和 DragonEye 仍引用其数据目录，不能移动。
- `KLineChart.vue`：`StockKlineModal.vue` 正在使用。
- `TVKlineChart.vue`：策略详情、K 线训练和默认市场图正在使用。
- `PatternKLineChart.vue`：`PatternCaseReplay.vue` 正在使用。
- `KLineChartV2.vue` / `DataManagerV2.ts`：虽未发现页面引用，但两者存在直接依赖关系，先保留并标记为待进一步确认。
- `DataManager.ts`：`KLineChart.vue` 正在使用。
- `polars_data_loader*`、`unified_data_manager*`、`matrix_cache_manager`：后端存在多版本实现且调用关系复杂，本轮不做高风险移动。

## 验收原则

归档后必须通过前端构建、后端 import、API smoke 和浏览器回归；任一失败则恢复对应文件并重新审计。
