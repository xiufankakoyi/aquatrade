"""
MA金叉死叉策略测试 - 调试版7
检查 data_dict 是否包含目标股票数据
"""
import os
import sys
import pandas as pd
import numpy as np

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.vectorized_base import VectorizedStrategyBase


class MACrossStrategyDebug(VectorizedStrategyBase):
    """简单均线金叉死叉策略 - 调试版"""
    
    strategy_id = "ma_cross_debug"
    strategy_name = "MA金叉死叉策略-调试版"
    
    def __init__(self, stock_code='000001'):
        super().__init__()
        self.target_stock = stock_code
        
    def generate_signals_vectorized(
        self,
        price_matrix,
        trading_dates: list,
        stock_codes: list,
        data_query,
        preloaded_data=None
    ) -> np.ndarray:
        """生成交易信号"""
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_stock not in stock_codes:
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        
        # 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        if self.ma5 is None or self.ma10 is None:
            return signals
        
        ma5_stock = self.ma5[:, n_idx]
        ma10_stock = self.ma10[:, n_idx]
        
        # 计算金叉死叉 - 只处理2025年的信号
        for t in range(1, T):
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
            
            current_date = trading_dates[t]
            
            if not current_date.startswith('2025'):
                continue
            
            # 金叉
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                
            # 死叉
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
        
        return signals


print("=" * 70)
print("MA金叉死叉策略测试 - 调试版7")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategyDebug(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 初始化完成")

    # 运行回测
    print("\n[2] 运行回测...")
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print("=" * 70)
    
    results_list = []
    trades_log = []
    signal_days = []
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        results_list.append(event)
        
        if event.get('type') == 'trade':
            trades_log.append(event)
    
    # 手动测试 _load_day_data_from_matrix
    print("\n" + "=" * 70)
    print("检查 data_dict 内容")
    print("=" * 70)
    
    test_dates = ['2025-01-23', '2025-04-17', '2025-05-09']
    
    for date_str in test_dates:
        print(f"\n{date_str}:")
        
        # 获取信号
        ts = pd.Timestamp(date_str)
        signals = engine._get_vectorized_signals_for_day(ts)
        print(f"  信号: {signals}")
        
        # 获取 data_dict
        _, _, data_dict = engine._load_day_data(ts)
        
        if '000001' in data_dict:
            data = data_dict['000001']
            print(f"  000001 数据:")
            print(f"    open: {data.get('open')}")
            print(f"    close: {data.get('close')}")
            print(f"    is_suspended: {data.get('is_suspended')}")
            print(f"    is_limit_down: {data.get('is_limit_down')}")
        else:
            print(f"  000001 不在 data_dict 中!")
            print(f"  data_dict 前5个键: {list(data_dict.keys())[:5]}")
    
    # 检查因子矩阵中的股票代码
    print("\n" + "=" * 70)
    print("检查因子矩阵")
    print("=" * 70)
    
    if hasattr(engine, '_factor_matrix') and engine._factor_matrix is not None:
        fm = engine._factor_matrix
        print(f"\n因子矩阵 codes_str 前10个: {fm.codes_str[:10]}")
        print(f"因子矩阵 codes_str 长度: {len(fm.codes_str)}")
        
        if '000001' in fm.codes_str:
            idx = fm.codes_str.index('000001')
            print(f"000001 在因子矩阵中的索引: {idx}")
        else:
            print(f"000001 不在因子矩阵中!")
    
    # 显示结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    if results_list:
        final_result = results_list[-1]
        metrics = final_result.get('metrics', {})
        
        print(f"\n  初始资金: 100,000")
        print(f"  最终资金: {metrics.get('final_value', 100000):.2f}")
        print(f"  策略收益: {metrics.get('total_return', 0):.2%}")
        print(f"  基准收益: {metrics.get('benchmark_return', 0):.2%}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2%}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    
    print(f"\n  交易记录 ({len(trades_log)} 笔):")
    if trades_log:
        for trade_event in trades_log:
            trade = trade_event.get('trade', {})
            print(f"    {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} "
                  f"@{trade.get('price', 0):.2f}")
    else:
        print("    无交易")
    
    print("\n" + "=" * 70)
    print("调试完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
