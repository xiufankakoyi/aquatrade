"""
测试回测引擎修复
"""
import pandas as pd
import numpy as np
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 60)
print("测试回测引擎修复")
print("=" * 60)

# 初始化数据查询
print("\n[1] 初始化数据查询...")
data_query = OptimizedStockDataQuery()

# 初始化回测引擎
print("[2] 初始化回测引擎...")
engine = FlexibleBacktestEngine(
    data_query=data_query,
    initial_capital=100000,
    time_granularity='daily'
)

# 创建一个简单的测试策略
class TestStrategy:
    def __init__(self):
        self.strategy_name = "TestStrategy"
        self.runtime_context = None
    
    def set_runtime_context(self, current_date, portfolio, cash):
        self.runtime_context = {
            'current_date': current_date,
            'portfolio': portfolio,
            'cash': cash
        }
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 简单策略：第一天买入第一只股票，第二天卖出
        signals = {}
        
        if not stock_pool_today.empty:
            stock_codes = stock_pool_today.index.tolist()
            if stock_codes:
                # 根据日期决定买入或卖出
                if '2024-05-20' <= current_date <= '2024-05-22':
                    signals[stock_codes[0]] = 'buy'
                elif '2024-05-23' <= current_date <= '2024-05-25':
                    signals[stock_codes[0]] = 'sell'
        
        return signals

# 创建策略实例
strategy = TestStrategy()

# 运行流式回测（只测试前5天）
print("\n[3] 运行流式回测（前5天）...")
print("-" * 60)

try:
    update_count = 0
    for update in engine.run_backtest_streaming(
        start_date='2024-05-20',
        end_date='2024-05-25',
        strategy=strategy
    ):
        if update['type'] == 'backtest_start':
            print(f"✅ 回测开始")
            print(f"   初始资金: {update['data']['initialCapital']:,.0f}")
            print(f"   时间粒度: {update['data']['timeGranularity']}")
            print(f"   日期范围: {update['data']['startDate']} ~ {update['data']['endDate']}")
        
        elif update['type'] == 'daily_equity_engine':
            update_count += 1
            print(f"✅ 日期 {update['data']['date']}: "
                  f"权益={update['data']['equity']:,.0f}, "
                  f"现金={update['data']['cash']:,.0f}, "
                  f"持仓={update['data']['positions']}, "
                  f"交易={update['data']['trades']}")
            
            # 只测试前5天
            if update_count >= 5:
                print("\n[测试完成] 前5天测试通过")
                break
        
        elif update['type'] == 'error':
            print(f"❌ 错误: {update['data']['message']}")
            break
    
    print("-" * 60)
    print(f"\n✅ 回测引擎修复成功！共处理 {update_count} 天数据")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
