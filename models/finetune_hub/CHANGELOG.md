# 更新日志

## 从 Mock 到实际 API 集成

### 已完成的工作

#### 1. 后端 API 服务器 (`api_server.py`)
- ✅ 创建了完整的 Flask API 服务器
- ✅ 实现了训练启动 API (`/api/train/start`)
- ✅ 实现了训练状态查询 API (`/api/train/status`)
- ✅ 实现了模型预测 API (`/api/predict`)
- ✅ 实现了数据验证 API (`/api/data/validate`)
- ✅ 实现了数据清理 API (`/api/data/clean`)
- ✅ 添加了健康检查端点 (`/api/health`)
- ✅ 集成了实际的训练流程（使用 transformers + LoRA）
- ✅ 支持实时训练进度更新

#### 2. 前端代码更新
- ✅ **TrainingConfigPanel.jsx**: 替换 mock 为实际 API 调用
  - 训练启动连接到 `/api/train/start`
  - 实时轮询训练状态 (`/api/train/status`)
  - 显示实际训练进度
  
- ✅ **PromptLab.jsx**: 替换 mock 为实际 API 调用
  - 基座模型预测连接到 `/api/predict?use_finetuned=false`
  - 微调模型预测连接到 `/api/predict?use_finetuned=true`
  - 显示实际模型输出
  
- ✅ **DataPreparationPanel.jsx**: 替换 mock 为实际 API 调用
  - 数据验证连接到 `/api/data/validate`
  - 数据清理连接到 `/api/data/clean`
  - 添加加载状态指示

#### 3. 启动脚本
- ✅ **start.bat** (Windows): 一键启动脚本
  - 自动检查依赖
  - 创建虚拟环境
  - 启动后端和前端服务
  
- ✅ **start.sh** (Linux/Mac): 一键启动脚本
  - 自动检查依赖
  - 创建虚拟环境
  - 启动后端和前端服务

#### 4. 配置文件
- ✅ **requirements.txt**: Python 依赖列表
- ✅ **config.js**: API 配置（支持环境变量）
- ✅ **README_RUN.md**: 详细运行指南

### API 端点说明

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/train/start` | POST | 启动训练 |
| `/api/train/status` | GET | 获取训练状态 |
| `/api/predict` | POST | 模型预测 |
| `/api/data/validate` | POST | 验证 JSONL 数据 |
| `/api/data/clean` | POST | 清理数据 |

### 使用方式

#### 快速启动（推荐）
```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

#### 手动启动
```bash
# 1. 启动后端
cd llm-finetuning-hub
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python api_server.py

# 2. 启动前端（新终端）
cd llm-finetuning-hub
npm install
npm run dev
```

### 注意事项

1. **模型路径**: 需要在 `api_server.py` 中配置正确的模型路径
2. **训练数据**: 确保 `train_sentiment.jsonl` 文件存在
3. **GPU 要求**: 训练需要 CUDA 支持的 GPU
4. **端口**: 后端默认 5001，前端默认 3000

### 下一步改进

- [ ] 添加 WebSocket 支持实时训练进度（替代轮询）
- [ ] 添加训练日志查看功能
- [ ] 支持多实验管理
- [ ] 添加模型版本管理
- [ ] 支持断点续训

