# AQUATRADE 研究工作台数据结构

## daily_event_tags

阶段 1 在 SQLite `Config.DB_PATH` 中按需创建 `daily_event_tags` 表，主键为 `(stock_code, trade_date)`。字段包含原始行情上下文、均线距离、量能分位和事件布尔标签。

核心字段：

- 标识：`stock_code`、`stock_name`、`trade_date`
- 行情：`open`、`high`、`low`、`close`、`prev_close`、`change_pct`、`volume`、`amount`、`total_mv`
- 事件：`is_big_up`、`is_limit_up`、`is_failed_limit_up`、`strong_attack_day`、`first_divergence_day`、`counterattack_day`、`break_board_day`
- 统计：`ma5`、`ma10`、`amount_rank_20d`、`distance_to_ma5`、`distance_to_20d_high`

## ConceptResearch

`knowledge/concepts.yaml`：

- `concept_id`
- `concept_name`
- `aliases`
- `parent_concepts`
- `industry_chain`
- `keywords`
- `description`

`knowledge/stock_concept_mapping.csv`：

- `symbol`
- `stock_name`
- `concept_id`
- `chain_position`
- `relevance_score`
- `purity_score`
- `evidence_type`
- `evidence_text`
- `evidence_source`
- `updated_at`
- `notes`
- `is_sample`

## local_news

阶段 6 在 SQLite `Config.DB_PATH` 中按导入创建 `local_news` 表：

- `title`
- `summary`
- `source`
- `publish_time`
- `url`
- `related_symbols`
- `related_concepts`
- `created_at`

新闻层只支持本地 CSV/JSON 导入和关键词匹配，不包含网页爬虫或外部 API。
