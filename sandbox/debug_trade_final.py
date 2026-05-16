"""
最终调试脚本 - 追踪交易执行
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import pandas as pd
import polars as pl
from datetime import datetime

from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy


def run_debug_backtest():
    """运行调试回测"""
    print("=" * 80)
    print("调试回测 - 追踪交易执行")
    print("=" * 80)
    
    # 创建数据管理器
    data_manager = UnifiedDataManager()
    
    # 创建回测配置
    config = BacktestConfig(
        initial_capital=1000000.0,
        commission_rate=0.0003,
        min_commission=5.0,
        position_ratio=0.1,  # 每只10%仓位
        max_positions=10,    # 最多10只持仓
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
    end_date = '2024-01-31'
    
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print(f"初始资金: {config.initial_capital:,.2f}")
    print(f"仓位比例: {config.position_ratio*100}%")
    print(f"最大持仓: {config.max_positions}")
    print("=" * 80)
    
    # 运行回测
    results = []
    trades = []
    daily_signals = []
    
    start_time = time.time()
    
    try:
        for event in engine.run_backtest_streaming(start_date, end_date, strategy):
            event_type = event.get('type')
            data = event.get('data', {})
            
            if event_type == 'daily_equity_engine':
                results.append({
                    'date': data.get('date'),
                    'equity': data.get('equity', 0),
                    'cash': data.get('cash', 0),
                    'positions': data.get('positions', 0),
                    'trades': data.get('trades', 0)
                })
                
                # 打印每日详情
                print(f"\n[{data.get('date')}] 权益: {data.get('equity', 0):,.2f} | "
                      f"现金: {data.get('cash', 0):,.2f} | "
                      f"持仓: {data.get('positions', 0)} | "
                      f"当日交易: {data.get('trades', 0)}")
                
            elif event_type == 'new_trade_engine':
                trades.append(data)
                action = data.get('action', 'unknown')
                code = data.get('code', 'N/A')
                shares = data.get('shares', 0)
                price = data.get('price', 0)
                print(f"  >>> 交易: {action.upper()} {code} {shares}股 @ {price:.2f}")
                
            elif event_type == 'error':
                print(f"\n[错误] {data.get('message')}")
                return None
                
    except Exception as e:
        print(f"\n[异常] {e}")
        import traceback
        traceback.print_exc()
        return None
    
    duration = time.time() - start_time
    
    # 最终结果
    print("\n" + "=" * 80)
    print("回测结果汇总")
    print("=" * 80)
    
    if results:
        initial = results[0]['equity']
        final = results[-1]['equity']
        total_return = (final - initial) / initial * 100
        
        print(f"初始资金: {initial:,.2f}")
        print(f"最终资金: {final:,.2f}")
        print(f"总收益率: {total_return:.2f}%")
        print(f"总交易日: {len(results)}")
        print(f"总交易数: {len(trades)}")
        
        buy_trades = [t for t in trades if t.get('action') == 'buy']
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        print(f"  - 买入: {len(buy_trades)}")
        print(f"  - 卖出: {len(sell_trades)}")
        print(f"回测耗时: {duration:.3f}s")
        
        # 检查信号矩阵
        if engine._signal_matrix is not None:
            print(f"\n信号矩阵信息:")
            print(f"  形状: {engine._signal_matrix.shape}")
            print(f"  买入信号总数: {(engine._signal_matrix == 1).sum()}")
            print(f"  卖出信号总数: {(engine._signal_matrix == -1).sum()}")
        
        if trades:
            print(f"\n前10笔交易:")
            for i, trade in enumerate(trades[:10], 1):
                print(f"  {i}. {trade.get('date')} {trade.get('action').upper():4} "
                      f"{trade.get('code'):>6} {trade.get('shares'):>6}股 @ "
                      f"{trade.get('price', 0):>8.2f}")
        else:
            print("\n[警告] 没有产生任何交易!")
            print("可能原因:")
            print("  1. 策略没有生成信号")
            print("  2. 信号生成但交易执行失败")
            print("  3. 风控限制导致交易被过滤")
    else:
        print("[错误] 没有回测结果!")
    
    return {
        'results': results,
        'trades': trades,
        'duration': duration
    }


if __name__ == "__main__":
    result = run_debug_backtest()
