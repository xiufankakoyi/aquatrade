# 按模块重构计划

## 📊 代码质量分析结果

### 主要问题

1. **文件过大** (>1000行): 8个文件
2. **函数过多** (>30个): 2个文件  
3. **嵌套过深** (>5层): 12个文件
4. **重复模式**: 多处发现

---

## 🎯 重构优先级

### 优先级 1: Server 模块（最紧急）

#### 1.1 `server/app.py` (2466行, 53个函数, 嵌套深度15)

**问题**:
- 文件过大，包含所有路由和Socket.IO处理
- 函数过多，职责不清
- 嵌套过深，可读性差
- 4个重复模式

**重构方案**:
```
server/
├── app.py (精简，只保留Flask应用初始化)
├── routes/
│   ├── __init__.py
│   ├── strategy_routes.py (策略相关路由)
│   ├── backtest_routes.py (回测相关路由)
│   ├── data_routes.py (数据查询路由)
│   ├── sentiment_routes.py (已存在)
│   └── scatter_routes.py (散点图路由)
├── socketio_handlers/
│   ├── __init__.py
│   ├── backtest_handlers.py (回测Socket.IO事件)
│   └── optimization_handlers.py (优化Socket.IO事件)
└── utils/
    ├── __init__.py
    ├── api_helpers.py (API辅助函数)
    └── error_handlers.py (错误处理)
```

**拆分步骤**:
1. 提取所有 `@app.route` 到对应的路由文件
2. 提取 Socket.IO 事件处理器
3. 提取公共辅助函数
4. 简化 `app.py` 只保留应用初始化

#### 1.2 `server/visualization_api.py` (2081行, 嵌套深度10)

**问题**:
- 文件过大，包含所有API逻辑
- 嵌套过深

**重构方案**:
```
server/
├── visualization_api.py (主类，精简)
├── api/
│   ├── __init__.py
│   ├── strategy_api.py (策略相关API)
│   ├── backtest_api.py (回测相关API)
│   ├── data_api.py (数据查询API)
│   ├── sentiment_api.py (情感分析API)
│   └── scatter_api.py (散点图API)
└── services/
    ├── __init__.py
    ├── qfq_calculator.py (前复权计算)
    ├── data_loader.py (数据加载)
    └── result_processor.py (结果处理)
```

**拆分步骤**:
1. 提取前复权计算逻辑到 `services/qfq_calculator.py`
2. 按功能拆分API方法到对应的 `api/*.py`
3. 提取数据加载和处理逻辑到 `services/`
4. 保留主类作为门面（Facade）

---

### 优先级 2: Core 模块

#### 2.1 `core/backtest/optimized_backtest_engine.py` (1472行)

**问题**:
- 文件过大
- 包含数据加载、指标计算、回测执行等多个职责

**重构方案**:
```
core/backtest/
├── optimized_backtest_engine.py (主引擎，精简)
├── data_loader.py (数据加载)
├── indicator_calculator.py (指标计算，已存在但需整合)
├── backtest_executor.py (回测执行)
└── result_aggregator.py (结果聚合)
```

#### 2.2 `core/backtest/optimization_engine.py` (1375行)

**问题**:
- 文件过大
- 嵌套过深

**重构方案**:
```
core/backtest/
├── optimization_engine.py (主引擎)
├── optimizers/
│   ├── __init__.py
│   ├── ga_optimizer.py (遗传算法优化器)
│   └── bayesian_optimizer.py (贝叶斯优化器)
└── fitness_calculator.py (适应度计算)
```

#### 2.3 `core/strategies/strategy_factory.py` (6个重复模式)

**问题**:
- 重复代码模式多

**重构方案**:
- 提取公共的注册逻辑
- 使用装饰器模式简化策略注册
- 统一策略接口

---

### 优先级 3: Data Service 模块

#### 3.1 `data_svc/spider/1.py` (1470行, 嵌套深度10)

**问题**:
- 文件过大
- 嵌套过深
- 文件名不规范

**重构方案**:
- 重命名文件（根据实际功能）
- 拆分为多个模块
- 降低嵌套深度

#### 3.2 `data_svc/spider/app.py` (1368行, 33个函数, 嵌套深度13)

**问题**:
- 文件过大
- 函数过多
- 嵌套过深
- 4个重复模式

**重构方案**:
- 检查是否还在使用（可能是旧的Flask应用）
- 如果不再使用，删除或移动到 `examples/`
- 如果仍在使用，按 `server/app.py` 的方式重构

---

## 📝 重构步骤

### 阶段 1: Server 模块重构（第1周）

1. **Day 1-2: 拆分 `server/app.py`**
   - [ ] 创建路由目录结构
   - [ ] 提取策略路由
   - [ ] 提取回测路由
   - [ ] 提取数据路由
   - [ ] 提取散点图路由

2. **Day 3-4: 拆分 Socket.IO 处理器**
   - [ ] 创建 `socketio_handlers/` 目录
   - [ ] 提取回测事件处理器
   - [ ] 提取优化事件处理器

3. **Day 5: 拆分 `server/visualization_api.py`**
   - [ ] 提取前复权计算服务
   - [ ] 按功能拆分API方法
   - [ ] 提取数据加载服务

### 阶段 2: Core 模块重构（第2周）

1. **Day 1-2: 重构回测引擎**
   - [ ] 拆分数据加载逻辑
   - [ ] 拆分指标计算逻辑
   - [ ] 拆分回测执行逻辑

2. **Day 3-4: 重构优化引擎**
   - [ ] 拆分优化器
   - [ ] 提取适应度计算

3. **Day 5: 优化策略工厂**
   - [ ] 消除重复代码
   - [ ] 使用装饰器模式

### 阶段 3: Data Service 模块重构（第3周）

1. **Day 1-2: 清理 Spider 模块**
   - [ ] 检查 `spider/app.py` 是否还在使用
   - [ ] 重命名和拆分 `spider/1.py`
   - [ ] 降低嵌套深度

2. **Day 3-5: 优化数据库模块**
   - [ ] 检查冗余文件
   - [ ] 统一接口
   - [ ] 优化查询逻辑

---

## 🔧 重构原则

1. **单一职责原则**: 每个文件/类只负责一个功能
2. **文件大小限制**: 单个文件不超过 500 行
3. **函数大小限制**: 单个函数不超过 50 行
4. **嵌套深度限制**: 不超过 4 层
5. **消除重复**: 提取公共逻辑到工具函数
6. **保持向后兼容**: 重构过程中保持API接口不变

---

## ✅ 验收标准

1. **代码行数**: 单个文件不超过 500 行
2. **函数数量**: 单个文件不超过 20 个函数
3. **嵌套深度**: 不超过 4 层
4. **重复模式**: 消除所有重复代码
5. **测试通过**: 所有功能测试通过
6. **性能不降**: 重构后性能不下降

---

## 📊 预期效果

- **代码可读性**: 提升 50%+
- **维护成本**: 降低 40%+
- **开发效率**: 提升 30%+
- **Bug 率**: 降低 20%+

---

## 🚀 开始重构

建议从 **优先级 1** 开始，先重构 `server/app.py`，因为它是项目的入口，影响最大。

