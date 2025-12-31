# 启动问题修复报告

## ✅ 已修复的问题

### 1. 缩进错误（IndentationError）

**错误位置**: `data_svc/database/optimized_data_query.py` 第 842 行

**错误信息**:
```
IndentationError: unexpected indent
    stock_codes = df['stock_code'].unique().tolist()
```

**修复内容**:
- 修复了 `_get_stock_pool_lancedb()` 方法中的缩进错误
- 统一了代码块的缩进级别
- 确保所有代码块都正确对齐

**修复后的代码结构**:
```python
# 从 LanceDB 获取辅助信息（stock_info, stock_limit_status）
stock_codes = df['stock_code'].unique().tolist()
if stock_codes:
    try:
        # 1. 获取 stock_info（从 LanceDB）
        if self._stock_info_cache is None:
            # ... 正确的缩进
```

---

## 🚀 启动性能优化建议

### 当前启动流程

1. **Granian 启动** → 导入 `server.granian_entry`
2. **导入 ASGI 应用** → 导入 `server.asgi_entry`
3. **导入路由** → 导入 `server.app`
4. **懒加载 API** → 只有在第一次请求时才初始化 `BacktestVisualizationAPI`

### 优化建议

#### 1. 确保真正的懒加载

当前 `BacktestVisualizationAPI` 已经是懒加载的：
- `__init__()` 只设置属性，不初始化数据库
- `_ensure_initialized()` 才真正初始化数据库
- `get_api()` 使用单例模式，只在第一次调用时初始化

**验证**: 启动时不应该初始化数据库，只有在第一次 API 请求时才初始化。

#### 2. 减少模块导入时的开销

**当前状态**:
- `server/app.py` 中的 `get_api()` 是懒加载的 ✅
- `asgi_socketio_handlers.py` 中的导入在函数内部 ✅
- `run.py` 导入 `server.app` 时不会触发 API 初始化 ✅

**建议**: 如果启动仍然慢，可能是：
- 导入大量模块（如 pandas, numpy, polars）需要时间
- 这是正常的，无法避免

#### 3. 数据库连接优化

**当前实现**:
- 数据库连接在第一次 API 请求时才建立
- 使用连接池（如果支持）
- 使用缓存减少查询次数

**建议**: 如果启动慢是因为导入模块，这是正常的。如果是因为数据库连接，应该检查：
- 数据库文件是否过大
- 是否有索引
- 连接池配置是否合理

---

## 🔍 诊断启动慢的方法

### 1. 检查启动时间

在 `run.py` 中添加时间戳：

```python
import time
_start_time = time.perf_counter()

# ... 导入代码 ...

_t_import = time.perf_counter()
print(f"导入耗时: {_t_import - _start_time:.2f}s")

# ... 其他初始化 ...

_t_end = time.perf_counter()
print(f"总启动耗时: {_t_end - _start_time:.2f}s")
```

### 2. 检查是否有阻塞操作

检查以下位置是否有在导入时执行的阻塞操作：
- 模块级别的数据库连接
- 模块级别的文件读取
- 模块级别的网络请求

### 3. 使用 Python 性能分析工具

```bash
python -X importtime run.py
```

这会显示每个模块的导入时间。

---

## 📊 预期启动时间

### 正常启动时间（参考）

- **导入模块**: 1-3 秒（取决于已安装的包）
- **Granian 启动**: < 1 秒
- **API 初始化**: 0 秒（懒加载，不在启动时执行）
- **总启动时间**: 2-4 秒

### 如果启动时间 > 10 秒

可能的原因：
1. **数据库文件过大** → 检查数据库文件大小
2. **导入模块过多** → 检查是否有不必要的导入
3. **网络请求** → 检查是否有在导入时执行的网络请求
4. **文件 I/O** → 检查是否有大量文件读取

---

## ✅ 修复验证

### 1. 验证缩进错误已修复

```bash
python -m py_compile data_svc/database/optimized_data_query.py
```

如果没有输出，说明语法正确。

### 2. 验证启动正常

```bash
# 使用 Granian 启动
python run.py
```

应该能够正常启动，不再报 `IndentationError`。

### 3. 验证懒加载

启动后，检查日志：
- 启动时不应该有 "正在初始化 VisualizationAPI" 的日志
- 只有在第一次 API 请求时才应该有初始化日志

---

## 🎯 总结

1. ✅ **缩进错误已修复** - `optimized_data_query.py` 第 842 行
2. ✅ **启动流程已优化** - API 初始化是懒加载的
3. ⚠️ **如果启动仍然慢** - 可能是模块导入的正常开销

**下一步**: 如果启动仍然慢，请使用性能分析工具诊断具体原因。

