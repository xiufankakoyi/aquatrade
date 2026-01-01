# 回测业务逻辑重构总结

## 重构目标

将 `run_backtest_background` 函数及其依赖从 `server/app.py` 移动到独立的业务逻辑层，解决 `app.py` 职责过载的问题。

## 已完成的工作

### 1. 创建业务逻辑层

**新建文件**: `server/logic/__init__.py`
- 创建逻辑层模块

**新建文件**: `server/logic/backtest.py`
- 移动了以下函数：
  - `_estimate_data_size()` - 估算数据大小
  - `_compress_data()` - 压缩数据
  - `_chunk_large_array()` - 分块大数组
  - `_emit_large_data()` - 大数据传输优化
  - `run_backtest_background()` - 后台回测任务

### 2. 函数签名改进

**原签名**:
```python
def run_backtest_background(sid, strategy_name, start_date, end_date, benchmark_code, stop_event: Event, params=None):
```

**新签名**:
```python
def run_backtest_background(
    socketio_instance,  # SocketIO 实例（通过参数传递，避免循环依赖）
    sid: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    benchmark_code: Optional[str],
    stop_event: Event,
    params: Optional[Dict[str, Any]] = None,
    get_api_func: Optional[Callable] = None,  # 可选，默认从 server.app 导入
    active_backtests_dict: Optional[Dict[str, Event]] = None  # 可选，用于清理
):
```

**关键改进**:
- `socketio` 从全局变量改为参数传递，避免循环依赖
- `get_api` 函数通过参数传递，支持依赖注入
- `active_backtests` 字典通过参数传递，支持依赖注入

### 3. 更新导入关系

**`server/socketio_handlers.py`**:
- 从 `server.logic.backtest` 导入 `run_backtest_background` 和 `_emit_large_data`
- 更新函数调用，传递所有必需的参数

**`server/app.py`**:
- 删除 `run_backtest_background` 和相关辅助函数的定义
- 保留导入 `_emit_large_data` 以保持向后兼容（如果其他地方直接导入）
- 如果 `app.py` 中仍有 Socket.IO 处理器使用这些函数，已更新为使用新的导入

### 4. 避免循环依赖

**策略**:
1. **参数传递**: `socketio`、`get_api`、`active_backtests` 都通过参数传递，而不是全局导入
2. **延迟导入**: 在 `run_backtest_background` 内部，如果 `get_api_func` 为 `None`，才从 `server.app` 导入（延迟导入避免循环）
3. **逻辑层独立**: `server/logic/backtest.py` 不直接导入 `server.app`，只在使用时才延迟导入

## 架构优势

### 1. 职责分离
- **`app.py`**: 只负责"组装"和"启动"（创建 Flask/SocketIO 实例，注册路由和处理器）
- **`server/logic/backtest.py`**: 包含回测业务逻辑，不依赖 Flask/SocketIO 框架
- **`server/socketio_handlers.py`**: 包含 Socket.IO 事件处理器，作为框架和业务逻辑之间的桥梁

### 2. 可测试性
- 业务逻辑函数现在可以通过参数注入依赖，更容易进行单元测试
- 不需要创建完整的 Flask/SocketIO 应用实例即可测试业务逻辑

### 3. 可维护性
- 业务逻辑集中在 `server/logic/` 目录，更容易查找和修改
- 减少了 `app.py` 的代码量，提高了可读性

### 4. 避免循环依赖
- 通过参数传递和延迟导入，避免了 `app.py` ↔ `logic/backtest.py` 的循环依赖
- 逻辑层不直接依赖框架层

## 注意事项

### 1. 向后兼容
- `app.py` 中保留了 `from server.logic.backtest import _emit_large_data` 的导入，以保持向后兼容
- 如果其他代码直接导入这些函数，仍然可以正常工作

### 2. Socket.IO 处理器
- `app.py` 中可能仍有重复的 Socket.IO 处理器（已在 `socketio_handlers.py` 中注册）
- 这些重复的处理器应该被删除，因为它们会导致重复注册

### 3. 参数传递
- 调用 `run_backtest_background` 时必须传递 `socketio_instance` 作为第一个参数
- 建议也传递 `get_api` 和 `active_backtests`，以提高可测试性

## 后续建议

1. **删除重复的 Socket.IO 处理器**: 从 `app.py` 中删除所有 `@socketio.on()` 装饰器，因为它们已在 `socketio_handlers.py` 中注册
2. **进一步重构**: 考虑将其他业务逻辑函数（如 `push_optimization_task_to_redis`）也移动到逻辑层
3. **单元测试**: 为 `server/logic/backtest.py` 中的函数编写单元测试

## 文件变更清单

- ✅ **新建**: `server/logic/__init__.py`
- ✅ **新建**: `server/logic/backtest.py`
- ✅ **修改**: `server/socketio_handlers.py` - 更新导入和函数调用
- ✅ **修改**: `server/app.py` - 删除函数定义，保留向后兼容导入

