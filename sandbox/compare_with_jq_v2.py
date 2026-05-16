"""
与聚宽回测结果对比 - 完全匹配版

聚宽全市场策略的关键逻辑：
1. 股票池：全市场
2. 过滤：排除ST、停牌、次新股（上市不足60天）
3. MA计算：使用收盘价
4. 信号：金叉买入，死叉卖出
5. 执行：T+1（信号产生后次日开盘成交）
6. 仓位：最多持仓5只，均分资金
7. 佣金：买入0.03%，卖出0.03%+0.1%印花税

聚宽全市场数据：
- 策略收益：-34.29%
- 最大回撤：45.03%
- Sharpe：-1.60
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
import polars as pl
from pathlib import Path


def get_stock_filter_info():
    """直接从parquet读取股票过滤信息"""
    info_path = Path("data/parquet_data/stock_info.parquet")
    if not info_path.exists():
        return None
    
    df = pl.read_parquet(info_path)
    
    # ST股票
    st_df = df.filter(pl.col('is_st') == 1)
    st_codes = set(st_df['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    # 次新股（2022-11-01后上市）
    new_df = df.filter(pl.col('list_date') > 20221101)
    new_codes = set(new_df['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    return st_codes, new_codes


def run_matched_backtest():
    """完全匹配聚宽逻辑的回测"""
    print("\n" + "=" * 70)
    print("聚宽 vs Aquatrade 回测对比（完全匹配版）")
    print("=" * 70)
    
    # 聚宽结果（全市场）
    jq_results = {
        '策略收益': -34.29,
        '最大回撤': 45.03,
        'Sharpe': -1.60
    }
    
    print("\n聚宽回测结果（2023.1.1-2023.12.31，资金10万，全市场）：")
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
    
    # 获取股票过滤信息
    print("构建过滤条件...")
    filter_info = get_stock_filter_info()
    
    if filter_info:
        st_codes, new_stock_codes = filter_info
    else:
        st_codes = set()
        new_stock_codes = set()
    
    print(f"  ST股票: {len(st_codes)} 只")
    print(f"  次新股: {len(new_stock_codes)} 只")
    
    # 过滤有效股票
    close_prices = matrices['close']
    open_prices = matrices['open']
    
    valid_indices = []
    valid_codes = []
    
    for i, code in enumerate(stock_codes):
        code_str = str(code)
        
        # 排除ST
        if code_str in st_codes:
            continue
        
        # 排除次新股
        if code_str in new_stock_codes:
            continue
        
        # 检查数据有效性
        col = close_prices[:, i]
        if np.sum(~np.isnan(col)) >= 20:
            valid_indices.append(i)
            valid_codes.append(code_str)
    
    N_valid = len(valid_indices)
    print(f"  有效股票: {N_valid} 只")
    
    # 提取数据
    close_prices = close_prices[:, valid_indices]
    open_prices = open_prices[:, valid_indices]
    
    # 计算MA
    print("计算MA...")
    ma5 = np.zeros((T, N_valid))
    ma10 = np.zeros((T, N_valid))
    
    for i in range(N_valid):
        col = close_prices[:, i]
        for t in range(4, T):
            ma5[t, i] = np.mean(col[t-4:t+1])
        for t in range(9, T):
            ma10[t, i] = np.mean(col[t-9:t+1])
    
    # 回测参数（匹配聚宽）
    initial_capital = 100000
    commission_rate = 0.0003  # 佣金
    stamp_tax = 0.001  # 印花税（卖出时）
    max_holdings = 5
    
    cash = initial_capital
    positions = {}
    daily_values = []
    trades = []
    
    print("运行回测...")
    
    for t in range(2, T):
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
        
        # 卖出（死叉）
        to_sell = []
        for i in list(positions.keys()):
            if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                continue
            if np.isnan(ma5[t-2, i]) or np.isnan(ma10[t-2, i]):
                continue
            
            if ma5[t-2, i] >= ma10[t-2, i] and ma5[t-1, i] < ma10[t-1, i]:
                if not np.isnan(today_open[i]) and today_open[i] > 0:
                    to_sell.append(i)
        
        for i in to_sell:
            if i in positions:
                shares = positions[i]
                price = today_open[i]
                value = shares * price
                # 卖出费用：佣金 + 印花税
                fee = value * (commission_rate + stamp_tax)
                cash += value - fee
                del positions[i]
                trades.append({'date': date, 'action': '卖出', 'code': valid_codes[i]})
        
        # 买入（金叉）
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
                        fee = cost * commission_rate
                        total_cost = cost + fee
                        
                        if total_cost <= cash:
                            positions[i] = shares
                            cash -= total_cost
                            trades.append({'date': date, 'action': '买入', 'code': valid_codes[i]})
                            
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
    print("\n" + "=" * 70)
    print("回测结果对比")
    print("=" * 70)
    print(f"\n{'指标':<15} {'聚宽':<15} {'Aquatrade':<15} {'差异':<15}")
    print("-" * 60)
    print(f"{'策略收益':<15} {jq_results['策略收益']}%{'':<8} {total_return*100:.2f}%{'':<8} {total_return*100-jq_results['策略收益']:+.2f}%")
    print(f"{'最大回撤':<15} {jq_results['最大回撤']}%{'':<8} {max_drawdown*100:.2f}%{'':<8} {max_drawdown*100-jq_results['最大回撤']:+.2f}%")
    print(f"{'Sharpe':<15} {jq_results['Sharpe']:<15} {sharpe:.2f}{'':<11} {sharpe-jq_results['Sharpe']:+.2f}")
    print(f"{'交易次数':<15} {'-':<15} {len(trades):<15}")
    
    diff = abs(total_return*100 - jq_results['策略收益'])
    print("\n" + "=" * 70)
    if diff < 5:
        print(f"✅ 收益率差异 {diff:.2f}% 在可接受范围内")
    else:
        print(f"⚠️ 收益率差异 {diff:.2f}% 仍然较大")
        print("\n可能原因：")
        print("  1. 复权方式不同 - 聚宽使用动态复权")
        print("  2. 停牌处理不同 - 我们用价格无效判断")
        print("  3. 涨跌停处理 - 聚宽可能跳过涨跌停")
    print("=" * 70)


if __name__ == "__main__":
    run_matched_backtest()
