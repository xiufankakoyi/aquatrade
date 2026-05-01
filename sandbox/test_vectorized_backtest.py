"""
向量化回测验证测试
==================
对比传统执行和向量化执行的结果一致性
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import pandas as pd
import polars as pl

from data_svc.arctic_data_manager import ArcticDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine


class SimpleTestStrategy:
    """简单测试策略"""
    strategy_name = "SimpleTestStrategy"
    
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
        self.prefer_polars = True
    
    def set_runtime_context(self, current_date: str, portfolio: dict, cash: float):
        self.current_date = current_date
        self.portfolio = portfolio
        self.cash = cash
    
    def generate_signals(self, current_date: str, stock_pool_today: pl.DataFrame, data_query):
        signals = {}
        if stock_pool_today.is_empty():
            return signals
        
        required_cols = ['stock_code', 'open', 'close']
        if not all(col in stock_pool_today.columns for col in required_cols):
            return signals
        
        for row in stock_pool_today.iter_rows(named=True):
            code = row.get('stock_code')
            open_price = row.get('open', 0)
            close_price = row.get('close', 0)
            
            if close_price > open_price * 1.02:
                signals[code] = {'action': 'buy'}
            elif close_price < open_price * 0.98:
                signals[code] = {'action': 'sell'}
        
        return signals


def run_backtest_test(use_vectorized: bool = True):
    """运行回测测试"""
    print(f"\n{'='*60}")
    print(f"回测测试 - 向量化执行: {use_vectorized}")
    print(f"{'='*60}")
    
    # 创建数据管理器
    data_manager = ArcticDataManager()
    
    # 检查是否有数据
    symbols = data_manager.store.list_symbols()
    if not symbols:
        print("[错误] ArcticDB 中没有数据，请先运行 create_test_data.py")
        return None
    
    print(f"可用股票: {len(symbols)} 只")
    
    # 创建回测引擎
    engine = UnifiedBacktestEngine(
        data_query=data_manager,
    )
    
    # 创建策略
    strategy = SimpleTestStrategy()
    
    # 运行回测
    start_date = '2024-01-01'
    end_date = '2024-03-31'
    
    print(f"回测区间: {start_date} ~ {end_date}")
    
    results = []
    trades = []
    start_time = time.time()
    
    try:
        for event in engine.run_backtest_streaming(start_date, end_date, strategy):
            event_type = event.get('type')
            data = event.get('data', {})
            
            if event_type == 'daily_equity_engine':
                results.append({
                    'date': data.get('date'),
                    'equity': data.get('equity', 0)
                })
            elif event_type == 'new_trade_engine':
                trades.append(data)
            elif event_type == 'error':
                print(f"[错误] {data.get('message')}")
                return None
    except Exception as e:
        print(f"[异常] {e}")
        import traceback
        traceback.print_exc()
        return None
    
    duration = time.time() - start_time
    
    # 计算结果
    if results:
        initial = results[0]['equity']
        final = results[-1]['equity']
        total_return = (final - initial) / initial * 100
        
        print(f"\n结果统计:")
        print(f"  初始资金: {initial:,.2f}")
        print(f"  最终资金: {final:,.2f}")
        print(f"  总收益率: {total_return:.2f}%")
        print(f"  交易次数: {len(trades)}")
        print(f"  回测耗时: {duration:.3f}s")
        
        if use_vectorized and engine._vectorized_executor:
            stats = engine._vectorized_executor.get_perf_stats()
            print(f"  执行引擎调用: {stats['total_calls']} 次")
            print(f"  执行引擎耗时: {stats['total_duration']:.3f}s")
    
    data_manager.close()
    
    return {
        'results': results,
        'trades': trades,
        'duration': duration,
        'use_vectorized': use_vectorized
    }


def compare_results(result_v, result_nv):
    """对比向量化与非向量化结果"""
    print(f"\n{'='*60}")
    print("结果对比")
    print(f"{'='*60}")
    
    if not result_v or not result_nv:
        print("[错误] 结果不完整，无法对比")
        return
    
    # 对比收益率
    if result_v['results'] and result_nv['results']:
        v_final = result_v['results'][-1]['equity']
        nv_final = result_nv['results'][-1]['equity']
        
        print(f"\n最终资金:")
        print(f"  向量化:   {v_final:,.2f}")
        print(f"  非向量化: {nv_final:,.2f}")
        print(f"  差异:     {abs(v_final - nv_final):,.2f}")
        
        if abs(v_final - nv_final) < 0.01:
            print(f"  [✓] 结果一致!")
        else:
            print(f"  [✗] 结果有差异")
    
    # 对比交易次数
    v_trades = len(result_v['trades'])
    nv_trades = len(result_nv['trades'])
    
    print(f"\n交易次数:")
    print(f"  向量化:   {v_trades}")
    print(f"  非向量化: {nv_trades}")
    
    # 对比性能
    v_time = result_v['duration']
    nv_time = result_nv['duration']
    
    print(f"\n执行耗时:")
    print(f"  向量化:   {v_time:.3f}s")
    print(f"  非向量化: {nv_time:.3f}s")
    
    if v_time > 0 and nv_time > 0:
        speedup = nv_time / v_time
        print(f"  性能提升: {speedup:.2f}x")


def main():
    print("向量化回测验证测试")
    print("=" * 60)
    
    # 测试向量化执行
    result_v = run_backtest_test(use_vectorized=True)
    
    # 测试非向量化执行
    result_nv = run_backtest_test(use_vectorized=False)
    
    # 对比结果
    compare_results(result_v, result_nv)
    
    print("\n" + "=" * 60)
    print("测试完成!")


if __name__ == "__main__":
    main()
