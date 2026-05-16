"""
测试后端事件发送
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3, SimpleVolumeConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
import warnings
warnings.filterwarnings('ignore')


def test_backend_events():
    """测试后端发送的事件"""
    print("=" * 80)
    print("测试后端事件发送")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        initial_capital=1_000_000
    )
    
    config = SimpleVolumeConfig()
    strategy = SimpleVolumeStrategyV3(config=config)
    
    start_date = '2024-01-01'
    end_date = '2024-01-10'  # 只测试10天
    
    print(f"\n回测期间: {start_date} ~ {end_date}")
    print("\n事件流:")
    print("-" * 80)
    
    event_counts = {
        'daily_equity_engine': 0,
        'new_trade_engine': 0,
        'final_metrics': 0,
        'stream_complete': 0
    }
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        event_type = update.get('type')
        
        if event_type in event_counts:
            event_counts[event_type] += 1
        
        if event_type == 'daily_equity_engine':
            data = update.get('data', {})
            print(f"[daily_equity_engine] {data.get('date')}: equity={data.get('equity'):,.2f}, strategyReturn={data.get('strategyReturn'):.4f}")
        
        elif event_type == 'new_trade_engine':
            data = update.get('data', {})
            print(f"[new_trade_engine] {data.get('date')}: {data.get('action')} {data.get('symbol')} @ {data.get('price')}")
        
        elif event_type == 'final_metrics':
            data = update.get('data', {})
            print(f"\n[final_metrics] 总收益: {data.get('totalReturn'):.2f}%, 最大回撤: {data.get('maxDrawdown'):.2f}%")
        
        elif event_type == 'stream_complete':
            data = update.get('data', {})
            print(f"\n[stream_complete] 最终权益: {data.get('finalEquity'):,.2f}, 交易数: {len(data.get('trades', []))}")
    
    print("-" * 80)
    print("\n事件统计:")
    for event_type, count in event_counts.items():
        print(f"  {event_type}: {count} 次")


if __name__ == "__main__":
    test_backend_events()
