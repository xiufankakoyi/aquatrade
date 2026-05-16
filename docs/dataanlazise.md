我们已经完成了 IndustryChainRadar 第一版，问题是缺少数据。现在开始第二版：Data Enrichment Layer。

目标：
为 IndustryChainRadar 增加真实可维护的数据层，但不要做大模型、不要做爬虫、不要编造公司映射。第二版重点是：

1. 外部概念成分候选池；
2. 本地行情确认；
3. 本地证据库；
4. 节点热度计算；
5. 前端展示数据来源和验证状态。

核心原则：

- 外部数据源只作为候选，不作为最终正宗性结论。
- 正宗性以本地 evidence/mapping 为准。
- 所有数据源必须 provider 化，不能把 Tushare/AKShare 调用写死在业务逻辑里。
- 前端不直接调用外部数据源。
- 所有同步结果落到本地 parquet/csv/cache。
- 没有 token 或外部源不可用时，系统必须降级，不影响页面打开。
- 不允许输出投资建议。

请先审计现有 IndustryChainRadar 第一版代码，再实现第二版。

后端新增模块：

backend/data_providers/
  __init__.py
  base.py
  manual_provider.py
  tushare_provider.py
  akshare_provider.py

backend/data_sync/
  __init__.py
  sync_industry_data.py
  normalizer.py

backend/industry_chain/
  stock_enricher.py
  node_metrics_service.py
  evidence_service.py

tools/
  sync_industry_data.py

如果项目没有 backend 目录，请按现有项目结构放置，不要强行重构。

一、Provider 抽象

base.py 定义统一接口：

class BaseMarketDataProvider:
    name: str

    def get_concept_members(self, concept_name: str | None = None) -> DataFrame:
        pass
    
    def get_market_snapshot(self, trade_date: str | None = None) -> DataFrame:
        pass
    
    def get_stock_profile(self, symbols: list[str]) -> DataFrame:
        pass
    
    def get_news_titles(self, start_date: str | None = None, end_date: str | None = None) -> DataFrame:
        pass

第一版允许部分方法返回空 DataFrame。

二、ManualProvider

从本地 CSV 读取数据。

新增目录：
knowledge/data_sources/

文件：
knowledge/data_sources/manual_concept_members.csv
knowledge/data_sources/company_evidence.csv

manual_concept_members.csv 字段：

- source
- source_concept_name
- chain_id
- node_id
- symbol
- stock_name
- updated_at
- notes

company_evidence.csv 字段：

- chain_id
- node_id
- symbol
- stock_name
- evidence_type
- evidence_text
- evidence_source
- confidence
- updated_at
- is_verified

三、TushareProvider

实现可选 Tushare provider。

要求：

- 从环境变量读取 TUSHARE_TOKEN。
- 如果没有 token，不报错，返回空 DataFrame，并记录 warning。
- 不要在业务逻辑里硬编码 token。
- 先只实现 get_concept_members 的框架。
- 如果可以识别同花顺概念成分接口，则支持 ths_member。
- 注意 Tushare 接口可能需要积分，不要假设用户一定可用。
- 返回字段要归一化为统一 schema：
  source
  source_concept_code
  source_concept_name
  symbol
  stock_name
  in_date
  out_date
  is_new
  updated_at

四、AkshareProvider

实现可选 AKShare provider。

要求：

- 如果没有安装 akshare，不报错，返回空 DataFrame，并提示安装。
- 不要让系统启动依赖 akshare。
- 先实现 get_market_snapshot 的框架。
- 如果能安全调用东方财富 A 股实时行情或板块行情接口，则返回统一 schema。
- 所有字段必须经过 normalizer.py 归一化。
- AKShare 接口失败时要降级，不影响主程序。

五、Normalizer

新增 normalizer.py，统一股票代码格式：

输入可能是：
000001
000001.SZ
SZ000001
sh600000
600000.SH

统一输出：
symbol: 000001.SZ / 600000.SH
exchange: SZ / SH
raw_symbol: 原始代码

同时统一字段：
pct_chg
amount
close
stock_name
trade_date

六、本地落库

同步结果保存到：

data/industry/
  concept_members.parquet
  company_evidence.parquet
  stock_market_snapshot.parquet
  node_market_metrics.parquet

如果项目已有 parquet_data 或 data 目录，请优先复用现有结构。

七、StockEnricher

新增 stock_enricher.py。

功能：
合并以下数据：

