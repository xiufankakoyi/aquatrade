# K线形态研究：短线形态雷达

短线形态雷达是 K线形态研究模块内的事件型扫描能力，用阶段 1 生成的 `daily_event_tags` 检索 A 股短线/波段形态样本。它只输出候选、命中原因、风险标签和后续收益统计，结果仅用于形态研究与样本统计。

## 后端 API

- `GET /api/patterns/templates`：返回内置模板。
- `POST /api/patterns/search`：按模板、日期、股票池和参数扫描。
- `POST /api/patterns/backtest`：返回样本统计、成功样本和失败样本。
- `GET /api/patterns/cases`：按成功/失败/近端候选筛选案例。
- `GET /api/patterns/symbol/<symbol>/events`：查询单只股票事件标签。

## 前端入口

- 路由：`/similarity?module=radar`
- 页面：`myapp/src/views/SimilarityPage.vue`
- 侧边栏：统一入口“形态研究”
- 兼容：`/pattern-radar` 会重定向到统一形态研究页面。

## 运行示例

```powershell
Invoke-RestMethod -Method Post http://localhost:5000/api/patterns/search -ContentType "application/json" -Body '{"pattern_id":"strong_break_reversal","start_date":"2024-01-01","end_date":"2024-03-31","limit":20}'
```

## 边界

所有结果都是历史事件结构与统计研究信息。样本成功率、后续收益和风险标签不能解释为交易指令。
