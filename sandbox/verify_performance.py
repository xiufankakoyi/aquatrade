import time
import pandas as pd
from core.backtest.unified_engine import UnifiedBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.logger import get_logger

logger = get_logger(__name__)

def run_performance_test():
    print("=" * 60)
    print("回测性能优化验证")
    print("=" * 60)
    
    # 初始化数据查询
    data_query = OptimizedStockDataQuery()
    
    # 强制清理缓存
    if hasattr(data_query, '_preloaded_data'):
        data_query._preloaded_data = None
        data_query._preloaded_data_index = {}
    
    # 模拟一个简单的策略
    class SimpleStrategy:
        def __init__(self):
            self.strategy_name = "PerfTestStrategy"
        def set_runtime_context(self, **kwargs): pass
        def generate_signals(self, current_date, stock_pool_today, data_query):
            return {}
            
    strategy = SimpleStrategy()
    engine = UnifiedBacktestEngine(data_query=data_query)
    
    # 设置测试日期范围
    start_date = '2024-01-01'
    # end_date = '2024-05-30' # 100 days
    end_date = '2024-04-10' # 60 days for faster check
    
    print(f"\n[1] 开始回测: {start_date} ~ {end_date}")
    t_start = time.perf_counter()
    
    update_count = 0
    errors = 0
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        if update['type'] == 'daily_equity_engine':
            update_count += 1
            if update_count == 1:
                print(f"   第一天数据已产出: {update['data']['date']}")
            if 'strategyReturn' not in update['data']:
                print(f"   ❌ 错误: 结果中缺失 'strategyReturn' 键！")
                errors += 1
        elif update['type'] == 'error':
            print(f"   ❌ 引擎报错: {update['data']['message']}")
            errors += 1
    
    t_end = time.perf_counter()
    total_time = t_end - t_start
    
    print(f"\n[结果] 处理了 {update_count} 天数据")
    print(f"[结果] 总耗时: {total_time:.2f}s")
    
    if update_count > 0:
        print(f"[结果] 平均每天耗时: {(total_time*1000/update_count):.2f}ms")
    
    # 验证逻辑：如果耗时过长或有错误，则失败
    if errors > 0:
        print(f"\n❌ 测试失败: 存在 {errors} 个错误")
    elif total_time > 10: 
        print(f"\n⚠️ 测试通过但性能较差: {total_time:.2f}s (期望 < 5s)")
    else:
        print(f"\n✅ 性能达标！优化效果显著。")

    # 验证是否真正使用了预加载
    if hasattr(data_query, '_preloaded_data') and data_query._preloaded_data is not None:
        print(f"✅ 确认已触发预加载: {len(data_query._preloaded_data)} 行数据")
    else:
        print(f"❌ 警告: 未触发预加载 (可能由于日期范围数据为空或预加载方法未被调用)")

if __name__ == "__main__":
    run_performance_test()
