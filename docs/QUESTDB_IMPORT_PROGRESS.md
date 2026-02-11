# QuestDB 导入进度查看指南

## 📊 在 Web UI 中查看进度

### 方法 1: 实时查看数据量（最简单）

在 QuestDB Web UI (http://localhost:9000) 的 SQL 编辑器中运行：

```sql
-- 查看各表当前数据量
SELECT 'base_daily' as table_name, COUNT(*) as row_count FROM base_daily
UNION ALL
SELECT 'factors_momentum', COUNT(*) FROM factors_momentum
UNION ALL
SELECT 'factors_valuation', COUNT(*) FROM factors_valuation;
```

**预期结果**（导入完成后）：
- `base_daily`: 6,841,370 行
- `factors_momentum`: 6,841,370 行  
- `factors_valuation`: 6,841,370 行

---

### 方法 2: 查看最新插入的数据

```sql
-- 查看 base_daily 最新 10 条记录
SELECT * FROM base_daily 
ORDER BY ts DESC 
LIMIT 10;
```

如果能看到数据，说明导入正在进行中！

---

### 方法 3: 按日期范围统计

```sql
-- 查看已导入的日期范围和数量
SELECT 
    MIN(ts) as earliest_date,
    MAX(ts) as latest_date,
    COUNT(*) as total_rows,
    COUNT(DISTINCT code) as stock_count
FROM base_daily;
```

---

### 方法 4: 每分钟刷新一次

在 Web UI 中：
1. 点击右上角的 "⚙️ Configure" 按钮
2. 选择 "Run every" -> "1 minute"
3. 查询会自动刷新，显示最新数据量

---

## 🔍 命令行查看进度

如果不想用 Web UI，也可以在命令行中查看：

```python
python -c "import psycopg2; conn = psycopg2.connect(host='localhost', port=8812, user='admin', password='quest', database='qdb'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM base_daily'); print(f'base_daily: {cursor.fetchone()[0]:,} 行'); conn.close()"
```

---

## ⏱️ 预计完成时间

- **当前已运行**: 27 分钟
- **预计总时长**: 30-45 分钟（取决于系统性能）
- **完成标志**: 当 3 张表的行数都达到 6,841,370 时表示完成

---

## 💡 如果导入很慢怎么办？

### 方案 A: 继续等待（推荐）
- PostgreSQL 批量导入虽慢但稳定
- 适合一次性导入大量历史数据

### 方案 B: 手动导入（快速）
1. 在 Web UI 右上角点击 "Import" 按钮
2. 选择 "Parquet" 格式
3. 拖拽文件：
   - `d:\aquatrade\data\parquet_data\base_daily_hot.parquet`
   - `d:\aquatrade\data\parquet_data\factors_momentum_hot.parquet`
   - `d:\aquatrade\data\parquet_data\factors_valuation_hot.parquet`
4. 点击 "Upload" - 通常 1-2 分钟完成！

---

## ✅ 验证导入成功

导入完成后，运行这个查询确认数据完整性：

```sql
SELECT 
    'base_daily' as table_name,
    COUNT(*) as total_rows,
    MIN(ts) as start_date,
    MAX(ts) as end_date,
    COUNT(DISTINCT code) as stock_count
FROM base_daily

UNION ALL

SELECT 
    'factors_momentum',
    COUNT(*),
    MIN(ts),
    MAX(ts),
    COUNT(DISTINCT code)
FROM factors_momentum

UNION ALL

SELECT 
    'factors_valuation',
    COUNT(*),
    MIN(ts),
    MAX(ts),
    COUNT(DISTINCT code)
FROM factors_valuation;
```

预期结果应该显示：
- 总行数：~684万
- 日期范围：2020-01-01 到最新
- 股票数量：4000+ 只