1. concept_stock_mapping.csv
2. manual_concept_members.csv
3. Tushare/AKShare concept_members
4. company_evidence.csv
5. stock_market_snapshot

输出给前端的 stock rows：

- symbol
- stock_name
- chain_id
- node_id
- source
- source_concept_name
- is_verified
- is_candidate
- relevance_score
- purity_score
- evidence_score
- market_confirm_score
- final_score
- evidence_type
- evidence_text
- evidence_source
- pct_chg
- return_5d
- amount
- amount_change_ratio
- limit_status
- pattern_signal

规则：

- 本地 concept_stock_mapping 和 company_evidence 标记为 verified。
- Tushare/AKShare/东方财富来源标记为 candidate。
- candidate 不得显示为“正宗”，只能显示为“外部候选”。
- final_score 对 candidate 默认较低，除非有 evidence。
- 如果没有行情数据，行情字段显示 null。

八、NodeMetricsService

新增 node_metrics_service.py。

按 chain_id + node_id + trade_date 聚合：

- stock_count
- verified_stock_count
- candidate_stock_count
- avg_return_1d
- avg_return_5d
- limit_up_count
- strong_stock_count
- total_amount
- amount_change_ratio
- hot_score
- market_strength

hot_score 简化公式：
hot_score =
  avg_return_score * 0.30

+ limit_up_score * 0.25
+ amount_score * 0.20
+ verified_stock_score * 0.15
+ pattern_score * 0.10

如果缺字段，自动降级。

market_strength：

- hot_score >= 80: 很强
- 60-80: 强
- 40-60: 中
- 20-40: 弱
- <20: 很弱

九、API 增强

增强现有 API：

GET /api/industry-chain/graph

nodes 中新增：

- hot_score
- market_strength
- stock_count
- verified_stock_count
- candidate_stock_count
- avg_return_1d
- avg_return_5d
- limit_up_count
- total_amount

GET /api/industry-chain/node/{node_id}

返回：

- verified_stocks
- candidate_stocks
- evidence_summary
- market_metrics

GET /api/industry-chain/node/{node_id}/stocks

支持参数：

- include_candidates=true/false
- verified_only=true/false
- sort_by=final_score/hot_score/pct_chg/amount

新增 API：

GET /api/industry-chain/data-sources/status

返回：

- manual provider 是否可用
- tushare token 是否存在
- akshare 是否安装
- 最近同步时间
- 本地 parquet 是否存在

POST /api/industry-chain/sync

触发一次同步。
如果项目不适合前端触发同步，可以先只提供工具脚本，不开放 POST。

十、同步脚本

新增：
tools/sync_industry_data.py

支持：
python tools/sync_industry_data.py --chain optical_communication --date 2026-05-16
python tools/sync_industry_data.py --all --date 2026-05-16

执行：

1. 加载 industry_chains yaml；
2. 加载 manual provider；
3. 可选加载 Tushare；
4. 可选加载 AKShare；
5. 归一化 symbol；
6. 保存 concept_members.parquet；
7. 保存 company_evidence.parquet；
8. 保存 stock_market_snapshot.parquet；
9. 计算 node_market_metrics.parquet；
10. 输出同步摘要。

十一、前端增强

IndustryChainRadar 页面增加：

1. 数据源状态卡片：
- 本地证据

- 外部候选

- 行情更新时间

- Tushare 状态

- AKShare 状态
2. 节点 tooltip 增加：
- 热度分数

- 已验证个股数

- 外部候选个股数

- 今日平均涨幅

- 涨停数

- 市场强度
3. 个股表增加：
- 来源

- 是否验证

- 候选/已验证标签

- 证据类型

- 数据更新时间
4. 过滤：
- 只看已验证

- 显示外部候选

- 按热度排序

- 按今日涨幅排序

- 按正宗性排序
5. 空状态：
   如果没有数据，明确提示：
   “当前仅有产业链结构，暂无本地公司证据。请维护 company_evidence.csv 或运行 sync_industry_data.py 获取外部候选。”

十二、验收标准

1. 没有 Tushare token 时，系统不报错。
2. 没有安装 AKShare 时，系统不报错。
3. 只有手工 CSV 时，页面能展示已验证数据。
4. 有外部数据时，页面能展示 candidate，但不能把 candidate 当成 verified。
5. 节点能显示 hot_score 和 market_strength。
6. 个股表能区分“已验证”和“外部候选”。
7. 后端启动正常。
8. 前端构建通过。
9. 输出修改文件清单、API 列表、同步命令、已知限制。
