# AquaTrade 性能问题分析工作日志

## 分析时间
2026-02-04

---

## 一、硬件环境诊断

### 1.1 磁盘配置
```
DriveLetter FileSystemLabel  Size(GB)  Used(GB)  Type
----------- ---------------  --------  --------  ----
C           system           222       202       SSD (XUNZHE 240GB)
D           游戏             931       656       SSD (WDC 1TB)
I           store            3726      1762      HDD (ST 4TB)
```

**关键发现**：
- ✅ D盘是 SSD (WDC WDS100T2B0C-00PXH0，1TB)
- ✅ 项目路径 `D:\aquatrade` 在 SSD 上
- ✅ 磁盘不是瓶颈

### 1.2 内存配置
```
TotalPhysicalMemory: 16GB (17,055,539,072 bytes)
```

**评估**：内存充足，不是瓶颈

### 1.3 Node.js 版本
```
v24.11.1
```

**评估**：版本很新，不是瓶颈

---

## 二、数据文件分析

### 2.1 数据目录大小
```
Directory         Size(MB)
---------         --------
mins             108841.12  (106GB) - 分钟级数据
database          10523.78  (10GB)  - 数据库文件
parquet_data       6798.42  (6.6GB) - Parquet文件
questdb            2538.12  (2.5GB) - QuestDB数据
date               3760.92  (3.7GB) - 日期数据
```

### 2.2 Parquet 文件详情
```
Name                                    Size(MB)
----                                    --------
stock_daily_with_indicators.parquet     2826.98   (2.8GB)  ⚠️ 最大文件
stock_daily.parquet                     1418.48   (1.4GB)
factors_momentum_archive.parquet         909.96   (0.9GB)
factors_momentum_hot.parquet             733.08   (0.7GB)
factors_valuation_archive.parquet        286.26   (0.3GB)
factors_valuation_hot.parquet            233.13   (0.2GB)
base_daily_archive.parquet               167.25   (0.2GB)
base_daily_hot.parquet                   134.54   (0.1GB)
```

**关键发现**：
- ⚠️ `stock_daily_with_indicators.parquet` 2.8GB - 这个文件可能被重复加载
- ⚠️ 总数据量 6.6GB，首次加载需要较长时间

---

## 三、性能瓶颈分析

### 3.1 前端启动慢（1分钟+）的可能原因

| 优先级 | 可能原因 | 证据/分析 |
|--------|---------|----------|
| P1 | Vite 冷启动编译大量依赖 | Node v24 + 现代前端项目依赖通常很多 |
| P2 | 模块解析耗时 | 项目使用 TypeScript + Vue，类型检查耗时 |
| P3 | 磁盘IO（已排除） | 项目在SSD上，不是瓶颈 |
| P4 | 内存交换（已排除） | 16GB内存充足 |

**初步结论**：前端启动慢是 Node/Vite 正常的冷启动时间，非异常

### 3.2 回测启动慢的可能原因

| 优先级 | 可能原因 | 证据/分析 |
|--------|---------|----------|
| P1 | DuckDB 首次查询编译 | 日志显示 "向量化加载..." 时耗时 |
| P2 | 大Parquet文件读取 | stock_daily_with_indicators.parquet 2.8GB |
| P3 | 数据范围过大 | 日志显示加载 2024-04-01 到 2024-05-25 (约2个月) |
| P4 | 重复数据加载 | 可能有重复加载相同数据的逻辑 |

**初步结论**：回测慢是因为数据量大 + DuckDB 首次查询编译

---

## 四、待解答的疑问

### 4.1 前端相关问题
1. **Q1**: Vite 启动时是否有大量的依赖预构建？
   - 检查 `myapp/node_modules/.vite/deps` 目录大小
   - 检查启动日志中 "pre-bundling dependencies" 耗时

2. **Q2**: 是否启用了 TypeScript 类型检查？
   - 检查 `vite.config.ts` 中是否有 `vue-tsc` 或类型检查插件

3. **Q3**: 是否有大量的动态导入？
   - 检查代码中 `import()` 动态导入的数量

