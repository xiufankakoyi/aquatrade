# AquaTrade 策略开发指南（数据库优先版）

## 核心理念

**策略开发的第一原则：数据库里有的数据，绝不要自己计算！**

所有技术指标（MA、RSI、MACD、KDJ、布林带等）已经在数据层预计算完成，策略只需：
1. **查询** - 从数据库获取预计算指标
2. **筛选** - 使用条件过滤股票
3. **决策** - 返回买卖信号

---

## 数据库表结构

### 1. 基础行情表 `stock_daily`

```sql
-- 可直接使用的字段
stock_code    -- 股票代码
trade_date    -- 交易日期
open          -- 开盘价
high          -- 最高价
low           -- 最低价
close         -- 收盘价
prev_close    -- 昨收价
volume        -- 成交量
amount        -- 成交额
total_mv      -- 总市值
float_mv      -- 流通市值
turnover_rate -- 换手率
turnover_free -- 自由流通换手率
volume_ratio  -- 量比
volume_ma5    -- 5日平均成交量
adj_factor    -- 复权因子

-- 预计算均线
ma5           -- 5日均线
ma10          -- 10日均线
ma20          -- 20日均线
```

### 2. 动量因子表 `factors_momentum`

```sql
-- 预计算技术指标（无需自己算）
rsi_14        -- RSI指标(14日)
kdj_k         -- KDJ的K值
kdj_d         -- KDJ的D值
kdj_j         -- KDJ的J值
macd_dif      -- MACD的DIF线
macd_dea      -- MACD的DEA线
macd_histogram-- MACD柱状图
atr_14        -- 平均真实波幅
ma5/ma10/ma20 -- 移动平均线
ma60/ma120/ma250 -- 长期均线
boll_upper    -- 布林带上轨
boll_mid      -- 布林带中轨
boll_lower    -- 布林带下轨
bias_5/10/20  -- 乖离率
```

### 3. 估值因子表 `factors_valuation`

```sql
pe            -- 市盈率
pe_ttm        -- 滚动市盈率
pb            -- 市净率
ps            -- 市销率
total_mv      -- 总市值（万元）
float_mv      -- 流通市值
dividend_yield-- 股息率
```

### 4. 股票信息表 `stock_info`

```sql
stock_code    -- 股票代码
name          -- 股票名称
industry      -- 所属行业
list_date     -- 上市日期
is_st         -- 是否ST（0/1）
is_kc         -- 是否科创板（0/1）
is_cy         -- 是否创业板（0/1）
```

### 5. 涨跌停状态表 `stock_limit_status`

```sql
stock_code    -- 股票代码
trade_date    -- 交易日期
is_limit_up   -- 是否涨停（0/1）
is_limit_down -- 是否跌停（0/1）
is_suspended  -- 是否停牌（0/1）
```

---

## 快速开始

### 最简单的策略（3分钟上手）

```python
# core/strategies/user/my_strategy.py
from core.strategies.strategy_framework import StrategyBase

class MyStrategy(StrategyBase):
    """
    示例策略：使用数据库预计算指标
    
    买入条件：
    - 收盘价 > MA20（趋势向上）
    - 量比 > 2（放量）
    - 非ST、非涨停
    
    卖出条件：
    - 收盘价 < MA5（短期走弱）
    """
    strategy_name = "我的策略"
    
    def __init__(self, name=None):
        super().__init__(name)
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        策略入口：每天调用一次
        
        参数:
            current_date: 当前日期 '2024-01-15'
            stock_pool_today: DataFrame，包含当日所有股票数据
            data_query: 数据查询对象（用于获取历史数据）
        
        返回:
            Dict[str, str]: {股票代码: 'buy'/'sell'/'hold'}
        """
        signals = {}
        
        # stock_pool_today 已经包含所有预计算指标！
        # 可用字段：open, high, low, close, ma5, ma10, ma20, volume_ratio, 
        #          is_st, is_limit_up, total_mv 等
        
        for _, row in stock_pool_today.iterrows():
            code = row['stock_code']
            
            # 买入条件（直接使用数据库字段）
            if (row['close'] > row['ma20'] and      # 收盘价 > MA20
                row['volume_ratio'] > 2.0 and       # 量比 > 2
                not row['is_st'] and                # 非ST
                not row['is_limit_up']):            # 非涨停
                signals[code] = 'buy'
            
            # 卖出条件
            elif row['close'] < row['ma5']:         # 收盘价跌破MA5
                signals[code] = 'sell'
            
            else:
                signals[code] = 'hold'
        
        return signals
```

---

## 策略开发模式

### 模式1：简单策略（推荐新手）

适用于大多数策略，直接操作 `stock_pool` DataFrame。

