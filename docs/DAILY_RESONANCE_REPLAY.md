# 每日共振复盘模块 (Daily Resonance Replay)

## 📖 概述

每日共振复盘模块是一个自动化的市场分析工具，通过分析涨停股票的概念标签分布，识别市场"主线"（热点概念），并结合机构资金流向，生成每日复盘报告。

### 核心理念

**概念共振 (Concept Resonance)**: 当多只涨停股票共享同一个概念标签时，该概念就代表了市场的"主线"。例如，如果今天50只涨停股中有20只带"华为"标签，那么"华为"就是当日主线。

## 🎯 功能特性

- ✅ **自动数据获取**: 从 Tushare 获取涨停数据和机构资金流向
- ✅ **概念知识库**: 本地维护股票-概念映射关系
- ✅ **共振算法**: 智能识别市场主线概念
- ✅ **强度评分**: 计算封单强度 (封单额/流通市值)
- ✅ **机构追踪**: 标记机构参与的涨停股
- ✅ **历史存储**: 数据存储在 LanceDB，支持高效查询

## 📊 数据流程

```
1. 获取原始数据 (Tushare)
   ├─ limit_list_d: 涨停股票列表
   └─ top_inst: 机构资金流向

2. 关联概念库 (LanceDB)
   └─ stock_concepts: 股票-概念映射

3. 计算共振强度
   ├─ 统计概念频率
   ├─ 筛选主线 (出现>3次 且 占比>5%)
   └─ 排序主线

4. 生成复盘报告
   ├─ 为每只股票分配主线归属
   ├─ 注入机构资金数据
   ├─ 计算强度得分
   └─ 写入 daily_limit_history 表
```

## 🚀 快速开始

### 1. 环境准备

确保已安装依赖：
```bash
pip install tushare lancedb pandas polars tqdm
```

### 2. 配置 Tushare Token

在 `config/config.py` 中设置：
```python
TUSHARE_TOKEN = "你的Tushare_Token"
```

### 3. 初始化概念库（首次运行）

```bash
# 方法1: 使用测试脚本（推荐）
python test_resonance_replay.py --init-concepts --concept-limit 50

# 方法2: 直接运行概念加载器
python data_svc/concept_data_loader.py --limit 50
```

**注意**: `--limit 50` 表示只加载前50个概念（用于测试）。正式使用时去掉 `--limit` 参数以加载全部概念。

### 4. 运行复盘分析

```bash
# 分析指定日期
python test_resonance_replay.py --date 20241231

# 或者使用模块直接调用
python data_svc/daily_resonance_replay.py 20241231
```

## 💻 使用示例

### 示例 1: 基本使用

```python
from data_svc.daily_resonance_replay import DailyResonanceReplay

# 创建分析器
analyzer = DailyResonanceReplay()

# 运行复盘
result = analyzer.run_daily_replay('20241231')

if result['success']:
    print(f"主线概念: {result['stats']['main_themes']}")
    print(f"涨停总数: {result['stats']['total_limits']}")
```

### 示例 2: 查询历史数据

```python
from data_svc.lance_manager import LanceDBManager

# 打开历史表
mgr = LanceDBManager(table_name="daily_limit_history")

# 查询指定日期
df = mgr.load_to_polars(
    start_date='20241231',
    end_date='20241231'
).to_pandas()

# 筛选主线股票
df_main = df[df['concept_resonance'] != '杂毛/独立逻辑']
print(df_main[['stock_name', 'concept_resonance', 'strength_score']])
```

### 示例 3: 批量复盘

```python
from data_svc.daily_resonance_replay import DailyResonanceReplay

analyzer = DailyResonanceReplay()

# 分析一周的数据
dates = ['20241227', '20241230', '20241231']
for date in dates:
    result = analyzer.run_daily_replay(date)
    if result['success']:
        print(f"{date}: {result['stats']['main_themes'][:3]}")
```

更多示例请参考 `examples/daily_resonance_example.py`

## 📁 数据库表结构

### stock_concepts (概念知识库)

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | str | Tushare 代码 (如 "000001.SZ") |
| stock_code | str | 标准代码 (如 "000001") |
| stock_name | str | 股票名称 |
| concepts | str | 概念标签 (逗号分隔) |
| update_date | str | 更新日期 (YYYYMMDD) |

### daily_limit_history (复盘历史)

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | str | 股票代码 |
| stock_name | str | 股票名称 |
| trade_date | str | 交易日期 |
| limit_times | int | 连板数 |
| first_limit_time | str | 首次涨停时间 |
| last_limit_time | str | 最后涨停时间 |
| limit_amount | float | 封单金额 (万元) |
| circ_mv | float | 流通市值 (万元) |
| **concept_tags** | str | 所有概念标签 |
| **concept_resonance** | str | 主线归属 |
| **resonance_rank** | int | 主线排名 (1=最强) |
| **inst_net_buy** | float | 机构净买入 (万元) |
| **strength_score** | float | 强度得分 (封单额/流通市值) |

## 🔧 高级配置

### 调整共振算法参数

在 `daily_resonance_replay.py` 的 `calculate_resonance()` 方法中：

```python
# 当前默认值
threshold_count = 3      # 最小出现次数
threshold_ratio = 0.05   # 最小占比 (5%)

# 可根据市场情况调整，例如：
# - 牛市/活跃市场: threshold_count = 5, threshold_ratio = 0.08
# - 熊市/冷清市场: threshold_count = 2, threshold_ratio = 0.03
```

### 更新概念库频率

建议：
- **每月更新一次**: 捕捉新概念和新股
- **重大事件后更新**: 如政策发布、新板块上市

```bash
# 强制重建概念库
python data_svc/concept_data_loader.py --rebuild
```

## 📈 性能优化

- **批量查询**: 使用 LanceDB 批量查询概念，避免逐个查询
- **缓存机制**: 概念数据在单次运行中缓存在内存
- **频控管理**: 自动遵守 Tushare 500次/分钟限制
- **增量更新**: 支持断点续传，避免重复拉取数据

## ⚠️ 注意事项

1. **Tushare 权限**: 需要 `limit_list_d` 和 `top_inst` 接口权限
2. **数据延迟**: Tushare 数据通常在收盘后1-2小时更新
3. **休市日期**: 非交易日会返回错误，属于正常现象
4. **概念变化**: 股票的概念标签可能随时间变化，建议定期更新

## 🐛 故障排查

### 问题 1: "未找到 Tushare Token"

**解决**: 在 `config/config.py` 中设置 `TUSHARE_TOKEN`

### 问题 2: "表 stock_concepts 不存在"

**解决**: 运行概念库初始化
```bash
python test_resonance_replay.py --init-concepts
```

### 问题 3: "今日无涨停数据"

**原因**: 
- 可能是休市日
- 或者 Tushare 数据未更新

**解决**: 使用历史交易日测试，如 `20241231`

### 问题 4: API 频率限制

**解决**: 
- 检查是否有其他程序在调用 Tushare API
- 增加 `time.sleep()` 延迟
- 使用更高级别的 Tushare 账户

## 📚 相关文档

- [Tushare 官方文档](https://tushare.pro/document/2)
- [LanceDB 文档](https://lancedb.github.io/lancedb/)
- [项目架构文档](../docs/ARCHITECTURE_MONITORING.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本模块遵循项目主许可证。
