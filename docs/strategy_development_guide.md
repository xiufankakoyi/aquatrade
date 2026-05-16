# 策略开发指南

本文档介绍如何在 AquaTrade 系统中开发量化策略。

---

## 目录

1. [快速开始](#快速开始)
2. [策略层级](#策略层级)
3. [因子系统](#因子系统)
4. [信号工具库](#信号工具库)
5. [预置策略模板](#预置策略模板)
6. [完整示例](#完整示例)
7. [API 参考](#api-参考)
8. [常见问题](#常见问题)

---

## 快速开始

### 最简单的方式：使用预置模板

```python
from core.strategies.strategy_layers import DualMAStrategy

# 一行代码创建双均线策略
strategy = DualMAStrategy(fast=5, slow=10)
```

### 自定义策略：声明式因子

```python
from core.strategies.strategy_layers import SimpleStrategy
from core.strategies.utils.signal_utils import crossover, crossunder

class MyStrategy(SimpleStrategy):
    required_factors = ['ma5', 'ma10', 'rsi_14']
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        ma5 = factors['ma5']
        ma10 = factors['ma10']
        
        # 金叉买入，死叉卖出
        golden = crossover(ma5, ma10)
        death = crossunder(ma5, ma10)
        
        signals = np.zeros(ma5.shape, dtype=int)
        signals[1:][golden] = 1  # buy
        signals[1:][death] = 2   # sell
        return signals
```

---

## 策略层级

系统提供三个层级的策略开发方式，从简单到高级：

```
┌─────────────────────────────────────────────────────────────┐
│                    策略开发难度层级                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第一层：配置策略（最简单）                                    │
│  └── YAML 配置文件，无需写代码                                │
│                                                             │
│  第二层：函数策略（中等）                                      │
│  └── 简单 Python 函数，逐日调用                               │
│                                                             │
│  第三层：类策略（高级）                                        │
│  ├── SimpleStrategy：声明式 + 内置信号函数                    │
│  └── VectorizedStrategyBase：完全控制                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 第一层：配置策略（YAML）

适用于：非程序员、快速验证策略思路

配置文件示例（`configs/my_strategy.yaml`）：

```yaml
strategy:
  name: "双均线策略"
  
  parameters:
    - name: fast_window
      type: int
      default: 5
    - name: slow_window
      type: int
      default: 20

  indicators:
    - name: ma_fast
      type: ma
      params:
        column: close
        window: "${fast_window}"
    - name: ma_slow
      type: ma
      params:
        column: close
        window: "${slow_window}"

  rules:
    - action: buy
      condition: "crossover(ma_fast, ma_slow)"
    - action: sell
      condition: "crossunder(ma_fast, ma_slow)"
```

### 第二层：函数策略

适用于：需要状态管理、逻辑较简单的策略

```python
from core.strategies.strategy_layers import FunctionStrategy, Position

def my_strategy(date: str, factors: dict, position: Position, history: list):
    """
    策略函数
    
    Args:
        date: 当前日期 (YYYY-MM-DD)
        factors: 当日因子值字典，包含声明的因子
        position: 当前持仓状态
        history: 历史交易记录
    
    Returns:
        tuple: (action, ratio)
            - action: 'buy', 'sell', 'hold'
            - ratio: 买入仓位比例 (0-1)，卖出时为 None
    """
    # 买入条件
    if not position.has_position:
        if factors['ma5'] > factors['ma10'] and factors['volume'] > 1e6:
            return 'buy', 0.1  # 买入 10% 仓位
    
    # 卖出条件
    else:
        if factors['ma5'] < factors['ma10']:
            return 'sell', None  # 全卖
    
    return 'hold', None

# 创建策略实例
strategy = FunctionStrategy(
    my_strategy,
    required_factors=['ma5', 'ma10', 'volume']
)
```

### 第三层：类策略（推荐）

#### SimpleStrategy（简化版）

适用于：大多数策略，代码简洁

```python
from core.strategies.strategy_layers import SimpleStrategy
from core.strategies.utils.signal_utils import crossover, crossunder

class MyStrategy(SimpleStrategy):
    """我的策略"""
    
    # 声明所需因子
    required_factors = ['ma5', 'ma10', 'rsi_14']
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        """
        生成信号矩阵
        
        Args:
            factors: 因子字典 {name: matrix(T, N)}
            trading_dates: 日期列表
            stock_codes: 股票代码列表
        
        Returns:
            signals: 信号矩阵 (T, N), 0=hold, 1=buy, 2=sell
        """
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        ma5 = factors['ma5']
        ma10 = factors['ma10']
        rsi = factors['rsi_14']
        
        # 金叉 + RSI 超卖 -> 买入
        golden = crossover(ma5, ma10)
        oversold = rsi[1:] < 30
        signals[1:][golden & oversold] = 1
        
        # 死叉 -> 卖出
        death = crossunder(ma5, ma10)
        signals[1:][death] = 2
        
        return signals
```

#### VectorizedStrategyBase（完全控制）

适用于：需要访问更多数据、完全控制逻辑

```python
from core.strategies.vectorized_base import VectorizedStrategyBase

class AdvancedStrategy(VectorizedStrategyBase):
    """高级策略"""
    
    required_factors = ['ma5', 'ma10']
    
    def generate_signals_vectorized(
        self,
        price_matrix,      # (T, N, 4) [open, high, low, close]
        trading_dates,     # 日期列表
        stock_codes,       # 股票代码列表
        data_query,        # 数据查询对象
        preloaded_data     # 预加载数据
    ):
        # 准备数据（自动构建矩阵）
        self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
        
        # 访问内置属性
        close = self.close      # 收盘价矩阵 (T, N)
        volume = self.volume    # 成交量矩阵 (T, N)
        total_mv = self.total_mv  # 总市值矩阵 (T, N)
        
        # 访问因子
        ma5 = self.factors['ma5']
        ma10 = self.factors['ma10']
        
        # 生成信号
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        # ... 策略逻辑
        
        return signals
```

---

## 因子系统

### 可用因子列表

#### 数据库预计算因子（直接加载）

| 因子名 | 说明 | 数据类型 |
|--------|------|----------|
| `ma5`, `ma10`, `ma20`, `ma60` | 移动平均线 | float |
| `rsi_14` | 相对强弱指标 | float |
| `kdj_k`, `kdj_d`, `kdj_j` | KDJ 指标 | float |
| `macd_dif`, `macd_dea`, `macd_histogram` | MACD 指标 | float |
| `atr_14` | 平均真实波幅 | float |
| `boll_upper`, `boll_mid`, `boll_lower` | 布林带 | float |
| `bias_5`, `bias_10`, `bias_20` | 乖离率 | float |

#### 基础数据因子

| 因子名 | 说明 | 数据类型 |
|--------|------|----------|
| `close` | 收盘价 | float |
| `open` | 开盘价 | float |
| `high` | 最高价 | float |
| `low` | 最低价 | float |
| `volume` | 成交量 | float |
| `amount` | 成交额 | float |
| `total_mv` | 总市值（万元） | float |
| `float_mv` | 流通市值（万元） | float |
| `turnover_rate` | 换手率（%） | float |
| `volume_ratio` | 量比 | float |
| `is_st` | 是否 ST | int (0/1) |
| `days_listed` | 上市天数 | int |

### 因子使用方式

```python
class MyStrategy(SimpleStrategy):
    # 1. 声明所需因子
    required_factors = ['ma5', 'ma10', 'rsi_14', 'close']
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        # 2. 从 factors 字典获取因子
        ma5 = factors['ma5']       # 形状: (T, N)
        ma10 = factors['ma10']
        rsi = factors['rsi_14']
        close = factors['close']
        
        # 3. 使用因子进行计算
        # ...
```

### 因子矩阵说明

所有因子都是二维 NumPy 数组：

```
形状: (T, N)
  - T: 交易日数量
  - N: 股票数量

索引:
  - factors['close'][t, n]  # 第 t 天第 n 只股票的收盘价
```

---

## 信号工具库

`core.strategies.utils.signal_utils` 提供常用信号检测函数：

### crossover - 金叉检测

```python
from core.strategies.utils.signal_utils import crossover

# 检测 MA5 上穿 MA10
golden = crossover(ma5, ma10)  # 返回 bool 数组

# 结果形状: (T-1, N)
# golden[t, n] = True 表示第 t+1 天发生金叉
```

### crossunder - 死叉检测

```python
from core.strategies.utils.signal_utils import crossunder

# 检测 MA5 下穿 MA10
death = crossunder(ma5, ma10)
```

### above / below - 阈值检测

```python
from core.strategies.utils.signal_utils import above, below

# RSI > 70（超买）
overbought = above(rsi, 70)

# RSI < 30（超卖）
oversold = below(rsi, 30)

# 价格 > MA5
above_ma = above(close, ma5)
```

### rising / falling - 连续上涨/下跌

```python
from core.strategies.utils.signal_utils import rising, falling

# 连续 3 天上涨
up_3d = rising(close, 3)

# 连续 2 天下跌
down_2d = falling(close, 2)
```

### in_range - 区间检测

```python
from core.strategies.utils.signal_utils import in_range

# RSI 在 30-70 之间
normal_rsi = in_range(rsi, 30, 70)
```

### breakout - 突破检测

```python
from core.strategies.utils.signal_utils import breakout

# 布林带突破
upper_break, lower_break = breakout(boll_upper, boll_lower, close)

# upper_break: 价格突破上轨
# lower_break: 价格跌破下轨
```

### divergence - 背离检测

```python
from core.strategies.utils.signal_utils import divergence

# RSI 背离
bullish_div, bearish_div = divergence(close, rsi, window=5)

# bullish_div: 底背离（价格新低，指标未新低）
# bearish_div: 顶背离（价格新高，指标未新高）
```

---

## 预置策略模板

系统内置常用策略模板，一行代码即可使用：

### 双均线策略

```python
from core.strategies.strategy_layers import DualMAStrategy

strategy = DualMAStrategy(
    fast=5,      # 快线周期
    slow=10      # 慢线周期
)
```

### RSI 策略

```python
from core.strategies.strategy_layers import RSIStrategy

strategy = RSIStrategy(
    period=14,       # RSI 周期
    oversold=30,     # 超卖阈值
    overbought=70    # 超买阈值
)
```

### MACD 策略

```python
from core.strategies.strategy_layers import MACDStrategy

strategy = MACDStrategy()
```

### 布林带策略

```python
from core.strategies.strategy_layers import BollingerStrategy

strategy = BollingerStrategy()
```

---

## 完整示例

### 示例 1：聚宽量比策略

```python
import numpy as np
from core.strategies.strategy_layers import SimpleStrategy

class JQVolumeStrategy(SimpleStrategy):
    """
    聚宽量比策略
    
    买入条件：
    - 市值 20-60 亿
    - 量比 > 3
    - 大阳线（收盘 >= 开盘 * 1.03）
    - 非ST，上市 > 60 天
    
    卖出条件：
    - 收盘价跌破 MA5
    """
    
    strategy_name = "聚宽量比策略"
    required_factors = [
        'close', 'open', 'high', 'volume',
        'total_mv', 'volume_ratio', 'is_st', 'ma5', 'days_listed'
    ]
    
    def __init__(self, **kwargs):
        super().__init__()
        self.market_cap_min = kwargs.get('market_cap_min', 20_0000)  # 20亿
        self.market_cap_max = kwargs.get('market_cap_max', 60_0000)  # 60亿
        self.volume_ratio_threshold = kwargs.get('volume_ratio_threshold', 3.0)
        self.min_list_days = kwargs.get('min_list_days', 60)
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        # 获取因子
        close = factors['close']
        open_p = factors['open']
        total_mv = factors['total_mv']
        volume_ratio = factors['volume_ratio']
        is_st = factors['is_st']
        ma5 = factors['ma5']
        days_listed = factors['days_listed']
        
        # 买入条件
        buy_condition = (
            (total_mv >= self.market_cap_min) &
            (total_mv <= self.market_cap_max) &
            (volume_ratio > self.volume_ratio_threshold) &
            (is_st == 0) &
            (days_listed >= self.min_list_days) &
            (close >= open_p * 1.03)  # 大阳线
        )
        
        # 卖出条件
        sell_condition = (close < ma5) & ~np.isnan(close)
        
        # T+1 执行
        signals[1:][buy_condition[:-1]] = 1
        signals[1:][sell_condition[:-1]] = 2
        
        return signals
```

### 示例 2：多因子组合策略

```python
import numpy as np
from core.strategies.strategy_layers import SimpleStrategy
from core.strategies.utils.signal_utils import crossover, crossunder, below

class MultiFactorStrategy(SimpleStrategy):
    """多因子组合策略"""
    
    required_factors = ['close', 'ma5', 'ma10', 'rsi_14', 'macd_dif', 'macd_dea']
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        close = factors['close']
        ma5 = factors['ma5']
        ma10 = factors['ma10']
        rsi = factors['rsi_14']
        macd_dif = factors['macd_dif']
        macd_dea = factors['macd_dea']
        
        # 买入条件：金叉 + RSI 超卖 + MACD 金叉
        ma_golden = crossover(ma5, ma10)
        rsi_oversold = below(rsi[1:], 30)
        macd_golden = crossover(macd_dif, macd_dea)
        
        buy_signal = ma_golden & rsi_oversold & macd_golden
        signals[1:][buy_signal] = 1
        
        # 卖出条件：死叉
        ma_death = crossunder(ma5, ma10)
        signals[1:][ma_death] = 2
        
        return signals
```

### 示例 3：函数策略（带状态管理）

```python
from core.strategies.strategy_layers import FunctionStrategy, Position

def momentum_strategy(date: str, factors: dict, position: Position, history: list):
    """
    动量策略（带持仓天数管理）
    """
    # 买入条件
    if not position.has_position:
        if factors['close'] > factors['ma5'] and factors['volume'] > factors['volume_ma5']:
            return 'buy', 0.2
    
    # 卖出条件：持仓超过 10 天 或 跌破 MA5
    else:
        if position.holding_days >= 10 or factors['close'] < factors['ma5']:
            return 'sell', None
    
    return 'hold', None

strategy = FunctionStrategy(
    momentum_strategy,
    required_factors=['close', 'ma5', 'volume', 'volume_ma5']
)
```

---

## API 参考

### SimpleStrategy 类

```python
class SimpleStrategy(VectorizedStrategyBase):
    """
    声明式向量化策略基类
    
    属性:
        required_factors: List[str]  # 所需因子列表
        strategy_name: str           # 策略名称
    
    方法:
        _generate_signals(factors, trading_dates, stock_codes) -> np.ndarray
            # 子类必须实现
    """
```

### FunctionStrategy 类

```python
class FunctionStrategy:
    """
    函数策略
    
    参数:
        signal_func: Callable  # 信号函数
        required_factors: List[str]  # 所需因子
    
    方法:
        generate_signals(current_date, stock_pool_today, data_query) -> Dict[str, str]
        reset()  # 重置状态
    """
```

### Position 数据类

```python
@dataclass
class Position:
    """持仓状态"""
    has_position: bool = False      # 是否持仓
    shares: int = 0                 # 持仓股数
    cost_price: float = 0.0         # 成本价
    holding_days: int = 0           # 持仓天数
    unrealized_pnl: float = 0.0     # 未实现盈亏
```

### 信号矩阵说明

```python
# 信号值:
#   0 = hold（持有/观望）
#   1 = buy（买入）
#   2 = sell（卖出）

# 形状: (T, N)
#   T = 交易日数量
#   N = 股票数量

# T+1 执行逻辑:
#   signals[t, n] = 1  表示在第 t+1 天买入第 n 只股票
#   signals[t, n] = 2  表示在第 t+1 天卖出第 n 只股票
```

---

## 常见问题

### Q: 如何添加新的因子？

A: 在 `required_factors` 列表中添加因子名称即可：

```python
class MyStrategy(SimpleStrategy):
    required_factors = ['ma5', 'ma10', 'new_factor']  # 添加新因子
```

如果因子不在预计算列表中，需要在 `FactorCalculator` 中实现计算逻辑。

### Q: 如何处理 NaN 值？

A: 使用 NumPy 的 NaN 处理函数：

```python
# 检查 NaN
valid = ~np.isnan(close)

# 忽略 NaN 计算
mean_val = np.nanmean(close, axis=0)

# 填充 NaN
filled = np.nan_to_num(close, nan=0.0)
```

### Q: 如何实现止损/止盈？

A: 在策略中添加条件判断：

```python
def _generate_signals(self, factors, trading_dates, stock_codes):
    # ...
    
    # 止损：跌幅超过 8%
    stop_loss = (close / cost_price - 1) < -0.08
    
    # 止盈：涨幅超过 20%
    take_profit = (close / cost_price - 1) > 0.20
    
    sell_condition = stop_loss | take_profit
    signals[sell_condition] = 2
```

### Q: 如何进行参数优化？

A: 使用回测引擎的参数优化功能：

```python
from core.backtest.unified_engine import UnifiedBacktestEngine

engine = UnifiedBacktestEngine()

# 参数网格
param_grid = {
    'fast': [5, 10, 15],
    'slow': [20, 30, 60]
}

results = engine.optimize(
    strategy_class=DualMAStrategy,
    param_grid=param_grid,
    start_date='2020-01-01',
    end_date='2024-01-01'
)
```

### Q: 函数策略和类策略如何选择？

A: 
- **函数策略**：适合简单逻辑、需要状态管理（如持仓天数）
- **类策略**：适合复杂逻辑、需要向量化计算、性能要求高

---

## 文件结构

```
core/strategies/
├── strategy_layers.py      # 三层策略系统
├── vectorized_base.py      # 向量化策略基类
├── strategy_framework.py   # 策略框架基类
├── jq_volume_strategy_v3.py  # 示例：聚宽量比策略
├── dual_ma_strategy.py     # 示例：双均线策略
├── utils/
│   ├── signal_utils.py     # 信号工具库
│   ├── factor_calculator.py # 因子计算器
│   └── factor_loader.py    # 因子加载器
└── configs/                # YAML 配置文件
    └── dual_ma_strategy.yaml
```

---

## 更新日志

- **2024-02**: 初始版本，支持三层策略系统
- **2024-02**: 添加声明式因子系统
- **2024-02**: 添加信号工具库