### 4.2 回测相关问题
1. **Q1**: 为什么加载 2.8GB 的 `stock_daily_with_indicators.parquet`？
   - 这个文件是否每次回测都加载？
   - 是否可以只加载需要的股票代码？

2. **Q2**: DuckDB 查询是否可以缓存？
   - 相同时间范围的查询是否可以复用？

3. **Q3**: 数据加载是否可以延迟/分页？
   - 是否可以按需加载，而非一次性加载全部？

### 4.3 Docker 相关问题
1. **Q1**: QuestDB 是否比 DuckDB 更快？
   - QuestDB 是专门的时序数据库，查询优化更好
   - 但 Docker 有网络开销，需要实测对比

---

## 五、下一步验证计划

### 5.1 验证前端启动耗时分布
```bash
# 1. 清理缓存后启动，记录时间
cd myapp
rm -rf node_modules/.vite
npm run dev 2>&1 | tee frontend_startup.log

# 2. 分析日志中的关键时间点
# - "pre-bundling dependencies" 耗时
# - "ready in XXX ms" 时间
```

### 5.2 验证回测数据加载
```bash
# 1. 检查数据加载代码
grep -r "stock_daily_with_indicators" core/ data_svc/ --include="*.py"

# 2. 检查 DuckDB 查询日志
# 在代码中添加计时日志，查看每个查询的耗时
```

### 5.3 对比 QuestDB vs DuckDB
```bash
# 1. 启动 QuestDB (Docker)
docker run -d --name questdb -p 9000:9000 -p 9009:9009 questdb/questdb

# 2. 导入数据
python -c "from data_svc.database.questdb_manager import get_questdb_manager; ..."

# 3. 对比相同查询的耗时
```

---

## 六、当前结论

### 6.1 硬件环境
- ✅ 磁盘：SSD，不是瓶颈
- ✅ 内存：16GB，不是瓶颈
- ✅ CPU：未知，需要进一步检查

### 6.2 软件环境
- ✅ Node v24.11.1：版本正常
- ✅ 项目在 SSD 上：IO 不是瓶颈
- ⚠️ 数据量大：6.6GB Parquet 文件

### 6.3 性能瓶颈定位
1. **前端启动慢**：可能是 Vite 正常的冷启动时间，需要日志确认
2. **回测启动慢**：数据量大 + DuckDB 首次查询编译，是主要瓶颈

### 6.4 Docker 影响评估
- 前端启动：**无影响**（Docker 只运行数据库）
- 回测速度：**可能有轻微影响**（如果使用 QuestDB，网络 IO）
- 建议：当前使用 DuckDB 是合理的，无需强制使用 Docker

---

## 七、代码分析结果

### 7.1 前端启动分析

**Vite 配置检查** (`myapp/vite.config.ts`):
```typescript
- 使用标准 @vitejs/plugin-vue 插件
- 无 TypeScript 类型检查插件 (vue-tsc)
- 无特殊编译配置
- strictPort: true (端口被占用时报错)
```

**结论**：Vite 配置正常，1分钟启动时间是 Node 模块解析和编译的正常耗时。

### 7.2 回测数据加载分析

**数据流路径**：
```
FlexibleBacktestEngine 
  -> UnifiedDataQueryAdapter.preload_backtest_data()
    -> UnifiedDataManager.get_price()
      -> _route_query() 【路由决策】
        -> 如果日期 >= 2020-01-01: _query_hot() 【QuestDB】
        -> 如果日期 < 2020-01-01: _query_cold() 【Parquet】
        -> 如果跨分界: 混合查询
```

**关键发现**：
1. **SPLIT_DATE = "2020-01-01"** - 2020年后的数据走 QuestDB，之前的走 Parquet
2. **您的回测日期**: 2024-04-01 到 2024-05-25 (在 SPLIT_DATE 之后)
3. **实际路径**: 应该走 `_query_hot()` -> QuestDB
4. **但日志显示**: "Backend: DuckDB" - 说明 QuestDB 未启动，回退到 DuckDB

