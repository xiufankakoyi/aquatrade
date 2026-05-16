"""
调试后端回测错误
"""
import sys
import os
import traceback

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from server.services.data_initialization_service import DataInitializationService
from server.services.metrics_service import MetricsService
from server.services.stock_data_service import StockDataService
from server.services.backtest_service import BacktestService

# 初始化服务
print("初始化服务...")
data_init_service = DataInitializationService()
data_init_service.ensure_initialized()
stock_data_service = StockDataService(data_init_service)
metrics_service = MetricsService(data_init_service, stock_data_service)
backtest_service = BacktestService(data_init_service, metrics_service, stock_data_service)

params = {
    "strategy_name": "收敛三角形倒计时策略",
    "start_date": "2024-05-20",
    "end_date": "2024-05-25",
    "benchmark_code": "000300"
}

print(f"\n运行回测: {params}")
print("="*60)

try:
    event_count = 0
    error_event = None
    stream_complete_event = None
    
    for event in backtest_service.stream_backtest(**params):
        event_count += 1
        event_type = event.get('type', 'unknown')
        
        if event_type == 'error':
            error_event = event
            print(f"\n❌ 错误事件 #{event_count}: {event}")
            break
        elif event_type == 'stream_complete':
            stream_complete_event = event
            print(f"\n✅ 回测完成 #{event_count}")
            print(f"数据: {event.get('data', {})}")
            break
        elif event_count <= 10:
            # 只打印前10个事件
            print(f"事件 #{event_count}: {event_type}")
            if event_type in ['daily_equity', 'new_trade']:
                print(f"  数据: {event.get('data', {})}")
    
    print(f"\n{'='*60}")
    print(f"总事件数: {event_count}")
    
    if error_event:
        print(f"\n❌ 回测失败，收到错误事件")
        print(f"错误详情: {error_event}")
    elif stream_complete_event:
        print(f"\n✅ 回测成功完成")
        data = stream_complete_event.get('data', {})
        print(f"最终权益: {data.get('finalEquity')}")
        print(f"总收益率: {data.get('totalReturn')}%")
        print(f"交易次数: {data.get('totalTrades')}")
    else:
        print(f"\n⚠️ 未收到 stream_complete 或 error 事件")
        
except Exception as e:
    print(f"\n❌ 异常: {e}")
    traceback.print_exc()
