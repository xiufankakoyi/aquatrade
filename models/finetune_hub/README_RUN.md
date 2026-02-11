# 运行指南

## 快速启动

### Windows
```bash
start.bat
```

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

## 手动启动

### 1. 安装依赖

**Python 依赖：**
```bash
cd llm-finetuning-hub
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Node.js 依赖：**
```bash
npm install
```

### 2. 启动后端 API 服务器

```bash
# 激活虚拟环境
source venv/bin/activate  # Windows: venv\Scripts\activate

# 启动 API 服务器
python api_server.py
```

后端 API 将在 `http://localhost:5001` 运行。

### 3. 启动前端开发服务器

```bash
npm run dev
```

前端应用将在 `http://localhost:3000` 运行。

## API 端点

- `GET /api/health` - 健康检查
- `POST /api/train/start` - 启动训练
- `GET /api/train/status` - 获取训练状态
- `POST /api/predict` - 模型预测
- `POST /api/data/validate` - 验证 JSONL 数据
- `POST /api/data/clean` - 清理数据

## 配置

### 模型路径
在 `api_server.py` 中修改 `MODEL_PATH` 变量：
```python
MODEL_PATH = "I:/models_cache/qwen/Qwen2.5-1.5B-Instruct"
```

### 训练数据
确保训练数据文件存在：
- 路径：`../train_sentiment.jsonl`（相对于 `llm-finetuning-hub` 目录）

### API 基础 URL
前端默认连接到 `http://localhost:5001`，如需修改：
1. 创建 `.env` 文件
2. 添加：`VITE_API_BASE_URL=http://your-api-url:port`

## 故障排除

### 后端无法启动
- 检查 Python 版本（需要 3.8+）
- 检查所有依赖是否安装：`pip install -r requirements.txt`
- 检查模型路径是否正确

### 前端无法连接后端
- 确认后端 API 服务器正在运行
- 检查浏览器控制台的错误信息
- 确认 CORS 配置正确

### 训练失败
- 检查 GPU 是否可用（需要 CUDA）
- 检查训练数据文件是否存在
- 查看后端日志获取详细错误信息

## 注意事项

1. **GPU 要求**：训练需要 CUDA 支持的 GPU
2. **显存要求**：至少 8GB 显存（已优化配置）
3. **训练时间**：根据数据量和配置，训练可能需要几分钟到几十分钟
4. **模型路径**：确保模型路径正确且模型文件完整

