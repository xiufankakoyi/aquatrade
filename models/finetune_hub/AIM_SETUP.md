# Aim Stack 安装和配置指南

## 问题诊断

如果看到 `ERR_CONNECTION_REFUSED` 错误，说明 Aim Stack 服务没有运行。

## 安装 Aim Stack

### 方法 1: 使用 pip 安装（推荐）

```bash
pip install aim
```

### 方法 2: 使用 conda 安装

```bash
conda install -c conda-forge aim
```

## 启动 Aim Stack

### 方式 1: 使用 aim up（推荐）

```bash
# 在项目根目录运行
aim up

# 或者指定端口
aim up --port 43800
```

### 方式 2: 使用 aim server

```bash
aim server
```

### 方式 3: 使用 Python API

```python
from aim import Run

# 这会自动启动 Aim UI
run = Run()
```

## 验证 Aim 是否运行

1. **检查端口是否监听**
   ```bash
   # Windows
   netstat -an | findstr 43800
   
   # Linux/Mac
   lsof -i :43800
   ```

2. **访问 Web UI**
   打开浏览器访问：http://localhost:43800

3. **检查进程**
   ```bash
   # Windows
   tasklist | findstr aim
   
   # Linux/Mac
   ps aux | grep aim
   ```

## 常见问题

### 1. 端口被占用

如果 43800 端口被占用，可以：
- 使用其他端口：`aim up --port 43801`
- 在前端修改 Aim URL 为新的端口

### 2. 防火墙阻止

确保防火墙允许本地连接：
- Windows: 检查 Windows Defender 防火墙
- Linux: 检查 iptables 或 ufw

### 3. Aim 未安装

如果 `aim` 命令不存在：
```bash
# 检查是否安装
pip list | grep aim

# 如果未安装，安装它
pip install aim
```

## 集成到训练流程

### 在训练代码中使用 Aim

确保训练配置中启用了 "Aim Logging"：

```python
from aim import Run

run = Run()
run['learning_rate'] = 3e-4
run['batch_size'] = 8

# 训练过程中记录指标
for epoch in range(num_epochs):
    loss = train_one_epoch()
    run.track(loss, name='loss', epoch=epoch)
```

### 自动启动 Aim（可选）

可以在启动脚本中添加 Aim 启动：

```bash
# 检查 Aim 是否运行，如果没有则启动
if ! lsof -i :43800 > /dev/null 2>&1; then
    echo "启动 Aim Stack..."
    aim up &
fi
```

## 不使用 Aim 的替代方案

如果不想使用 Aim，可以：

1. **关闭 Aim Logging**
   - 在训练配置面板中关闭 "Aim Logging" 开关
   - 训练仍然会正常进行，只是不记录到 Aim

2. **使用 TensorBoard（如果已集成）**
   - 某些训练框架支持 TensorBoard
   - 访问 http://localhost:6006

3. **查看训练日志**
   - 训练过程中的日志会显示在控制台
   - 可以通过 API 获取训练状态

## 快速启动脚本

创建一个 `start_aim.bat` (Windows) 或 `start_aim.sh` (Linux/Mac)：

**Windows (start_aim.bat):**
```batch
@echo off
echo 启动 Aim Stack...
aim up --port 43800
pause
```

**Linux/Mac (start_aim.sh):**
```bash
#!/bin/bash
echo "启动 Aim Stack..."
aim up --port 43800
```

## 验证安装

运行以下命令验证 Aim 是否正确安装：

```bash
aim --version
```

应该显示类似：
```
aim, version 3.x.x
```

## 下一步

1. 安装 Aim：`pip install aim`
2. 启动 Aim：`aim up`
3. 在前端可视化监控页面查看




