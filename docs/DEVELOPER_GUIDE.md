# Aquatrade 开发者指南 (Developer Guide)

本指南旨在为开发者及 AI 助手提供 `aquatrade` 系统的深度技术架构分析，确保在修改代码或扩展功能时遵循系统的核心设计哲学，避免逻辑冲突。

---

## 1. 核心设计哲学 (Core Philosophy)

*   **性能至上 (Performance First)**: 针对量化回测的计算密集型场景，系统深度集成了 **QuestDB** (时序数据库), **Polars** (并行处理), **NumPy** (向量化) 和 **Numba** (JIT 加速)。
*   **流式架构 (Streaming Architecture)**: 回测引擎采用生成器模式，实时推送结果，支持超大规模数据集的低延迟反馈。
*   **组件化与解耦 (Decoupling)**: 数据查询、回测执行、策略定义、可视化呈现均高度模块化。

---

## 2. 系统架构 (System Architecture)

### 2.1 数据层 (Data Layer)
*   **混合存储架构 (Hybrid Storage)**:
    *   **QuestDB (Hot)**: 用于存储近期活跃数据（如 2020 年至今），支持高性能的 SQL 查询和 ILP 高速写入。
    *   **Parquet (Cold)**: 用于存储历史存档数据（如 2020 年以前），通过 Polars LazyScan 低能耗读取。
*   **统一数据入口 (`UnifiedDataManager`)**:
    *   **自动路由**: 根据查询的日期范围，自动将请求路由至 QuestDB、Parquet 或两者的合并结果。
*   **数据访问代理 (`UnifiedDataQueryAdapter`)**:
    *   兼容旧版回测引擎接口。
    *   **预加载 (Preloading)**: 通过 `preload_backtest_data` 将路由后的数据统一读入内存。
*   **标准化**: 股票代码在数据库中统一为 6 位数字符串（如 `000001`），去除了 `.SZ/.SH` 后缀。

### 2.2 回测引擎层 (Backtest Engine)
*   **`FlexibleBacktestEngine`**: 
    *   支持日线、分钟线、Tick 级回测。
    *   内置 **自动除权除息 (Dividend/Split)** 处理。
    *   采用 **流式生成器** (`run_backtest_streaming`) 返回结果。
*   **性能优化路径**:
    *   如果数据已预加载，优先走 **向量化信号生成** (`generate_signals_vectorized`)。
    *   核心匹配循环支持 `Numba` JIT 加速。

### 2.3 策略框架层 (Strategy Layer)
*   **`StrategyBase`**: 所有策略的基类。
*   **`StrategyFactory`**: 
    *   通过 `pkgutil` 自动扫描 `strategies/` 目录。
    *   支持 **延迟加载 (Lazy Loading)** 和 **热重载 (Hot Reloading)**。
    *   策略识别依赖类属性 `strategy_id` 或 `strategy_name`。

### 2.4 API 与 UI 层
*   **WebSocket (Socket.IO)**: 承载回测进度的实时推送。
*   **Vue 3 + ECharts**: 前端数据可视化。

---

## 3. 关键业务逻辑 (Key Business Logic)

### 3.1 前复权 (QFQ) 计算
系统不存储全量复权后价格，而是动态计算。
*   **公式**: `QFQ价格 = 原始价格 * (当日复权因子 / 全局最新复权因子)`。
*   **注意**: 即使是回测历史数据，计算基准也应当是系统的“最新因子”，以确保与当前市价对齐。

### 3.2 撮合机制
*   **买入**: 以当日 `Open` 价格成交（或考虑滑点）。
*   **卖出**: 以当日 `Open` 价格成交。
*   **约束**: 自动检查停牌、涨跌停状态。

---

## 4. 开发规范 (Coding Standards)

### 4.1 数据处理
*   **优先使用 Polars**: 处理大规模表格数据时，性能远超 Pandas。
*   **避免 Python 原生循环**: 在回测执行的核心路径（Core Loop）上，必须使用 `NumPy` 向量化或 `Numba`。

### 4.2 路由与命名
*   **路径**: 始终使用 `pathlib.Path` 处理路径，确保 Windows/Linux 兼容。
*   **日志**: 使用 `config.logger` 获取统一格式的日志。

### 4.3 基础设施升级组件 (新)
*   **`ResearchNote`**: 实验前必须初始化笔记，通过 `note.save_markdown()` 记录过程。
*   **`ResearchPipeline`**: 复杂任务（如参数扫描）应封装为 `WorkflowTask` 加入流。
*   **`OverfittingDetector`**: 策略交付前应通过 `monte_carlo_test` 或 `walk_forward_test`。

---

## 5. 常见坑点 (Common Pitfalls)

1.  **代码补零**: 查找 QuestDB 时通常使用 6 位代码 (如 `000001`)。冷数据 Parquet 中可能被压缩为 int (如 `1`)，`UnifiedDataManager` 已处理此转换。
2.  **JSON 序列化**: 回测结果中常含 `inf` 或 `NaN`。必须使用 `_make_json_serializable` 进行清洗。
3.  **时序对齐**: QuestDB 使用纳秒级时间戳，查询时应注意日期字符串的格式化。

