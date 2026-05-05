# 🚀 AquaTrade 启动指南

## 推荐启动方式

### Windows

**使用自动清理脚本（推荐）**：
```bash
clean_start.bat
```

这个脚本会自动：
1. ✅ 清理所有旧的 Python、Node、Granian 进程
2. ✅ 等待端口释放
3. ✅ 启动所有服务

**手动启动**：
```bash
# 1. 先清理进程
taskkill /F /IM python.exe /T
taskkill /F /IM node.exe /T

# 2. 等待2秒
timeout /t 2

# 3. 启动服务
honcho start
```

---

## 服务地址

启动后访问：
- **后端**: http://localhost:5000
- **前端**: http://localhost:5173 (或 5174, 5175... 如果端口被占用会自动切换)

---

## 停止服务

按 `Ctrl + C` 统一停止所有进程

如果无法停止，运行：
```bash
taskkill /F /IM python.exe /T
taskkill /F /IM node.exe /T
```

---

## 功能说明

### ✅ 已启用的功能
- 🔥 **策略热重载** - 修改策略文件自动重新加载
- 📊 **实时回测** - WebSocket 流式推送回测进度
- ⚙️ **参数管理** - 5个 API 端点管理策略配置
- 📈 **因子库** - 统一的因子计算和加载系统

### 🔧 配置文件
- `.env` - 环境变量（数据库后端：lancedb）
- `Procfile` - Honcho 进程配置
- `core/strategies/configs/*.json` - 策略参数配置

---

## 故障排查

### 问题：端口被占用

**症状**：`Port 5173 is in use, trying another one...`

**解决**：使用 `clean_start.bat` 自动清理，或手动清理：
```bash
# 查看占用端口的进程
netstat -ano | findstr :5173
netstat -ano | findstr :5000

# 终止进程（替换 <PID> 为实际进程ID）
taskkill /F /PID <PID>
```

### 问题：Socket.IO 连接失败

**症状**：浏览器控制台显示 "Socket.IO 连接错误"

**检查**：
1. 后端是否启动成功（查看终端日志）
2. CORS 是否配置正确（应该看到 "Socket.IO event handlers registered!"）
3. 浏览器控制台是否有 CORS 错误

**解决**：重启服务
```bash
clean_start.bat
```

### 问题：中文乱码

**症状**：终端显示乱码

**解决**：已修复，所有 print 语句使用英文或已移除特殊字符

---

## 开发提示

### 修改策略参数
1. 编辑 `core/strategies/configs/jq_volume_v1pro.json`
2. 保存后自动重新加载（无需重启）
3. 或通过前端 API 调用 `PUT /api/strategies/{id}/config`

### 查看日志
- **后端日志**：终端输出
- **前端日志**：浏览器控制台 (F12)
- **调试日志**：查找 `[DEBUG]` 前缀

### 热重载测试
1. 修改 `core/strategies/jq_volume_strategy_v2.py`
2. 保存文件
3. 查看终端输出："Strategy reloaded: jq_volume_v1pro"

---

**版本**: v2.0 (热重载系统)  
**最后更新**: 2026-01-11  
**支持**: 请查看 `walkthrough.md` 了解完整功能
