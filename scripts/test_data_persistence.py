#!/usr/bin/env python3
"""
测试数据持久化功能
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.unified_engine import UnifiedBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.strategy_factory import StrategyFactory

def test_data_persistence():
    """测试数据持久化功能"""
    print("=== 测试数据持久化功能 ===")
    
    try:
        # 创建数据查询和回测引擎
        data_query = OptimizedStockDataQuery()
        engine = UnifiedBacktestEngine(data_query)
        
        # 创建一个简单的策略
        strategy = StrategyFactory.create_strategy("simple_volume_v3", use_simple=True)
        
        # 设置短时间范围，快速测试
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        print(f"\n1. 开始测试回测: {start_date} 到 {end_date}")
        print(f"2. 策略类型: {type(strategy).__name__}")
        
        # 运行回测
        results = list(engine.run_backtest_streaming(start_date, end_date, strategy))
        
        print(f"\n3. 回测完成，生成了 {len(results)} 个事件")
        
        # 检查是否有错误事件
        error_events = [r for r in results if r.get('type') == 'error']
        if error_events:
            print(f"   错误事件: {len(error_events)}")
            for error in error_events:
                print(f"     - {error.get('data', {}).get('message', '未知错误')}")
            return False
        
        # 检查是否有最终指标事件
        final_metrics_events = [r for r in results if r.get('type') == 'final_metrics']
        if final_metrics_events:
            print(f"4. 生成了最终指标: {list(final_metrics_events[0].get('data', {}).keys())[:10]}...")
        
        # 检查是否有交易记录事件
        trade_events = [r for r in results if r.get('type') in ['new_trade', 'new_trade_engine']]
        print(f"5. 生成了 {len(trade_events)} 笔交易记录")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_data_persistence()
