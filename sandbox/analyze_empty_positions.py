"""
分析策略空仓情况
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from collections import Counter


def analyze_empty_positions():
    from sandbox.top3_backtest_fixed import load_data, create_signal_generator
    from core.backtest.lookahead_safe_engine import LookaheadSafeBacktestEngine, BacktestConfig
    
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print("加载数据...")
    daily_data = load_data(start_date, end_date)
    
    config = {
        'name': '策略2: VS>=0.5+RSI<50',
        'vs_threshold': 0.5,
        'rsi_filter': True,
        'volume_filter': False
    }
    
    backtest_config = BacktestConfig(
        initial_capital=100000.0,
        max_positions=5,
        position_ratio=0.18,
        take_profit_pct=0.03,
        trailing_stop_pct=0.02,
        max_holding_days=10,
        commission_rate=0.0003,
        min_commission=5.0,
        sell_tax=0.001
    )
    
    print("运行回测...")
    engine = LookaheadSafeBacktestEngine(backtest_config)
    signal_gen = create_signal_generator(config)
    
    result = engine.run_backtest(
        daily_data=daily_data,
        start_date=start_date,
        end_date=end_date,
        signal_generator=signal_gen,
    )
    
    print("\n" + "=" * 60)
    print("空仓分析")
    print("=" * 60)
    
    equity_curve = result['equity_curve']
    position_counts = [p.get('position_count', 0) for p in equity_curve]
    
    print(f"\n持仓天数统计:")
    counter = Counter(position_counts)
    for pos_count in sorted(counter.keys()):
        days = counter[pos_count]
        pct = days / len(position_counts) * 100
        print(f"  {pos_count}个持仓: {days}天 ({pct:.1f}%)")
    
    empty_days = sum(1 for p in position_counts if p == 0)
    print(f"\n总空仓天数: {empty_days} / {len(equity_curve)}")
    
    print(f"\n信号统计:")
    print(f"  总交易次数: {result['trade_count']}")


if __name__ == "__main__":
    analyze_empty_positions()