```python
from core.strategies.strategy_framework import StrategyBase

class SimpleStrategy(StrategyBase):
    strategy_name = "简单策略"
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        简单策略模板
        
        stock_pool_today 字段：
        - 基础行情：open, high, low, close, volume, amount
        - 预计算均线：ma5, ma10, ma20
        - 量价指标：volume_ratio, turnover_rate
        - 状态标记：is_st, is_limit_up, is_limit_down, is_suspended
        - 市值数据：total_mv, float_mv
        """
        signals = {}
        
        # 向量化操作（比循环快100倍）
        # 买入条件：均线多头排列 + 放量
        buy_mask = (
            (stock_pool_today['close'] > stock_pool_today['ma5']) &
            (stock_pool_today['ma5'] > stock_pool_today['ma10']) &
            (stock_pool_today['ma10'] > stock_pool_today['ma20']) &
            (stock_pool_today['volume_ratio'] > 1.5) &
            (~stock_pool_today['is_st']) &
            (~stock_pool_today['is_limit_up'])
        )
        
        # 卖出条件：跌破MA10
        sell_mask = stock_pool_today['close'] < stock_pool_today['ma10']
        
        # 生成信号
        for code in stock_pool_today.loc[buy_mask, 'stock_code']:
            signals[code] = 'buy'
        
        for code in stock_pool_today.loc[sell_mask, 'stock_code']:
            signals[code] = 'sell'
        
        return signals
```

### 模式2：需要额外因子时

当 `stock_pool` 中没有你需要的指标（如RSI、MACD等），从 `factors_momentum` 表查询：

```python
from core.strategies.strategy_framework import StrategyBase

class FactorStrategy(StrategyBase):
    """使用预计算因子的策略"""
    strategy_name = "因子策略"
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        """
        当需要额外因子时，从数据库查询
        """
        # 方法1：使用 data_query 查询额外因子
        # 获取当日所有股票的RSI指标
        rsi_df = data_query.query(f"""
            SELECT stock_code, rsi_14
            FROM factors_momentum
            WHERE trade_date = '{current_date}'
        """)
        
        # 合并到 stock_pool
        stock_pool = stock_pool_today.merge(
            rsi_df, on='stock_code', how='left'
        )
        
        signals = {}
        
        # 使用RSI进行决策
        for _, row in stock_pool.iterrows():
            code = row['stock_code']
            rsi = row.get('rsi_14', 50)  # 默认50
            
            if rsi < 30 and row['close'] > row['ma20']:
                signals[code] = 'buy'
            elif rsi > 70:
                signals[code] = 'sell'
            else:
                signals[code] = 'hold'
        
        return signals
```

### 模式3：需要历史数据时

```python
class HistoryStrategy(StrategyBase):
    """需要历史数据的策略"""
    strategy_name = "历史数据策略"
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        signals = {}
        
        for _, row in stock_pool_today.iterrows():
            code = row['stock_code']
            
            # 获取最近20天历史数据
            history = data_query.get_stock_history(
                stock_code=code,
                start_date='2024-01-01',  # 适当调整
                end_date=current_date,
                columns=['trade_date', 'close', 'volume', 'ma5', 'ma20']
            )
            
            if len(history) < 20:
                continue
            
            # 使用历史数据计算（尽量避免，优先用预计算指标）
            recent_trend = history['close'].iloc[-1] / history['close'].iloc[-10] - 1
            
            if recent_trend > 0.1:  # 近10天涨幅>10%
                signals[code] = 'buy'
            else:
                signals[code] = 'hold'
        
        return signals
```

---

## 可用数据字段速查

### stock_pool_today 默认字段

| 字段名 | 说明 | 类型 |
|--------|------|------|
| stock_code | 股票代码 | str |
| trade_date | 交易日期 | str |
| open | 开盘价 | float |
| high | 最高价 | float |
| low | 最低价 | float |
| close | 收盘价 | float |
| prev_close | 昨收价 | float |
| volume | 成交量 | int |
| amount | 成交额 | float |
| total_mv | 总市值 | float |
| float_mv | 流通市值 | float |
| turnover_rate | 换手率 | float |
| volume_ratio | 量比 | float |
| ma5 | 5日均线 | float |
| ma10 | 10日均线 | float |
| ma20 | 20日均线 | float |
| volume_ma5 | 5日均量 | float |
| is_st | 是否ST | bool/int |
| is_kc | 是否科创板 | bool/int |
| is_cy | 是否创业板 | bool/int |
| is_limit_up | 是否涨停 | bool/int |
| is_limit_down | 是否跌停 | bool/int |
| is_suspended | 是否停牌 | bool/int |
| list_date | 上市日期 | str |

### 需要额外查询的因子

