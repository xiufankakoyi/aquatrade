"""
完整测试后端事件流 - 模拟前端接收
一步到位验证：事件名称、数据格式、权益曲线
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import warnings
warnings.filterwarnings('ignore')

from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3, SimpleVolumeConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine


def test_complete_backtest_flow():
    """完整测试回测事件流"""
    print("=" * 80)
    print("完整回测事件流测试")
    print("=" * 80)
    
    # 1. 初始化
    print("\n[1] 初始化引擎...")
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(
        data_query=data_query,
        initial_capital=1_000_000
    )
    
    config = SimpleVolumeConfig()
    strategy = SimpleVolumeStrategyV3(config=config)
    
    # 2. 运行回测
    start_date = '2024-01-01'
    end_date = '2024-01-10'
    
    print(f"\n[2] 运行回测: {start_date} ~ {end_date}")
    print("-" * 80)
    
    # 收集所有事件
    events = {
        'daily_equity_engine': [],
        'new_trade_engine': [],
        'final_metrics': [],
        'stream_complete': []
    }
    
    equity_curve = []
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        event_type = update.get('type')
        data = update.get('data', {})
        
        if event_type in events:
            events[event_type].append(data)
        
        # 打印事件详情
        if event_type == 'daily_equity_engine':
            equity_curve.append({
                'date': data.get('date'),
                'equity': data.get('equity'),
                'return': data.get('strategyReturn')
            })
            print(f"  [daily_equity_engine] {data.get('date')}: equity={data.get('equity'):,.2f}, return={data.get('strategyReturn')*100:.2f}%")
        
        elif event_type == 'new_trade_engine':
            print(f"  [new_trade_engine] {data.get('date')}: {data.get('action')} {data.get('symbol')} @ {data.get('price')}")
        
        elif event_type == 'final_metrics':
            print(f"\n  [final_metrics] 总收益: {data.get('totalReturn')}%, 最大回撤: {data.get('maxDrawdown')}%")
        
        elif event_type == 'stream_complete':
            print(f"\n  [stream_complete] 最终权益: {data.get('finalEquity'):,.2f}")
    
    print("-" * 80)
    
    # 3. 验证结果
    print("\n[3] 验证结果:")
    print("-" * 80)
    
    # 检查事件数量
    print(f"  daily_equity_engine 事件数: {len(events['daily_equity_engine'])}")
    print(f"  new_trade_engine 事件数: {len(events['new_trade_engine'])}")
    print(f"  final_metrics 事件数: {len(events['final_metrics'])}")
    print(f"  stream_complete 事件数: {len(events['stream_complete'])}")
    
    # 检查权益曲线
    if equity_curve:
        print(f"\n  权益曲线点数: {len(equity_curve)}")
        print(f"  初始权益: {equity_curve[0]['equity']:,.2f}")
        print(f"  最终权益: {equity_curve[-1]['equity']:,.2f}")
        
        # 计算总收益
        total_return = (equity_curve[-1]['equity'] / equity_curve[0]['equity'] - 1) * 100
        print(f"  计算总收益: {total_return:.2f}%")
        
        # 检查日收益率
        daily_returns = [p['return'] for p in equity_curve if p['return'] is not None]
        if daily_returns:
            print(f"  日均收益: {sum(daily_returns)/len(daily_returns)*100:.4f}%")
            print(f"  日收益范围: [{min(daily_returns)*100:.2f}%, {max(daily_returns)*100:.2f}%]")
    
    # 检查交易记录
    if events['new_trade_engine']:
        trades = events['new_trade_engine']
        buys = [t for t in trades if t.get('action') == 'buy']
        sells = [t for t in trades if t.get('action') == 'sell']
        print(f"\n  交易记录: {len(trades)} 笔 (买入 {len(buys)}, 卖出 {len(sells)})")
    
    # 4. 模拟前端接收格式
    print("\n[4] 模拟前端接收格式:")
    print("-" * 80)
    
    # 模拟后端发送到前端的事件名映射
    event_mapping = {
        'daily_equity_engine': 'daily_equity',  # 后端发送 daily_equity_engine -> 前端接收 daily_equity
        'new_trade_engine': 'new_trade',
        'final_metrics': 'final_metrics',
        'stream_complete': 'stream_complete'
    }
    
    print("  后端事件 -> 前端事件映射:")
    for backend_event, frontend_event in event_mapping.items():
        count = len(events.get(backend_event, []))
        print(f"    {backend_event} -> {frontend_event}: {count} 条")
    
    # 5. 最终验证
    print("\n[5] 最终验证:")
    print("-" * 80)
    
    all_passed = True
    
    # 检查是否有权益数据
    if len(equity_curve) == 0:
        print("  ❌ 没有权益曲线数据!")
        all_passed = False
    else:
        print(f"  ✅ 权益曲线数据正常 ({len(equity_curve)} 点)")
    
    # 检查初始权益是否正确
    if equity_curve and abs(equity_curve[0]['equity'] - 1_000_000) > 10000:
        print(f"  ❌ 初始权益异常: {equity_curve[0]['equity']:,.2f} (预期约 1,000,000)")
        all_passed = False
    else:
        print(f"  ✅ 初始权益正常")
    
    # 检查日收益率是否合理
    if daily_returns:
        max_daily = max(abs(r) for r in daily_returns)
        if max_daily > 1:  # 单日涨跌超过 100%
            print(f"  ❌ 日收益率异常: 最大单日变化 {max_daily*100:.2f}%")
            all_passed = False
        else:
            print(f"  ✅ 日收益率正常 (最大单日变化 {max_daily*100:.2f}%)")
    
    # 检查交易记录
    if events['new_trade_engine']:
        print(f"  ✅ 交易记录正常 ({len(events['new_trade_engine'])} 笔)")
    else:
        print(f"  ⚠️ 没有交易记录")
    
    print("-" * 80)
    if all_passed:
        print("\n🎉 所有验证通过! 后端事件流正常。")
    else:
        print("\n❌ 验证失败，请检查上述错误。")
    
    return all_passed


if __name__ == "__main__":
    test_complete_backtest_flow()
