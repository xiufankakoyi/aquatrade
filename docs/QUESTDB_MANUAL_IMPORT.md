# QuestDB Web UI 手动导入指南

## 🚀 快速导入步骤（1-2分钟完成）

### 前提准备
✅ QuestDB 已运行：http://localhost:9000  
✅ 3 个 Parquet 文件已准备好

---

### 📥 导入步骤

#### 步骤 1: 打开导入界面
1. 访问 http://localhost:9000
2. 点击右上角的 **"Import"** 按钮（在 "Console" 旁边）

#### 步骤 2: 导入 base_daily（基础行情）
1. 在导入页面中，点击 **"Select file"** 或直接拖拽文件
2. 选择文件：`d:\aquatrade\data\parquet_data\base_daily_hot.parquet`
3. **重要配置**：
   - **Table name**: `base_daily`
   - **Timestamp column**: `ts`（选择 trade_date 列作为时间戳）
   - **Partition by**: `MONTH`
4. 点击 **"Import"** 按钮
5. 等待进度条完成（约 30 秒）

#### 步骤 3: 导入 factors_momentum（动量因子）
1. 点击 **"Import another file"** 或返回导入页面
2. 选择文件：`d:\aquatrade\data\parquet_data\factors_momentum_hot.parquet`
3. 配置：
   - **Table name**: `factors_momentum`
   - **Timestamp column**: `ts`
   - **Partition by**: `MONTH`
4. 点击 **"Import"**
5. 等待完成（约 30 秒）

#### 步骤 4: 导入 factors_valuation（估值因子）
1. 再次点击 **"Import another file"**
2. 选择文件：`d:\aquatrade\data\parquet_data\factors_valuation_hot.parquet`
3. 配置：
   - **Table name**: `factors_valuation`
   - **Timestamp column**: `ts`
   - **Partition by**: `MONTH`
4. 点击 **"Import"**
5. 等待完成（约 30 秒）

---

### ✅ 验证导入成功

返回 **Console** 标签，运行以下查询：

```sql
SELECT 
    'base_daily' as 表名, 
    COUNT(*) as 行数,
    COUNT(DISTINCT code) as 股票数,
    MIN(ts) as 最早日期,
    MAX(ts) as 最新日期
FROM base_daily
UNION ALL
SELECT 'factors_momentum', COUNT(*), COUNT(DISTINCT code), MIN(ts), MAX(ts)
FROM factors_momentum
UNION ALL
SELECT 'factors_valuation', COUNT(*), COUNT(DISTINCT code), MIN(ts), MAX(ts)
FROM factors_valuation;
```

**预期结果**：
- 每张表约 **684 万**行
- 股票数：**4000+** 只
- 日期范围：**2020-01-01** 到最新

---

### 💡 常见问题

**Q: 导入时找不到 Timestamp 列？**  
A: 在导入界面的列映射中，手动将 `trade_date` 列设置为 `TIMESTAMP` 类型

**Q: 导入失败？**  
A: 检查：
1. 文件路径是否正确
2. 文件大小是否正常（base_daily 约 135MB）
3. QuestDB 磁盘空间是否充足

**Q: 导入后数据量不对？**  
A: 运行 `DROP TABLE table_name;` 删除表，重新导入

---

### 🎯 导入完成后

数据导入成功后，可以：
1. 运行示例查询测试性能
2. 开始适配回测引擎使用 QuestDB
3. 配置每日增量更新脚本

完成后请告知，我会帮您进行下一步配置！
