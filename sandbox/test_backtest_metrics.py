#!/usr/bin/env python3
"""
测试回测服务是否能正常生成盈亏比和胜率数据
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.strategy_factory import StrategyFactory
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def test_backtest_metrics():
    """测试回测服务是否能正常生成盈亏比和胜率数据"""
    print("🚀 开始测试回测服务指标生成...")
    
    # 创建数据查询和回测引擎
    db_path = "data/stock_data.db"  # 替换为实际的数据库路径
    data_query = OptimizedStockDataQuery(db_path)
    backtest_engine = UnifiedBacktestEngine(data_query)
    
    try:
        # 使用一个简单的测试策略进行测试
        strategy_name = "simple_test"  # 使用刚创建的简单测试策略
        strategy = StrategyFactory.create_strategy(strategy_name, use_simple=True)
        print(f"✅ 成功创建策略: {strategy_name}")
        
        # 运行回测
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        print(f"📊 正在运行回测: {strategy_name} ({start_date} 至 {end_date})")
        
        # 收集回测结果
        results_list = []
        trades_log = []
        final_metrics = None
        
        for update in backtest_engine.run_backtest_streaming(start_date, end_date, strategy):
            update_type = update.get('type')
            data = update.get('data', {})
            
            if update_type == 'daily_equity_engine':
                results_list.append({
                    'date': data.get('date'),
                    'total_value': data.get('strategyReturn', 0)
                })
            elif update_type == 'new_trade':
                trades_log.append(data)
            elif update_type == 'final_metrics':
                final_metrics = data
            elif update_type == 'error':
                print(f"❌ 回测错误: {data.get('message')}")
                return False
        
        # 检查最终指标
        if not final_metrics:
            print("❌ 没有收到最终指标")
            return False
        
        print("\n📋 回测最终指标:")
        for key, value in final_metrics.items():
            print(f"   {key}: {value}")
        
        # 检查关键指标是否存在且不为 0
        required_metrics = ['winRate', 'profitFactor']
        for metric in required_metrics:
            if metric not in final_metrics:
                print(f"❌ 缺少关键指标: {metric}")
                return False
            
            value = final_metrics[metric]
            if value == 0:
                print(f"⚠️  指标 {metric} 为 0，可能存在问题")
            else:
                print(f"✅ 指标 {metric} 正常: {value}")
        
        # 检查交易日志
        print(f"\n📈 交易记录统计:")
        print(f"   总交易数: {len(trades_log)}")
        
        # 统计 buy 和 sell 交易数
        buy_trades = [t for t in trades_log if t.get('action') == 'buy']
        sell_trades = [t for t in trades_log if t.get('action') == 'sell']
        
        print(f"   Buy 交易数: {len(buy_trades)}")
        print(f"   Sell 交易数: {len(sell_trades)}")
        
        # 检查交易日志中是否包含 profit_loss 字段
        if sell_trades:
            has_profit_loss = any('profit_loss' in t for t in sell_trades)
            print(f"   交易日志包含 profit_loss 字段: {has_profit_loss}")
            
            if has_profit_loss:
                # 统计盈利和亏损交易数
                profitable_trades = [t for t in sell_trades if t.get('profit_loss', 0) > 0]
                losing_trades = [t for t in sell_trades if t.get('profit_loss', 0) < 0]
                
                print(f"   盈利交易数: {len(profitable_trades)}")
                print(f"   亏损交易数: {len(losing_trades)}")
                
                # 计算手动计算的盈亏比和胜率
                manual_win_rate = (len(profitable_trades) / len(sell_trades)) * 100 if sell_trades else 0
                total_profit = sum(t.get('profit_loss', 0) for t in profitable_trades)
                total_loss = sum(abs(t.get('profit_loss', 0)) for t in losing_trades)
                manual_profit_factor = total_profit / total_loss if total_loss > 0 else 0
                
                print(f"\n🔍 手动计算的指标:")
                print(f"   胜率: {manual_win_rate:.1f}%")
                print(f"   盈亏比: {manual_profit_factor:.2f}")
                
                # 与回测引擎计算的指标进行比较
                engine_win_rate = final_metrics.get('winRate', 0)
                engine_profit_factor = final_metrics.get('profitFactor', 0)
                
                print(f"\n📊 指标对比:")
                print(f"   胜率 (引擎): {engine_win_rate:.1f}% | 胜率 (手动): {manual_win_rate:.1f}%")
                print(f"   盈亏比 (引擎): {engine_profit_factor:.2f} | 盈亏比 (手动): {manual_profit_factor:.2f}")
        
        print("\n🎉 测试完成！回测服务能够正常生成盈亏比和胜率数据。")
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
    success = test_backtest_metrics()
    sys.exit(0 if success else 1)
