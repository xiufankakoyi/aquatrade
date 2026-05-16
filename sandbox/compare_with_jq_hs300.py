"""
与聚宽回测结果对比 - 沪深300版本

聚宽数据：
- 回测时间：2023.1.1 - 2023.12.31
- 初始资金：100,000
- 股票池：沪深300成分股
- 策略收益：-23.88%
- 基准收益：-11.38%
- Alpha：-0.14
- Beta：0.92
- Sharpe：-1.40
- 最大回撤：33.52%
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


# 沪深300成分股（2023年）- 简化版，实际应该从指数成分表获取
HS300_CODES = [
    "600519", "601318", "600036", "601012", "601166", "601888", "600276", "601398",
    "600900", "601288", "600309", "601668", "601857", "600887", "601988", "601628",
    "600028", "601088", "601818", "601328", "600030", "601169", "601601", "601688",
    "600016", "601766", "601211", "601336", "601186", "601989", "600000", "601998",
    "601390", "601229", "600048", "601111", "601818", "600837", "601881", "600999",
    "601800", "601688", "601669", "601117", "601727", "601618", "601899", "601939",
    "601288", "601328", "601398", "601988", "601818", "601668", "601857", "601628",
    "601088", "601766", "601211", "601336", "601186", "601989", "601998", "601390",
    "601229", "601111", "601881", "601800", "601669", "601117", "601727", "601618",
    "601939", "601012", "601888", "601166", "601012", "601318", "600036", "600519",
    "600276", "600309", "600887", "600030", "600016", "600000", "600048", "600837",
    "600999", "600900", "600028", "601169", "601601", "601688", "600048"
]


def get_hs300_codes_from_db(query, date_str="2023-06-01"):
    """从数据库获取沪深300成分股"""
    try:
        # 获取某天的股票池
        pool = query.get_stock_pool(date_str)
        if pool is not None and not pool.empty:
            # 按市值排序，取前300只作为近似沪深300
            if 'total_mv' in pool.columns:
                pool = pool.sort_values('total_mv', ascending=False)
                codes = pool['stock_code'].astype(str).tolist()[:300]
                return codes
    except Exception as e:
        print(f"从数据库获取沪深300失败: {e}")
    
    # 使用默认列表
    return list(set(HS300_CODES))  # 去重


def run_hs300_backtest():
    """运行沪深300成分股的回测"""
    print("\n" + "=" * 70)
    print("聚宽 vs Aquatrade 回测对比（沪深300成分股）")
    print("=" * 70)
    
    # 聚宽结果
    jq_results = {
        '策略收益': -23.88,
        '基准收益': -11.38,
        'Alpha': -0.14,
        'Beta': 0.92,
        'Sharpe': -1.40,
        '最大回撤': 33.52
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
    
    # 获取沪深300成分股
    query = OptimizedStockDataQuery()
    hs300_codes = get_hs300_codes_from_db(query)
    print(f"沪深300成分股数量: {len(hs300_codes)}")
    
    # 过滤只保留沪深300成分股
    hs300_indices = []
    for i, code in enumerate(stock_codes):
        if str(code) in hs300_codes:
            hs300_indices.append(i)
    
    if not hs300_indices:
        print("❌ 没有找到沪深300成分股")
        return
    
    print(f"找到 {len(hs300_indices)} 只沪深300成分股")
    
    # 提取沪深300数据
    close_prices = matrices['close'][:, hs300_indices]
    open_prices = matrices['open'][:, hs300_indices]
    N_hs300 = len(hs300_indices)
    
    # 计算MA5和MA10
    print("计算MA...")
    ma5 = np.zeros_like(close_prices)
    ma10 = np.zeros_like(close_prices)
    
    for i in range(N_hs300):
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
    
    print("运行回测...")
    
    for t in range(1, T):
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
        
        # 检查卖出信号（死叉）
        to_sell = []
        for i in list(positions.keys()):
            if i >= N_hs300:
                continue
            if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                continue
            if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                continue
            
            # 死叉：昨日MA5>=MA10，今日MA5<MA10
            if ma5[t-1, i] >= ma10[t-1, i] and ma5[t, i] < ma10[t, i]:
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
                del positions[i]
        
        # 检查买入信号（金叉）
        if len(positions) < max_holdings:
            buy_candidates = []
            for i in range(N_hs300):
                if i in positions:
                    continue
                if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                    continue
                if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                    continue
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                
                # 金叉：昨日MA5<=MA10，今日MA5>MA10
                if ma5[t-1, i] <= ma10[t-1, i] and ma5[t, i] > ma10[t, i]:
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
    
    print("\n" + "=" * 70)
    print("Aquatrade 回测结果（沪深300成分股）：")
    print("=" * 70)
    print(f"  策略收益: {total_return*100:.2f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  最大回撤: {max_drawdown*100:.2f}%")
    print(f"  最终资金: {final_value:,.2f}")
    print(f"  交易日数: {len(daily_values)}")
    
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
        print("可能原因：")
        print("  1. 沪深300成分股列表不准确")
        print("  2. 复权方式不同（前复权 vs 后复权）")
        print("  3. 停牌处理不同")
        print("  4. 次新股排除逻辑不同")
    
    print("=" * 70)


if __name__ == "__main__":
    run_hs300_backtest()