| 因子 | 表名 | 字段名 |
|------|------|--------|
| RSI | factors_momentum | rsi_14 |
| KDJ | factors_momentum | kdj_k, kdj_d, kdj_j |
| MACD | factors_momentum | macd_dif, macd_dea, macd_histogram |
| 布林带 | factors_momentum | boll_upper, boll_mid, boll_lower |
| ATR | factors_momentum | atr_14 |
| 乖离率 | factors_momentum | bias_5, bias_10, bias_20 |
| 市盈率 | factors_valuation | pe, pe_ttm |
| 市净率 | factors_valuation | pb |

---

## 最佳实践

### 1. 优先使用向量化操作

```python
# ❌ 不好：循环遍历
for _, row in stock_pool.iterrows():
    if row['close'] > row['ma20']:
        signals[row['stock_code']] = 'buy'

# ✅ 好：向量化操作（快100倍）
buy_mask = stock_pool['close'] > stock_pool['ma20']
for code in stock_pool.loc[buy_mask, 'stock_code']:
    signals[code] = 'buy'
```

### 2. 不要重复计算指标

```python
# ❌ 不好：自己计算MA20
ma20 = history['close'].rolling(20).mean().iloc[-1]

# ✅ 好：直接使用预计算字段
ma20 = row['ma20']  # 从stock_pool获取
```

### 3. 合理使用缓存

```python
class CachedStrategy(StrategyBase):
    def __init__(self, name=None):
        super().__init__(name)
        self._rsi_cache = {}  # 缓存RSI数据
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 检查缓存
        if current_date not in self._rsi_cache:
            # 查询并缓存
            self._rsi_cache[current_date] = data_query.query(
                f"SELECT stock_code, rsi_14 FROM factors_momentum WHERE trade_date = '{current_date}'"
            )
        
        rsi_df = self._rsi_cache[current_date]
        # ... 使用缓存数据
```

### 4. 防御性编程

```python
def generate_signals(self, current_date, stock_pool_today, data_query):
    signals = {}
    
    for _, row in stock_pool_today.iterrows():
        code = row['stock_code']
        
        # ✅ 使用 .get() 避免 KeyError
        ma20 = row.get('ma20', row['close'])  # 如果没有ma20，用close代替
        volume_ratio = row.get('volume_ratio', 1.0)  # 默认1.0
        
        # ✅ 检查数据有效性
        if pd.isna(ma20) or ma20 == 0:
            continue
        
        # 决策逻辑...
    
    return signals
```

---

## 完整示例策略

### 示例1：RSI超卖反弹策略

```python
from core.strategies.strategy_framework import StrategyBase

class RSIStrategy(StrategyBase):
    """
    RSI超卖反弹策略
    
    买入：RSI < 30（超卖）且 价格 > MA20（趋势向上）
    卖出：RSI > 70（超买）
    """
    strategy_name = "RSI超卖策略"
    
    def __init__(self, name=None, rsi_buy=30, rsi_sell=70):
        super().__init__(name)
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 查询RSI因子
        rsi_df = data_query.query(f"""
            SELECT stock_code, rsi_14
            FROM factors_momentum
            WHERE trade_date = '{current_date}'
        """)
        
        # 合并数据
        df = stock_pool_today.merge(rsi_df, on='stock_code', how='left')
        
        signals = {}
        
        for _, row in df.iterrows():
            code = row['stock_code']
            rsi = row.get('rsi_14', 50)
            
            # 买入：RSI超卖 + 趋势向上
            if (rsi < self.rsi_buy and 
                row['close'] > row.get('ma20', 0) and
                not row.get('is_st', False)):
                signals[code] = {
                    'action': 'buy',
                    'weight': 0.2,
                    'score': (self.rsi_buy - rsi) / self.rsi_buy,
                    'params': {'rsi': rsi, 'reason': 'RSI超卖'}
                }
            
            # 卖出：RSI超买
            elif rsi > self.rsi_sell:
                signals[code] = 'sell'
            
            else:
                signals[code] = 'hold'
        
        return signals
```

### 示例2：多因子选股策略

```python
class MultiFactorStrategy(StrategyBase):
    """
    多因子选股策略
    
    综合使用：
    - 估值因子（PE）
    - 动量因子（RSI）
    - 量价因子（量比、均线）
    """
    strategy_name = "多因子策略"
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 查询多个因子
        factors = data_query.query(f"""
            SELECT 
                m.stock_code,
                m.rsi_14,
                m.macd_histogram,
                v.pe_ttm,
                v.pb
            FROM factors_momentum m
            JOIN factors_valuation v ON m.stock_code = v.stock_code
            WHERE m.trade_date = '{current_date}'
              AND v.trade_date = '{current_date}'
        """)
        
        # 合并数据
        df = stock_pool_today.merge(factors, on='stock_code', how='left')
        
        signals = {}
        
        # 向量化筛选条件
        buy_mask = (
            (df['rsi_14'] < 40) &              # RSI偏低
            (df['macd_histogram'] > 0) &       # MACD金叉
            (df['pe_ttm'] < 30) &              # 低PE
            (df['pb'] < 3) &                   # 低PB
            (df['close'] > df['ma20']) &       # 趋势向上
            (df['volume_ratio'] > 1.5) &       # 放量
            (~df['is_st'])                     # 非ST
        )
        
        sell_mask = (
            (df['rsi_14'] > 70) |              # RSI超买
            (df['macd_histogram'] < 0)         # MACD死叉
        )
        
        # 生成信号
        for code in df.loc[buy_mask, 'stock_code']:
            signals[code] = 'buy'
        
        for code in df.loc[sell_mask, 'stock_code']:
            signals[code] = 'sell'
        
        return signals
```

