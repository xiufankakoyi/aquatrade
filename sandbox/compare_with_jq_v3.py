"""
与聚宽回测结果对比 - 精确匹配版

聚宽策略关键逻辑：
1. 每天开盘(09:30)运行
2. history获取的是昨天及之前的数据（开盘时当天还没收盘）
3. MA5 = hist.iloc[-5:].mean() = T-5到T-1的收盘价均值
4. MA5_prev = hist.iloc[-6:-1].mean() = T-6到T-2的收盘价均值
5. 金叉：MA5_prev <= MA10_prev 且 MA5 > MA10
6. 执行：当天开盘价成交
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
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
    
    # 次新股（上市不足60天，相对于2023-01-01）
    # 2023-01-01 前60天 = 2022-11-02
    cutoff_int = 20221102
    new_df = df.filter(pl.col('list_date') > cutoff_int)
    new_codes = set(new_df['stock_code'].cast(pl.Utf8).str.zfill(6).to_list())
    
    return st_codes, new_codes


def run_matched_backtest():
    """精确匹配聚宽逻辑的回测"""
    print("\n" + "=" * 70)
    print("聚宽 vs Aquatrade 回测对比（精确匹配版）")
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
        required_fields=['open', 'close'],
        use_adj_price=False  # 聚宽用不复权价格计算MA
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
    
    # 计算MA（匹配聚宽逻辑）
    print("计算MA（聚宽方式）...")
    
    # 聚宽的MA计算：
    # 在T日开盘时，history返回的是T-1及之前的数据
    # MA5 = hist.iloc[-5:].mean() = close[T-5:T]的均值（T-5,T-4,T-3,T-2,T-1）
    # MA5_prev = hist.iloc[-6:-1].mean() = close[T-6:T-1]的均值（T-6,T-5,T-4,T-3,T-2）
    
    ma5 = np.full((T, N_valid), np.nan)
    ma10 = np.full((T, N_valid), np.nan)
    ma5_prev = np.full((T, N_valid), np.nan)
    ma10_prev = np.full((T, N_valid), np.nan)
    
    for t in range(11, T):  # 从第12天开始（确保有足够数据）
        for i in range(N_valid):
            # MA5 = T-5到T-1的收盘价均值（5天）
            if not np.any(np.isnan(close_prices[t-5:t, i])):
                ma5[t, i] = np.mean(close_prices[t-5:t, i])
            
            # MA10 = T-10到T-1的收盘价均值（10天）
            if not np.any(np.isnan(close_prices[t-10:t, i])):
                ma10[t, i] = np.mean(close_prices[t-10:t, i])
            
            # MA5_prev = T-6到T-2的收盘价均值（5天）
            if not np.any(np.isnan(close_prices[t-6:t-1, i])):
                ma5_prev[t, i] = np.mean(close_prices[t-6:t-1, i])
            
            # MA10_prev = T-11到T-2的收盘价均值（10天）
            if not np.any(np.isnan(close_prices[t-11:t-1, i])):
                ma10_prev[t, i] = np.mean(close_prices[t-11:t-1, i])
    
    # 回测参数（匹配聚宽）
    initial_capital = 100000
    commission_rate = 0.0003  # 佣金
    stamp_tax = 0.001  # 印花税（卖出时）
    min_commission = 5  # 最低佣金
    max_holdings = 5
    
    cash = initial_capital
    positions = {}  # {idx: shares}
    daily_values = []
    trades = []
    
    print("运行回测...")
    
    for t in range(11, T):  # 从第12天开始
        date = trading_dates[t]
        today_open = open_prices[t]
        today_close = close_prices[t]
        
        # 计算当前市值（用收盘价计算，模拟收盘时的账户状态）
        position_value = 0
        for i, shares in positions.items():
            if not np.isnan(today_close[i]):
                position_value += shares * today_close[i]
        total_value = cash + position_value
        daily_values.append(total_value)
        
        # 卖出（死叉）
        # 聚宽：ma5_prev >= ma10_prev 且 ma5 < ma10
        to_sell = []
        for i in list(positions.keys()):
            if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                continue
            if np.isnan(ma5_prev[t, i]) or np.isnan(ma10_prev[t, i]):
                continue
            
            # 死叉：MA5_prev >= MA10_prev 且 MA5 < MA10
            if ma5_prev[t, i] >= ma10_prev[t, i] and ma5[t, i] < ma10[t, i]:
                if not np.isnan(today_open[i]) and today_open[i] > 0:
                    to_sell.append(i)
        
        for i in to_sell:
            if i in positions:
                shares = positions[i]
                price = today_open[i]
                value = shares * price
                # 卖出费用：佣金 + 印花税
                fee = max(value * (commission_rate + stamp_tax), min_commission)
                cash += value - fee
                del positions[i]
                trades.append({'date': date, 'action': '卖出', 'code': valid_codes[i], 
                              'price': price, 'shares': shares})
        
        # 买入（金叉）
        # 聚宽：ma5_prev <= ma10_prev 且 ma5 > ma10
        buy_candidates = []
        for i in range(N_valid):
            if i in positions:
                continue
            if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                continue
            if np.isnan(ma5_prev[t, i]) or np.isnan(ma10_prev[t, i]):
                continue
            if np.isnan(today_open[i]) or today_open[i] <= 0:
                continue
            
            # 金叉：MA5_prev <= MA10_prev 且 MA5 > MA10
            if ma5_prev[t, i] <= ma10_prev[t, i] and ma5[t, i] > ma10[t, i]:
                buy_candidates.append(i)
        
        hold_count = len(positions)
        n_to_buy = min(len(buy_candidates), max_holdings - hold_count)
        
        if n_to_buy > 0:
            # 聚宽：cash_per_stock = available_cash / (max_hold - hold_count)
            cash_per_stock = cash / (max_holdings - hold_count)
            
            for i in buy_candidates[:n_to_buy]:
                price = today_open[i]
                shares = int(cash_per_stock / price / 100) * 100
                
                if shares > 0:
                    cost = shares * price
                    fee = max(cost * commission_rate, min_commission)
                    total_cost = cost + fee
                    
                    if total_cost <= cash:
                        positions[i] = shares
                        cash -= total_cost
                        trades.append({'date': date, 'action': '买入', 'code': valid_codes[i],
                                      'price': price, 'shares': shares})
                        
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
    if diff < 3:
        print(f"✅ 收益率差异 {diff:.2f}% 在可接受范围内")
    elif diff < 5:
        print(f"⚠️ 收益率差异 {diff:.2f}% 较小，基本匹配")
    else:
        print(f"❌ 收益率差异 {diff:.2f}% 较大")
        print("\n可能原因：")
        print("  1. 数据源不同 - 聚宽数据 vs 本地数据")
        print("  2. 停牌处理不同 - 聚宽用paused字段")
        print("  3. 最低佣金影响 - 聚宽最低5元")
    print("=" * 70)
    
    # 打印前10笔交易
    print("\n前10笔交易：")
    print(f"{'日期':<12} {'操作':<6} {'代码':<10} {'价格':<10} {'数量':<10}")
    print("-" * 50)
    for trade in trades[:10]:
        print(f"{trade['date']:<12} {trade['action']:<6} {trade['code']:<10} {trade['price']:<10.2f} {trade['shares']:<10}")


if __name__ == "__main__":
    run_matched_backtest()
