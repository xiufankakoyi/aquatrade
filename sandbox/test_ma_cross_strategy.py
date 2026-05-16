"""
简单金叉死叉策略测试
- 股票: 000001 (平安银行)
- 买入条件: MA5 上穿 MA10 (金叉)
- 卖出条件: MA5 下穿 MA10 (死叉)
- 回测区间: 2025-01-01 到 2026-01-01
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


class MACrossStrategy(VectorizedStrategyBase):
    """简单均线金叉死叉策略"""
    
    strategy_id = "ma_cross"
    strategy_name = "MA金叉死叉策略"
    
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
        """
        生成交易信号
        信号: 1=买入, -1=卖出, 0=无操作
        """
        T = len(trading_dates)
        N = len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int8)
        
        # 找到目标股票的索引
        if self.target_stock not in stock_codes:
            print(f"警告: 股票 {self.target_stock} 不在股票池中")
            return signals
            
        n_idx = stock_codes.index(self.target_stock)
        
        # 使用 prepare_data 准备数据
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 获取均线数据
        ma5 = self.ma5 if self.ma5 is not None else np.full((T, N), np.nan)
        ma10 = self.ma10 if self.ma10 is not None else np.full((T, N), np.nan)
        
        # 获取目标股票的均线
        ma5_stock = ma5[:, n_idx]
        ma10_stock = ma10[:, n_idx]
        
        # 计算金叉死叉
        cross_count = 0
        for t in range(1, T):
            # 跳过NaN值
            if np.isnan(ma5_stock[t]) or np.isnan(ma10_stock[t]):
                continue
                
            # 金叉: MA5上穿MA10 (昨天MA5<MA10, 今天MA5>MA10)
            if ma5_stock[t-1] < ma10_stock[t-1] and ma5_stock[t] > ma10_stock[t]:
                signals[t, n_idx] = 1
                cross_count += 1
                print(f"  金叉信号: {trading_dates[t]} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
                
            # 死叉: MA5下穿MA10 (昨天MA5>MA10, 今天MA5<MA10)
            elif ma5_stock[t-1] > ma10_stock[t-1] and ma5_stock[t] < ma10_stock[t]:
                signals[t, n_idx] = -1
                cross_count += 1
                print(f"  死叉信号: {trading_dates[t]} MA5={ma5_stock[t]:.2f} MA10={ma10_stock[t]:.2f}")
        
        print(f"  总共发现 {cross_count} 个交叉信号")
                
        return signals


print("=" * 70)
print("MA金叉死叉策略测试")
print("=" * 70)
print(f"目标股票: 000001 (平安银行)")
print(f"买入条件: MA5 上穿 MA10 (金叉)")
print(f"卖出条件: MA5 下穿 MA10 (死叉)")
print(f"回测区间: 2025-01-01 ~ 2026-01-01")
print("=" * 70)

try:
    # 初始化
    print("\n[1/3] 初始化...")
    data_query = OptimizedStockDataQuery()
    strategy = MACrossStrategy(stock_code='000001')
    engine = UnifiedBacktestEngine(data_query)
    print(f"  ✓ 数据查询初始化完成")
    print(f"  ✓ 策略: {strategy.name}")
    print(f"  ✓ 回测引擎初始化完成")

    # 检查股票数据
    print("\n[2/3] 检查股票数据...")
    df = data_query.get_market_data('2025-01-02')
    stock_data = df[df['stock_code'] == '000001']
    if len(stock_data) > 0:
        row = stock_data.iloc[0]
        print(f"  ✓ 000001 数据存在")
        print(f"    收盘价: {row.get('close', 'N/A')}")
        print(f"    MA5: {row.get('ma5', 'N/A')}")
        print(f"    MA10: {row.get('ma10', 'N/A')}")
        print(f"    MA20: {row.get('ma20', 'N/A')}")
    else:
        print(f"  ✗ 000001 数据不存在!")
        exit(1)

    # 运行回测
    print("\n[3/3] 运行回测...")
    print("=" * 70)
    
    results_list = []
    trades_log = []
    
    for event in engine.run_backtest(
        start_date='2025-01-01',
        end_date='2026-01-01',
        strategy=strategy
    ):
        results_list.append(event)
        
        # 记录交易
        if event.get('type') == 'trade':
            trades_log.append(event)
            trade = event.get('trade', {})
            print(f"\n>>> 交易执行: {trade.get('date')} {trade.get('action')} {trade.get('stock_code')} "
                  f"价格:{trade.get('price', 0):.2f} 数量:{trade.get('quantity', 0)}")
        
        # 显示进度
        if event.get('type') == 'day_end':
            date = event.get('date', '')
            nav = event.get('nav', 0)
            if nav != 100000:  # 只显示有变化的
                print(f"  {date}: NAV={nav:.2f}")
    
    # 显示结果
    if results_list:
        final_result = results_list[-1]
        metrics = final_result.get('metrics', {})
        
        print("\n" + "=" * 70)
        print("回测结果")
        print("=" * 70)
        print(f"\n  初始资金: 100,000")
        print(f"  最终资金: {metrics.get('final_value', 100000):.2f}")
        print(f"  策略收益: {metrics.get('total_return', 0):.2%}")
        print(f"  基准收益: {metrics.get('benchmark_return', 0):.2%}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2%}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
        
        # 显示所有交易
        if trades_log:
            print(f"\n  交易记录 ({len(trades_log)} 笔):")
            for trade_event in trades_log:
                trade = trade_event.get('trade', {})
                print(f"    {trade.get('date')} {trade.get('action'):4} {trade.get('stock_code')} "
                      f"@{trade.get('price', 0):.2f} x {trade.get('quantity', 0)}")
    
    print("\n" + "=" * 70)
    print("回测完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
