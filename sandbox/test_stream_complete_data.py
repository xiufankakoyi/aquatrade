"""
测试 stream_complete 事件的数据格式
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置日志级别为 DEBUG
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from server.services.data_initialization_service import DataInitializationService
from server.services.metrics_service import MetricsService
from server.services.stock_data_service import StockDataService
from server.services.backtest_service import BacktestService

data_init_service = DataInitializationService()
data_init_service.ensure_initialized()
stock_data_service = StockDataService(data_init_service)
metrics_service = MetricsService(data_init_service, stock_data_service)
backtest_service = BacktestService(data_init_service, metrics_service, stock_data_service)

params = {
    'strategy_name': '收敛三角形倒计时策略',
    'start_date': '2024-05-20',
    'end_date': '2024-05-25',
    'benchmark_code': '000300'
}

print('开始流式回测...')
for event in backtest_service.stream_backtest(**params):
    t = event.get('type')
    data = event.get('data')
    print(f"事件: {t}")
    
    if t == 'stream_complete':
        print(f"\n=== stream_complete 数据 ===")
        print(f"类型: {type(data)}")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {type(value)} = {value if not isinstance(value, list) else f'[列表, 长度={len(value)}]'}")
        print("=" * 50)
        break
    elif t == 'error':
        print(f"错误: {data}")
        break
