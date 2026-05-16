"""
回测准确性调试 - 逐笔交易对比

聚宽全市场结果：
- 策略收益：-34.29%
- 最大回撤：45.03%
- Sharpe：-1.60

我们的结果：
- 策略收益：-48.26%
- 最大回撤：53.73%
- Sharpe：-2.41

差异：约14%的收益差距
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5


def debug_backtest():
    """详细调试回测过程"""
    print("\n" + "=" * 80)
    print("回测准确性详细调试")
    print("=" * 80)
    
    # 加载数据
    print("\n加载数据...")
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2023-01-01",
        "2023-12-31",
        required_fields=['open', 'high', 'low', 'close', 'volume']
    )
    
    if matrix_data is None:
        print("❌ 数据加载失败")
        return
    
    matrices = matrix_data['matrices']
    trading_dates = matrix_data['trading_dates']
    stock_codes = matrix_data['stock_codes']
    T = matrix_data['T']
    N = matrix_data['N']
    
    print(f"数据维度: {T} 天 x {N} 只股票")
    
    # 提取数据
    close_prices = matrices['close']
    open_prices = matrices['open']
    
    # 过滤有效股票
    valid_indices = []
    for i in range(N):
        col = close_prices[:, i]
        if np.sum(~np.isnan(col)) >= 20:
            valid_indices.append(i)
    
    N_valid = len(valid_indices)
    print(f"有效股票: {N_valid} 只")
    
    close_prices = close_prices[:, valid_indices]
    open_prices = open_prices[:, valid_indices]
    valid_codes = [str(stock_codes[i]) for i in valid_indices]
    
    # 计算MA
    print("\n计算MA5和MA10...")
    ma5 = np.zeros((T, N_valid))
    ma10 = np.zeros((T, N_valid))
    
    for i in range(N_valid):
        col = close_prices[:, i]
        for t in range(4, T):
            ma5[t, i] = np.mean(col[t-4:t+1])
        for t in range(9, T):
            ma10[t, i] = np.mean(col[t-9:t+1])
    
    # 回测参数
    initial_capital = 100000
    commission_rate = 0.0003
    max_holdings = 5
    
    cash = initial_capital
    positions = {}  # {idx: shares}
    daily_values = []
    trades = []
    
    print("\n运行回测...")
    print(f"{'日期':<12} {'操作':<6} {'代码':<10} {'价格':<10} {'数量':<10} {'市值':<12} {'现金':<12}")
    print("-" * 90)
    
    for t in range(2, T):  # 从第3天开始，确保有足够MA数据
        date = trading_dates[t]
        today_open = open_prices[t]
        today_close = close_prices[t]
        
        # 计算当前市值
        position_value = sum(
            positions.get(i, 0) * today_close[i]
            for i in positions
            if not np.isnan(today_close[i])
        )
        total_value = cash + position_value
        daily_values.append(total_value)
        
        # 检查卖出（死叉）- T-2和T-1的MA判断，T日执行
        to_sell = []
        for i in list(positions.keys()):
            if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                continue
            if np.isnan(ma5[t-2, i]) or np.isnan(ma10[t-2, i]):
                continue
            
            # 死叉：T-2日MA5>=MA10，T-1日MA5<MA10
            if ma5[t-2, i] >= ma10[t-2, i] and ma5[t-1, i] < ma10[t-1, i]:
                if not np.isnan(today_open[i]) and today_open[i] > 0:
                    to_sell.append(i)
        
        for i in to_sell:
            if i in positions:
                shares = positions[i]
                price = today_open[i]
                value = shares * price
                commission = value * commission_rate
                cash += value - commission
                
                trades.append({
                    'date': date, 'action': '卖出', 'code': valid_codes[i],
                    'price': price, 'shares': shares, 'value': value
                })
                
                if len(trades) <= 20:
                    print(f"{date:<12} {'卖出':<6} {valid_codes[i]:<10} {price:<10.2f} {shares:<10} {position_value:<12.2f} {cash:<12.2f}")
                
                del positions[i]
        
        # 检查买入（金叉）
        if len(positions) < max_holdings:
            buy_candidates = []
            for i in range(N_valid):
                if i in positions:
                    continue
                if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                    continue
                if np.isnan(ma5[t-2, i]) or np.isnan(ma10[t-2, i]):
                    continue
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                
                # 金叉：T-2日MA5<=MA10，T-1日MA5>MA10
                if ma5[t-2, i] <= ma10[t-2, i] and ma5[t-1, i] > ma10[t-1, i]:
                    buy_candidates.append(i)
            
            n_to_buy = min(len(buy_candidates), max_holdings - len(positions))
            if n_to_buy > 0:
                cash_per_stock = cash * 0.95 / n_to_buy
                
                for i in buy_candidates[:n_to_buy]:
                    price = today_open[i]
                    shares = int(cash_per_stock / price / 100) * 100
                    
                    if shares > 0:
                        cost = shares * price
                        commission = cost * commission_rate
                        total_cost = cost + commission
                        
                        if total_cost <= cash:
                            positions[i] = shares
                            cash -= total_cost
                            
                            trades.append({
                                'date': date, 'action': '买入', 'code': valid_codes[i],
                                'price': price, 'shares': shares, 'value': cost
                            })
                            
                            if len(trades) <= 20:
                                print(f"{date:<12} {'买入':<6} {valid_codes[i]:<10} {price:<10.2f} {shares:<10} {position_value:<12.2f} {cash:<12.2f}")
                            
                            if len(positions) >= max_holdings:
                                break
    
    # 计算指标
    final_value = daily_values[-1] if daily_values else initial_capital
    total_return = (final_value - initial_capital) / initial_capital
    
    peak = daily_values[0]
    max_drawdown = 0
    for v in daily_values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    returns = [(daily_values[i] - daily_values[i-1]) / daily_values[i-1] 
               for i in range(1, len(daily_values))]
    volatility = np.std(returns) * np.sqrt(252) if returns else 0
    sharpe = (total_return / (len(daily_values) / 252) - 0.03) / volatility if volatility > 0 else 0
    
    # 打印结果
    print("\n" + "=" * 80)
    print("回测结果对比")
    print("=" * 80)
    print(f"\n{'指标':<15} {'聚宽（全市场）':<15} {'Aquatrade':<15} {'差异':<15}")
    print("-" * 60)
    print(f"{'策略收益':<15} {'-34.29%':<15} {f'{total_return*100:.2f}%':<15} {f'{total_return*100+34.29:+.2f}%':<15}")
    print(f"{'最大回撤':<15} {'45.03%':<15} {f'{max_drawdown*100:.2f}%':<15} {f'{max_drawdown*100-45.03:+.2f}%':<15}")
    print(f"{'Sharpe':<15} {'-1.60':<15} {f'{sharpe:.2f}':<15} {f'{sharpe+1.60:+.2f}':<15}")
    print(f"{'交易次数':<15} {'-':<15} {len(trades):<15}")
    
    print("\n" + "=" * 80)
    print("可能的问题分析：")
    print("=" * 80)
    print("1. 股票代码显示不正常（显示1, 10, 100等）- 可能是索引而非真实代码")
    print("2. 需要检查MA计算是否正确")
    print("3. 需要检查T+1执行逻辑是否正确")
    print("4. 聚宽可能有额外的过滤条件（如排除ST、次新股等）")
    print("=" * 80)


if __name__ == "__main__":
    debug_backtest()