---

> [!TIP]
> **性能诊断**: 如果回测变慢，请检查控制台是否输出了 `[ARCH] ⚠️ 警告: 未使用数据预加载`。

---

## 6. 项目管理与规范

### 6.1 实际项目目录结构
```text
aquatrade/
├── core/                    # 核心引擎 (回测引擎、策略基类、算力加速优化)
├── data_svc/               # 数据服务层 (UnifiedDataManager、QuestDB/Parquet 管理)
├── server/                 # 后端 API (FastAPI, Socket.IO 实时进度推送)
├── myapp/                  # 前端分析台 (Vue 3 + Vite + ECharts 交互界面)
├── tests/                  # 测试体系 (单元、集成、数据库 Schema 校验)
├── config/                 # 配置中心 (环境变量、路径映射、统一日志配置)
├── data/                   # 持久化存储 (未提交 Git，含数据库、Parquet、爬虫数据)
├── logs/                   # 日志中心 (回测明细、系统运行记录)
├── scripts/                # 运维工具 (数据迁移、环境初始化、质量分析)
├── models/                 # 模型仓库 (NLP 情绪分析、LLM 微调资产)
└── requirements.txt        # 核心生产环境依赖
```

### 6.2 开发工作流 (Current Project Standard)
- **分支策略**：建议主干开发或使用 `feature/*` 分支。
- **配置管理**：本地敏感信息放在 `.env`，参考 `.env.template` 进行配置。
- **运维指令**：使用 `start.bat` 一键启动服务。

---

## 7. 测试与验证策略

### 7.1 现有测试框架
- **工具链**：`pytest`
- **目录结构**：
    - `tests/unit/`: 核心逻辑单元测试。
    - `tests/integration/`: 模块协同及 API 功能测试。
    - `tests/schema/`: 数据库完整性验证工具（`document_db_schema.py` 自动生成文档）。
- **运行测试**：在根目录执行 `pytest tests/`。

### 7.2 回测验证规程
- **复权校验**：修改撮合逻辑后，需运行 `tests/test_price_adjustment_fix.py` 确保价格计算逻辑未退化。

### 7.3 性能分析
- 开发者可使用 `scripts/profile_backtest.py` 针对特定策略进行 CPU 性能剖析，记录耗时分布。

---

## 8. 持续集成与部署 (CI/CD)

### 8.1 生产部署
- **PM2 托管**：通过 `ecosystem.config.js` 管理应用生命周期。
- **数据库容器化**：通过 `start_questdb.bat` 调用容器或 Docker 部署时序库。

### 8.2 自动化 (Planned)
- 未来计划集成 GitHub Actions 实现自动化 Linting 和单元测试回归。

---

## 9. 错误处理与日志

### 9.1 结构化日志系统
- **配置地址**: `config/logger.py`
- **机制**: 支持控制台彩色输出与文件持久化（`logs/debug.log`）。
- **监控端点**: API 提供基础的健康检查能力，确保前端与 SocketIO 链路连通。

### 9.2 关键异异常处理
- 策略生成信号失败时，系统会捕获 Traceback 并通过 `BacktestVisualizationAPI` 返回前端，避免全应用崩溃。

---

## 10. 扩展机制

### 10.1 策略自动注册
- 任何放置在 `core/strategies/` 下且继承自 `StrategyBase` 的 Python 类，都会通过 `StrategyFactory` 在启动时自动扫描并注册，无需手动改动工厂代码。

### 10.2 数据后端插拔
- 若需支持新数据源，需在 `data_svc/` 下扩展 Manager 类，并在 `UnifiedDataManager` 中添加路由分支。

---

## 11. 开发者工具与文档

### 11.1 自动生成文档
- **数据库架构**: 实时同步于主 README.md 底部，由 `generate_schema_doc.py` 维护。

### 11.2 上手资源
- **环境搭建**: 详见 `STARTUP.md`。
- **代码示例**: `demo_infrastructure.py` 展示了新版基础设施的调用方式。

---

## 12. AI 助手协作规范

### 12.1 架构红线
- **禁止绕过路由**: AI 严禁绕过 `UnifiedDataManager` 直接拼写 SQL 访问 QuestDB。
- **流式兼容**: 修改回测逻辑必须兼容 `run_backtest_streaming` 的生成器协议。

### 12.2 代码风格
- AI 生成代码应强制包含 `typing` 注解。
- 优先复用 `config` 中的路径常量，严禁在代码中出现 `r"D:\..."` 之类的硬编码路径。

---

> [!NOTE]
> 本文档为动态更新文档，任何架构调整、工具链升级或流程变更都应同步更新至此。
> 如果你是 AI，请在修改代码前确认你已理解相关模块的设计意图和性能约束。
