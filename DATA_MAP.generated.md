# AquaTrade 数据地图（自动生成）

生成时间：2026-06-12T13:03:52+08:00

| 数据集 | 角色 | blocking | 路径 | 来源 | 状态 | 字段数 |
| --- | --- | :---: | --- | --- | --- | ---: |
| sqlite | `metadata_store` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\database\stock_data.db` | `local_sqlite` | `warning` | 0 |
| lancedb | `primary_market_store` | true | `C:\Users\Liu\Desktop\projects\aquatrade\data\lancedb` | `local_lancedb` | `ok` | 42 |
| parquet | `optional_snapshot` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\parquet_data` | `local_parquet` | `ok` | 38 |
| factor_matrix_cache | `backtest_cache` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\factor_matrix_cache` | `local_cache` | `ok` | N/A |
| matrix_cache | `backtest_cache` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\matrix_cache` | `local_cache` | `ok` | N/A |
| spider_data | `derived_evidence` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\spider_data` | `local_spider` | `ok` | N/A |
| industry | `derived_evidence` | false | `C:\Users\Liu\Desktop\projects\aquatrade\data\industry` | `local_structured_evidence` | `ok` | N/A |
