# AI 策略生成框架

这是一个完整的 AI 策略生成框架，可以将自然语言描述转换为符合规范的量化策略代码。

## 架构设计

### Step 1: 立法 —— 定义 AI 策略的标准模版 (Protocol)
- **文件**: `ai_base.py`
- **内容**: `AIStrategyBase` 基类和 `AIStrategyConfig` 配置类
- **作用**: 定义 AI 生成代码的"宪法"，强制遵守状态管理和参数分离规则

### Step 2: 后端指标计算 (待实现)
- **作用**: 根据策略声明的指标，在 `stock_pool` 中计算并添加指标列
- **位置**: 回测引擎或数据服务层

### Step 3: 桥梁 —— 构建 Prompt 工程 (AI Generator)
- **文件**: `prompt_template.py` 和 `ai_generator.py`
- **作用**: 将用户的自然语言描述转换为符合规范的 Python 代码

## 快速开始

### 1. 使用 AI 生成器创建策略

```python
from core.strategies.templates import AIStrategyGenerator

# 创建生成器
generator = AIStrategyGenerator()

# 设置 OpenAI API（或使用自定义 LLM）
generator.set_openai_api(
    api_key="sk-your-api-key",
    model="gpt-4"
)

# 生成策略代码
user_description = "写一个策略：股价突破20日均线买入，RSI大于70卖出，最多持仓5天。"
code = generator.generate(user_description)

# 保存到文件
with open("my_strategy.py", "w", encoding="utf-8") as f:
    f.write(code)
```

### 2. 手动实现策略（符合规范）

```python
from core.strategies.templates import AIStrategyBase, AIStrategyConfig

class MyStrategy(AIStrategyBase):
    strategy_name = "我的策略"
    
    def __init__(self, config: AIStrategyConfig = None):
        if config is None:
            config = AIStrategyConfig(params={
                "ma_period": 20,
                "rsi_sell_threshold": 70,
                "max_holding_days": 5,
            })
        super().__init__(config)
    
    def get_required_indicators(self):
        """声明需要的指标"""
        return [
            {"name": "MA", "period": self.config.params.get("ma_period", 20), "column": "close"},
            {"name": "RSI", "period": 14, "column": "close"},
        ]
    
    def _generate_signals_impl(self, current_date: str, stock_pool):
        """核心逻辑：只做判断，不计算指标"""
        signals = {}
        ma_period = self.config.params.get("ma_period", 20)
        rsi_sell_threshold = self.config.params.get("rsi_sell_threshold", 70)
        max_holding_days = self.config.params.get("max_holding_days", 5)
        
        for _, row in stock_pool.iterrows():
            code = row["stock_code"]
            
            # 卖出逻辑
            if code in self.current_portfolio:
                holding_days = self.holding_state.get(code, {}).get("holding_days", 0)
                if holding_days >= max_holding_days:
                    signals[code] = "sell"
                    continue
                
                if row["RSI"] > rsi_sell_threshold:
                    signals[code] = "sell"
                    continue
            
            # 买入逻辑
            ma_column = f"MA_{ma_period}"
            if ma_column in row.index and row["close"] > row[ma_column]:
                signals[code] = "buy"
            else:
                signals[code] = "hold"
        
        return signals
```

## 核心规则

### 1. 参数分离
- ✅ **正确**: 所有参数从 `self.config.params` 获取
- ❌ **错误**: 硬编码数字 `if row["RSI"] < 70`

### 2. 指标声明
- ✅ **正确**: 在 `get_required_indicators()` 中声明指标
- ❌ **错误**: 在 `_generate_signals_impl()` 中计算指标

### 3. 逻辑判断
- ✅ **正确**: 使用 `stock_pool` 中已有的指标列
- ❌ **错误**: 使用 `talib.RSI()` 或 `pandas.rolling()` 计算指标

## 支持的指标类型

- **MA**: 移动平均线
- **EMA**: 指数移动平均线
- **RSI**: 相对强弱指标
- **MACD**: MACD 指标
- **BOLL**: 布林带
- **VOLUME_MA**: 成交量均线

## 文件结构

```
core/strategies/templates/
├── __init__.py              # 模块导出
├── ai_base.py              # Step 1: 基类和配置
├── prompt_template.py      # Step 3: Prompt 模板
├── ai_generator.py         # Step 3: 代码生成器
├── example_usage.py         # 使用示例
└── README.md              # 本文档
```

## 下一步

1. **实现 Step 2**: 在后端添加指标计算逻辑，根据 `get_required_indicators()` 的结果计算指标
2. **集成到回测引擎**: 确保回测引擎能够识别 AI 策略并自动计算指标
3. **前端集成**: 在 Web 界面中添加策略生成功能