### 示例3：趋势跟踪策略

```python
class TrendFollowingStrategy(StrategyBase):
    """
    趋势跟踪策略
    
    使用预计算均线判断趋势
    """
    strategy_name = "趋势跟踪策略"
    
    def __init__(self, name=None):
        super().__init__(name)
        self.execution_price = {
            "buy": "close",   # 收盘买入
            "sell": "open"    # 开盘卖出
        }
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        signals = {}
        
        for _, row in stock_pool_today.iterrows():
            code = row['stock_code']
            
            # 获取均线
            close = row['close']
            ma5 = row.get('ma5', close)
            ma20 = row.get('ma20', close)
            ma60 = row.get('ma60', close)  # 可能需要额外查询
            
            # 判断趋势
            short_trend = close > ma5 > ma20
            
            # 买入：短期趋势向上 + 放量突破
            if (short_trend and 
                row.get('volume_ratio', 1) > 2 and
                close > row.get('prev_close', close) * 1.03):  # 涨幅>3%
                signals[code] = {
                    'action': 'buy',
                    'weight': 0.25,
                    'score': close / ma20,
                    'params': {
                        'trend': 'up',
                        'volume_ratio': row.get('volume_ratio', 1)
                    }
                }
            
            # 卖出：跌破MA10或趋势反转
            elif close < row.get('ma10', close * 0.95):
                signals[code] = 'sell'
            
            else:
                signals[code] = 'hold'
        
        return signals
```

---

## 调试技巧

### 1. 查看可用字段

```python
def generate_signals(self, current_date, stock_pool_today, data_query):
    # 打印可用字段
    print("可用字段:", stock_pool_today.columns.tolist())
    print("数据样例:", stock_pool_today.head(1).to_dict('records'))
    
    # ... 策略逻辑
```

### 2. 验证数据质量

```python
def generate_signals(self, current_date, stock_pool_today, data_query):
    # 检查关键字段
    required_cols = ['close', 'ma5', 'ma20', 'volume_ratio']
    missing = [c for c in required_cols if c not in stock_pool_today.columns]
    if missing:
        print(f"警告：缺少字段 {missing}")
    
    # 检查数据完整性
    null_counts = stock_pool_today[required_cols].isnull().sum()
    if null_counts.any():
        print(f"空值统计:\n{null_counts}")
    
    # ... 策略逻辑
```

### 3. 记录信号详情

```python
def generate_signals(self, current_date, stock_pool_today, data_query):
    signals = {}
    buy_count = 0
    sell_count = 0
    
    for _, row in stock_pool_today.iterrows():
        code = row['stock_code']
        
        if self._should_buy(row):
            signals[code] = 'buy'
            buy_count += 1
            # 记录买入理由
            print(f"[BUY] {code} @ {current_date}: close={row['close']:.2f}, ma20={row['ma20']:.2f}")
        
        elif self._should_sell(row):
            signals[code] = 'sell'
            sell_count += 1
    
    print(f"[{current_date}] 买入:{buy_count} 卖出:{sell_count}")
    return signals
```

---

## 常见问题

**Q: stock_pool 中没有我需要的指标怎么办？**
A: 使用 `data_query.query()` 从 `factors_momentum` 或 `factors_valuation` 表查询。

**Q: 如何获取历史均线数据？**
A: 使用 `data_query.get_stock_history()` 获取历史数据，其中已包含预计算均线。

**Q: 策略运行很慢怎么办？**
A: 
1. 使用向量化操作替代循环
2. 避免重复查询相同数据（使用缓存）
3. 不要自己计算指标，使用预计算字段

**Q: 如何知道哪些指标已经预计算？**
A: 查看本文档的「数据库表结构」章节，或直接在策略中打印 `stock_pool_today.columns`。

---

## 参考文件

- `core/strategies/strategy_framework.py` - 策略基类
- `data_svc/database/questdb_manager.py` - 数据库表结构定义
- `data_svc/database/optimized_data_query.py` - 数据查询接口
- `core/strategies/jq_volume_strategy.py` - 生产级策略示例
