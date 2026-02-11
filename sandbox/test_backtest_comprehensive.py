"""
综合测试脚本 - 验证所有回测引擎修复
"""
import sys
import time
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.logger import get_logger

logger = get_logger(__name__)

class TestStrategy:
    def __init__(self):
        self.strategy_name = "TestStrategy"
    
    def set_runtime_context(self, **kwargs):
        pass
    
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 简单策略：随机选择1只股票买入
        if hasattr(stock_pool_today, 'to_pandas'):
            df = stock_pool_today.to_pandas()
        else:
            df = stock_pool_today
        
        if df is not None and not df.empty and len(df) > 0:
            # 买入第一只股票
            code = df.iloc[0]['stock_code']
            return {code: 'buy'}
        return {}

def main():
    print("=" * 80)
    print("回测引擎综合验证测试")
    print("=" * 80)
    
    # 1. 初始化
    print("\n[1/5] 初始化数据查询和引擎...")
    data_query = OptimizedStockDataQuery()
    engine = FlexibleBacktestEngine(data_query=data_query)
    strategy = TestStrategy()
    
    # 2. 运行回测
    print("[2/5] 运行回测 (2024-05-20 ~ 2024-05-22, 3天)...")
    start_date = '2024-05-20'
    end_date = '2024-05-22'
    
    updates_received = {
        'daily_equity_engine': 0,
        'new_trade_engine': 0,
        'final_metrics': 0,
        'stream_complete': 0
    }
    
    has_strategyReturn = True
    has_equity = True
    
    try:
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            update_type = update.get('type')
            if update_type in updates_received:
                updates_received[update_type] += 1
            
            # 检查 daily_equity_engine 事件
            if update_type == 'daily_equity_engine':
                data = update.get('data', {})
                if 'strategyReturn' not in data:
                    has_strategyReturn = False
                    print(f"   ❌ 缺少 strategyReturn 键: {data.keys()}")
                if 'equity' not in data:
                    has_equity = False
                    print(f"   ❌ 缺少 equity 键: {data.keys()}")
        
        print("   ✅ 回测完成")
        
    except Exception as e:
        print(f"   ❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 验证事件
    print(f"\n[3/5] 验证事件接收:")
    print(f"   daily_equity_engine: {updates_received['daily_equity_engine']} 个")
    print(f"   new_trade_engine: {updates_received['new_trade_engine']} 个")
    print(f"   final_metrics: {updates_received['final_metrics']} 个")
    print(f"   stream_complete: {updates_received['stream_complete']} 个")
    
    if not has_strategyReturn:
        print(f"   ❌ strategyReturn 键缺失")
        return False
    if not has_equity:
        print(f"   ❌ equity 键缺失")
        return False
    
    print(f"   ✅ 所有必需键都存在")
    
    # 4. 检查数据库
    print(f"\n[4/5] 检查数据库记录...")
    import sqlite3
    from config.config import Config
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        
        # 检查最新回测
        cursor.execute("""
            SELECT id, strategy_name, trade_count, created_at
            FROM backtest_results
            ORDER BY created_at DESC
            LIMIT 1
        """)
        result = cursor.fetchone()
        
        if result:
            backtest_id, strategy_name, trade_count, created_at = result
            print(f"   ✅ 找到回测记录: ID={backtest_id}, 策略={strategy_name}, 交易数={trade_count}")
            
            # 检查交易记录
            cursor.execute("""
                SELECT COUNT(*) FROM trade_records WHERE backtest_id = ?
            """, (backtest_id,))
            db_trade_count = cursor.fetchone()[0]
            print(f"   ✅ 交易记录数: {db_trade_count}")
            
        else:
            print(f"   ⚠️ 未找到回测记录（可能是旧数据库）")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ 数据库检查失败: {e}")
    
    # 5. 总结
    print(f"\n[5/5] 测试总结:")
    all_passed = (
        updates_received['daily_equity_engine'] > 0 and
        updates_received['final_metrics'] == 1 and
        updates_received['stream_complete'] == 1 and
        has_strategyReturn and
        has_equity
    )
    
    if all_passed:
        print("   ✅ 所有测试通过！")
        print("\n" + "=" * 80)
        print("✅ 回测引擎验证成功")
        print("=" * 80)
        return True
    else:
        print("   ❌ 部分测试失败")
        print("\n" + "=" * 80)
        print("❌ 回测引擎验证失败")
        print("=" * 80)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
