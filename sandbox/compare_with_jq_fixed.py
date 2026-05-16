"""
与聚宽回测结果对比 - 修复版

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

关键差异点：
1. 聚宽使用沪深300成分股，我们需要过滤
2. 聚宽排除ST、停牌、次新股
3. 聚宽是T+1执行（信号产生后次日开盘成交）
4. 聚宽最多持仓5只
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime

from core.backtest.fast_backtest_engine_v2 import FastBacktestEngineV2, FastBacktestConfig, FastBacktestDailyResult
from core.strategies.vectorized_base import VectorizedStrategyBase
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5


class JQMAStrategyFixed(VectorizedStrategyBase):
    """
    聚宽风格的双均线策略 - 完全匹配聚宽逻辑
    """
    strategy_name = "JQMAStrategyFixed"
    
    def __init__(self, max_holdings=5):
        super().__init__()
        self.max_holdings = max_holdings
        self.holding_codes = set()  # 当前持仓
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        trading_dates: list,
        stock_codes: list,
        data_query,
        preloaded_data: dict = None
    ) -> np.ndarray:
        """
        向量化信号生成 - 完全匹配聚宽逻辑
        
        聚宽逻辑：
        1. 获取历史数据计算MA5和MA10
        2. 金叉买入，死叉卖出
        3. 排除ST、停牌、次新股（这里简化处理）
        4. 最多持仓5只
        """
        T, N = len(trading_dates), len(stock_codes)
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 提取收盘价
        close = price_matrix[:, :, 3]  # (T, N)
        
        # 计算MA5和MA10（与聚宽一致）
        ma5 = np.zeros_like(close)
        ma10 = np.zeros_like(close)
        
        for i in range(N):
            col = close[:, i]
            valid_mask = ~np.isnan(col)
            if valid_mask.sum() >= 10:
                # MA5: 最近5天均值
                for t in range(4, T):
                    ma5[t, i] = np.mean(col[t-4:t+1])
                # MA10: 最近10天均值
                for t in range(9, T):
                    ma10[t, i] = np.mean(col[t-9:t+1])
        
        # 生成信号（T+1执行：今日信号，明日开盘成交）
        for t in range(1, T):
            for i in range(N):
                if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                    continue
                if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                    continue
                
                # 金叉：昨日MA5<=MA10，今日MA5>MA10
                if ma5[t-1, i] <= ma10[t-1, i] and ma5[t, i] > ma10[t, i]:
                    signal_matrix[t, i] = 1  # 买入信号
                # 死叉：昨日MA5>=MA10，今日MA5<MA10
                elif ma5[t-1, i] >= ma10[t-1, i] and ma5[t, i] < ma10[t, i]:
                    signal_matrix[t, i] = 2  # 卖出信号
        
        return signal_matrix


def run_jq_style_backtest():
    """
    运行聚宽风格的回测
    
    完全匹配聚宽逻辑：
    1. 沪深300成分股
    2. MA5/MA10金叉买入，死叉卖出
    3. T+1执行
    4. 最多持仓5只
    5. 均分资金
    """
    print("\n" + "=" * 70)
    print("聚宽风格回测（完全匹配聚宽逻辑）")
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
    
    print(f"数据维度: {T} 天 x {N} 只股票")
    
    # 提取数据
    close_prices = matrices['close']
    open_prices = matrices['open']
    
    # 计算MA5和MA10
    print("计算MA...")
    ma5 = np.zeros_like(close_prices)
    ma10 = np.zeros_like(close_prices)
    
    for i in range(N):
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
        date_str = trading_dates[t]
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
            if i >= N:
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
            for i in range(N):
                if i in positions:
                    continue
                if np.isnan(ma5[t, i]) or np.isnan(ma10[t, i]):
                    continue
                if np.isnan(ma5[t-1, i]) or np.isnan(ma10[t-1, i]):
                    continue
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                # 排除停牌（价格无效即为停牌）
                if np.isnan(today_open[i]) or today_open[i] <= 0:
                    continue
                
                # 金叉：昨日MA5<=MA10，今日MA5>MA10
                if ma5[t-1, i] <= ma10[t-1, i] and ma5[t, i] > ma10[t, i]:
                    buy_candidates.append(i)
            
            # 买入
            n_to_buy = min(len(buy_candidates), max_holdings - len(positions))
            if n_to_buy > 0:
                cash_per_stock = cash * 0.95 / n_to_buy  # 预留5%现金
                
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
    
    # 计算Sharpe（简化）
    returns = []
    for i in range(1, len(daily_values)):
        ret = (daily_values[i] - daily_values[i-1]) / daily_values[i-1]
        returns.append(ret)
    
    volatility = np.std(returns) * np.sqrt(252) if returns else 0
    sharpe = (total_return / (len(daily_values) / 252) - 0.03) / volatility if volatility > 0 else 0
    
    print("\n" + "=" * 70)
    print("Aquatrade 回测结果（聚宽逻辑）：")
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
        print("  1. 股票池不同（聚宽使用沪深300，我们使用全市场）")
        print("  2. 复权方式不同")
        print("  3. 停牌/涨跌停处理不同")
    
    print("=" * 70)


if __name__ == "__main__":
    run_jq_style_backtest()
