"""
调试回测错误，捕获完整堆栈
"""
import sys
import os
import traceback
import logging

# 设置详细日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from server.services.data_initialization_service import DataInitializationService
from server.services.metrics_service import MetricsService
from server.services.stock_data_service import StockDataService
from server.services.backtest_service import BacktestService

# 初始化服务
print("初始化数据服务...")
data_init_service = DataInitializationService()
data_init_service.ensure_initialized()

print("初始化股票数据服务...")
stock_data_service = StockDataService(data_init_service)

print("初始化指标服务...")
metrics_service = MetricsService(data_init_service, stock_data_service)

print("初始化回测服务...")
backtest_service = BacktestService(data_init_service, metrics_service, stock_data_service)

# 运行流式回测
params = {
    "strategy_name": "收敛三角形倒计时策略",
    "start_date": "2024-05-20",
    "end_date": "2024-05-25",
    "benchmark_code": "000300"
}

print("=== 开始流式回测 ===")
print(f"参数: {params}")

try:
    event_count = 0
    for event in backtest_service.stream_backtest(**params):
        event_count += 1
        event_type = event.get('type', 'unknown')
        
        if event_type == 'error':
            print(f"\n❌ 错误事件 #{event_count}: {event}")
            break
        elif event_type == 'stream_complete':
            print(f"\n✅ 回测完成 #{event_count}")
            print(f"数据: {event.get('data', {})}")
            break
        elif event_type in ['daily_equity', 'new_trade']:
            if event_count <= 5:
                print(f"事件 #{event_count}: {event_type} - {event.get('data', {})}")
        else:
            print(f"事件 #{event_count}: {event_type}")
            
        if event_count > 100:
            print("事件过多，停止")
            break
            
    print(f"\n总事件数: {event_count}")
    
except Exception as e:
    print(f"\n❌ 异常: {e}")
    traceback.print_exc()
