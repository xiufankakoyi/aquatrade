# AI 策略生成框架 - 实现总结

## 已完成的工作

### ✅ Step 1: 立法 —— 定义 AI 策略的标准模版 (Protocol)

**文件**: `core/strategies/templates/ai_base.py`

**核心组件**:
1. **AIStrategyConfig**: 策略配置类
   - 强制所有参数存储在 `params` 字典中
   - 禁止硬编码参数

2. **AIStrategyBase**: AI 策略基类
   - 继承自 `StrategyBase`
   - 强制内置状态管理 (`holding_state`)
   - 提供两个关键接口：
     - `get_required_indicators()`: 声明需要的指标
     - `_generate_signals_impl()`: 核心逻辑实现

**核心规则**:
- ✅ 参数必须从 `config.params` 获取
- ✅ 指标必须通过 `get_required_indicators()` 声明
- ✅ 在 `_generate_signals_impl()` 中只做逻辑判断，不计算指标
- ✅ 使用 `holding_state` 管理持仓状态

### ✅ Step 3: 桥梁 —— 构建 Prompt 工程 (AI Generator)

**文件**: 
- `core/strategies/templates/prompt_template.py`: Prompt 模板
- `core/strategies/templates/ai_generator.py`: 代码生成器

**核心功能**:
1. **Prompt 模板** (`prompt_template.py`):
   - 系统提示词
   - 硬性约束（6条规则）
   - 代码模板
   - 指标映射表
   - 常见策略模式

2. **代码生成器** (`ai_generator.py`):
   - `AIStrategyGenerator`: 主生成器类
   - 支持 OpenAI API
   - 支持自定义 LLM 函数
   - 代码清理和验证
   - 自动保存功能

**特性**:
- ✅ 自动清理 Markdown 标记
- ✅ 代码语法验证
- ✅ 规范符合性检查
- ✅ 禁止函数检测（如 `talib`, `pandas.rolling`）

## 测试结果

所有测试通过 ✅:

1. **Prompt 生成测试**: ✅ 通过
2. **代码验证测试**: ✅ 通过
   - 正确代码验证通过
   - 错误代码检测正确
   - 禁止函数检测正确
3. **代码清理测试**: ✅ 通过
   - Markdown 标记移除成功
4. **自定义 LLM 测试**: ✅ 通过
   - 代码生成成功
   - 动态加载成功
   - 策略实例创建成功
5. **完整工作流程测试**: ✅ 通过
   - 代码生成 → 保存 → 验证 → 清理

## 使用示例

### 方式1: 使用 OpenAI API

```python
from core.strategies.templates import AIStrategyGenerator

generator = AIStrategyGenerator()
generator.set_openai_api(
    api_key="sk-your-api-key",
    model="gpt-4"
)

code = generator.generate(
    "写一个策略：股价突破20日均线买入，RSI大于70卖出，最多持仓5天。"
)

# 保存到文件
generator.generate_and_save(
    "写一个策略：股价突破20日均线买入，RSI大于70卖出，最多持仓5天。",
    "my_strategy.py"
)
```

### 方式2: 使用自定义 LLM

```python
from core.strategies.templates import AIStrategyGenerator

def my_llm_function(prompt: str) -> str:
    # 调用你的 LLM API
    return generated_code

generator = AIStrategyGenerator()
generator.set_custom_llm(my_llm_function)

code = generator.generate("写一个策略...")
```

### 方式3: 使用便捷函数

```python
from core.strategies.templates import generate_strategy_code

code = generate_strategy_code(
    "股价突破20日均线买入，RSI大于70卖出",
    openai_api_key="sk-your-api-key"
)
```

## 文件结构

```
core/strategies/templates/
├── __init__.py                    # 模块导出
├── ai_base.py                     # Step 1: 基类和配置
├── prompt_template.py             # Step 3: Prompt 模板
├── ai_generator.py                # Step 3: 代码生成器
├── example_usage.py               # 使用示例
├── test_generator.py              # 测试脚本
├── README.md                      # 使用文档
└── IMPLEMENTATION_SUMMARY.md      # 本文档
```

## 下一步工作

### 🔲 Step 2: 后端指标计算 (待实现)

需要在回测引擎或数据服务层实现：

1. **指标计算服务**
   - 根据 `get_required_indicators()` 的结果计算指标
   - 将指标添加到 `stock_pool` DataFrame 中
   - 支持 MA、EMA、RSI、MACD、BOLL 等指标

2. **集成到回测引擎**
   - 检测策略是否为 `AIStrategyBase` 的子类
   - 在生成信号前，自动调用 `get_required_indicators()`
   - 计算指标并添加到 `stock_pool`
   - 然后调用 `generate_signals()`

3. **指标列名规范**
   - 统一指标列名格式（如 `MA_20`, `RSI_14`）
   - 确保策略代码能正确访问指标列

### 🔲 前端集成

1. **Web 界面**
   - 策略生成输入框
   - LLM API 配置
   - 生成的代码预览和编辑
   - 一键保存和测试

2. **API 接口**
   - `/api/strategy/generate`: 生成策略代码
   - `/api/strategy/validate`: 验证策略代码
   - `/api/strategy/save`: 保存策略

## 核心设计理念

1. **分离关注点**
   - 指标计算：后端负责
   - 逻辑判断：策略负责

2. **强制规范**
   - 通过基类强制遵守规则
   - 通过验证确保代码质量

3. **可扩展性**
   - 支持多种 LLM 后端
   - 支持自定义指标类型
   - 支持自定义策略模式

## 技术栈

- **Python 3.8+**
- **Pandas**: 数据处理
- **OpenAI API**: 代码生成（可选）
- **标准库**: `dataclasses`, `typing`, `importlib`

## 注意事项

1. **LLM 质量**: 生成的代码质量取决于 LLM 的能力
   - 建议使用 GPT-4 或同等能力的模型
   - 对于简单策略，GPT-3.5 也可以

2. **代码验证**: 生成的代码需要经过验证
   - 自动验证：语法、规范符合性
   - 手动验证：逻辑正确性、回测测试

3. **指标计算**: 目前需要手动实现 Step 2
   - 或者使用现有的指标计算服务
   - 确保指标列名与策略代码中的访问方式一致

## 总结

✅ **Step 1 和 Step 3 已完成**
- 基类框架完整
- Prompt 工程完善
- 代码生成器功能齐全
- 测试全部通过

🔲 **Step 2 待实现**
- 需要集成到回测引擎
- 实现自动指标计算

框架已经可以投入使用，只需要：
1. 配置 LLM API（OpenAI 或自定义）
2. 实现 Step 2 的指标计算逻辑
3. 集成到回测系统


