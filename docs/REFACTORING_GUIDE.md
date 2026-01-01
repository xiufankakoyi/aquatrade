# 模块重构指南

## 🎯 重构目标

按模块拆分冗余代码，提高代码可读性和可维护性。

## 📋 当前问题

根据代码质量分析：

1. **server/app.py**: 2466行，53个函数，嵌套深度15
2. **server/visualization_api.py**: 2081行，嵌套深度10
3. **core/backtest/optimized_backtest_engine.py**: 1472行
4. **data_svc/spider/app.py**: 1368行，33个函数

## 🚀 重构步骤

### 步骤 1: 拆分 server/app.py

已创建示例文件 `server/routes/strategy_routes.py`，展示了如何：

1. 创建 Blueprint
2. 提取路由函数
3. 使用统一的错误处理
4. 使用 `json_response` 工具函数

**下一步**：按照相同模式创建其他路由文件：

- `server/routes/backtest_routes.py` - 回测相关路由
- `server/routes/data_routes.py` - 数据查询路由
- `server/routes/scatter_routes.py` - 散点图路由
- `server/routes/optimization_routes.py` - 优化相关路由

### 步骤 2: 更新 server/app.py

在 `server/app.py` 中：

1. 导入路由注册函数
2. 调用 `register_routes(app)` 注册所有路由
3. 删除已提取的路由函数

### 步骤 3: 拆分 Socket.IO 处理器

创建 `server/socketio_handlers/` 目录，提取 Socket.IO 事件处理器。

### 步骤 4: 拆分 visualization_api.py

按功能拆分到 `server/api/` 目录。

## 📝 重构原则

1. **单一职责**: 每个文件只负责一个功能模块
2. **文件大小**: 单个文件不超过 500 行
3. **函数大小**: 单个函数不超过 50 行
4. **嵌套深度**: 不超过 4 层
5. **向后兼容**: 保持 API 接口不变

## ✅ 验收标准

- [ ] 所有路由正常工作
- [ ] 所有 Socket.IO 事件正常工作
- [ ] 代码行数减少 30%+
- [ ] 嵌套深度降低到 4 层以下
- [ ] 测试通过

## 🔄 下一步

1. 完成 `server/routes/` 目录下的所有路由文件
2. 更新 `server/app.py` 使用新的路由结构
3. 测试所有功能
4. 继续重构其他模块

