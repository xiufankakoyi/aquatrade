"""
详细调试脚本 - 检查信号生成和交易执行的每个步骤
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import pandas as pd
import polars as pl
import numpy as np
from datetime import datetime

from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy


def debug_backtest():
    """详细调试回测"""
    print("=" * 80)
    print("详细调试 - 检查信号生成和交易执行")
    print("=" * 80)

    # 创建数据管理器
    data_manager = UnifiedDataManager()

    # 创建回测配置
    config = BacktestConfig(
        initial_capital=1000000.0,
        commission_rate=0.0003,
        min_commission=5.0,
        position_ratio=0.1,
        max_positions=10,
    )

    # 创建回测引擎
    engine = UnifiedBacktestEngine(
        data_query=data_manager,
        config=config
    )

    # 创建策略
    strategy = MainWaveTrendStrategy(
        data_manager=data_manager,
        lookback_days=20,
        breakout_days=5,
        volume_threshold=1.5,
        trend_period=20
    )

    # 设置回测区间
    start_date = '2024-01-02'
    end_date = '2024-01-10'

    print(f"\n回测区间: {start_date} ~ {end_date}")
    print("=" * 80)

    # 获取时间序列
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    time_series = engine._get_time_series(start_ts, end_ts)
    print(f"交易日数量: {len(time_series)}")

    # 预加载数据
    print("\n预加载数据...")
    preloaded_data = engine._preload_data(start_ts, end_ts)
    if preloaded_data:
        print(f"预加载完成: {list(preloaded_data.keys())}")
    else:
        print("预加载返回 None，使用空字典继续")
        preloaded_data = {}

    # 初始化向量化信号
    print("\n初始化向量化信号...")
    engine._generate_vectorized_signals(strategy, preloaded_data, time_series, time_series[0])

    # 检查信号矩阵
    if engine._signal_matrix is not None:
        print(f"\n信号矩阵信息:")
        print(f"  形状: {engine._signal_matrix.shape}")
        print(f"  交易日数: {len(engine._date_to_idx)}")
        print(f"  股票数: {len(engine._stock_codes_list)}")
        print(f"  买入信号总数: {(engine._signal_matrix == 1).sum()}")
        print(f"  卖出信号总数: {(engine._signal_matrix == -1).sum()}")

        # 检查每一天的信号
        print(f"\n每日信号统计:")
        for date_str, idx in list(engine._date_to_idx.items())[:5]:
            day_signals = engine._signal_matrix[idx]
            buy_count = (day_signals == 1).sum()
            sell_count = (day_signals == -1).sum()
            print(f"  {date_str}: 买入={buy_count}, 卖出={sell_count}")
    else:
        print("\n[错误] 信号矩阵未生成!")
        return

    # 模拟回测执行 - 详细追踪
    print("\n" + "=" * 80)
    print("逐日执行回测:")
    print("=" * 80)

    portfolio = {}
    cash = config.initial_capital
    position_info = {}
    all_trades = []

    for idx, current_time in enumerate(time_series, 1):
        date_str = current_time.strftime('%Y-%m-%d')
        print(f"\n--- Day {idx}: {date_str} ---")

        # 1. 加载当日数据
        stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
        print(f"  股票池大小: {len(data_dict) if data_dict else 0}")

        if not data_dict:
            print("  跳过: 无数据")
            continue

        # 2. 设置策略上下文
        engine._set_strategy_context(strategy, current_time, portfolio, cash)

        # 3. 生成信号
        signals = engine._generate_signals(
            strategy, current_time, stock_pool, preloaded_data, idx, time_series
        )

        buy_signals = {k: v for k, v in signals.items() if v.get('action') == 'buy'}
        sell_signals = {k: v for k, v in signals.items() if v.get('action') == 'sell'}
        print(f"  信号统计: 总={len(signals)}, 买入={len(buy_signals)}, 卖出={len(sell_signals)}")

        if signals:
            # 显示前3个买入信号
            if buy_signals:
                print(f"  买入信号示例:")
                for code, sig in list(buy_signals.items())[:3]:
                    print(f"    {code}: {sig}")

            # 检查数据_dict中是否有这些股票
            print(f"  数据覆盖: {len(set(signals.keys()) & set(data_dict.keys()))}/{len(signals)}")

        # 4. 执行交易前的状态
        print(f"  执行前: 持仓={len(portfolio)}, 现金={cash:,.2f}")

        # 5. 执行交易
        portfolio, cash, trades = engine._execute_trades(
            current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
        )

        # 6. 执行交易后的状态
        print(f"  执行后: 持仓={len(portfolio)}, 现金={cash:,.2f}, 交易数={len(trades)}")

        if trades:
            for trade in trades:
                print(f"    >>> 交易: {trade.action} {trade.code} {trade.shares}股 @ {trade.price:.2f}")
            all_trades.extend(trades)

        # 7. 计算账户价值
        portfolio_value = engine._calculate_portfolio_value(portfolio, data_dict)
        total_value = cash + portfolio_value
        print(f"  总资产: {total_value:,.2f} (持仓市值={portfolio_value:,.2f})")

    # 最终结果
    print("\n" + "=" * 80)
    print("回测结果汇总:")
    print("=" * 80)
    print(f"总交易数: {len(all_trades)}")
    print(f"买入交易: {sum(1 for t in all_trades if t.action == 'buy')}")
    print(f"卖出交易: {sum(1 for t in all_trades if t.action == 'sell')}")
    print(f"最终持仓: {len(portfolio)}")
    print(f"最终现金: {cash:,.2f}")

    if all_trades:
        print("\n交易列表:")
        for trade in all_trades[:10]:
            print(f"  {trade.date} {trade.action.upper():4} {trade.code:>6} {trade.shares:>6}股 @ {trade.price:>8.2f}")
    else:
        print("\n[警告] 没有产生任何交易!")
        print("\n诊断建议:")
        print("  1. 检查策略是否正确生成信号")
        print("  2. 检查信号是否正确传递给交易执行")
        print("  3. 检查风控限制是否过于严格")
        print("  4. 检查股票数据是否完整")


if __name__ == "__main__":
    debug_backtest()
