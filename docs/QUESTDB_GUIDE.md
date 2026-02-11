# QuestDB 部署与使用指南

## 🚀 快速启动

### 方式 1: Docker 部署 (推荐)

```bash
# 启动 QuestDB
docker run -d \
  --name questdb \
  -p 9000:9000 \
  -p 9009:9009 \
  -p 8812:8812 \
  -v "d:/aquatrade/data/questdb:/var/lib/questdb" \
  questdb/questdb

# 访问 Web UI
# 打开浏览器: http://localhost:9000
```

### 方式 2: Windows 可执行文件

1. 下载: https://questdb.io/get-questdb/
2. 解压后运行 `questdb.exe start`
3. 访问 http://localhost:9000

---

## 📊 数据导入

### 步骤 1: 启动 QuestDB
确保 QuestDB 服务已运行（端口 9000 可访问）

### 步骤 2: 创建表结构
```python
from data_svc.database.questdb_manager import get_questdb_manager

qdb = get_questdb_manager()
qdb.create_tables()
```

### 步骤 3: 导入热数据
```python
import polars as pl

# 导入基础行情
base_df = pl.read_parquet(r"d:\aquatrade\data\parquet_data\base_daily_hot.parquet")
qdb.insert_base_daily(base_df)

# 导入动量因子
momentum_df = pl.read_parquet(r"d:\aquatrade\data\parquet_data\factors_momentum_hot.parquet")
qdb.insert_factors_momentum(momentum_df)

# 导入估值因子
valuation_df = pl.read_parquet(r"d:\aquatrade\data\parquet_data\factors_valuation_hot.parquet")
qdb.insert_factors_valuation(valuation_df)
```

---

## 🔍 常用查询示例

### 查询单只股票历史数据
```sql
SELECT * 
FROM base_daily 
WHERE code = '000001.SZ' 
  AND ts >= '2023-01-01'
ORDER BY ts DESC
LIMIT 100;
```

### 查询所有股票最新 RSI
```sql
SELECT code, ts, rsi_14
FROM factors_momentum
WHERE ts = (SELECT MAX(ts) FROM factors_momentum)
  AND rsi_14 < 30  -- 超卖
ORDER BY rsi_14 ASC
LIMIT 20;
```

### 时间序列聚合
```sql
SELECT 
  ts, 
  code,
  AVG(close) as avg_close,
  MAX(high) as max_high,
  MIN(low) as min_low
FROM base_daily
WHERE code = '000001.SZ'
  AND ts >= '2023-01-01'
SAMPLE BY 1w  -- 按周聚合
ORDER BY ts DESC;
```

---

## 📁 当前数据架构

```
data/
├── parquet_data/
│   ├── base_daily_archive.parquet          (167 MB, < 2020)
│   ├── factors_momentum_archive.parquet    (910 MB, < 2020)
│   ├── factors_valuation_archive.parquet   (286 MB, < 2020)
│   ├── base_daily_hot.parquet             (135 MB, 2020+)
│   ├── factors_momentum_hot.parquet       (733 MB, 2020+)
│   └── factors_valuation_hot.parquet      (233 MB, 2020+)
└── questdb/                                (QuestDB 数据目录)
    └── db/
        ├── base_daily/
        ├── factors_momentum/
        └── factors_valuation/
```

---

## ⚙️ .env 配置

在项目根目录的 `.env` 文件中添加：

```bash
# QuestDB 配置
QUESTDB_HOST=localhost
QUESTDB_HTTP_PORT=9000
QUESTDB_ILP_PORT=9009
QUESTDB_PG_PORT=8812
```

---

## 🔄 每日更新流程

### 方式 1: 手动更新
```python
from data_svc.database.questdb_updater import QuestDBDailyUpdater

updater = QuestDBDailyUpdater()
updater.update_today()  # 更新今天的数据
```

### 方式 2: 定时任务
使用 Windows 任务计划程序，每天收盘后运行：
```bash
python scripts/daily_update_questdb.py
```

---

## 🛠️ 常见问题

### Q: 如何检查 QuestDB 是否运行？
```python
from data_svc.database.questdb_manager import get_questdb_manager
qdb = get_questdb_manager()
print("QuestDB 状态:", "运行中" if qdb.health_check() else "未运行")
```

### Q: 数据导入速度慢怎么办？
- 使用批量导入（默认 10 万行/批）
- 确保 QuestDB 有足够内存（建议 4GB+）
- 使用 ILP 协议（端口 9009）而非 HTTP

### Q: 如何备份数据？
QuestDB 数据存储在 `data/questdb` 目录，直接复制整个目录即可。

---

## 📚 相关文档

- [QuestDB 官方文档](https://questdb.io/docs/)
- [QuestDB Python Client](https://py-questdb-client.readthedocs.io/)
- [SQL 语法参考](https://questdb.io/docs/reference/sql/select/)

## 7. 故障排查

### 常见问题

**Q: 数据导入显示成功，但查询结果为 0 行？**
A: 可能是 WAL (Write Ahead Log) 损坏导致表被挂起。
请检查 WAL 状态：
```sql
SELECT * FROM wal_tables();
```
如果 `suspended` 为 `true`，尝试恢复：
```sql
ALTER TABLE [table_name] RESUME WAL;
```
如果恢复失败，可能需要删除表并使用 `BYPASS WAL` 模式重新创建。

**Q: 导入速度慢？**
A: 确保使用了 ILP (InfluxDB Line Protocol) 接口（端口 9009），并启用了批量提交。

**Q: 连接被重置 (Connection Reset)？**
A: 可能是批量数据过大导致缓冲区溢出。尝试减小批量大小（例如从 50000 减小到 5000）。
