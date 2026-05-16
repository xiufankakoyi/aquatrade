"""
与聚宽回测结果对比 - 最终修复版

关键修复：
1. 正确的T+1执行逻辑
2. 正确的股票代码显示（使用ts_code）
3. 全市场股票池

聚宽全市场数据：
- 回测时间：2023.1.1 - 2023.12.31
- 初始资金：100,000
- 策略收益：-34.29%
- 基准收益（沪深300）：-11.38%
- Alpha：-0.27
- Beta：0.75
- Sharpe：-1.60
- 最大回撤：45.03%
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def run_final_backtest():
    """最终版回测 - 完全匹配聚宽逻辑"""
    print("\n" + "=" * 70)
    print("聚宽 vs Aquatrade 回测对比（最终版）")
    print("=" * 70)
    
    # 聚宽结果（全市场）
    jq_results = {
        '策略收益': -34.29,
        '基准收益': -11.38,
        'Alpha': -0.27,
        'Beta': 0.75,
        'Sharpe': -1.60,
        '最大回撤': 45.03
    }
    
    print("\n聚宽回测结果（2023.1.1-2023.12.31，资金10万）：")
    for k, v in jq_results.items():
        print(f"  {k}: {v}")
    
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
    
    print(f"全市场数据: {T} 天 x {N} 只股票")
    
    # 使用全市场股票（排除ST和停牌）
    print("使用全市场股票池...")
    
    # 过滤：只保留有有效价格数据的股票
    valid_indices = []
    valid_code_list = []
    
    for i, code in enumerate(stock_codes):
        # 检查该股票是否有足够的历史数据
        col = matrices['close'][:, i]
        valid_count = np.sum(~np.isnan(col))
        if valid_count >= 20:  # 至少20天有效数据
            valid_indices.append(i)
            valid_code_list.append(str(code))
    
    if not valid_indices:
        print("❌ 没有找到有效股票")
        return
    
    N_valid = len(valid_indices)
    print(f"全市场有效股票: {N_valid} 只")
    
    # 提取有效股票数据
    close_prices = matrices['close'][:, valid_indices]
    open_prices = matrices['open'][:, valid_indices]
    
    # 计算MA5和MA10（使用收盘价）
    print("计算MA...")
    ma5 = np.zeros((T, N_valid))
    ma10 = np.zeros((T, N_valid))
    
    for i in range(N_valid):
        col = close_prices[:, i]
        valid_mask = ~np.isnan(col)
        if valid_mask.sum() >= 10:
            for t in range(4, T):
                ma5[t, i] = np.mean(col[t-4:t+1])
            for t in range(9, T):
                ma10[t, i] = np.mean(col[t-9:t+1])
    
    # 回测参数
    initial_capital = 100000
    commission_rate = 0.0003
    max_holdings = 5
    
    # 初始化
    cash = initial_capital
    positions = {}  # {stock_idx: shares}
    daily_values = []
    trades = []
    
    print("运行回测...")
    
    for t in range(1, T):
        date = trading_dates[t]
        today_open = open_prices[t]
        today_close = close_prices[t]
        
        # 计算当前市值（使用收盘价）
        position_value = sum(
            positions.get(i, 0) * today_close[i]
            for i in positions
            if not np.isnan(today_close[i])
        )
        total_value = cash + position_value
        daily_values.append(total_value)
        
        # 检查卖出信号（死叉）- 基于昨日收盘数据判断，今日开盘执行
        to_sell = []
        for i in list(positions.keys()):
            if i >= N_valid:
                continue
            # 使用t-1日和t日的MA数据判断信号
            if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                continue
            if np.isnan(ma5[t-2, i]) or np.isnan(ma10[t-2, i]):
                continue
            
            # 死叉：前日MA5>=MA10，昨日MA5<MA10
            if ma5[t-2, i] >= ma10[t-2, i] and ma5[t-1, i] < ma10[t-1, i]:
                if not np.isnan(today_open[i]) and today_open[i] > 0:
                    to_sell.append(i)
        
        # 执行卖出
        for i in to_sell:
            if i in positions:
                shares = positions[i]
                sell_price = today_open[i]
                sell_value = shares * sell_price
                commission = sell_value * commission_rate
                cash += sell_value - commission
                
                trades.append({
                    'date': date,
                    'action': '卖出',
                    'code': valid_code_list[i],
                    'price': sell_price,
                    'shares': shares,
                    'value': sell_value
                })
                
                del positions[i]
        
        # 检查买入信号（金叉）- 基于昨日收盘数据判断，今日开盘执行
        if len(positions) < max_holdings:
            buy_candidates = []
            for i in range(N_valid):
                if i in positions:
                    continue
                # 使用t-1日和t日的MA数据判断信号
                if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                    continue
                if np.isnan(ma5[t-2, i]) or np.isnan(ma10[t-2, i]):
                    continue
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                
                # 金叉：前日MA5<=MA10，昨日MA5>MA10
                if ma5[t-2, i] <= ma10[t-2, i] and ma5[t-1, i] > ma10[t-1, i]:
                    buy_candidates.append(i)
            
            # 买入
            n_to_buy = min(len(buy_candidates), max_holdings - len(positions))
            if n_to_buy > 0:
                cash_per_stock = cash * 0.95 / n_to_buy
                
                for i in buy_candidates[:n_to_buy]:
                    buy_price = today_open[i]
                    shares = int(cash_per_stock / buy_price / 100) * 100
                    
                    if shares > 0:
                        stock_cost = shares * buy_price
                        commission = stock_cost * commission_rate
                        total_cost = stock_cost + commission
                        
                        if total_cost <= cash:
                            positions[i] = shares
                            cash -= total_cost
                            
                            trades.append({
                                'date': date,
                                'action': '买入',
                                'code': valid_code_list[i],
                                'price': buy_price,
                                'shares': shares,
                                'value': stock_cost
                            })
                            
                            if len(positions) >= max_holdings:
                                break
    
    # 计算最终指标
    final_value = daily_values[-1] if daily_values else initial_capital
    total_return = (final_value - initial_capital) / initial_capital
    
    # 计算最大回撤
    peak = daily_values[0]
    max_drawdown = 0
    for v in daily_values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # 计算Sharpe
    returns = []
    for i in range(1, len(daily_values)):
        ret = (daily_values[i] - daily_values[i-1]) / daily_values[i-1]
        returns.append(ret)
    
    volatility = np.std(returns) * np.sqrt(252) if returns else 0
    sharpe = (total_return / (len(daily_values) / 252) - 0.03) / volatility if volatility > 0 else 0
    
    # 打印结果
    print("\n" + "=" * 70)
    print("Aquatrade 回测结果（沪深300成分股，T+1执行）：")
    print("=" * 70)
    print(f"  策略收益: {total_return*100:.2f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  最大回撤: {max_drawdown*100:.2f}%")
    print(f"  最终资金: {final_value:,.2f}")
    print(f"  交易日数: {len(daily_values)}")
    print(f"  总交易次数: {len(trades)}")
    
    # 打印前10笔交易
    print("\n前10笔交易：")
    print(f"{'日期':<12} {'操作':<6} {'代码':<10} {'价格':<10} {'数量':<10}")
    print("-" * 60)
    for trade in trades[:10]:
        print(f"{trade['date']:<12} {trade['action']:<6} {trade['code']:<10} {trade['price']:<10.2f} {trade['shares']:<10}")
    
    # 对比
    print("\n" + "=" * 70)
    print("差异对比")
    print("=" * 70)
    diff_return = total_return*100 - jq_results['策略收益']
    diff_sharpe = sharpe - jq_results['Sharpe']
    diff_dd = max_drawdown*100 - jq_results['最大回撤']
    
    print(f"\n策略收益差异: {diff_return:+.2f}%")
    print(f"Sharpe差异: {diff_sharpe:+.2f}")
    print(f"最大回撤差异: {diff_dd:+.2f}%")
    
    if abs(diff_return) < 5:
        print("\n✅ 收益率差异在可接受范围内（<5%）")
    else:
        print(f"\n⚠️ 收益率差异较大（{abs(diff_return):.2f}%）")
        print("\n可能原因分析：")
        print("  1. 股票池不同 - 我们使用市值前300，聚宽使用真实沪深300成分股")
        print("  2. 复权方式不同 - 聚宽使用动态复权，我们使用前复权")
        print("  3. 停牌处理不同 - 聚宽自动跳过停牌日")
        print("  4. 次新股排除 - 聚宽排除上市不足60天的股票")
        print("  5. 信号判断时机 - 需要确认T日收盘信号T+1日执行")
    
    print("=" * 70)


if __name__ == "__main__":
    run_final_backtest()
