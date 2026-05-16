# ConceptResearch 概念研究库

ConceptResearch 是本地可维护的概念知识库，用于记录概念定义、别名、产业链、关键词和人工维护的股票证据映射。系统不爬取网页，不调用大模型，不凭空判断公司业务正宗性。

## 数据文件

- `knowledge/concepts.yaml`：概念定义。当前使用 JSON 兼容 YAML 格式，便于标准库解析。
- `knowledge/stock_concept_mapping.csv`：股票证据映射。默认只有表头，真实证据由人工维护。

## 后端 API

- `GET /api/concepts`
- `GET /api/concepts/<concept_id>`
- `GET /api/concepts/<concept_id>/stocks`
- `POST /api/concepts/search`
- `GET /api/concepts/<concept_id>/market-confirm`

## 前端入口

- 路由：`/concept-research`
- 页面：`myapp/src/views/ConceptResearch.vue`

## 评分规则

`concept_score = relevance_score * 0.45 + purity_score * 0.25 + evidence_score * 0.15 + market_confirm_score * 0.15`

证据强度由结构化 `evidence_type` 决定，年报/公告强于官网、互动问答和概念板块。映射为空时页面显示“暂无本地证据”。
