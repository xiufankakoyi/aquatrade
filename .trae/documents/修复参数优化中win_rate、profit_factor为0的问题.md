## 问题分析

在参数优化过程中，`win_rate`、`profit_factor`和`trade_count`都显示为0，经过排查发现：

1. **根本原因**：在`optimized_backtest_engine.py`中，交易记录生成时只包含基本信息（日期、股票、动作、价格、数量），但缺少`profit_loss`（盈亏）字段
2. **影响范围**：
   - `win_rate`：依赖`profit_loss > 0`的交易数量
   - `profit_factor`：依赖总盈利/总亏损
   - 所有依赖这些指标的优化目标都会失效

## 解决方案

### 修复步骤

1. **修改`optimized_backtest_engine.py`文件**：
   - 在生成交易记录时添加持仓跟踪逻辑
   - 为卖出交易计算并添加`profit_loss`字段
   - 确保`profit_loss`字段在所有相关位置都正确传递

2. **具体实现**：
   - 在`run_backtest_streaming`方法中添加持仓追踪字典
   - 在处理卖出交易时，根据持仓记录计算盈亏
   - 将计算结果添加到交易记录中
   - 确保买入交易的成本信息被正确记录

### 核心代码修改

```python
# 在run_backtest_streaming方法中添加持仓跟踪
positions_tracker = {}

# 在生成trade_record时
if action == "buy":
    # 记录买入成本
    if stock_code not in positions_tracker:
        positions_tracker[stock_code] = []
    positions_tracker[stock_code].append({
        "shares": shares,
        "entry_price": price
    })
else:  # sell
    # 计算盈亏（使用FIFO规则）
    remaining_shares = shares
    profit_loss = 0.0
    
    while remaining_shares > 0 and stock_code in positions_tracker and positions_tracker[stock_code]:
        # 获取最早的持仓
        position = positions_tracker[stock_code][0]
        sell_shares = min(remaining_shares, position["shares"])
        
        # 计算该部分持仓的盈亏
        position_profit = (price - position["entry_price"]) * sell_shares
        profit_loss += position_profit
        
        # 更新持仓
        position["shares"] -= sell_shares
        remaining_shares -= sell_shares
        
        # 如果持仓已卖完，移除该持仓记录
        if position["shares"] <= 0:
            positions_tracker[stock_code].pop(0)
    
    # 添加盈亏信息到交易记录
    trade_record["profit_loss"] = profit_loss
```

## 预期效果

1. **修复后指标正常显示**：
   - `win_rate`：正确计算盈利交易比例
   - `profit_factor`：正确计算盈利/亏损比率
   - `trade_count`：正确统计交易次数

2. **优化目标可正常使用**：
   - 支持选择`win_rate`作为优化目标
   - 支持选择`profit_factor`作为优化目标

3. **不影响现有功能**：
   - 修复后与现有代码兼容
   - 不影响其他指标计算
   - 不影响前端展示

## 测试验证

1. **单元测试**：确保盈亏计算逻辑正确
2. **集成测试**：运行完整的回测流程
3. **端到端测试**：在前端查看优化结果，确认指标正常显示

该修复方案针对根本原因，通过添加盈亏计算逻辑，确保了参数优化过程中所有相关指标都能正确计算和显示。