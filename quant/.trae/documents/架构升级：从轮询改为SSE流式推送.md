## 目标
将现有的 HTTP 轮询机制升级为 SSE (Server-Sent Events) 流式推送，并优化前端渲染性能。

## 核心优化点

### 1. 后端升级 (server.py)
**新增 SSE 端点 `/api/stream`**
- 使用 Flask 的 `Response` + `stream_with_context` 实现流式响应
- 通过 `yield` 实时推送日志到前端
- 保持原有轮询接口兼容（作为 fallback）

**修改任务执行函数**
- 使用 `queue.Queue` 实现线程安全的日志传递
- 生产者（子进程读取线程）→ 队列 → 消费者（SSE 生成器）

### 2. 前端升级 (app.js)
**使用 EventSource 接收 SSE**
- 建立持久连接：`new EventSource('/api/stream?job_id=xxx')`
- 监听 `message` 事件接收日志
- 自动重连机制（EventSource 原生支持）

**优化渲染性能**
- 使用 `insertAdjacentHTML('beforeend', ...)` 替代 `innerHTML`
- 虚拟滚动：只保留最近 500 行，超出时移除顶部旧节点
- CSS `contain: content` 优化布局性能

### 3. 具体实现步骤

#### 后端修改
1. 添加 `queue` 模块导入
2. 新增 `job_queues` 字典存储每个任务的日志队列
3. 修改 `run_crawler_background` 和 `run_clean_and_push_background`：
   - 创建队列
   - 读取线程将日志放入队列
   - 新增 SSE 路由 `/api/stream`

#### 前端修改
1. 新增 `connectEventSource(jobId)` 函数
2. 新增 `appendLog(message)` 函数（增量渲染）
3. 新增 `trimLogContainer()` 函数（限制行数）
4. 修改 `handleSubmit` 和 `handleCleanAndPush`：
   - 启动任务后连接 SSE
   - 任务完成/失败时关闭 SSE

### 4. 代码结构

**后端 SSE 路由示例：**
```python
@app.route('/api/stream')
def stream():
    job_id = request.args.get('job_id')
    def generate():
        while True:
            msg = queue.get(timeout=1)
            yield f"data: {json.dumps(msg)}\n\n"
    return Response(generate(), mimetype='text/event-stream')
```

**前端 SSE 示例：**
```javascript
const evtSource = new EventSource(`/api/stream?job_id=${jobId}`);
evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    appendLog(data.message);
};
```

### 5. 降级方案
- 如果浏览器不支持 EventSource，自动回退到轮询机制
- 保持原有 `/api/status` 接口可用

请确认此计划后，我将开始实施具体的代码修改。