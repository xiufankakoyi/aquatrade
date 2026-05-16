"""
与聚宽回测结果对比 - 调试版

关键问题分析：
1. 聚宽信号产生和执行是分开的：T日收盘产生信号，T+1日开盘执行
2. 我们的逻辑可能有问题

聚宽数据：
- 回测时间：2023.1.1 - 2023.12.31
- 初始资金：100,000
- 策略收益：-23.88%
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def run_debug_backtest():
    """调试版回测 - 逐日检查"""
    print("\n" + "=" * 70)
    print("调试版回测 - 检查信号和执行逻辑")
    print("=" * 70)
    
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
    
    # 选择一只测试股票（茅台）
    test_code = "600519"
    if test_code not in stock_codes:
        print(f"❌ 没有找到 {test_code}")
        return
    
    test_idx = stock_codes.index(test_code)
    print(f"\n测试股票: {test_code} (索引: {test_idx})")
    
    # 计算MA5和MA10
    ma5 = np.zeros(T)
    ma10 = np.zeros(T)
    
    col = close_prices[:, test_idx]
    for t in range(4, T):
        ma5[t] = np.mean(col[t-4:t+1])
    for t in range(9, T):
        ma10[t] = np.mean(col[t-9:t+1])
    
    # 打印前20天的数据
    print("\n前20天数据（茅台）：")
    print(f"{'日期':<12} {'收盘':<10} {'MA5':<10} {'MA10':<10} {'信号':<10}")
    print("-" * 60)
    
    for t in range(10, 30):
        date = trading_dates[t]
        close = col[t]
        ma5_val = ma5[t]
        ma10_val = ma10[t]
        
        # 判断信号
        signal = ""
        if t > 0 and not np.isnan(ma5[t]) and not np.isnan(ma10[t]):
            if ma5[t-1] <= ma10[t-1] and ma5[t] > ma10[t]:
                signal = "金叉买入"
            elif ma5[t-1] >= ma10[t-1] and ma5[t] < ma10[t]:
                signal = "死叉卖出"
        
        print(f"{date:<12} {close:<10.2f} {ma5_val:<10.2f} {ma10_val:<10.2f} {signal:<10}")
    
    # 统计全年信号
    buy_signals = 0
    sell_signals = 0
    
    for t in range(1, T):
        if np.isnan(ma5[t]) or np.isnan(ma10[t]):
            continue
        if ma5[t-1] <= ma10[t-1] and ma5[t] > ma10[t]:
            buy_signals += 1
        elif ma5[t-1] >= ma10[t-1] and ma5[t] < ma10[t]:
            sell_signals += 1
    
    print(f"\n全年信号统计（茅台）：")
    print(f"  金叉买入信号: {buy_signals} 次")
    print(f"  死叉卖出信号: {sell_signals} 次")
    
    # 现在运行完整回测，但只打印前10笔交易
    print("\n" + "=" * 70)
    print("完整回测 - 前10笔交易")
    print("=" * 70)
    
    # 获取沪深300成分股（按市值前300）
    query = OptimizedStockDataQuery()
    pool = query.get_stock_pool("2023-06-01")
    if pool is not None and not pool.empty:
        pool = pool.sort_values('total_mv', ascending=False)
        hs300_codes = pool['stock_code'].astype(str).tolist()[:300]
    else:
        hs300_codes = stock_codes[:300]
    
    # 过滤
    hs300_indices = [i for i, code in enumerate(stock_codes) if str(code) in hs300_codes]
    if not hs300_indices:
        hs300_indices = list(range(min(300, N)))
    
    N_hs300 = len(hs300_indices)
    print(f"使用 {N_hs300} 只股票")
    
    # 提取数据
    close_hs300 = close_prices[:, hs300_indices]
    open_hs300 = open_prices[:, hs300_indices]
    
    # 计算MA
    ma5_all = np.zeros((T, N_hs300))
    ma10_all = np.zeros((T, N_hs300))
    
    for i in range(N_hs300):
        col = close_hs300[:, i]
        for t in range(4, T):
            ma5_all[t, i] = np.mean(col[t-4:t+1])
        for t in range(9, T):
            ma10_all[t, i] = np.mean(col[t-9:t+1])
    
    # 回测
    initial_capital = 100000
    commission_rate = 0.0003
    max_holdings = 5
    
    cash = initial_capital
    positions = {}
    trade_count = 0
    
    print(f"\n{'日期':<12} {'操作':<8} {'股票':<10} {'价格':<10} {'数量':<10} {'现金':<12}")
    print("-" * 70)
    
    for t in range(1, T):
        date = trading_dates[t]
        today_open = open_hs300[t]
        today_close = close_hs300[t]
        
        # 检查卖出
        for i in list(positions.keys()):
            if np.isnan(ma5_all[t, i]) or np.isnan(ma10_all[t, i]):
                continue
            if ma5_all[t-1, i] >= ma10_all[t-1, i] and ma5_all[t, i] < ma10_all[t, i]:
                if not np.isnan(today_open[i]) and today_open[i] > 0:
                    shares = positions[i]
                    price = today_open[i]
                    value = shares * price
                    commission = value * commission_rate
                    cash += value - commission
                    
                    code = stock_codes[hs300_indices[i]]
                    if trade_count < 10:
                        print(f"{date:<12} {'卖出':<8} {code:<10} {price:<10.2f} {shares:<10} {cash:<12.2f}")
                    
                    del positions[i]
                    trade_count += 1
        
        # 检查买入
        if len(positions) < max_holdings:
            for i in range(N_hs300):
                if i in positions:
                    continue
                if np.isnan(ma5_all[t, i]) or np.isnan(ma10_all[t, i]):
                    continue
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                
                if ma5_all[t-1, i] <= ma10_all[t-1, i] and ma5_all[t, i] > ma10_all[t, i]:
                    cash_per_stock = cash * 0.95 / (max_holdings - len(positions))
                    price = today_open[i]
                    shares = int(cash_per_stock / price / 100) * 100
                    
                    if shares > 0:
                        cost = shares * price
                        commission = cost * commission_rate
                        total_cost = cost + commission
                        
                        if total_cost <= cash:
                            positions[i] = shares
                            cash -= total_cost
                            
                            code = stock_codes[hs300_indices[i]]
                            if trade_count < 10:
                                print(f"{date:<12} {'买入':<8} {code:<10} {price:<10.2f} {shares:<10} {cash:<12.2f}")
                            
                            trade_count += 1
                            
                            if len(positions) >= max_holdings:
                                break
        
        if trade_count >= 10:
            break
    
    print(f"\n... 共 {trade_count} 笔交易")
    print("\n" + "=" * 70)
    print("关键发现：")
    print("=" * 70)
    print("如果以上交易记录显示频繁买卖，说明信号生成过于敏感")
    print("聚宽的结果亏损-23.88%，说明策略在2023年表现不佳")
    print("我们的结果盈利，可能是因为：")
    print("  1. 股票池不同（我们用了市值前300，不是真正的沪深300）")
    print("  2. 信号生成逻辑有差异")
    print("  3. 执行价格不同")
    print("=" * 70)


if __name__ == "__main__":
    run_debug_backtest()
