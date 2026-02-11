# LLM 集成总结

## 完成的工作

已成功将 LLM 代码生成功能集成到 AquaTrade 系统中，并整合了之前创建的 AIStrategyBase 架构。

## 修改的文件

### 1. `requirements.txt`
- ✅ 添加了 `openai>=1.0.0` 依赖

### 2. `config/config.py`
- ✅ 添加了 LLM 配置项：
  - `LLM_API_BASE`: LLM API 地址（默认: `http://127.0.0.1:1234/v1`）
  - `LLM_API_KEY`: API Key（默认: `lm-studio`）
  - `LLM_MODEL_NAME`: 模型名称（默认: `deepseek-r1-qwen3-8b`）
  - `LLM_TEMPERATURE`: 温度参数（默认: `0.1`）
  - `LLM_MAX_TOKENS`: 最大 token 数（默认: `4096`）

### 3. `server/services/__init__.py`
- ✅ 添加了 `StrategyGenerator` 的导出

## 新增的文件

### 1. `core/utils/llm_client.py`
**LLM 客户端类 `AquaLLM`**

功能：
- 连接到本地 LLM 服务（如 LM Studio）或 OpenAI API
- 自动清洗 Markdown 标记和思考过程标签
- 支持 DeepSeek R1 的 `<think>` 标签清理
- 完整的错误处理和日志记录

主要方法：
- `generate_code(user_prompt, system_prompt)`: 生成代码
- `_clean_code(raw_text)`: 清洗代码输出

### 2. `server/services/strategy_generator.py`
**策略生成服务类 `StrategyGenerator`**

功能：
- 将用户的自然语言描述转换为策略代码
- 整合了 `prompt_template.py` 的 Prompt 工程
- 自动保存生成的策略到 `core/strategies/user/` 目录
- 后处理代码，确保包含正确的策略ID和名称

主要方法：
- `create_strategy(user_description, strategy_name)`: 生成并保存策略

### 3. `core/strategies/user/__init__.py`
**用户生成的策略目录**

用于存放 AI 生成的策略文件。

## 架构整合

### 使用 AIStrategyBase 架构

生成的策略代码会：
1. ✅ 继承 `AIStrategyBase`（而不是旧的 `StrategyBase`）
2. ✅ 使用 `AIStrategyConfig` 存储参数
3. ✅ 实现 `get_required_indicators()` 声明指标
4. ✅ 实现 `_generate_signals_impl()` 核心逻辑
5. ✅ 所有参数从 `config.params` 获取

### Prompt 工程

使用了之前创建的 `prompt_template.py`：
- 系统提示词
- 硬性约束（6条规则）
- 代码模板
- 指标映射表
- 常见策略模式

## 使用方式

### 方式1: 直接调用服务

```python
from server.services import StrategyGenerator

generator = StrategyGenerator()
filename = generator.create_strategy(
    user_description="写一个策略：股价突破20日均线买入，RSI大于70卖出，最多持仓5天。",
    strategy_name="AI突破策略"
)
```

### 方式2: 命令行测试

```bash
python server/services/strategy_generator.py
```

### 方式3: API 接口（待实现）

可以在 `server/routes/` 中添加 API 接口：

```python
@bp.route('/api/strategy/generate', methods=['POST'])
def generate_strategy():
    data = request.json
    generator = StrategyGenerator()
    filename = generator.create_strategy(
        user_description=data['description'],
        strategy_name=data.get('name', 'AI策略')
    )
    return jsonify({'filename': filename})
```

## 配置说明

### 环境变量

可以通过环境变量覆盖默认配置：

```bash
# Windows
set LLM_API_BASE=http://127.0.0.1:1234/v1
set LLM_API_KEY=lm-studio
set LLM_MODEL_NAME=deepseek-r1-qwen3-8b
set LLM_TEMPERATURE=0.1
set LLM_MAX_TOKENS=4096

# Linux/Mac
export LLM_API_BASE=http://127.0.0.1:1234/v1
export LLM_API_KEY=lm-studio
export LLM_MODEL_NAME=deepseek-r1-qwen3-8b
export LLM_TEMPERATURE=0.1
export LLM_MAX_TOKENS=4096
```

### LM Studio 配置

1. 启动 LM Studio
2. 加载模型（如 deepseek-r1-qwen3-8b）
3. 启动本地服务器（默认端口 1234）
4. 确保 API 地址为 `http://127.0.0.1:1234/v1`

## 文件结构

```
aquatrade/
├── config/
│   └── config.py                    # ✅ 已修改：添加 LLM 配置
├── core/
│   ├── strategies/
│   │   ├── templates/                # AIStrategyBase 架构
│   │   │   ├── ai_base.py
│   │   │   ├── prompt_template.py
│   │   │   └── ...
│   │   └── user/                     # ✅ 新增：用户生成的策略目录
│   │       └── __init__.py
│   └── utils/
│       └── llm_client.py            # ✅ 新增：LLM 客户端
├── server/
│   └── services/
│       ├── __init__.py              # ✅ 已修改：导出 StrategyGenerator
│       └── strategy_generator.py    # ✅ 新增：策略生成服务
└── requirements.txt                 # ✅ 已修改：添加 openai 依赖
```

## 测试

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 LLM 服务

确保 LM Studio 或其他 LLM 服务运行在 `http://127.0.0.1:1234/v1`

### 3. 运行测试

```bash
python server/services/strategy_generator.py
```

### 4. 检查生成的文件

生成的策略文件会保存在：
```
core/strategies/user/ai_gen_<timestamp>.py
```

## 下一步

1. **API 接口**: 在 `server/routes/` 中添加策略生成的 API 接口
2. **前端集成**: 在 Web 界面中添加策略生成功能
3. **指标计算**: 实现 Step 2，确保生成的策略能正确获取指标数据
4. **策略验证**: 添加更严格的代码验证逻辑
5. **错误处理**: 增强错误处理和用户反馈

## 注意事项

1. **LLM 服务**: 确保 LLM 服务正在运行
2. **模型选择**: 建议使用支持代码生成的模型（如 DeepSeek、GPT-4）
3. **代码质量**: 生成的代码需要经过验证和测试
4. **参数配置**: 根据实际使用的模型调整 `LLM_TEMPERATURE` 和 `LLM_MAX_TOKENS`

## 总结

✅ 所有文件已创建和修改完成
✅ 已整合 AIStrategyBase 架构
✅ 已整合 Prompt 工程
✅ 代码生成功能已可用

现在可以通过 `StrategyGenerator` 将自然语言描述转换为符合规范的策略代码！


