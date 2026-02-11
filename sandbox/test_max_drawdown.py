#!/usr/bin/env python3
"""
测试回测引擎返回的maxDrawdown值是否为负值
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
from core.strategies.strategy_factory import StrategyFactory
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def test_max_drawdown_value():
    """测试回测引擎返回的maxDrawdown值是否为负值"""
    print("🚀 开始测试maxDrawdown值...")
    
    # 创建数据查询和回测引擎
    db_path = "data/stock_data.db"
    data_query = OptimizedStockDataQuery(db_path)
    backtest_engine = OptimizedBacktestEngine(data_query)
    
    try:
        # 使用简单测试策略
        strategy = StrategyFactory.create_strategy("simple_test", use_simple=True)
        print(f"✅ 成功创建策略: simple_test")
        
        # 运行回测
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        print(f"📊 正在运行回测...")
        
        final_metrics = None
        
        for update in backtest_engine.run_backtest_streaming(start_date, end_date, strategy):
            update_type = update.get('type')
            data = update.get('data', {})
            
            if update_type == 'final_metrics':
                final_metrics = data
                break
            elif update_type == 'error':
                print(f"❌ 回测错误: {data.get('message')}")
                return False
        
        if not final_metrics:
            print("❌ 没有收到最终指标")
            return False
        
        print("\n📋 回测最终指标:")
        for key, value in final_metrics.items():
            print(f"   {key}: {value}")
        
        # 检查maxDrawdown值
        max_drawdown = final_metrics.get('maxDrawdown', 0)
        print(f"\n🔍 maxDrawdown值: {max_drawdown}")
        print(f"   类型: {type(max_drawdown)}")
        print(f"   是否为负值: {max_drawdown < 0}")
        
        # 检查max_drawdown（下划线版本）
        max_drawdown_underscore = final_metrics.get('max_drawdown', 0)
        print(f"\n🔍 max_drawdown值: {max_drawdown_underscore}")
        print(f"   类型: {type(max_drawdown_underscore)}")
        print(f"   是否为负值: {max_drawdown_underscore < 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 关闭资源
        data_query.close()

if __name__ == "__main__":
    success = test_max_drawdown_value()
    sys.exit(0 if success else 1)