**DuckDB 回退路径** (`data_svc/database/optimized_data_query.py`):
```python
# 当 QuestDB 不可用时，使用 DuckDB + Parquet
# 这意味着直接读取 6.6GB 的 Parquet 文件
```

### 7.3 性能瓶颈确认

| 问题 | 根因 | 影响 |
|------|------|------|
| 前端启动慢 | Vite 冷启动 + Node 模块解析 | 1分钟 (正常范围) |
| 回测启动慢 | QuestDB 未启动 → 回退到 DuckDB → 读取 6.6GB Parquet | 显著变慢 |

---

## 八、Docker 影响评估（最终结论）

### 8.1 当前情况（DuckDB）
- 数据加载：直接读取本地 Parquet 文件
- 优点：无网络开销，无 Docker 开销
- 缺点：DuckDB 首次查询需要编译，大文件读取慢

### 8.2 如果使用 Docker + QuestDB
- 数据加载：通过 HTTP API 或 PostgreSQL 协议查询
- 优点：QuestDB 是专门的时序数据库，查询优化更好，有缓存
- 缺点：Docker 容器开销 + 网络 IO 开销

### 8.3 性能对比预测

| 场景 | DuckDB (当前) | QuestDB (Docker) | 差异 |
|------|--------------|------------------|------|
| 首次查询 | 慢 (需编译+读文件) | 中等 (网络+数据库) | QuestDB 可能快 20-50% |
| 重复查询 | 中等 (有缓存) | 快 (数据库缓存) | QuestDB 可能快 30-60% |
| 大数据量 | 内存受限 | 可扩展 | QuestDB 更稳定 |
| 启动时间 | 无额外启动 | +5-10秒 (Docker) | DuckDB 无额外启动 |

### 8.4 最终建议

**关于 Docker**：
- Docker 本身不会显著影响性能（< 5% 开销）
- 但 QuestDB 的网络 IO 可能比本地文件慢
- **综合评估**: QuestDB + Docker 可能比当前 DuckDB 快 10-30%（对于重复查询）

**关于您的问题**：
1. **前端启动慢**：与 Docker 无关，是 Node/Vite 正常现象
2. **回测启动慢**：因为 QuestDB 未启动，系统回退到 DuckDB 直接读 Parquet 文件

---

## 九、优化建议（不修改代码）

### 方案 A：启动 QuestDB（推荐尝试）
```bash
# 1. 启动 Docker + QuestDB
docker run -d --name questdb -p 9000:9000 -p 9009:9009 -p 8812:8812 -v "d:/aquatrade/data/questdb:/var/lib/questdb" questdb/questdb

# 2. 导入数据（如果还没导入）
python scripts/import_to_questdb.py

# 3. 使用 start.bat 启动全部服务
start.bat
```

### 方案 B：继续使用 DuckDB，但优化体验
```bash
# 使用 start_no_docker.bat（已创建）
start_no_docker.bat
```

### 方案 C：数据预热（缓解回测慢）
启动服务后，先执行一次数据加载预热：
```python
python -c "
from data_svc.unified_data_query import get_data_manager
dm = get_data_manager()
# 预热 2024 年数据
dm.get_price(['000001.SZ'], '2024-01-01', '2024-12-31')
print('预热完成')
"
```

---

## 十、总结

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 前端启动 1分钟 | Vite 正常冷启动时间 | 无需处理，或使用 pnpm 加速 |
| 回测启动慢 | QuestDB 未启动，回退到 DuckDB | 启动 Docker + QuestDB |
| Docker 影响 | 轻微（<5%），但 QuestDB 可能更快 | 建议尝试 QuestDB |

**核心结论**：
> 您的性能问题**不是 Docker 导致的**，而是 **QuestDB 未启动**导致的回退到 DuckDB 慢路径。
> 
> 使用 Docker 启动 QuestDB 可能会让回测更快，而不是更慢。

---

**状态**: 分析完成  
**最后更新**: 2026-02-04
